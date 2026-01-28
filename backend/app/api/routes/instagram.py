from fastapi import APIRouter, HTTPException, BackgroundTasks, UploadFile, File
from typing import Optional
import asyncio
import logging
import zipfile
import json
import tempfile
import shutil
from pathlib import Path
from datetime import datetime

from app.schemas.models import InstagramImportRequest, Account, Post
from app.services.instagram_service import instagram_service
from app.services.face_recognition_service import face_recognition_service
from app.core.config import settings
from app.core.database import execute_write

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/instagram", tags=["instagram"])


# Store for tracking import jobs
import_jobs: dict[str, dict] = {}


@router.post("/login")
async def login(username: str, password: str):
    """Login to Instagram for accessing private profiles."""
    success = instagram_service.login(username, password)
    if not success:
        raise HTTPException(status_code=401, detail="Failed to login to Instagram")
    return {"message": "Successfully logged in"}


@router.get("/profile/{username}", response_model=Account)
async def get_profile(username: str):
    """Get Instagram profile information."""
    account = instagram_service.get_profile(username)
    if not account:
        raise HTTPException(status_code=404, detail="Profile not found")
    return account


@router.post("/import")
async def import_posts(request: InstagramImportRequest, background_tasks: BackgroundTasks):
    """Import posts from an Instagram profile."""
    import uuid

    job_id = str(uuid.uuid4())
    import_jobs[job_id] = {
        "status": "pending",
        "username": request.username,
        "total_posts": 0,
        "processed_posts": 0,
        "faces_detected": 0,
        "errors": [],
    }

    background_tasks.add_task(
        _import_posts_task,
        job_id,
        request.username,
        request.max_posts,
        request.include_tagged,
    )

    return {
        "job_id": job_id,
        "message": f"Import started for @{request.username}",
        "status_url": f"/api/instagram/import/{job_id}/status",
    }


async def _import_posts_task(
    job_id: str,
    username: str,
    max_posts: int,
    include_tagged: bool,
):
    """Background task for importing posts."""
    import_jobs[job_id]["status"] = "running"

    try:
        # Get profile first
        account = instagram_service.get_profile(username)
        if not account:
            import_jobs[job_id]["status"] = "failed"
            import_jobs[job_id]["errors"].append("Profile not found")
            return

        # Import user's posts
        posts_processed = 0
        faces_detected = 0

        for post in instagram_service.get_posts(username, max_posts):
            try:
                # Download images
                image_paths = instagram_service.download_post_images(post)

                # Process faces in each image
                for image_path in image_paths:
                    faces = face_recognition_service.process_image_faces(
                        image_path, post.id
                    )
                    faces_detected += len(faces)

                posts_processed += 1
                import_jobs[job_id]["processed_posts"] = posts_processed
                import_jobs[job_id]["faces_detected"] = faces_detected

                # Small delay to avoid rate limiting
                await asyncio.sleep(0.5)

            except Exception as e:
                logger.error(f"Error processing post {post.shortcode}: {e}")
                import_jobs[job_id]["errors"].append(f"Post {post.shortcode}: {str(e)}")

        # Import tagged posts if requested
        if include_tagged:
            for post in instagram_service.get_tagged_posts(username, max_posts // 2):
                try:
                    image_paths = instagram_service.download_post_images(post)

                    for image_path in image_paths:
                        faces = face_recognition_service.process_image_faces(
                            image_path, post.id
                        )
                        faces_detected += len(faces)

                    posts_processed += 1
                    import_jobs[job_id]["processed_posts"] = posts_processed
                    import_jobs[job_id]["faces_detected"] = faces_detected

                    await asyncio.sleep(0.5)

                except Exception as e:
                    logger.error(f"Error processing tagged post {post.shortcode}: {e}")
                    import_jobs[job_id]["errors"].append(f"Tagged {post.shortcode}: {str(e)}")

        import_jobs[job_id]["status"] = "completed"
        import_jobs[job_id]["total_posts"] = posts_processed

    except Exception as e:
        logger.error(f"Import failed: {e}")
        import_jobs[job_id]["status"] = "failed"
        import_jobs[job_id]["errors"].append(str(e))


@router.get("/import/{job_id}/status")
async def get_import_status(job_id: str):
    """Get the status of an import job."""
    if job_id not in import_jobs:
        raise HTTPException(status_code=404, detail="Import job not found")
    return import_jobs[job_id]


@router.get("/import/jobs")
async def list_import_jobs():
    """List all import jobs."""
    return list(import_jobs.values())


@router.post("/post/{shortcode}")
async def import_single_post(shortcode: str):
    """Import a single post by shortcode."""
    try:
        import instaloader

        loader = instaloader.Instaloader(
            download_pictures=True,
            download_videos=False,
            download_geotags=True,
        )

        post = instaloader.Post.from_shortcode(loader.context, shortcode)

        # Convert to our model
        from app.schemas.models import PostCreate
        import re

        image_urls = []
        if post.typename == "GraphSidecar":
            for node in post.get_sidecar_nodes():
                if not node.is_video:
                    image_urls.append(node.display_url)
        elif not post.is_video:
            image_urls.append(post.url)

        hashtags = []
        if post.caption:
            hashtags = re.findall(r"#(\w+)", post.caption)

        location_name = post.location.name if post.location else None

        post_create = PostCreate(
            shortcode=post.shortcode,
            caption=post.caption,
            posted_at=post.date_utc,
            likes=post.likes,
            comments=post.comments,
            image_urls=image_urls,
            location_name=location_name,
            account_username=post.owner_username,
            hashtags=hashtags,
        )

        # Create post via existing endpoint
        from app.api.routes.posts import create_post
        created_post = await create_post(post_create)

        # Download and process images
        from pathlib import Path
        import httpx

        for idx, url in enumerate(image_urls):
            try:
                response = httpx.get(url, follow_redirects=True)
                if response.status_code == 200:
                    from app.core.config import settings

                    filepath = settings.UPLOAD_DIR / shortcode / f"{shortcode}_{idx}.jpg"
                    filepath.parent.mkdir(parents=True, exist_ok=True)
                    filepath.write_bytes(response.content)

                    # Process faces
                    faces = face_recognition_service.process_image_faces(
                        filepath, created_post.id
                    )

            except Exception as e:
                logger.error(f"Failed to download/process image: {e}")

        return created_post

    except Exception as e:
        logger.error(f"Failed to import post {shortcode}: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/search/{query}")
async def search_instagram(query: str, limit: int = 20):
    """Search for Instagram profiles (requires login)."""
    try:
        import instaloader

        loader = instaloader.Instaloader()
        # This requires being logged in for most searches
        profiles = []

        # Basic profile search
        try:
            profile = instaloader.Profile.from_username(loader.context, query)
            profiles.append({
                "username": profile.username,
                "full_name": profile.full_name,
                "followers": profile.followers,
                "is_private": profile.is_private,
                "profile_pic_url": profile.profile_pic_url,
            })
        except Exception:
            pass

        return {"profiles": profiles}

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/import-export")
async def import_from_export(
    file: UploadFile = File(...),
    process_faces: bool = True,
    background_tasks: BackgroundTasks = None
):
    """
    Import posts from Instagram data export zip file.

    This endpoint accepts the zip file you download from Instagram
    (Settings > Your Activity > Download Your Information).

    The zip typically contains:
    - content/posts_1.json (your posts metadata)
    - media/posts/ (your post images)

    This is the recommended way to import your own data without scraping.
    """
    import uuid

    if not file.filename.endswith('.zip'):
        raise HTTPException(
            status_code=400,
            detail="File must be a zip archive from Instagram data export"
        )

    job_id = str(uuid.uuid4())
    temp_dir = Path(tempfile.mkdtemp())

    try:
        # Save uploaded zip
        zip_path = temp_dir / "export.zip"
        content = await file.read()
        zip_path.write_bytes(content)

        # Extract zip
        extract_dir = temp_dir / "extracted"
        with zipfile.ZipFile(zip_path, 'r') as zip_ref:
            zip_ref.extractall(extract_dir)

        # Find posts JSON file (Instagram export structure varies)
        posts_json = None
        media_dir = None

        for json_path in extract_dir.rglob("*.json"):
            if "posts" in json_path.name.lower() or "content" in str(json_path.parent).lower():
                posts_json = json_path
                break

        # Also check for your_instagram_activity structure
        if not posts_json:
            for json_path in extract_dir.rglob("posts_1.json"):
                posts_json = json_path
                break

        if not posts_json:
            # Try to find any posts-related JSON
            for json_path in extract_dir.rglob("*.json"):
                try:
                    with open(json_path, 'r', encoding='utf-8') as f:
                        data = json.load(f)
                        if isinstance(data, list) and len(data) > 0:
                            first_item = data[0]
                            if isinstance(first_item, dict) and ('media' in first_item or 'uri' in str(first_item)):
                                posts_json = json_path
                                break
                except:
                    continue

        if not posts_json:
            raise HTTPException(
                status_code=400,
                detail="Could not find posts JSON in the export. Make sure this is a valid Instagram data export."
            )

        # Find media directory
        for d in extract_dir.rglob("*"):
            if d.is_dir() and ("media" in d.name.lower() or "posts" in d.name.lower()):
                media_dir = d
                break

        if not media_dir:
            media_dir = extract_dir

        # Parse posts JSON
        with open(posts_json, 'r', encoding='utf-8') as f:
            posts_data = json.load(f)

        # Handle different export formats
        if isinstance(posts_data, dict) and 'ig_posts' in posts_data:
            posts_data = posts_data['ig_posts']

        results = {
            "job_id": job_id,
            "posts_found": 0,
            "posts_imported": 0,
            "faces_detected": 0,
            "errors": []
        }

        for post_item in posts_data:
            try:
                # Extract post metadata (format varies)
                if isinstance(post_item, dict):
                    media_list = post_item.get('media', [post_item])
                    if not isinstance(media_list, list):
                        media_list = [media_list]
                else:
                    continue

                results["posts_found"] += 1

                for media in media_list:
                    # Get URI and other data
                    uri = media.get('uri', '')
                    title = media.get('title', '')
                    creation_timestamp = media.get('creation_timestamp', media.get('taken_at_timestamp'))

                    if not uri:
                        continue

                    # Find the media file
                    media_filename = Path(uri).name
                    media_file = None

                    for f in extract_dir.rglob(media_filename):
                        media_file = f
                        break

                    if not media_file and uri:
                        # Try relative path from extract dir
                        potential_path = extract_dir / uri
                        if potential_path.exists():
                            media_file = potential_path

                    # Generate shortcode from filename or timestamp
                    shortcode = media_filename.rsplit('.', 1)[0] if media_filename else str(uuid.uuid4())[:11]

                    # Create post in database
                    posted_at = datetime.fromtimestamp(creation_timestamp) if creation_timestamp else datetime.utcnow()

                    post_id = str(uuid.uuid4())
                    image_urls = []

                    # Copy media to uploads if found
                    if media_file and media_file.exists():
                        dest_dir = settings.UPLOAD_DIR / shortcode
                        dest_dir.mkdir(parents=True, exist_ok=True)
                        dest_path = dest_dir / media_file.name
                        shutil.copy2(media_file, dest_path)
                        image_urls.append(f"/uploads/{shortcode}/{media_file.name}")

                    # Create post node
                    create_query = """
                    MERGE (p:Post {shortcode: $shortcode})
                    ON CREATE SET
                        p.id = $id,
                        p.caption = $caption,
                        p.posted_at = datetime($posted_at),
                        p.image_urls = $image_urls,
                        p.created_at = datetime()
                    ON MATCH SET
                        p.updated_at = datetime()
                    RETURN p.id as id
                    """

                    result = execute_write(create_query, {
                        "id": post_id,
                        "shortcode": shortcode,
                        "caption": title or "",
                        "posted_at": posted_at.isoformat(),
                        "image_urls": image_urls
                    })

                    if result:
                        actual_post_id = result[0]["id"]
                        results["posts_imported"] += 1

                        # Process faces if media file exists and flag is set
                        if process_faces and media_file and media_file.exists():
                            try:
                                faces = face_recognition_service.detect_and_store_faces(
                                    str(dest_path),
                                    actual_post_id,
                                    shortcode
                                )
                                results["faces_detected"] += len(faces)
                            except Exception as face_error:
                                logger.warning(f"Face detection failed for {shortcode}: {face_error}")

            except Exception as e:
                logger.error(f"Error importing post: {e}")
                results["errors"].append(str(e))

        results["status"] = "completed"
        return results

    except zipfile.BadZipFile:
        raise HTTPException(status_code=400, detail="Invalid zip file")
    except json.JSONDecodeError:
        raise HTTPException(status_code=400, detail="Invalid JSON in export file")
    except Exception as e:
        logger.error(f"Import failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        # Cleanup temp directory
        try:
            shutil.rmtree(temp_dir)
        except:
            pass

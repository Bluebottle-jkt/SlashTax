from fastapi import APIRouter, HTTPException, BackgroundTasks
from typing import Optional
import asyncio
import logging

from app.schemas.models import InstagramImportRequest, Account, Post
from app.services.instagram_service import instagram_service
from app.services.face_recognition_service import face_recognition_service

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

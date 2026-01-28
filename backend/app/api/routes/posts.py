from fastapi import APIRouter, HTTPException, UploadFile, File, Form, BackgroundTasks
from typing import Optional
import uuid
from pathlib import Path
import aiofiles
import logging

from app.core.config import settings
from app.core.database import execute_query, execute_write
from app.schemas.models import Post, PostCreate, PostAnalysis, FaceDetection
from app.services.face_recognition_service import face_recognition_service
from app.services.ai_service import ai_service
from app.services.media_store import media_store

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/posts", tags=["posts"])


@router.get("/", response_model=list[Post])
async def list_posts(skip: int = 0, limit: int = 100):
    """List all posts."""
    query = """
    MATCH (p:Post)
    OPTIONAL MATCH (f:Face)-[:APPEARS_IN]->(p)
    WITH p, count(f) as faces_detected
    RETURN p {.*, faces_detected: faces_detected} as post
    ORDER BY p.posted_at DESC
    SKIP $skip
    LIMIT $limit
    """

    results = execute_query(query, {"skip": skip, "limit": limit})
    return [Post(**r["post"]) for r in results if r.get("post")]


@router.get("/{post_id}", response_model=Post)
async def get_post(post_id: str):
    """Get a post by ID."""
    query = """
    MATCH (p:Post {id: $id})
    OPTIONAL MATCH (f:Face)-[:APPEARS_IN]->(p)
    WITH p, count(f) as faces_detected
    RETURN p {.*, faces_detected: faces_detected} as post
    """

    results = execute_query(query, {"id": post_id})

    if not results or not results[0].get("post"):
        raise HTTPException(status_code=404, detail="Post not found")

    return Post(**results[0]["post"])


@router.post("/", response_model=Post)
async def create_post(post: PostCreate):
    """Create a new post manually."""
    post_id = str(uuid.uuid4())

    # Create post
    query = """
    CREATE (p:Post {
        id: $id,
        shortcode: $shortcode,
        caption: $caption,
        posted_at: $posted_at,
        likes: $likes,
        comments: $comments,
        image_urls: $image_urls,
        processed: false,
        created_at: datetime()
    })
    RETURN p
    """

    execute_write(query, {
        "id": post_id,
        "shortcode": post.shortcode,
        "caption": post.caption,
        "posted_at": post.posted_at.isoformat() if post.posted_at else None,
        "likes": post.likes,
        "comments": post.comments,
        "image_urls": post.image_urls,
    })

    # Link to account
    if post.account_username:
        query = """
        MERGE (a:Account {username: $username})
        ON CREATE SET a.id = randomUUID(), a.created_at = datetime()
        WITH a
        MATCH (p:Post {id: $post_id})
        MERGE (a)-[:POSTED]->(p)
        """
        execute_write(query, {
            "username": post.account_username,
            "post_id": post_id,
        })

    # Link to location
    if post.location_name:
        query = """
        MERGE (l:Location {name: $name})
        ON CREATE SET l.id = randomUUID(), l.created_at = datetime()
        WITH l
        MATCH (p:Post {id: $post_id})
        MERGE (p)-[:AT_LOCATION]->(l)
        """
        execute_write(query, {
            "name": post.location_name,
            "post_id": post_id,
        })

    # Link hashtags
    for tag in post.hashtags:
        query = """
        MERGE (h:Hashtag {name: $name})
        ON CREATE SET h.id = randomUUID(), h.created_at = datetime()
        WITH h
        MATCH (p:Post {id: $post_id})
        MERGE (p)-[:HAS_HASHTAG]->(h)
        """
        execute_write(query, {
            "name": tag.lower().lstrip("#"),
            "post_id": post_id,
        })

    return await get_post(post_id)


@router.post("/upload", response_model=PostAnalysis)
async def upload_and_analyze(
    background_tasks: BackgroundTasks,
    file: UploadFile = File(...),
    shortcode: Optional[str] = Form(None),
    caption: Optional[str] = Form(None),
    account_username: Optional[str] = Form(None),
    location_name: Optional[str] = Form(None),
):
    """Upload an image and analyze it for faces."""
    # Generate shortcode if not provided
    if not shortcode:
        shortcode = f"upload_{uuid.uuid4().hex[:12]}"

    # Save uploaded file
    upload_dir = settings.UPLOAD_DIR / shortcode
    upload_dir.mkdir(parents=True, exist_ok=True)
    upload_path = upload_dir / file.filename

    async with aiofiles.open(upload_path, "wb") as f:
        content = await file.read()
        await f.write(content)

    # Create post in database
    post_id = str(uuid.uuid4())
    query = """
    CREATE (p:Post {
        id: $id,
        shortcode: $shortcode,
        caption: $caption,
        image_urls: $image_urls,
        processed: false,
        created_at: datetime()
    })
    RETURN p
    """

    execute_write(query, {
        "id": post_id,
        "shortcode": shortcode,
        "caption": caption,
        "image_urls": [str(upload_path)],
    })

    # Link to account if provided
    if account_username:
        query = """
        MERGE (a:Account {username: $username})
        ON CREATE SET a.id = randomUUID(), a.created_at = datetime()
        WITH a
        MATCH (p:Post {id: $post_id})
        MERGE (a)-[:POSTED]->(p)
        """
        execute_write(query, {
            "username": account_username,
            "post_id": post_id,
        })

    # Detect and identify faces
    faces = face_recognition_service.process_image_faces(upload_path, post_id)

    # Analyze with AI
    caption_analysis = None
    if caption:
        caption_analysis = ai_service.analyze_caption(caption)

    # Extract hashtags from caption
    hashtags = []
    if caption:
        import re
        hashtags = re.findall(r"#(\w+)", caption)
        for tag in hashtags:
            query = """
            MERGE (h:Hashtag {name: $name})
            ON CREATE SET h.id = randomUUID(), h.created_at = datetime()
            WITH h
            MATCH (p:Post {id: $post_id})
            MERGE (p)-[:HAS_HASHTAG]->(h)
            """
            execute_write(query, {
                "name": tag.lower(),
                "post_id": post_id,
            })

    # Handle location
    location = None
    if location_name:
        query = """
        MERGE (l:Location {name: $name})
        ON CREATE SET l.id = randomUUID(), l.created_at = datetime()
        WITH l
        MATCH (p:Post {id: $post_id})
        MERGE (p)-[:AT_LOCATION]->(l)
        RETURN l
        """
        result = execute_write(query, {
            "name": location_name,
            "post_id": post_id,
        })
        if result:
            from app.schemas.models import Location
            location = Location(name=location_name)

    # Mark post as processed
    query = """
    MATCH (p:Post {id: $id})
    SET p.processed = true, p.faces_detected = $faces_count
    """
    execute_write(query, {"id": post_id, "faces_count": len(faces)})

    return PostAnalysis(
        post_id=post_id,
        faces=faces,
        location=location,
        hashtags=hashtags,
        caption_analysis=str(caption_analysis) if caption_analysis else None,
    )


@router.post("/{post_id}/process", response_model=PostAnalysis)
async def process_post(post_id: str):
    """Process a post for face detection.

    Downloads images if needed and creates Face nodes for each detected face.
    """
    # Get post
    query = """
    MATCH (p:Post {id: $id})
    RETURN p
    """
    results = execute_query(query, {"id": post_id})

    if not results:
        raise HTTPException(status_code=404, detail="Post not found")

    post_data = results[0]["p"]
    image_urls = post_data.get("image_urls", [])
    shortcode = post_data.get("shortcode", post_id)

    logger.info(f"Processing post {post_id} with {len(image_urls)} images")

    all_faces = []

    for idx, image_url in enumerate(image_urls):
        # Ensure image is available locally
        local_path = await media_store.ensure_local_image(
            url=image_url,
            shortcode=shortcode,
            index=idx
        )

        if local_path:
            logger.info(f"Processing image {local_path}")
            # Use new detect_and_store_faces method that persists Face nodes
            faces = face_recognition_service.detect_and_store_faces(
                local_path, post_id, shortcode
            )
            all_faces.extend(faces)
        else:
            logger.warning(f"Could not get local image for {image_url[:100]}")

    # Mark as processed (face count will be computed from Face nodes)
    query = """
    MATCH (p:Post {id: $id})
    OPTIONAL MATCH (f:Face)-[:APPEARS_IN]->(p)
    WITH p, count(f) as face_count
    SET p.processed = true, p.faces_detected = face_count
    """
    execute_write(query, {"id": post_id})

    logger.info(f"Finished processing post {post_id}: {len(all_faces)} faces found")

    return PostAnalysis(
        post_id=post_id,
        faces=all_faces,
        hashtags=[],
    )


@router.get("/{post_id}/faces")
async def get_post_faces(post_id: str):
    """Get all faces detected in a post (Face nodes)."""
    faces = face_recognition_service.get_faces_for_post(post_id)
    return faces


@router.get("/{post_id}/related")
async def get_related_posts(post_id: str, limit: int = 10):
    """Get posts related to this one (same people, location, or hashtags)."""
    query = """
    MATCH (p:Post {id: $id})
    CALL {
        WITH p
        MATCH (person:Person)-[:APPEARS_IN]->(p)
        MATCH (person)-[:APPEARS_IN]->(other:Post)
        WHERE other.id <> p.id
        RETURN other, 'shared_person' as reason
        UNION
        WITH p
        MATCH (p)-[:AT_LOCATION]->(loc:Location)<-[:AT_LOCATION]-(other:Post)
        WHERE other.id <> p.id
        RETURN other, 'same_location' as reason
        UNION
        WITH p
        MATCH (p)-[:HAS_HASHTAG]->(h:Hashtag)<-[:HAS_HASHTAG]-(other:Post)
        WHERE other.id <> p.id
        RETURN other, 'shared_hashtag' as reason
    }
    WITH other, collect(DISTINCT reason) as reasons
    RETURN {
        post: other {.*},
        reasons: reasons
    } as related
    LIMIT $limit
    """

    results = execute_query(query, {"id": post_id, "limit": limit})
    return [r["related"] for r in results]


@router.delete("/{post_id}")
async def delete_post(post_id: str):
    """Delete a post and its relationships."""
    query = """
    MATCH (p:Post {id: $id})
    DETACH DELETE p
    RETURN count(p) as deleted
    """

    result = execute_write(query, {"id": post_id})

    if not result or result[0]["deleted"] == 0:
        raise HTTPException(status_code=404, detail="Post not found")

    return {"message": "Post deleted successfully"}


@router.get("/{post_id}/analysis")
async def analyze_post(post_id: str):
    """Get AI analysis of a post."""
    # Get post data
    query = """
    MATCH (p:Post {id: $id})
    OPTIONAL MATCH (a:Account)-[:POSTED]->(p)
    OPTIONAL MATCH (p)-[:AT_LOCATION]->(l:Location)
    OPTIONAL MATCH (p)-[:HAS_HASHTAG]->(h:Hashtag)
    OPTIONAL MATCH (person:Person)-[:APPEARS_IN]->(p)
    RETURN p, a.username as account, l.name as location,
           collect(DISTINCT h.name) as hashtags,
           collect(DISTINCT person.name) as persons
    """

    results = execute_query(query, {"id": post_id})

    if not results:
        raise HTTPException(status_code=404, detail="Post not found")

    data = results[0]
    post_data = data["p"]

    # Analyze caption
    caption_analysis = None
    if post_data.get("caption"):
        caption_analysis = ai_service.analyze_caption(post_data["caption"])

    # Analyze first image if available
    image_analysis = None
    image_urls = post_data.get("image_urls", [])
    if image_urls:
        image_path = Path(image_urls[0])
        if image_path.exists():
            image_analysis = ai_service.analyze_image(image_path)

    return {
        "post": post_data,
        "account": data["account"],
        "location": data["location"],
        "hashtags": data["hashtags"],
        "persons": data["persons"],
        "caption_analysis": caption_analysis,
        "image_analysis": image_analysis,
    }

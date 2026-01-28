"""Diagnostics API endpoints for debugging and monitoring."""

from fastapi import APIRouter
from typing import Optional
import logging

from app.core.database import execute_query
from app.services.face_recognition_service import face_recognition_service
from app.services.media_store import media_store

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/diagnostics", tags=["diagnostics"])


@router.get("/stats")
async def get_detailed_stats():
    """Get detailed database statistics including Face nodes."""
    query = """
    MATCH (p:Post) WITH count(p) as posts
    MATCH (person:Person) WITH posts, count(person) as persons
    MATCH (f:Face) WITH posts, persons, count(f) as faces
    MATCH (l:Location) WITH posts, persons, faces, count(l) as locations
    MATCH (h:Hashtag) WITH posts, persons, faces, locations, count(h) as hashtags
    MATCH (a:Account) WITH posts, persons, faces, locations, hashtags, count(a) as accounts
    RETURN {
        posts: posts,
        persons: persons,
        faces: faces,
        locations: locations,
        hashtags: hashtags,
        accounts: accounts
    } as stats
    """
    # Need to handle case where some node types don't exist yet
    stats = {
        "posts": 0,
        "persons": 0,
        "faces": 0,
        "locations": 0,
        "hashtags": 0,
        "accounts": 0,
        "unassigned_faces": 0,
        "assigned_faces": 0,
        "processed_posts": 0,
        "unprocessed_posts": 0,
    }

    # Get counts separately to handle empty collections
    queries = [
        ("posts", "MATCH (n:Post) RETURN count(n) as count"),
        ("persons", "MATCH (n:Person) RETURN count(n) as count"),
        ("faces", "MATCH (n:Face) RETURN count(n) as count"),
        ("locations", "MATCH (n:Location) RETURN count(n) as count"),
        ("hashtags", "MATCH (n:Hashtag) RETURN count(n) as count"),
        ("accounts", "MATCH (n:Account) RETURN count(n) as count"),
        (
            "assigned_faces",
            "MATCH (f:Face)-[:BELONGS_TO]->(:Person) RETURN count(f) as count",
        ),
        (
            "unassigned_faces",
            "MATCH (f:Face) WHERE NOT (f)-[:BELONGS_TO]->(:Person) RETURN count(f) as count",
        ),
        ("processed_posts", "MATCH (p:Post {processed: true}) RETURN count(p) as count"),
        (
            "unprocessed_posts",
            "MATCH (p:Post) WHERE p.processed IS NULL OR p.processed = false RETURN count(p) as count",
        ),
    ]

    for key, query in queries:
        try:
            results = execute_query(query)
            if results:
                stats[key] = results[0]["count"]
        except Exception as e:
            logger.warning(f"Error getting {key} count: {e}")

    return stats


@router.get("/faces/unassigned")
async def get_unassigned_faces(limit: int = 50):
    """Get faces that haven't been assigned to a person yet."""
    faces = face_recognition_service.get_unassigned_faces(limit)
    return {"count": len(faces), "faces": faces}


@router.get("/posts/{post_id}/debug")
async def debug_post(post_id: str):
    """Get detailed debug info for a specific post."""
    # Get post info
    query = """
    MATCH (p:Post {id: $id})
    RETURN p
    """
    results = execute_query(query, {"id": post_id})

    if not results:
        return {"error": "Post not found"}

    post_data = dict(results[0]["p"])

    # Get face nodes
    faces = face_recognition_service.get_faces_for_post(post_id)

    # Check local files
    shortcode = post_data.get("shortcode", post_id)
    image_urls = post_data.get("image_urls", [])
    local_files = []
    for idx in range(len(image_urls)):
        local_path = media_store.get_local_path(shortcode, idx)
        local_files.append({
            "index": idx,
            "expected_path": str(local_path),
            "exists": local_path.exists(),
            "original_url": image_urls[idx] if idx < len(image_urls) else None,
        })

    # Get related persons
    query = """
    MATCH (f:Face)-[:APPEARS_IN]->(p:Post {id: $id})
    OPTIONAL MATCH (f)-[:BELONGS_TO]->(person:Person)
    RETURN collect(DISTINCT person.name) as persons
    """
    results = execute_query(query, {"id": post_id})
    persons = results[0]["persons"] if results else []

    return {
        "post": post_data,
        "face_count": len(faces),
        "faces": faces,
        "local_files": local_files,
        "identified_persons": [p for p in persons if p],
        "face_recognition_available": face_recognition_service.is_available(),
    }


@router.post("/posts/{post_id}/reprocess")
async def reprocess_post(post_id: str):
    """Delete existing Face nodes for a post and reprocess it."""
    # Delete existing faces for this post
    query = """
    MATCH (f:Face)-[:APPEARS_IN]->(p:Post {id: $id})
    DETACH DELETE f
    RETURN count(f) as deleted
    """
    results = execute_query(query, {"id": post_id})
    deleted = results[0]["deleted"] if results else 0

    # Reset processed flag
    query = """
    MATCH (p:Post {id: $id})
    SET p.processed = false
    """
    execute_query(query, {"id": post_id})

    return {
        "deleted_faces": deleted,
        "message": f"Deleted {deleted} faces. Call POST /posts/{post_id}/process to reprocess.",
    }


@router.post("/process-all-unprocessed")
async def process_all_unprocessed(limit: int = 10):
    """Process all unprocessed posts (up to limit)."""
    query = """
    MATCH (p:Post)
    WHERE p.processed IS NULL OR p.processed = false
    RETURN p.id as id, p.shortcode as shortcode
    LIMIT $limit
    """
    results = execute_query(query, {"limit": limit})

    processed = []
    errors = []

    for record in results:
        post_id = record["id"]
        shortcode = record["shortcode"]

        try:
            # Get post images
            query = """
            MATCH (p:Post {id: $id})
            RETURN p.image_urls as image_urls
            """
            post_results = execute_query(query, {"id": post_id})
            if not post_results:
                continue

            image_urls = post_results[0].get("image_urls", [])

            face_count = 0
            for idx, url in enumerate(image_urls):
                local_path = media_store.ensure_local_image_sync(url, shortcode, idx)
                if local_path:
                    faces = face_recognition_service.detect_and_store_faces(
                        local_path, post_id, shortcode
                    )
                    face_count += len(faces)

            # Mark as processed
            query = """
            MATCH (p:Post {id: $id})
            SET p.processed = true
            """
            execute_query(query, {"id": post_id})

            processed.append({"post_id": post_id, "shortcode": shortcode, "faces": face_count})

        except Exception as e:
            logger.error(f"Error processing post {post_id}: {e}")
            errors.append({"post_id": post_id, "error": str(e)})

    return {
        "processed": len(processed),
        "errors": len(errors),
        "details": processed,
        "error_details": errors,
    }


@router.get("/health")
async def health_check():
    """Health check with dependency status."""
    return {
        "status": "ok",
        "face_recognition_available": face_recognition_service.is_available(),
    }

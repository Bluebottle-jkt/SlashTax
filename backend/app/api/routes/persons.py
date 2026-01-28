from fastapi import APIRouter, HTTPException, UploadFile, File, Form
from typing import Optional
import uuid
from pathlib import Path

from app.core.config import settings
from app.core.database import execute_query, execute_write
from app.schemas.models import Person, PersonCreate, GraphData
from app.services.face_recognition_service import face_recognition_service
from app.services.graph_service import graph_service
from app.services.ai_service import ai_service

router = APIRouter(prefix="/persons", tags=["persons"])


@router.get("/", response_model=list[Person])
async def list_persons(skip: int = 0, limit: int = 100):
    """List all persons in the database."""
    query = """
    MATCH (p:Person)
    OPTIONAL MATCH (p)-[r:APPEARS_IN]->(post:Post)
    WITH p, count(post) as post_count
    RETURN p {.*, post_count: post_count} as person
    ORDER BY p.name
    SKIP $skip
    LIMIT $limit
    """

    results = execute_query(query, {"skip": skip, "limit": limit})
    return [Person(**r["person"]) for r in results if r.get("person")]


@router.get("/{person_id}", response_model=Person)
async def get_person(person_id: str):
    """Get a person by ID."""
    query = """
    MATCH (p:Person {id: $id})
    OPTIONAL MATCH (p)-[r:APPEARS_IN]->(post:Post)
    WITH p, count(post) as post_count
    RETURN p {.*, post_count: post_count} as person
    """

    results = execute_query(query, {"id": person_id})

    if not results or not results[0].get("person"):
        raise HTTPException(status_code=404, detail="Person not found")

    return Person(**results[0]["person"])


@router.post("/", response_model=Person)
async def create_person(person: PersonCreate):
    """Create a new person."""
    person_id = str(uuid.uuid4())

    query = """
    CREATE (p:Person {
        id: $id,
        name: $name,
        notes: $notes,
        face_encoding: $encoding,
        created_at: datetime()
    })
    RETURN p
    """

    result = execute_write(query, {
        "id": person_id,
        "name": person.name,
        "notes": person.notes,
        "encoding": person.face_encoding,
    })

    return Person(
        id=person_id,
        name=person.name,
        notes=person.notes,
        face_encoding=person.face_encoding,
    )


@router.post("/{person_id}/face", response_model=Person)
async def add_face_to_person(
    person_id: str,
    file: UploadFile = File(...),
):
    """Add a face to an existing person from an uploaded image."""
    # Save uploaded file
    upload_path = settings.UPLOAD_DIR / f"temp_{uuid.uuid4()}{Path(file.filename).suffix}"
    upload_path.parent.mkdir(parents=True, exist_ok=True)

    content = await file.read()
    upload_path.write_bytes(content)

    try:
        # Detect faces
        faces = face_recognition_service.detect_faces(upload_path)

        if not faces:
            raise HTTPException(status_code=400, detail="No face detected in image")

        if len(faces) > 1:
            raise HTTPException(
                status_code=400,
                detail="Multiple faces detected. Please upload an image with a single face."
            )

        # Add face encoding to person
        face_encoding = faces[0]["encoding"]
        success = face_recognition_service.add_face_to_person(person_id, face_encoding)

        if not success:
            raise HTTPException(status_code=404, detail="Person not found")

        # Save face crop
        face_recognition_service._save_face_crop(
            str(upload_path), faces[0]["bounding_box"], person_id
        )

        return await get_person(person_id)

    finally:
        upload_path.unlink(missing_ok=True)


@router.post("/from-image", response_model=Person)
async def create_person_from_image(
    name: str = Form(...),
    notes: Optional[str] = Form(None),
    file: UploadFile = File(...),
):
    """Create a new person with face extracted from an image."""
    # Save uploaded file
    upload_path = settings.UPLOAD_DIR / f"temp_{uuid.uuid4()}{Path(file.filename).suffix}"
    upload_path.parent.mkdir(parents=True, exist_ok=True)

    content = await file.read()
    upload_path.write_bytes(content)

    try:
        # Detect faces
        faces = face_recognition_service.detect_faces(upload_path)

        if not faces:
            raise HTTPException(status_code=400, detail="No face detected in image")

        if len(faces) > 1:
            raise HTTPException(
                status_code=400,
                detail="Multiple faces detected. Please upload an image with a single face."
            )

        # Create person with face
        person = face_recognition_service.create_person_from_face(
            name=name,
            face_encoding=faces[0]["encoding"],
            image_path=str(upload_path),
            bounding_box=faces[0]["bounding_box"],
        )

        # Add notes if provided
        if notes:
            query = """
            MATCH (p:Person {id: $id})
            SET p.notes = $notes
            """
            execute_write(query, {"id": person.id, "notes": notes})
            person.notes = notes

        return person

    finally:
        upload_path.unlink(missing_ok=True)


@router.get("/{person_id}/network", response_model=GraphData)
async def get_person_network(person_id: str, depth: int = 2):
    """Get the network graph around a person."""
    return graph_service.get_person_network(person_id, depth)


@router.get("/{person_id}/co-appearances")
async def get_co_appearances(person_id: str):
    """Get people who appear in the same posts."""
    return graph_service.get_co_appearances(person_id)


@router.get("/{person_id}/locations")
async def get_person_locations(person_id: str):
    """Get all locations where the person has appeared."""
    return graph_service.get_person_locations(person_id)


@router.get("/{person_id}/timeline")
async def get_person_timeline(person_id: str):
    """Get a timeline of the person's appearances."""
    return graph_service.get_timeline(person_id)


@router.get("/{person_id}/profile")
async def get_person_profile(person_id: str):
    """Generate an AI profile for a person."""
    # Get person data
    person = await get_person(person_id)
    locations = graph_service.get_person_locations(person_id)
    co_appearances = graph_service.get_co_appearances(person_id)

    # Get hashtags
    query = """
    MATCH (p:Person {id: $id})-[:APPEARS_IN]->(post:Post)-[:HAS_HASHTAG]->(h:Hashtag)
    WITH h.name as hashtag, count(*) as count
    ORDER BY count DESC
    LIMIT 10
    RETURN collect(hashtag) as hashtags
    """
    results = execute_query(query, {"id": person_id})
    hashtags = results[0]["hashtags"] if results else []

    person_data = {
        "name": person.name,
        "post_count": person.post_count,
        "locations": [loc["location_name"] for loc in locations],
        "co_appearances": [c["person_name"] for c in co_appearances],
        "hashtags": hashtags,
    }

    profile = ai_service.generate_person_profile(person_data)

    return {
        "person": person,
        "profile": profile,
        "locations": locations,
        "co_appearances": co_appearances,
        "hashtags": hashtags,
    }


@router.delete("/{person_id}")
async def delete_person(person_id: str):
    """Delete a person and all their relationships."""
    query = """
    MATCH (p:Person {id: $id})
    DETACH DELETE p
    RETURN count(p) as deleted
    """

    result = execute_write(query, {"id": person_id})

    if not result or result[0]["deleted"] == 0:
        raise HTTPException(status_code=404, detail="Person not found")

    return {"message": "Person deleted successfully"}


@router.put("/{person_id}", response_model=Person)
async def update_person(person_id: str, person: PersonCreate):
    """Update a person's information."""
    query = """
    MATCH (p:Person {id: $id})
    SET p.name = $name, p.notes = $notes, p.updated_at = datetime()
    RETURN p
    """

    result = execute_write(query, {
        "id": person_id,
        "name": person.name,
        "notes": person.notes,
    })

    if not result:
        raise HTTPException(status_code=404, detail="Person not found")

    return await get_person(person_id)

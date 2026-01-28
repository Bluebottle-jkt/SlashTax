import numpy as np
from PIL import Image
from pathlib import Path
from typing import Optional
import logging
import uuid

# Try to import face_recognition (requires dlib)
try:
    import face_recognition
    import cv2
    FACE_RECOGNITION_AVAILABLE = True
except ImportError:
    FACE_RECOGNITION_AVAILABLE = False
    face_recognition = None
    cv2 = None

from app.core.config import settings
from app.core.database import execute_query, execute_write
from app.schemas.models import FaceDetection, Person

logger = logging.getLogger(__name__)

if not FACE_RECOGNITION_AVAILABLE:
    logger.warning("face_recognition not available. Face detection features will be disabled.")


class FaceRecognitionService:
    """Service for detecting and recognizing faces in images."""

    def __init__(self):
        self.tolerance = settings.FACE_RECOGNITION_TOLERANCE
        self.model = settings.FACE_RECOGNITION_MODEL
        self.faces_dir = settings.FACES_DIR
        self.faces_dir.mkdir(parents=True, exist_ok=True)

    def detect_faces(self, image_path: str | Path) -> list[dict]:
        """Detect all faces in an image and return their locations and encodings."""
        if not FACE_RECOGNITION_AVAILABLE:
            logger.warning("Face recognition not available - skipping face detection")
            return []

        image = face_recognition.load_image_file(str(image_path))
        face_locations = face_recognition.face_locations(image, model=self.model)
        face_encodings = face_recognition.face_encodings(image, face_locations)

        faces = []
        for location, encoding in zip(face_locations, face_encodings):
            top, right, bottom, left = location
            faces.append({
                "bounding_box": {
                    "top": top,
                    "right": right,
                    "bottom": bottom,
                    "left": left,
                },
                "encoding": encoding.tolist(),
            })

        logger.info(f"Detected {len(faces)} faces in {image_path}")
        return faces

    def detect_faces_from_bytes(self, image_bytes: bytes) -> list[dict]:
        """Detect faces from image bytes."""
        if not FACE_RECOGNITION_AVAILABLE:
            logger.warning("Face recognition not available - skipping face detection")
            return []

        nparr = np.frombuffer(image_bytes, np.uint8)
        image = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
        image_rgb = cv2.cvtColor(image, cv2.COLOR_BGR2RGB)

        face_locations = face_recognition.face_locations(image_rgb, model=self.model)
        face_encodings = face_recognition.face_encodings(image_rgb, face_locations)

        faces = []
        for location, encoding in zip(face_locations, face_encodings):
            top, right, bottom, left = location
            faces.append({
                "bounding_box": {
                    "top": top,
                    "right": right,
                    "bottom": bottom,
                    "left": left,
                },
                "encoding": encoding.tolist(),
            })

        return faces

    def get_known_faces(self) -> list[tuple[str, str, np.ndarray]]:
        """Get all known faces from the database."""
        query = """
        MATCH (p:Person)
        WHERE p.face_encoding IS NOT NULL
        RETURN p.id as id, p.name as name, p.face_encoding as encoding
        """
        results = execute_query(query)

        known_faces = []
        for record in results:
            if record.get("encoding"):
                known_faces.append((
                    record["id"],
                    record["name"],
                    np.array(record["encoding"]),
                ))

        return known_faces

    def identify_face(self, face_encoding: list[float]) -> FaceDetection:
        """Identify a face by comparing with known faces."""
        if not FACE_RECOGNITION_AVAILABLE:
            return FaceDetection(
                confidence=0.0,
                bounding_box={},
                is_new_face=True,
            )

        known_faces = self.get_known_faces()
        encoding = np.array(face_encoding)

        if not known_faces:
            return FaceDetection(
                confidence=0.0,
                bounding_box={},
                is_new_face=True,
            )

        known_encodings = [face[2] for face in known_faces]
        distances = face_recognition.face_distance(known_encodings, encoding)

        if len(distances) > 0:
            best_match_idx = np.argmin(distances)
            best_distance = distances[best_match_idx]

            if best_distance <= self.tolerance:
                person_id, person_name, _ = known_faces[best_match_idx]
                confidence = 1 - best_distance

                return FaceDetection(
                    person_id=person_id,
                    person_name=person_name,
                    confidence=float(confidence),
                    bounding_box={},
                    is_new_face=False,
                )

        return FaceDetection(
            confidence=0.0,
            bounding_box={},
            is_new_face=True,
        )

    def process_image_faces(
        self, image_path: str | Path, post_id: Optional[str] = None
    ) -> list[FaceDetection]:
        """Process an image, detect and identify all faces."""
        faces = self.detect_faces(image_path)
        detections = []

        for face in faces:
            detection = self.identify_face(face["encoding"])
            detection.bounding_box = face["bounding_box"]

            if post_id and detection.person_id:
                self._link_person_to_post(detection.person_id, post_id)

            detections.append(detection)

        return detections

    def create_person_from_face(
        self,
        name: str,
        face_encoding: list[float],
        image_path: Optional[str] = None,
        bounding_box: Optional[dict] = None,
    ) -> Person:
        """Create a new person with a face encoding."""
        person_id = str(uuid.uuid4())

        # Save cropped face image if provided
        profile_image = None
        if image_path and bounding_box:
            profile_image = self._save_face_crop(
                image_path, bounding_box, person_id
            )

        query = """
        CREATE (p:Person {
            id: $id,
            name: $name,
            face_encoding: $encoding,
            profile_image: $profile_image,
            created_at: datetime()
        })
        RETURN p
        """

        execute_write(query, {
            "id": person_id,
            "name": name,
            "encoding": face_encoding,
            "profile_image": profile_image,
        })

        return Person(
            id=person_id,
            name=name,
            face_encoding=face_encoding,
            profile_image=profile_image,
        )

    def add_face_to_person(
        self, person_id: str, face_encoding: list[float]
    ) -> bool:
        """Add or update face encoding for an existing person."""
        query = """
        MATCH (p:Person {id: $id})
        SET p.face_encoding = $encoding, p.updated_at = datetime()
        RETURN p
        """

        result = execute_write(query, {
            "id": person_id,
            "encoding": face_encoding,
        })

        return len(result) > 0

    def _link_person_to_post(self, person_id: str, post_id: str) -> None:
        """Create APPEARS_IN relationship between person and post."""
        query = """
        MATCH (p:Person {id: $person_id})
        MATCH (post:Post {id: $post_id})
        MERGE (p)-[r:APPEARS_IN]->(post)
        ON CREATE SET r.created_at = datetime()
        RETURN r
        """

        execute_write(query, {
            "person_id": person_id,
            "post_id": post_id,
        })

    def _save_face_crop(
        self, image_path: str, bounding_box: dict, person_id: str
    ) -> str:
        """Crop and save a face from an image."""
        image = Image.open(image_path)
        top = bounding_box["top"]
        right = bounding_box["right"]
        bottom = bounding_box["bottom"]
        left = bounding_box["left"]

        # Add padding
        padding = 20
        top = max(0, top - padding)
        left = max(0, left - padding)
        right = min(image.width, right + padding)
        bottom = min(image.height, bottom + padding)

        face_crop = image.crop((left, top, right, bottom))

        face_filename = f"{person_id}.jpg"
        face_path = self.faces_dir / face_filename
        face_crop.save(face_path, "JPEG")

        return str(face_path)

    def find_similar_faces(
        self, face_encoding: list[float], threshold: float = 0.6, limit: int = 10
    ) -> list[dict]:
        """Find persons with similar faces."""
        if not FACE_RECOGNITION_AVAILABLE:
            return []

        known_faces = self.get_known_faces()
        encoding = np.array(face_encoding)

        similar = []
        for person_id, person_name, known_encoding in known_faces:
            distance = face_recognition.face_distance([known_encoding], encoding)[0]
            if distance <= threshold:
                similar.append({
                    "person_id": person_id,
                    "person_name": person_name,
                    "similarity": float(1 - distance),
                })

        similar.sort(key=lambda x: x["similarity"], reverse=True)
        return similar[:limit]

    @staticmethod
    def is_available() -> bool:
        """Check if face recognition is available."""
        return FACE_RECOGNITION_AVAILABLE


face_recognition_service = FaceRecognitionService()

from pydantic import BaseModel, Field
from datetime import datetime
from typing import Optional
import uuid


class PersonBase(BaseModel):
    name: str
    notes: Optional[str] = None


class PersonCreate(PersonBase):
    face_encoding: Optional[list[float]] = None


class Person(PersonBase):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    face_encoding: Optional[list[float]] = None
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: Optional[datetime] = None
    post_count: int = 0
    profile_image: Optional[str] = None

    class Config:
        from_attributes = True


class LocationBase(BaseModel):
    name: str
    latitude: Optional[float] = None
    longitude: Optional[float] = None
    address: Optional[str] = None


class Location(LocationBase):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    post_count: int = 0

    class Config:
        from_attributes = True


class AccountBase(BaseModel):
    username: str
    full_name: Optional[str] = None
    biography: Optional[str] = None
    profile_pic_url: Optional[str] = None


class Account(AccountBase):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    followers: int = 0
    following: int = 0
    post_count: int = 0
    is_private: bool = False

    class Config:
        from_attributes = True


class HashtagBase(BaseModel):
    name: str


class Hashtag(HashtagBase):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    post_count: int = 0

    class Config:
        from_attributes = True


class PostBase(BaseModel):
    shortcode: str
    caption: Optional[str] = None
    posted_at: Optional[datetime] = None
    likes: int = 0
    comments: int = 0


class PostCreate(PostBase):
    image_urls: list[str] = []
    location_name: Optional[str] = None
    account_username: str
    hashtags: list[str] = []


class Post(PostBase):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    image_urls: list[str] = []
    faces_detected: int = 0
    processed: bool = False

    class Config:
        from_attributes = True


class FaceDetection(BaseModel):
    person_id: Optional[str] = None
    person_name: Optional[str] = None
    confidence: float
    bounding_box: dict[str, int]  # top, right, bottom, left
    is_new_face: bool = False


class PostAnalysis(BaseModel):
    post_id: str
    faces: list[FaceDetection]
    location: Optional[Location] = None
    hashtags: list[str] = []
    mentioned_accounts: list[str] = []
    caption_analysis: Optional[str] = None


class GraphNode(BaseModel):
    id: str
    label: str
    type: str
    properties: dict


class GraphEdge(BaseModel):
    source: str
    target: str
    type: str
    properties: Optional[dict] = None


class GraphData(BaseModel):
    nodes: list[GraphNode]
    edges: list[GraphEdge]


class SearchQuery(BaseModel):
    query: str
    search_type: str = "all"  # all, person, location, caption, hashtag
    limit: int = 50


class InstagramImportRequest(BaseModel):
    username: str
    max_posts: int = 50
    include_tagged: bool = True


class UploadImageRequest(BaseModel):
    post_shortcode: Optional[str] = None
    account_username: Optional[str] = None
    caption: Optional[str] = None
    location_name: Optional[str] = None


class StatsResponse(BaseModel):
    total_persons: int
    total_posts: int
    total_locations: int
    total_accounts: int
    total_hashtags: int
    total_faces_detected: int
    recent_posts: list[Post]

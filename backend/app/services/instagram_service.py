from pathlib import Path
from datetime import datetime
from typing import Optional, Generator
import logging
import re
import httpx
import asyncio

# Try to import instaloader
try:
    import instaloader
    INSTALOADER_AVAILABLE = True
except ImportError:
    INSTALOADER_AVAILABLE = False
    instaloader = None

from app.core.config import settings
from app.core.database import execute_write, execute_query
from app.schemas.models import Post, Account, Location, Hashtag

logger = logging.getLogger(__name__)

if not INSTALOADER_AVAILABLE:
    logger.warning("instaloader not available. Instagram import features will be disabled.")


class InstagramService:
    """Service for extracting data from Instagram using Instaloader."""

    def __init__(self):
        self.loader = None
        self._logged_in = False

        if INSTALOADER_AVAILABLE:
            self.loader = instaloader.Instaloader(
                download_pictures=True,
                download_videos=False,
                download_video_thumbnails=False,
                download_geotags=True,
                download_comments=False,
                save_metadata=True,
                compress_json=False,
                dirname_pattern=str(settings.UPLOAD_DIR / "{target}"),
                filename_pattern="{shortcode}",
            )

    @staticmethod
    def is_available() -> bool:
        """Check if Instagram service is available."""
        return INSTALOADER_AVAILABLE

    def login(self, username: Optional[str] = None, password: Optional[str] = None) -> bool:
        """Login to Instagram for accessing private profiles."""
        if not INSTALOADER_AVAILABLE or not self.loader:
            logger.warning("Instaloader not available")
            return False

        username = username or settings.INSTAGRAM_USERNAME
        password = password or settings.INSTAGRAM_PASSWORD

        if not username or not password:
            logger.warning("Instagram credentials not provided")
            return False

        try:
            self.loader.login(username, password)
            self._logged_in = True
            logger.info(f"Logged in as {username}")
            return True
        except Exception as e:
            logger.error(f"Failed to login: {e}")
            return False

    def get_profile(self, username: str) -> Optional[Account]:
        """Get Instagram profile information."""
        if not INSTALOADER_AVAILABLE or not self.loader:
            logger.warning("Instaloader not available")
            return None

        try:
            profile = instaloader.Profile.from_username(
                self.loader.context, username
            )

            account = Account(
                username=profile.username,
                full_name=profile.full_name,
                biography=profile.biography,
                profile_pic_url=profile.profile_pic_url,
                followers=profile.followers,
                following=profile.followees,
                post_count=profile.mediacount,
                is_private=profile.is_private,
            )

            # Store in Neo4j
            self._store_account(account)

            return account
        except Exception as e:
            logger.error(f"Failed to get profile {username}: {e}")
            return None

    def get_posts(
        self, username: str, max_posts: int = 50
    ) -> Generator[Post, None, None]:
        """Get posts from a user's profile."""
        if not INSTALOADER_AVAILABLE or not self.loader:
            logger.warning("Instaloader not available")
            return

        try:
            profile = instaloader.Profile.from_username(
                self.loader.context, username
            )

            if profile.is_private and not self._logged_in:
                logger.warning(f"Profile {username} is private and not logged in")
                return

            posts_iter = profile.get_posts()
            count = 0

            for insta_post in posts_iter:
                if count >= max_posts:
                    break

                post = self._convert_post(insta_post, username)
                if post:
                    yield post
                    count += 1

        except Exception as e:
            logger.error(f"Failed to get posts for {username}: {e}")

    def get_tagged_posts(
        self, username: str, max_posts: int = 50
    ) -> Generator[Post, None, None]:
        """Get posts where the user is tagged."""
        if not INSTALOADER_AVAILABLE or not self.loader:
            logger.warning("Instaloader not available")
            return

        try:
            profile = instaloader.Profile.from_username(
                self.loader.context, username
            )

            if not self._logged_in:
                logger.warning("Must be logged in to get tagged posts")
                return

            tagged_iter = profile.get_tagged_posts()
            count = 0

            for insta_post in tagged_iter:
                if count >= max_posts:
                    break

                post = self._convert_post(insta_post, insta_post.owner_username)
                if post:
                    yield post
                    count += 1

        except Exception as e:
            logger.error(f"Failed to get tagged posts for {username}: {e}")

    def download_post_images(self, post: Post) -> list[Path]:
        """Download images from a post."""
        downloaded = []

        for url in post.image_urls:
            try:
                response = httpx.get(url, follow_redirects=True)
                if response.status_code == 200:
                    filename = f"{post.shortcode}_{len(downloaded)}.jpg"
                    filepath = settings.UPLOAD_DIR / post.shortcode / filename
                    filepath.parent.mkdir(parents=True, exist_ok=True)
                    filepath.write_bytes(response.content)
                    downloaded.append(filepath)
            except Exception as e:
                logger.error(f"Failed to download image: {e}")

        return downloaded

    def _convert_post(
        self, insta_post: instaloader.Post, account_username: str
    ) -> Optional[Post]:
        """Convert Instaloader post to our Post model."""
        try:
            # Extract image URLs
            image_urls = []
            if insta_post.typename == "GraphSidecar":
                for node in insta_post.get_sidecar_nodes():
                    if not node.is_video:
                        image_urls.append(node.display_url)
            elif not insta_post.is_video:
                image_urls.append(insta_post.url)

            # Extract location
            location_name = None
            if insta_post.location:
                location_name = insta_post.location.name

            # Extract hashtags from caption
            hashtags = []
            if insta_post.caption:
                hashtags = re.findall(r"#(\w+)", insta_post.caption)

            post = Post(
                shortcode=insta_post.shortcode,
                caption=insta_post.caption,
                posted_at=insta_post.date_utc,
                likes=insta_post.likes,
                comments=insta_post.comments,
                image_urls=image_urls,
            )

            # Store in Neo4j
            self._store_post(post, account_username, location_name, hashtags)

            return post

        except Exception as e:
            logger.error(f"Failed to convert post: {e}")
            return None

    def _store_account(self, account: Account) -> None:
        """Store account in Neo4j."""
        query = """
        MERGE (a:Account {username: $username})
        ON CREATE SET
            a.id = randomUUID(),
            a.created_at = datetime()
        SET
            a.full_name = $full_name,
            a.biography = $biography,
            a.profile_pic_url = $profile_pic_url,
            a.followers = $followers,
            a.following = $following,
            a.post_count = $post_count,
            a.is_private = $is_private,
            a.updated_at = datetime()
        RETURN a
        """

        execute_write(query, {
            "username": account.username,
            "full_name": account.full_name,
            "biography": account.biography,
            "profile_pic_url": account.profile_pic_url,
            "followers": account.followers,
            "following": account.following,
            "post_count": account.post_count,
            "is_private": account.is_private,
        })

    def _store_post(
        self,
        post: Post,
        account_username: str,
        location_name: Optional[str],
        hashtags: list[str],
    ) -> None:
        """Store post and its relationships in Neo4j."""
        # Create post
        query = """
        MERGE (p:Post {shortcode: $shortcode})
        ON CREATE SET
            p.id = randomUUID(),
            p.created_at = datetime()
        SET
            p.caption = $caption,
            p.posted_at = $posted_at,
            p.likes = $likes,
            p.comments = $comments,
            p.image_urls = $image_urls,
            p.updated_at = datetime()
        RETURN p.id as id
        """

        result = execute_write(query, {
            "shortcode": post.shortcode,
            "caption": post.caption,
            "posted_at": post.posted_at.isoformat() if post.posted_at else None,
            "likes": post.likes,
            "comments": post.comments,
            "image_urls": post.image_urls,
        })

        if result:
            post.id = result[0]["id"]

        # Link to account
        query = """
        MATCH (p:Post {shortcode: $shortcode})
        MATCH (a:Account {username: $username})
        MERGE (a)-[r:POSTED]->(p)
        ON CREATE SET r.created_at = datetime()
        """
        execute_write(query, {
            "shortcode": post.shortcode,
            "username": account_username,
        })

        # Create and link location
        if location_name:
            query = """
            MERGE (l:Location {name: $name})
            ON CREATE SET
                l.id = randomUUID(),
                l.created_at = datetime()
            WITH l
            MATCH (p:Post {shortcode: $shortcode})
            MERGE (p)-[r:AT_LOCATION]->(l)
            ON CREATE SET r.created_at = datetime()
            """
            execute_write(query, {
                "name": location_name,
                "shortcode": post.shortcode,
            })

        # Create and link hashtags
        for tag in hashtags:
            query = """
            MERGE (h:Hashtag {name: $name})
            ON CREATE SET
                h.id = randomUUID(),
                h.created_at = datetime()
            WITH h
            MATCH (p:Post {shortcode: $shortcode})
            MERGE (p)-[r:HAS_HASHTAG]->(h)
            ON CREATE SET r.created_at = datetime()
            """
            execute_write(query, {
                "name": tag.lower(),
                "shortcode": post.shortcode,
            })


instagram_service = InstagramService()

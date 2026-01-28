"""Media store service for managing local copies of images."""

from pathlib import Path
from typing import Optional
import logging
import httpx
import asyncio
from urllib.parse import urlparse

from app.core.config import settings

logger = logging.getLogger(__name__)


class MediaStore:
    """Service for ensuring images are available locally."""

    def __init__(self):
        self.upload_dir = settings.UPLOAD_DIR
        self.upload_dir.mkdir(parents=True, exist_ok=True)

    def get_local_path(self, shortcode: str, index: int = 0) -> Path:
        """Get expected local path for a post image."""
        return self.upload_dir / shortcode / f"{shortcode}_{index}.jpg"

    def image_exists_locally(self, shortcode: str, index: int = 0) -> bool:
        """Check if image exists locally."""
        local_path = self.get_local_path(shortcode, index)
        return local_path.exists()

    async def ensure_local_image(
        self, url: str, shortcode: str, index: int = 0, timeout: float = 30.0
    ) -> Optional[Path]:
        """
        Ensure an image is available locally, downloading if needed.

        Args:
            url: The image URL (can be CDN URL or local path)
            shortcode: Post shortcode for organizing files
            index: Image index for multi-image posts
            timeout: Download timeout in seconds

        Returns:
            Path to local image file, or None if download failed
        """
        local_path = self.get_local_path(shortcode, index)

        # Check if already exists locally
        if local_path.exists():
            logger.debug(f"Image already exists locally: {local_path}")
            return local_path

        # Check if url is already a local path
        url_path = Path(url)
        if url_path.exists():
            logger.debug(f"URL is a local path: {url}")
            return url_path

        # Need to download from URL
        try:
            local_path.parent.mkdir(parents=True, exist_ok=True)

            async with httpx.AsyncClient(timeout=timeout) as client:
                logger.info(f"Downloading image from {url[:100]}...")
                response = await client.get(url, follow_redirects=True)

                if response.status_code == 200:
                    local_path.write_bytes(response.content)
                    logger.info(f"Downloaded image to {local_path}")
                    return local_path
                else:
                    logger.warning(
                        f"Failed to download image: HTTP {response.status_code}"
                    )
                    return None

        except httpx.TimeoutException:
            logger.error(f"Timeout downloading image from {url[:100]}")
            return None
        except Exception as e:
            logger.error(f"Error downloading image: {e}")
            return None

    def ensure_local_image_sync(
        self, url: str, shortcode: str, index: int = 0, timeout: float = 30.0
    ) -> Optional[Path]:
        """Synchronous version of ensure_local_image."""
        local_path = self.get_local_path(shortcode, index)

        # Check if already exists locally
        if local_path.exists():
            logger.debug(f"Image already exists locally: {local_path}")
            return local_path

        # Check if url is already a local path
        url_path = Path(url)
        if url_path.exists():
            logger.debug(f"URL is a local path: {url}")
            return url_path

        # Need to download from URL
        try:
            local_path.parent.mkdir(parents=True, exist_ok=True)

            logger.info(f"Downloading image from {url[:100]}...")
            response = httpx.get(url, follow_redirects=True, timeout=timeout)

            if response.status_code == 200:
                local_path.write_bytes(response.content)
                logger.info(f"Downloaded image to {local_path}")
                return local_path
            else:
                logger.warning(
                    f"Failed to download image: HTTP {response.status_code}"
                )
                return None

        except httpx.TimeoutException:
            logger.error(f"Timeout downloading image from {url[:100]}")
            return None
        except Exception as e:
            logger.error(f"Error downloading image: {e}")
            return None

    async def ensure_all_post_images(
        self, image_urls: list[str], shortcode: str
    ) -> list[Path]:
        """
        Ensure all images for a post are available locally.

        Returns list of local paths for successfully downloaded images.
        """
        tasks = [
            self.ensure_local_image(url, shortcode, idx)
            for idx, url in enumerate(image_urls)
        ]
        results = await asyncio.gather(*tasks)
        return [path for path in results if path is not None]

    def ensure_all_post_images_sync(
        self, image_urls: list[str], shortcode: str
    ) -> list[Path]:
        """Synchronous version of ensure_all_post_images."""
        paths = []
        for idx, url in enumerate(image_urls):
            path = self.ensure_local_image_sync(url, shortcode, idx)
            if path:
                paths.append(path)
        return paths


media_store = MediaStore()

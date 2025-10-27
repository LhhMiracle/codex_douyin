from __future__ import annotations

import hashlib
import logging
from io import BytesIO
from pathlib import Path
from typing import Iterable, Iterator, Optional

import httpx
from PIL import Image

from ..models import ProductAsset

logger = logging.getLogger(__name__)


class ImageDownloader:
    """Download product assets to local files, with optional caching."""

    def __init__(
        self,
        cache_dir: Optional[Path] = None,
        timeout: float = 20.0,
        retries: int = 2,
    ) -> None:
        self.cache_dir = cache_dir
        self.timeout = timeout
        self.retries = retries
        if cache_dir is not None:
            cache_dir.mkdir(parents=True, exist_ok=True)

    def download(self, asset: ProductAsset) -> Image.Image:
        target_path = self._resolve_cache_path(asset)
        if target_path is not None and target_path.exists():
            logger.debug("Using cached asset for %s", asset.url)
            with Image.open(target_path) as cached:
                return cached.convert("RGBA")

        last_error: Optional[Exception] = None
        for attempt in range(self.retries + 1):
            try:
                with httpx.Client(timeout=self.timeout, follow_redirects=True) as client:
                    logger.debug("Downloading image %s (attempt %s)", asset.url, attempt + 1)
                    response = client.get(asset.url)
                    response.raise_for_status()
                    with Image.open(BytesIO(response.content)) as fetched:
                        image = fetched.convert("RGBA")
                    if target_path is not None:
                        image.save(target_path)
                    return image
            except Exception as exc:  # noqa: BLE001 - broad fallback to retry
                logger.warning("Failed to download %s: %s", asset.url, exc)
                last_error = exc
        assert last_error is not None
        raise RuntimeError(f"Unable to download asset {asset.url}") from last_error

    def bulk_download(self, assets: Iterable[ProductAsset]) -> Iterator[tuple[ProductAsset, Image.Image]]:
        for asset in assets:
            yield asset, self.download(asset)

    def _resolve_cache_path(self, asset: ProductAsset) -> Optional[Path]:
        if self.cache_dir is None:
            return None
        digest = hashlib.sha1(asset.url.encode("utf-8"), usedforsecurity=False).hexdigest()
        extension = (asset.format or "png").lower().split("?")[0]
        return self.cache_dir / f"{asset.id}_{digest}.{extension}"

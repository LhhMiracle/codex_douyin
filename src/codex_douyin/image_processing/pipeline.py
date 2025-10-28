from __future__ import annotations

import logging
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, List

import numpy as np
from PIL import Image

from ..media.downloader import ImageDownloader
from ..models import ProcessedImage, ProductAsset

try:
    import cv2
except ImportError as exc:  # pragma: no cover - optional dependency guard
    raise RuntimeError("OpenCV is required for background removal") from exc

logger = logging.getLogger(__name__)


@dataclass(slots=True)
class BackgroundRemovalConfig:
    iterations: int = 5
    dilation_iterations: int = 1


@dataclass(slots=True)
class EnhancementConfig:
    upscale_factor: float = 2.0
    max_size: int = 2048


class BackgroundRemover:
    def __init__(self, config: BackgroundRemovalConfig | None = None) -> None:
        self.config = config or BackgroundRemovalConfig()

    def remove_background(self, image: Image.Image) -> Image.Image:
        logger.debug("Running grabCut background removal")
        np_img = np.array(image.convert("RGB"))
        height, width = np_img.shape[:2]
        mask = np.zeros((height, width), np.uint8)
        rect_width = max(width - 2, 1)
        rect_height = max(height - 2, 1)
        rect = (1, 1, rect_width, rect_height)
        bgd_model = np.zeros((1, 65), np.float64)
        fgd_model = np.zeros((1, 65), np.float64)
        cv2.grabCut(np_img, mask, rect, bgd_model, fgd_model, self.config.iterations, cv2.GC_INIT_WITH_RECT)
        mask2 = np.where((mask == cv2.GC_FGD) | (mask == cv2.GC_PR_FGD), 1, 0).astype("uint8")
        if self.config.dilation_iterations > 0:
            kernel = np.ones((3, 3), np.uint8)
            mask2 = cv2.dilate(mask2, kernel, iterations=self.config.dilation_iterations)
            mask2 = np.clip(mask2, 0, 1)
        foreground = np_img * mask2[:, :, np.newaxis]
        alpha = (mask2 * 255).astype(np.uint8)
        rgba = np.dstack((foreground, alpha))
        return Image.fromarray(rgba, "RGBA")


class ResolutionEnhancer:
    def __init__(self, config: EnhancementConfig | None = None) -> None:
        self.config = config or EnhancementConfig()

    def enhance(self, image: Image.Image) -> Image.Image:
        logger.debug("Upscaling image with factor %s", self.config.upscale_factor)
        if self.config.upscale_factor <= 1.0:
            return image

        width, height = image.size
        target_width = min(int(width * self.config.upscale_factor), self.config.max_size)
        target_height = min(int(height * self.config.upscale_factor), self.config.max_size)
        enhanced = image.resize((target_width, target_height), Image.Resampling.LANCZOS)
        return enhanced


class ImageProcessingPipeline:
    def __init__(
        self,
        downloader: ImageDownloader,
        remover: BackgroundRemover | None = None,
        enhancer: ResolutionEnhancer | None = None,
        output_dir: Path | None = None,
    ) -> None:
        self.downloader = downloader
        self.remover = remover or BackgroundRemover()
        self.enhancer = enhancer or ResolutionEnhancer()
        self.output_dir = output_dir
        if output_dir is not None:
            output_dir.mkdir(parents=True, exist_ok=True)

    def process_assets(self, assets: Iterable[ProductAsset]) -> List[ProcessedImage]:
        processed: List[ProcessedImage] = []
        for asset, image in self.downloader.bulk_download(assets):
            logger.info("Processing asset %s", asset.id)
            no_bg = self.remover.remove_background(image)
            enhanced = self.enhancer.enhance(no_bg)
            path = self._store_image(asset, enhanced)
            processed.append(ProcessedImage(asset=asset, path=path))
        return processed

    def _store_image(self, asset: ProductAsset, image: Image.Image) -> Path:
        if self.output_dir is None:
            raise RuntimeError("output_dir must be set to store processed images")
        filename = f"{asset.id}.png"
        target = self.output_dir / filename
        image.save(target)
        return target

from __future__ import annotations

import argparse
import logging
from pathlib import Path

from ..douyin.product_parser import DouyinProductParser
from ..image_processing.pipeline import EnhancementConfig, ImageProcessingPipeline, ResolutionEnhancer
from ..media.downloader import ImageDownloader


logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Process Douyin product images")
    parser.add_argument("url", help="Douyin product share URL")
    parser.add_argument("--output", type=Path, default=Path("output"), help="Directory to store processed images")
    parser.add_argument("--cache", type=Path, default=None, help="Optional cache directory for original assets")
    parser.add_argument("--upscale", type=float, default=2.0, help="Upscale factor for enhanced images")
    parser.add_argument(
        "--max-size", type=int, default=2048, help="Maximum dimension (px) for processed images"
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    product_parser = DouyinProductParser()
    downloader = ImageDownloader(cache_dir=args.cache)
    enhancer = ResolutionEnhancer(EnhancementConfig(upscale_factor=args.upscale, max_size=args.max_size))
    pipeline = ImageProcessingPipeline(
        downloader=downloader,
        output_dir=args.output,
        enhancer=enhancer,
    )

    logger.info("Fetching product assets from %s", args.url)
    assets = product_parser.fetch_product_assets(args.url)
    logger.info("Retrieved %s assets", len(assets))
    processed = pipeline.process_assets(assets)
    for item in processed:
        logger.info("Stored processed image at %s", item.path)


if __name__ == "__main__":
    main()

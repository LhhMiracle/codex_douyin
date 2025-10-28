from __future__ import annotations

import argparse
import logging
import os
from pathlib import Path
from typing import Optional

from ..douyin.product_parser import DouyinProductParser, ParsedProductInput
from ..image_processing.pipeline import EnhancementConfig, ImageProcessingPipeline, ResolutionEnhancer
from ..media.downloader import ImageDownloader


logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Process Douyin product images")
    parser.add_argument(
        "input",
        help="Douyin product share input (supports long links, short links, or share text)",
    )
    parser.add_argument(
        "--output", type=Path, default=Path("output"), help="Directory to store processed images"
    )
    parser.add_argument(
        "--cache", type=Path, default=None, help="Optional cache directory for original assets"
    )
    parser.add_argument("--upscale", type=float, default=2.0, help="Upscale factor for enhanced images")
    parser.add_argument(
        "--max-size", type=int, default=2048, help="Maximum dimension (px) for processed images"
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Only parse the input without downloading or processing images",
    )
    parser.add_argument(
        "--cookies",
        default=None,
        help="Optional raw Cookie header value for authenticated HTML fallback",
    )
    return parser.parse_args()


def _initialize_pipeline(
    args: argparse.Namespace,
) -> tuple[ImageProcessingPipeline, DouyinProductParser, ParsedProductInput]:
    product_parser = DouyinProductParser()
    cookies = _load_cookies(args.cookies)
    parsed_input = product_parser.parse_input_to_product(args.input, cookies=cookies)

    if args.dry_run:
        logger.info(
            "Dry run complete: product_id=%s, final_url=%s",
            parsed_input.product_id,
            parsed_input.final_url,
        )
        raise SystemExit(0)

    downloader = ImageDownloader(cache_dir=args.cache)
    enhancer = ResolutionEnhancer(EnhancementConfig(upscale_factor=args.upscale, max_size=args.max_size))
    pipeline = ImageProcessingPipeline(
        downloader=downloader,
        output_dir=args.output,
        enhancer=enhancer,
    )
    return pipeline, product_parser, parsed_input


def _load_cookies(explicit: str | None) -> Optional[str]:
    if explicit:
        value = explicit.strip()
        return value or None

    env_value = os.getenv("DY_COOKIES")
    if env_value:
        value = env_value.strip()
        if value:
            return value

    env_path = Path(".env")
    if not env_path.exists():
        return None

    try:
        for line in env_path.read_text(encoding="utf-8").splitlines():
            stripped = line.strip()
            if not stripped or stripped.startswith("#"):
                continue
            if "=" not in stripped:
                continue
            key, raw_value = stripped.split("=", 1)
            if key.strip() == "DY_COOKIES":
                value = raw_value.strip().strip('"').strip("'")
                return value or None
    except OSError:
        logger.debug("Unable to read .env file for DY_COOKIES", exc_info=True)
    return None


def main() -> None:
    args = parse_args()
    try:
        pipeline, parser, parsed_input = _initialize_pipeline(args)
    except ValueError as exc:
        logger.error("Input parsing failed: %s", exc)
        raise SystemExit(1) from exc

    logger.info("Fetching product assets for product_id=%s", parsed_input.product_id)
    try:
        assets = parser.fetch_product_assets_from_parsed(parsed_input)
    except Exception as exc:  # pragma: no cover - network/HTTP errors
        logger.error("Failed to fetch product assets: %s", exc)
        raise SystemExit(2) from exc

    logger.info("Retrieved %s assets", len(assets))
    processed = pipeline.process_assets(assets)
    for item in processed:
        logger.info("Stored processed image at %s", item.path)


if __name__ == "__main__":
    main()

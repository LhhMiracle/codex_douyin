from __future__ import annotations

from pathlib import Path
from typing import Iterable

from PIL import Image

from codex_douyin.image_processing.pipeline import ImageProcessingPipeline
from codex_douyin.media.downloader import ImageDownloader
from codex_douyin.models import ProductAsset


class FakeDownloader(ImageDownloader):
    def __init__(self, image: Image.Image) -> None:
        self._image = image

    def download(self, asset: ProductAsset) -> Image.Image:  # type: ignore[override]
        return self._image

    def bulk_download(self, assets: Iterable[ProductAsset]):
        for asset in assets:
            yield asset, self._image


def test_pipeline_removes_background(tmp_path: Path) -> None:
    width, height = 200, 200
    image = Image.new("RGB", (width, height), "white")
    for x in range(60, 140):
        for y in range(60, 140):
            image.putpixel((x, y), (255, 0, 0))

    asset = ProductAsset(id="1", url="http://example.com/image.png")
    pipeline = ImageProcessingPipeline(
        downloader=FakeDownloader(image),
        output_dir=tmp_path,
    )

    processed = pipeline.process_assets([asset])
    assert len(processed) == 1
    output = Image.open(processed[0].path)
    assert output.mode == "RGBA"
    assert output.getpixel((10, 10))[3] == 0
    assert output.getpixel((100, 100))[3] == 255

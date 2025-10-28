from __future__ import annotations

import pytest

from codex_douyin.douyin.product_parser import DouyinProductParser


@pytest.mark.parametrize(
    "url, expected",
    [
        ("https://www.douyin.com/product/1234567890123456789?foo=bar", "1234567890123456789"),
        ("https://www.douyin.com/goods/9876543210987654321", "9876543210987654321"),
        ("https://haohuo.jinritemai.com/ecommerce/product/item/112233445566", "112233445566"),
        ("https://example.com?product_id=998877", "998877"),
        (
            "https://haohuo.snssdk.com/views/product/index.html?id=55667788",
            "55667788",
        ),
    ],
)
def test_extract_product_id(url: str, expected: str) -> None:
    parser = DouyinProductParser()
    assert parser._extract_product_id(url) == expected


def test_extract_images_from_payload() -> None:
    parser = DouyinProductParser()
    payload = {
        "product": {
            "images": [
                {"id": "1", "url": "https://example.com/1.png", "width": 800, "height": 600},
                {"id": "2", "url_list": ["https://example.com/2a.png", "https://example.com/2b.png"]},
            ]
        }
    }
    images = list(parser._extract_images(payload))
    assert len(images) == 2
    assert images[0].url == "https://example.com/1.png"
    assert images[1].url == "https://example.com/2a.png"

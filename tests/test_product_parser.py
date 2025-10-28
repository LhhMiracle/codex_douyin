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
        ("https://example.com/detail?goods_id=123456", "123456"),
        ("https://example.com/detail?item_id=654321", "654321"),
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


def test_parse_input_with_share_text_and_short_link(monkeypatch: pytest.MonkeyPatch) -> None:
    parser = DouyinProductParser()
    final_url = "https://haohuo.jinritemai.com/ecommerce/product/item/778899"

    def fake_resolve(client, url):
        assert url == "https://v.douyin.com/abc123/"
        return final_url

    monkeypatch.setattr(parser, "_resolve_share_link", fake_resolve)

    input_text = "爆款好物 https://v.douyin.com/abc123/，马上开抢！"
    parsed = parser.parse_input_to_product(input_text)

    assert parsed.normalized_url == "https://v.douyin.com/abc123/"
    assert parsed.final_url == final_url
    assert parsed.product_id == "778899"


@pytest.mark.parametrize(
    "input_value, expected_message",
    [
        ("", "non-empty string"),
        ("全是中文，没有链接", "http/https link"),
    ],
)
def test_parse_input_validation_errors(input_value: str, expected_message: str) -> None:
    parser = DouyinProductParser()
    with pytest.raises(ValueError) as excinfo:
        parser.parse_input_to_product(input_value)
    assert expected_message in str(excinfo.value)

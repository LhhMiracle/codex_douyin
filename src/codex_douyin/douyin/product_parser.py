from __future__ import annotations

import json
import logging
import re
from dataclasses import dataclass
from typing import Iterable, List, Optional

import httpx

from ..models import ProductAsset

logger = logging.getLogger(__name__)

_PRODUCT_ID_PATTERNS: tuple[re.Pattern[str], ...] = (
    re.compile(r"product/(\d+)", re.IGNORECASE),
    re.compile(r"goods/(\d+)", re.IGNORECASE),
    re.compile(r"item/(\d+)", re.IGNORECASE),
    re.compile(r"product_id=(\d+)", re.IGNORECASE),
    re.compile(r"index\.html\?id=(\d+)", re.IGNORECASE),
)


@dataclass(slots=True)
class DouyinProductParser:
    """Fetches product metadata (especially image assets) from Douyin."""

    timeout: float = 15.0
    user_agent: str = (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36"
    )

    def fetch_product_assets(self, url: str) -> List[ProductAsset]:
        """Resolve *url* and return the list of product image assets."""

        with httpx.Client(follow_redirects=True, timeout=self.timeout) as client:
            final_url = self._resolve_share_link(client, url)
            product_id = self._extract_product_id(final_url)
            if product_id is None:
                raise ValueError("Unable to determine product id from URL")

            logger.debug("Resolved product id %s from %s", product_id, final_url)
            payload = self._fetch_product_payload(client, product_id)

        images = list(self._extract_images(payload))
        if not images:
            raise ValueError("No images detected in Douyin response")
        return images

    def _resolve_share_link(self, client: httpx.Client, url: str) -> str:
        logger.debug("Resolving Douyin share link: %s", url)
        response = client.get(url, headers={"User-Agent": self.user_agent})
        response.raise_for_status()
        final_url = str(response.url)
        logger.debug("Final resolved URL: %s", final_url)
        return final_url

    def _extract_product_id(self, url: str) -> Optional[str]:
        for pattern in _PRODUCT_ID_PATTERNS:
            match = pattern.search(url)
            if match:
                return match.group(1)
        return None

    def _fetch_product_payload(self, client: httpx.Client, product_id: str) -> dict:
        endpoints = (
            "https://www.douyin.com/aweme/v1/web/product/detail/",
            "https://ec.snssdk.com/product/goods/detail/v2",
        )

        headers = {"User-Agent": self.user_agent, "Referer": "https://www.douyin.com/"}
        params_variants = (
            {"product_id": product_id},
            {"product_id": product_id, "scene": "detail"},
        )

        last_error: Optional[Exception] = None
        for endpoint in endpoints:
            for params in params_variants:
                try:
                    response = client.get(endpoint, params=params, headers=headers)
                    response.raise_for_status()
                    data = response.json()
                    logger.debug(
                        "Received response from %s with keys: %s", endpoint, list(data.keys())
                    )
                    return data
                except httpx.HTTPStatusError as exc:
                    logger.warning("Douyin endpoint %s returned status %s", endpoint, exc.response.status_code)
                    last_error = exc
                except json.JSONDecodeError as exc:
                    logger.warning("Unable to decode JSON from %s: %s", endpoint, exc)
                    last_error = exc
                except httpx.HTTPError as exc:
                    logger.warning("HTTP error while calling %s: %s", endpoint, exc)
                    last_error = exc
        if last_error:
            raise RuntimeError("Unable to fetch Douyin product detail") from last_error
        raise RuntimeError("Unable to fetch Douyin product detail")

    def _extract_images(self, payload: dict) -> Iterable[ProductAsset]:
        """Extract image metadata from any known payload schema."""

        candidate_lists = []
        if isinstance(payload, dict):
            if "product" in payload:
                product = payload["product"]
                if isinstance(product, dict):
                    candidate_lists.append(product.get("image") or product.get("images"))
            if "data" in payload:
                data = payload["data"]
                if isinstance(data, dict):
                    candidate_lists.append(data.get("images") or data.get("image_list"))
            if "image_list" in payload:
                candidate_lists.append(payload.get("image_list"))

        for images in candidate_lists:
            if not images:
                continue
            for index, item in enumerate(images):
                if not isinstance(item, (dict, str)):
                    continue
                if isinstance(item, str):
                    url = item
                    width = height = fmt = None
                else:
                    url = item.get("url") or item.get("origin_url") or item.get("image_url")
                    if not url and "url_list" in item:
                        url_list = item.get("url_list") or []
                        url = next((u for u in url_list if isinstance(u, str)), None)
                    width = item.get("width")
                    height = item.get("height")
                    fmt = item.get("format") or item.get("file_type")
                if not url:
                    continue
                asset_id = item.get("id") if isinstance(item, dict) else f"{index}"
                yield ProductAsset(
                    id=str(asset_id or index),
                    url=url,
                    width=width if isinstance(width, int) else None,
                    height=height if isinstance(height, int) else None,
                    format=fmt if isinstance(fmt, str) else None,
                )

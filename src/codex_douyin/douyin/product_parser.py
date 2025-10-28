from __future__ import annotations

import json
import logging
import re
from dataclasses import dataclass
from typing import Iterable, List, Optional
from urllib.parse import parse_qs, urlparse

import httpx

from ..models import ProductAsset

logger = logging.getLogger(__name__)

_PRODUCT_ID_PATTERNS: tuple[re.Pattern[str], ...] = (
    re.compile(r"product/(\d+)", re.IGNORECASE),
    re.compile(r"goods/(\d+)", re.IGNORECASE),
    re.compile(r"item/(\d+)", re.IGNORECASE),
    re.compile(r"product_id=(\d+)", re.IGNORECASE),
    re.compile(r"goods_id=(\d+)", re.IGNORECASE),
    re.compile(r"item_id=(\d+)", re.IGNORECASE),
)

_PRODUCT_ID_HTML_PATTERNS: tuple[re.Pattern[str], ...] = (
    re.compile(r'"product_id"\s*:\s*"(\d+)"', re.IGNORECASE),
    re.compile(r'"productId"\s*:\s*"(\d+)"', re.IGNORECASE),
    re.compile(r'data-product-id="(\d+)"', re.IGNORECASE),
    re.compile(r'"goods_id"\s*:\s*"(\d+)"', re.IGNORECASE),
)

_URL_PATTERN = re.compile(r"https?://[^\s]+", re.IGNORECASE)
_TRAILING_PUNCTUATION = "\u3002\uff01\uff1f\uff1b\uff0c\uff1a\u3001\u300b\u300d\u3011\uff09\u201d\u2019" + ".,!?;:)]>\"'"


@dataclass(frozen=True, slots=True)
class ParsedProductInput:
    original: str
    normalized_url: str
    final_url: str
    product_id: str


@dataclass(slots=True)
class DouyinProductParser:
    """Fetches product metadata (especially image assets) from Douyin."""

    timeout: float = 15.0
    user_agent: str = (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36"
    )

    def fetch_product_assets(
        self, input_value: str, *, cookies: Optional[str] = None
    ) -> List[ProductAsset]:
        """Resolve *input_value* and return the list of product image assets."""

        if not isinstance(input_value, str) or not input_value.strip():
            raise ValueError("Input must be a non-empty string containing a Douyin link")

        normalized = input_value.strip()
        if normalized.isdigit():
            parsed = ParsedProductInput(
                original=normalized,
                normalized_url="",
                final_url="",
                product_id=normalized,
            )
        else:
            parsed = self.parse_input_to_product(normalized, cookies=cookies)
        return self.fetch_product_assets_from_parsed(parsed)

    def fetch_product_assets_from_parsed(self, parsed_input: ParsedProductInput) -> List[ProductAsset]:
        with httpx.Client(follow_redirects=True, timeout=self.timeout) as client:
            payload = self._fetch_product_payload(client, parsed_input.product_id)

        images = list(self._extract_images(payload))
        if not images:
            raise ValueError("No images detected in Douyin response")
        return images

    def parse_input_to_product(
        self,
        raw_input: str,
        *,
        client: Optional[httpx.Client] = None,
        cookies: Optional[str] = None,
    ) -> ParsedProductInput:
        if not isinstance(raw_input, str) or not raw_input.strip():
            raise ValueError("Input must be a non-empty string containing a Douyin link")

        match = _URL_PATTERN.search(raw_input)
        if not match:
            raise ValueError("Unable to locate a http/https link within the provided input")

        candidate_url = match.group(0)
        normalized_url = self._normalize_url(candidate_url)
        if not normalized_url:
            raise ValueError("Unable to normalize extracted URL from input")
        logger.info("normalize: %s", normalized_url)

        should_close = False
        if client is None:
            client = httpx.Client(follow_redirects=True, timeout=self.timeout)
            should_close = True

        try:
            if self._is_short_link(normalized_url):
                final_url = self._resolve_share_link(client, normalized_url)
            else:
                final_url = normalized_url

            if final_url != normalized_url:
                logger.info("resolve: %s -> %s", normalized_url, final_url)
            else:
                logger.info("resolve: %s", final_url)

            product_id, source, effective_url = self._determine_product_id(
                client, final_url or "", cookies=cookies
            )
            final_url = effective_url or final_url
            logger.info("parse: product_id=%s (source=%s)", product_id, source)
            return ParsedProductInput(
                original=raw_input,
                normalized_url=normalized_url,
                final_url=final_url,
                product_id=product_id,
            )
        finally:
            if should_close:
                client.close()

    def _resolve_share_link(self, client: httpx.Client, url: str) -> str:
        logger.debug("Resolving Douyin share link: %s", url)
        response = client.get(url, headers={"User-Agent": self.user_agent})
        response.raise_for_status()
        final_url = str(response.url)
        logger.debug("Final resolved URL: %s", final_url)
        return final_url

    def _normalize_url(self, url: str) -> str:
        normalized = url.strip().strip("\"'“”‘’")
        normalized = normalized.rstrip(_TRAILING_PUNCTUATION)
        return normalized

    def _is_short_link(self, url: str) -> bool:
        parsed = urlparse(url)
        hostname = (parsed.netloc or "").lower()
        return hostname.endswith("v.douyin.com")

    def _extract_product_id(self, url: str) -> Optional[str]:
        for pattern in _PRODUCT_ID_PATTERNS:
            match = pattern.search(url)
            if match:
                return match.group(1)
        return None

    def _extract_product_id_from_query(self, url: str) -> Optional[str]:
        parsed = urlparse(url)
        query_params = parse_qs(parsed.query)
        if not query_params:
            return None
        for key in ("product_id", "goods_id", "item_id", "id"):
            for actual_key, values in query_params.items():
                if actual_key.lower() == key:
                    for value in values:
                        if value and value.isdigit():
                            return value
        return None

    def _extract_product_id_from_html(self, html: str) -> Optional[str]:
        for pattern in _PRODUCT_ID_HTML_PATTERNS:
            match = pattern.search(html)
            if match:
                return match.group(1)
        return None

    def _determine_product_id(
        self,
        client: httpx.Client,
        final_url: str,
        *,
        cookies: Optional[str] = None,
    ) -> tuple[str, str, str]:
        product_id = self._extract_product_id_from_query(final_url)
        if product_id:
            return product_id, "query", final_url

        product_id = self._extract_product_id(final_url)
        if product_id:
            return product_id, "url", final_url

        html, resolved_url = self._fetch_final_url_html(client, final_url, cookies)
        if resolved_url and resolved_url != final_url:
            logger.info("resolve: %s -> %s", final_url, resolved_url)
            final_url = resolved_url

        product_id = self._extract_product_id_from_query(final_url)
        if product_id:
            return product_id, "query", final_url

        product_id = self._extract_product_id(final_url)
        if product_id:
            return product_id, "url", final_url

        product_id = self._extract_product_id_from_html(html)
        if product_id:
            return product_id, "html", final_url

        snippet = self._format_html_snippet(html)
        raise ValueError(
            "Unable to determine product id from URL: %s\nHTML snippet: %s" % (final_url, snippet)
        )

    def _fetch_final_url_html(
        self, client: httpx.Client, url: str, cookies: Optional[str]
    ) -> tuple[str, str]:
        headers = {"User-Agent": self.user_agent}
        if cookies:
            headers["Cookie"] = cookies
        response = client.get(url, headers=headers)
        response.raise_for_status()
        return response.text, str(response.url)

    def _format_html_snippet(self, html: str) -> str:
        snippet = html[:300]
        snippet = re.sub(r"\s+", " ", snippet)
        return snippet.strip()

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

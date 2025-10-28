from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Optional


@dataclass(slots=True)
class ProductAsset:
    """Metadata describing an image asset attached to a Douyin product."""

    id: str
    url: str
    width: Optional[int] = None
    height: Optional[int] = None
    format: Optional[str] = None


@dataclass(slots=True)
class ProcessedImage:
    """Container for a processed (background-free, enhanced) image."""

    asset: ProductAsset
    path: Path

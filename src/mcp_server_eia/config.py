"""Environment configuration (no framework dependencies)."""

from __future__ import annotations

import os
from dataclasses import dataclass


@dataclass(frozen=True)
class Settings:
    eia_api_key: str
    eia_aeo_release: str = "2025"


def load_settings() -> Settings:
    key = (os.environ.get("EIA_API_KEY") or "").strip()
    release = (os.environ.get("EIA_AEO_RELEASE") or "2025").strip()
    return Settings(eia_api_key=key, eia_aeo_release=release)

"""Common configuration utilities and helpers for FoodFlow services."""

from __future__ import annotations

import os
from pathlib import Path
from typing import Optional
from urllib.parse import urlparse, urlunparse


def load_env_file() -> None:
    """Load key-value pairs from .env in the project root if not already set in environment."""
    root_dir = Path(__file__).resolve().parent.parent.parent
    env_path = root_dir / ".env"
    if env_path.exists():
        try:
            with open(env_path, "r", encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if line and not line.startswith("#") and "=" in line:
                        key, val = line.split("=", 1)
                        key = key.strip()
                        val = val.strip().strip("'\"")
                        if key and key not in os.environ:
                            os.environ[key] = val
        except Exception:
            pass


def mask_database_url(url: Optional[str]) -> str:
    """Mask credentials in database URL for safe logging and status reporting."""
    if not url:
        return "<NOT_SET>"
    try:
        parsed = urlparse(url)
        if not parsed.scheme:
            return "<INVALID_URL>"
        if parsed.password:
            netloc = f"{parsed.username}:********@{parsed.hostname}"
            if parsed.port:
                netloc += f":{parsed.port}"
        elif parsed.username:
            netloc = f"{parsed.username}@{parsed.hostname}"
            if parsed.port:
                netloc += f":{parsed.port}"
        else:
            netloc = parsed.netloc
        return urlunparse((parsed.scheme, netloc, parsed.path, parsed.params, parsed.query, parsed.fragment))
    except Exception:
        return "<MASKED_URL>"


class ConfigurationError(Exception):
    """Raised when service configuration validation fails."""
    pass


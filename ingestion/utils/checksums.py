"""FoodFlow Ingestion Checksum Utilities

Provides memory-bounded streaming SHA-256 calculation and file integrity verification.
"""

from __future__ import annotations

import hashlib
from pathlib import Path
from typing import Tuple


DEFAULT_CHUNK_SIZE = 1024 * 1024  # 1 MB chunk size for streaming


def compute_file_sha256(file_path: Path, chunk_size: int = DEFAULT_CHUNK_SIZE) -> str:
    """Compute the SHA-256 hexadecimal hash of a file using chunked streaming.
    
    Ensures bounded memory consumption regardless of file size (e.g. 1.8 GB RecipeNLG).
    """
    hasher = hashlib.sha256()
    with open(file_path, "rb") as f:
        while chunk := f.read(chunk_size):
            hasher.update(chunk)
    return hasher.hexdigest().lower()


def compute_bytes_sha256(data: bytes) -> str:
    """Compute SHA-256 of in-memory bytes."""
    return hashlib.sha256(data).hexdigest().lower()


def verify_file_sha256(file_path: Path, expected_sha256: str) -> bool:
    """Verify whether a file's actual SHA-256 matches the expected hash.
    
    Performs case-insensitive comparison.
    """
    if not file_path.exists() or not file_path.is_file():
        return False
    actual = compute_file_sha256(file_path)
    return actual == expected_sha256.strip().lower()


def get_file_metadata(file_path: Path) -> Tuple[int, str]:
    """Return a tuple of (file_size_in_bytes, sha256_hexdigest) for a file."""
    if not file_path.exists() or not file_path.is_file():
        raise FileNotFoundError(f"File not found: {file_path}")
    size_bytes = file_path.stat().st_size
    sha256_hash = compute_file_sha256(file_path)
    return size_bytes, sha256_hash


def format_bytes(size_bytes: int) -> str:
    """Format byte counts into human-readable strings (B, KB, MB, GB, TB)."""
    if size_bytes < 0:
        return f"{size_bytes} B"
    for unit in ["B", "KB", "MB", "GB", "TB"]:
        if size_bytes < 1024.0:
            return f"{size_bytes:.2f} {unit}" if unit != "B" else f"{size_bytes} B"
        size_bytes /= 1024.0
    return f"{size_bytes:.2f} PB"


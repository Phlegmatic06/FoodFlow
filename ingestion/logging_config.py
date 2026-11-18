"""NutriPod Ingestion Logging Configuration

Provides structured logging to stdout and persistent audit logs in data/reports/.
Includes specialized helpers for tracking malformed and rejected records.
"""

from __future__ import annotations

import logging
import sys
from pathlib import Path
from typing import Optional

from ingestion.config import REPORTS_DIR


_CONFIGURED = False


def setup_logging(
    level: int = logging.INFO,
    log_file: Optional[Path] = None,
    log_to_file: bool = True,
) -> None:
    """Initialize root logging configuration for the ingestion framework."""
    global _CONFIGURED
    if _CONFIGURED:
        return

    root_logger = logging.getLogger("foodflow.ingestion")
    root_logger.setLevel(level)

    # Console handler
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(level)
    console_format = logging.Formatter(
        fmt="%(asctime)s [%(levelname)-7s] %(name)s: %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )
    console_handler.setFormatter(console_format)
    root_logger.addHandler(console_handler)

    # File handler
    if log_to_file:
        try:
            REPORTS_DIR.mkdir(parents=True, exist_ok=True)
            target_file = log_file or (REPORTS_DIR / "ingestion.log")
            file_handler = logging.FileHandler(target_file, encoding="utf-8")
            file_handler.setLevel(logging.DEBUG)
            file_format = logging.Formatter(
                fmt="%(asctime)s [%(levelname)-7s] %(process)d %(name)s:%(lineno)d: %(message)s",
                datefmt="%Y-%m-%d %H:%M:%S",
            )
            file_handler.setFormatter(file_format)
            root_logger.addHandler(file_handler)
        except OSError:
            # If filesystem is read-only or reports dir is inaccessible, proceed with console only
            pass

    _CONFIGURED = True


def get_logger(name: str) -> logging.Logger:
    """Return a scoped logger under the foodflow.ingestion namespace."""
    if not _CONFIGURED:
        setup_logging()
    return logging.getLogger(f"foodflow.ingestion.{name}")


def log_rejected_row(
    logger: logging.Logger,
    dataset: str,
    file_name: str,
    line_number: int,
    reason: str,
    raw_sample: Optional[str] = None,
) -> None:
    """Log a malformed or rejected dataset record with line number and reason."""
    msg = f"[{dataset.upper()}] Rejected row in '{file_name}' at line {line_number}: {reason}"
    if raw_sample:
        # Truncate sample to 200 chars for log readability
        truncated = raw_sample.strip()[:200]
        if len(raw_sample.strip()) > 200:
            truncated += "..."
        msg += f" | Sample: {truncated!r}"
    logger.warning(msg)


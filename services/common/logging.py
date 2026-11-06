"""Structured logging setup with credential masking for FoodFlow services."""

from __future__ import annotations

import logging
import os
import re
from typing import Optional


class CredentialMaskingFilter(logging.Filter):
    """Filter that masks connection strings containing passwords in log messages."""

    # Matches postgresql://user:password@host
    _URL_PATTERN = re.compile(r"(postgres(?:ql)?://[^:]+:)([^@]+)(@[^\s]+)")

    def filter(self, record: logging.LogRecord) -> bool:
        if isinstance(record.msg, str):
            record.msg = self._URL_PATTERN.sub(r"\1********\3", record.msg)
        if record.args:
            args_list = list(record.args) if isinstance(record.args, tuple) else record.args
            if isinstance(args_list, list):
                for i, arg in enumerate(args_list):
                    if isinstance(arg, str):
                        args_list[i] = self._URL_PATTERN.sub(r"\1********\3", arg)
                record.args = tuple(args_list) if isinstance(record.args, tuple) else args_list
        return True


def setup_service_logger(service_name: str, level: Optional[str] = None) -> logging.Logger:
    """Configure and return a structured logger for a FoodFlow service."""
    log_level = (level or os.getenv("LOG_LEVEL", "INFO")).upper()
    logger = logging.getLogger(f"foodflow.{service_name}")
    logger.setLevel(getattr(logging, log_level, logging.INFO))

    if not logger.handlers:
        handler = logging.StreamHandler()
        handler.setLevel(getattr(logging, log_level, logging.INFO))
        formatter = logging.Formatter(
            fmt="%(asctime)s [%(levelname)-7s] %(name)s: %(message)s",
            datefmt="%Y-%m-%d %H:%M:%S",
        )
        handler.setFormatter(formatter)
        handler.addFilter(CredentialMaskingFilter())
        logger.addHandler(handler)

    logger.propagate = False
    return logger


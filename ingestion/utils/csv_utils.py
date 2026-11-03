"""FoodFlow Ingestion CSV Streaming & Inspection Utilities

Provides memory-bounded streaming CSV iteration, header inspection,
optional row counting, batch aggregation, and malformed row accounting.
"""

from __future__ import annotations

import csv
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, Generator, Iterable, List, Optional, Sequence, Tuple, TypeVar

from ingestion.config import CSV_FIELD_SIZE_LIMIT


T = TypeVar("T")


def configure_csv_limits() -> None:
    """Set the CSV field size limit to handle large recipe instruction and ingredient fields."""
    try:
        csv.field_size_limit(CSV_FIELD_SIZE_LIMIT)
    except (OverflowError, TypeError):
        # Fallback for systems where sys.maxsize exceeds C long range
        csv.field_size_limit(131072 * 16)


# Apply limit on module import
configure_csv_limits()


def inspect_csv_header(file_path: Path, encoding: str = "utf-8") -> List[str]:
    """Inspect and return the CSV header row without reading the rest of the file."""
    if not file_path.exists() or not file_path.is_file():
        raise FileNotFoundError(f"CSV file not found: {file_path}")

    with open(file_path, "r", encoding=encoding, errors="replace", newline="") as f:
        reader = csv.reader(f)
        for row in reader:
            if row:
                return [col.strip() for col in row]
    return []


def count_csv_rows(
    file_path: Path,
    encoding: str = "utf-8",
    has_header: bool = True,
    chunk_size: int = 1024 * 1024,
) -> int:
    """Count the number of data rows in a CSV file using streaming line-breaks.
    
    This function streams the file in binary chunks to avoid loading millions
    of lines into memory. If has_header is True, 1 is subtracted for the header row.
    """
    if not file_path.exists() or not file_path.is_file():
        raise FileNotFoundError(f"CSV file not found: {file_path}")

    line_count = 0
    with open(file_path, "rb") as f:
        while chunk := f.read(chunk_size):
            line_count += chunk.count(b"\n")

    if has_header and line_count > 0:
        return line_count - 1
    return line_count


def stream_csv_dict(
    file_path: Path,
    encoding: str = "utf-8",
) -> Generator[Tuple[int, Dict[str, str]], None, None]:
    """Stream a CSV file row-by-row as dictionaries, yielding (line_number, row_dict).
    
    Line number corresponds to the 1-based CSV line number (starting at 2 for the first data row).
    Uses lazy generation so peak memory consumption remains O(1) row.
    """
    if not file_path.exists() or not file_path.is_file():
        raise FileNotFoundError(f"CSV file not found: {file_path}")

    with open(file_path, "r", encoding=encoding, errors="replace", newline="") as f:
        reader = csv.DictReader(f)
        line_num = 1  # 1 is the header row
        for row in reader:
            line_num += 1
            yield line_num, row


def stream_csv_raw(
    file_path: Path,
    encoding: str = "utf-8",
) -> Generator[Tuple[int, List[str]], None, None]:
    """Stream a CSV file row-by-row as raw string lists, yielding (line_number, row_list)."""
    if not file_path.exists() or not file_path.is_file():
        raise FileNotFoundError(f"CSV file not found: {file_path}")

    with open(file_path, "r", encoding=encoding, errors="replace", newline="") as f:
        reader = csv.reader(f)
        line_num = 0
        for row in reader:
            line_num += 1
            yield line_num, row


def batch_iterator(
    iterable: Iterable[T],
    batch_size: int = 1000,
) -> Generator[List[T], None, None]:
    """Group an input stream or generator into discrete lists of up to batch_size elements.
    
    Ensures memory-bounded processing for bulk inserts and transactions.
    """
    if batch_size <= 0:
        raise ValueError(f"batch_size must be positive, got {batch_size}")

    batch: List[T] = []
    for item in iterable:
        batch.append(item)
        if len(batch) >= batch_size:
            yield batch
            batch = []
    if batch:
        yield batch


@dataclass
class RowRejection:
    line_number: int
    reason: str
    sample_preview: Optional[str] = None


@dataclass
class IngestionProgressTracker:
    """Tracks processed, accepted, and rejected records during streaming ingestion."""
    dataset_name: str
    file_name: str
    total_read: int = 0
    accepted_count: int = 0
    rejected_count: int = 0
    rejections: List[RowRejection] = field(default_factory=list)
    max_stored_rejections: int = 100  # Cap stored samples to prevent unbounded memory in error cases

    def record_accepted(self) -> None:
        """Mark a row as successfully validated and accepted."""
        self.total_read += 1
        self.accepted_count += 1

    def record_rejected(
        self,
        line_number: int,
        reason: str,
        sample: Optional[str] = None,
    ) -> None:
        """Mark a row as rejected with audit line number and reason."""
        self.total_read += 1
        self.rejected_count += 1
        if len(self.rejections) < self.max_stored_rejections:
            sample_preview = sample[:200] if sample else None
            self.rejections.append(
                RowRejection(
                    line_number=line_number,
                    reason=reason,
                    sample_preview=sample_preview,
                )
            )

    def summary(self) -> Dict[str, Any]:
        """Return a structured summary dictionary of the ingestion run."""
        return {
            "dataset": self.dataset_name,
            "file": self.file_name,
            "total_read": self.total_read,
            "accepted": self.accepted_count,
            "rejected": self.rejected_count,
            "sample_rejections": [
                {"line": r.line_number, "reason": r.reason, "preview": r.sample_preview}
                for r in self.rejections[:10]
            ],
        }


"""NutriPod Unified Sampling Engine - Audit Report Generator

Produces comprehensive JSON audit reports and console summaries documenting
sampling provenance, stratum allocations, rejection rates, output file checksums,
and interaction matching statistics.
"""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional


@dataclass
class OutputFileMetadata:
    filename: str
    relative_path: str
    absolute_path: str
    row_count: int
    size_bytes: int
    sha256_checksum: str


@dataclass
class StratumReportItem:
    stratum_id: str
    source_count: int
    target_quota: int
    selected_count: int
    source_percentage: float
    sample_percentage: float


@dataclass
class SamplingReport:
    """Audit report capturing complete provenance and statistics for a sampling run."""
    dataset: str
    source_path: str
    seed: int
    requested_sample_size: int
    actual_sample_size: int
    source_rows_scanned: int
    valid_rows: int
    rejected_rows: int
    sampling_algorithm: str = "proportional_stratified_reservoir_sampling"
    source_sha256: Optional[str] = None
    source_byte_size: Optional[int] = None
    timestamp: str = field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )
    strata: Dict[str, Dict[str, Any]] = field(default_factory=dict)
    output_files: Dict[str, Dict[str, Any]] = field(default_factory=dict)
    interaction_stats: Optional[Dict[str, Any]] = None
    sample_rejections: List[Dict[str, Any]] = field(default_factory=list)
    dry_run: bool = False

    def to_dict(self) -> Dict[str, Any]:
        """Convert report to dictionary suitable for JSON serialization."""
        return {
            "dataset": self.dataset,
            "source_path": self.source_path,
            "source_sha256": self.source_sha256,
            "source_byte_size": self.source_byte_size,
            "seed": self.seed,
            "requested_sample_size": self.requested_sample_size,
            "actual_sample_size": self.actual_sample_size,
            "source_rows_scanned": self.source_rows_scanned,
            "valid_rows": self.valid_rows,
            "rejected_rows": self.rejected_rows,
            "sampling_algorithm": self.sampling_algorithm,
            "timestamp": self.timestamp,
            "dry_run": self.dry_run,
            "strata": self.strata,
            "output_files": self.output_files,
            "interaction_stats": self.interaction_stats,
            "sample_rejections": self.sample_rejections,
        }

    def save(self, destination_path: Path) -> Path:
        """Write report to destination path as formatted JSON."""
        dest = Path(destination_path).resolve()
        dest.parent.mkdir(parents=True, exist_ok=True)
        with open(dest, "w", encoding="utf-8") as f:
            json.dump(self.to_dict(), f, indent=2, ensure_ascii=False)
        return dest

    def print_summary(self) -> None:
        """Format and print an executive summary to standard output."""
        print("\n" + "=" * 78)
        mode_tag = "[DRY-RUN] " if self.dry_run else ""
        print(f"NUTRIPOD DATASET SAMPLING REPORT: {mode_tag}{self.dataset.upper()}")
        print("=" * 78)
        print(f"Source Path:        {self.source_path}")
        if self.source_sha256:
            print(f"Source SHA256:      {self.source_sha256}")
        if self.source_byte_size is not None:
            print(f"Source Size:        {self.source_byte_size:,} bytes")
        print(f"Random Seed:        {self.seed}")
        print(f"Algorithm:          {self.sampling_algorithm}")
        print(f"Timestamp:          {self.timestamp}")
        print("-" * 78)
        print(f"Rows Scanned:       {self.source_rows_scanned:,}")
        print(f"Valid Rows:         {self.valid_rows:,}")
        print(f"Rejected Rows:      {self.rejected_rows:,}")
        print(f"Requested Sample:   {self.requested_sample_size:,}")
        print(f"Selected Sample:    {self.actual_sample_size:,}")
        print("-" * 78)
        print("STRATUM ALLOCATION BREAKDOWN:")
        print(f"{'Stratum Identifier':<38} {'Source':<10} {'Quota':<10} {'Selected':<10} {'Sample %':<8}")
        print("-" * 78)

        # Sort strata by source count descending
        sorted_strata = sorted(
            self.strata.items(),
            key=lambda item: item[1].get("source_count", 0),
            reverse=True,
        )
        for s_id, s_data in sorted_strata:
            src_cnt = s_data.get("source_count", 0)
            quota = s_data.get("target_quota", 0)
            sel_cnt = s_data.get("selected_count", 0)
            pct = s_data.get("sample_percentage", 0.0)
            print(f"{s_id[:36]:<38} {src_cnt:<10,} {quota:<10,} {sel_cnt:<10,} {pct:>6.2f}%")

        if self.interaction_stats:
            print("-" * 78)
            print("INTERACTION MATCHING & FILTERING (FOOD.COM):")
            scanned = self.interaction_stats.get("interactions_scanned", 0)
            retained = self.interaction_stats.get("interactions_retained", 0)
            unmatched = self.interaction_stats.get("interactions_unmatched", 0)
            unique_recipes = self.interaction_stats.get("recipes_with_interactions", 0)
            print(f"Interactions Scanned:  {scanned:,}")
            print(f"Matching Retained:     {retained:,} (100% referential integrity)")
            print(f"Unmatched Discarded:   {unmatched:,}")
            print(f"Recipes with Reviews:  {unique_recipes:,}")

        if not self.dry_run and self.output_files:
            print("-" * 78)
            print("GENERATED OUTPUT ARTIFACTS:")
            for fname, meta in self.output_files.items():
                print(f"• {fname} ({meta.get('row_count', 0):,} rows, {meta.get('size_bytes', 0):,} bytes)")
                print(f"  SHA256: {meta.get('sha256_checksum', '<none>')}")
                print(f"  Path:   {meta.get('path', '')}")

        print("=" * 78 + "\n")


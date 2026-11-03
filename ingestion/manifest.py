"""FoodFlow Dataset Manifest Management

Maintains a structured, audit-ready manifest of external datasets (USDA, Food.com, RecipeNLG).
Tracks verified file sizes, SHA-256 hashes, provenance metadata, and ingestion outcomes.

Rule: Never invent download dates, row counts, or file checksums.
Fields remain null or unverified until a real operation is executed on disk.
"""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

from ingestion.config import DATASET_REGISTRY, MANIFEST_PATH, DatasetMetadata, resolve_dataset_key


# Status Enum Constants
STATUS_NOT_DOWNLOADED = "not_downloaded"
STATUS_DOWNLOADED = "downloaded"
STATUS_VERIFIED = "verified"
STATUS_PARTIALLY_IMPORTED = "partially_imported"
STATUS_COMPLETED = "completed"
STATUS_FAILED = "failed"

VALID_STATUSES = {
    STATUS_NOT_DOWNLOADED,
    STATUS_DOWNLOADED,
    STATUS_VERIFIED,
    STATUS_PARTIALLY_IMPORTED,
    STATUS_COMPLETED,
    STATUS_FAILED,
}


@dataclass
class FileManifestRecord:
    file_name: str
    size_bytes: Optional[int] = None
    sha256_checksum: Optional[str] = None
    last_modified: Optional[str] = None
    original_row_count: Optional[int] = None


@dataclass
class FailureRecord:
    step: str
    error_message: str
    timestamp: str


@dataclass
class DatasetManifestEntry:
    dataset_id: str
    display_name: str
    official_source_url: str
    target_schema: str
    license_notes: str
    reference_citation: str
    expected_files: List[str]
    source_version: Optional[str] = None
    download_date: Optional[str] = None
    import_status: str = STATUS_NOT_DOWNLOADED
    files: Dict[str, FileManifestRecord] = field(default_factory=dict)
    imported_row_counts: Dict[str, int] = field(default_factory=dict)
    last_successful_ingestion: Optional[str] = None
    failure_record: Optional[FailureRecord] = None
    collections: Dict[str, Dict[str, Any]] = field(default_factory=dict)
    notes: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        """Convert entry to JSON-serializable dictionary."""
        return {
            "dataset_id": self.dataset_id,
            "display_name": self.display_name,
            "official_source_url": self.official_source_url,
            "target_schema": self.target_schema,
            "license_notes": self.license_notes,
            "reference_citation": self.reference_citation,
            "expected_files": self.expected_files,
            "source_version": self.source_version,
            "download_date": self.download_date,
            "import_status": self.import_status,
            "files": {k: asdict(v) for k, v in self.files.items()},
            "imported_row_counts": self.imported_row_counts,
            "last_successful_ingestion": self.last_successful_ingestion,
            "failure_record": asdict(self.failure_record) if self.failure_record else None,
            "collections": self.collections,
            "notes": self.notes,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> DatasetManifestEntry:
        """Construct entry from parsed JSON dictionary."""
        files_dict = {}
        for fname, fmeta in data.get("files", {}).items():
            files_dict[fname] = FileManifestRecord(**fmeta)

        fail_rec = None
        if data.get("failure_record"):
            fail_rec = FailureRecord(**data["failure_record"])

        return cls(
            dataset_id=data["dataset_id"],
            display_name=data["display_name"],
            official_source_url=data["official_source_url"],
            target_schema=data["target_schema"],
            license_notes=data["license_notes"],
            reference_citation=data.get("reference_citation", ""),
            expected_files=data.get("expected_files", []),
            source_version=data.get("source_version"),
            download_date=data.get("download_date"),
            import_status=data.get("import_status", STATUS_NOT_DOWNLOADED),
            files=files_dict,
            imported_row_counts=data.get("imported_row_counts", {}),
            last_successful_ingestion=data.get("last_successful_ingestion"),
            failure_record=fail_rec,
            collections=data.get("collections", {}),
            notes=data.get("notes"),
        )


@dataclass
class Manifest:
    version: str = "1.0.0"
    created_at: str = field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )
    last_updated: str = field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )
    datasets: Dict[str, DatasetManifestEntry] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "version": self.version,
            "created_at": self.created_at,
            "last_updated": self.last_updated,
            "datasets": {k: v.to_dict() for k, v in self.datasets.items()},
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> Manifest:
        datasets = {
            k: DatasetManifestEntry.from_dict(v)
            for k, v in data.get("datasets", {}).items()
        }
        return cls(
            version=data.get("version", "1.0.0"),
            created_at=data.get("created_at", datetime.now(timezone.utc).isoformat()),
            last_updated=data.get("last_updated", datetime.now(timezone.utc).isoformat()),
            datasets=datasets,
        )


def create_initial_manifest() -> Manifest:
    """Create a pristine initial manifest with official metadata and zero fabricated values."""
    manifest = Manifest()
    for key, meta in DATASET_REGISTRY.items():
        collections_dict: Dict[str, Dict[str, Any]] = {}
        if key == "usda":
            collections_dict = {
                "foundation": {
                    "collection_id": "foundation",
                    "display_name": "USDA Foundation Foods",
                    "release_date": "October 2026",
                    "source_url": "https://fdc.nal.usda.gov/download-datasets/",
                    "download_date": None,
                    "import_status": STATUS_NOT_DOWNLOADED,
                    "files": {},
                    "imported_row_counts": {},
                    "rejected_counts": {},
                    "last_successful_ingestion": None,
                    "failure_record": None,
                },
                "sr_legacy": {
                    "collection_id": "sr_legacy",
                    "display_name": "USDA SR Legacy",
                    "release_date": "April 2018",
                    "source_url": "https://fdc.nal.usda.gov/download-datasets/",
                    "download_date": None,
                    "import_status": STATUS_NOT_DOWNLOADED,
                    "files": {},
                    "imported_row_counts": {},
                    "rejected_counts": {},
                    "last_successful_ingestion": None,
                    "failure_record": None,
                },
            }

        manifest.datasets[key] = DatasetManifestEntry(
            dataset_id=meta.identifier,
            display_name=meta.display_name,
            official_source_url=meta.official_source_url,
            target_schema=meta.target_schema,
            license_notes=meta.license_terms,
            reference_citation=meta.reference_citation,
            expected_files=list(meta.expected_files),
            source_version=meta.source_version,
            download_date=None,  # Not downloaded yet
            import_status=STATUS_NOT_DOWNLOADED,
            files={},  # Populated only upon actual verification
            imported_row_counts={},
            last_successful_ingestion=None,
            failure_record=None,
            collections=collections_dict,
            notes=meta.notes,
        )
    return manifest


def load_manifest(path: Optional[Path] = None) -> Manifest:
    """Load the manifest from disk, or initialize and return a pristine manifest if missing."""
    target_path = path or MANIFEST_PATH
    if not target_path.exists():
        manifest = create_initial_manifest()
        save_manifest(manifest, target_path)
        return manifest

    with open(target_path, "r", encoding="utf-8") as f:
        data = json.load(f)
    return Manifest.from_dict(data)


def save_manifest(manifest: Manifest, path: Optional[Path] = None) -> None:
    """Persist the manifest to disk with ISO timestamp updates."""
    target_path = path or MANIFEST_PATH
    target_path.parent.mkdir(parents=True, exist_ok=True)
    manifest.last_updated = datetime.now(timezone.utc).isoformat()
    with open(target_path, "w", encoding="utf-8") as f:
        json.dump(manifest.to_dict(), f, indent=2, ensure_ascii=False)


def record_verified_file(
    dataset_key: str,
    file_name: str,
    size_bytes: int,
    sha256_checksum: str,
    last_modified: Optional[str] = None,
    original_row_count: Optional[int] = None,
    path: Optional[Path] = None,
) -> None:
    """Record verified file metadata in the manifest following a genuine disk inspection."""
    resolved = resolve_dataset_key(dataset_key)
    if not resolved:
        raise ValueError(f"Unknown dataset key: {dataset_key}")

    manifest = load_manifest(path)
    entry = manifest.datasets[resolved]
    entry.files[file_name] = FileManifestRecord(
        file_name=file_name,
        size_bytes=size_bytes,
        sha256_checksum=sha256_checksum,
        last_modified=last_modified,
        original_row_count=original_row_count,
    )

    # Check if all expected files have been verified
    all_present = all(ef in entry.files for ef in entry.expected_files)
    if all_present:
        entry.import_status = STATUS_VERIFIED
    else:
        entry.import_status = STATUS_DOWNLOADED

    save_manifest(manifest, path)


def record_ingestion_success(
    dataset_key: str,
    imported_counts: Dict[str, int],
    path: Optional[Path] = None,
) -> None:
    """Record a completed ingestion operation for a dataset."""
    resolved = resolve_dataset_key(dataset_key)
    if not resolved:
        raise ValueError(f"Unknown dataset key: {dataset_key}")

    manifest = load_manifest(path)
    entry = manifest.datasets[resolved]
    entry.imported_row_counts.update(imported_counts)
    entry.import_status = STATUS_COMPLETED
    entry.last_successful_ingestion = datetime.now(timezone.utc).isoformat()
    entry.failure_record = None
    save_manifest(manifest, path)


def record_ingestion_failure(
    dataset_key: str,
    step: str,
    error_message: str,
    path: Optional[Path] = None,
) -> None:
    """Record an ingestion failure with step and error message."""
    resolved = resolve_dataset_key(dataset_key)
    if not resolved:
        raise ValueError(f"Unknown dataset key: {dataset_key}")

    manifest = load_manifest(path)
    entry = manifest.datasets[resolved]
    entry.import_status = STATUS_FAILED
    entry.failure_record = FailureRecord(
        step=step,
        error_message=error_message,
        timestamp=datetime.now(timezone.utc).isoformat(),
    )
    save_manifest(manifest, path)


def record_collection_file(
    dataset_key: str,
    collection_id: str,
    file_name: str,
    size_bytes: int,
    sha256_checksum: str,
    last_modified: Optional[str] = None,
    original_row_count: Optional[int] = None,
    path: Optional[Path] = None,
) -> None:
    """Record verified file metadata for a specific sub-collection (e.g. USDA Foundation or SR Legacy)."""
    resolved = resolve_dataset_key(dataset_key)
    if not resolved:
        raise ValueError(f"Unknown dataset key: {dataset_key}")

    manifest = load_manifest(path)
    entry = manifest.datasets[resolved]
    colls = entry.collections
    if collection_id not in colls:
        colls[collection_id] = {
            "collection_id": collection_id,
            "import_status": STATUS_NOT_DOWNLOADED,
            "files": {},
            "imported_row_counts": {},
            "rejected_counts": {},
            "last_successful_ingestion": None,
            "failure_record": None,
        }

    colls[collection_id]["files"][file_name] = {
        "file_name": file_name,
        "size_bytes": size_bytes,
        "sha256_checksum": sha256_checksum,
        "last_modified": last_modified,
        "original_row_count": original_row_count,
    }
    colls[collection_id]["import_status"] = STATUS_DOWNLOADED
    save_manifest(manifest, path)


def record_collection_success(
    dataset_key: str,
    collection_id: str,
    imported_counts: Dict[str, int],
    rejected_counts: Optional[Dict[str, int]] = None,
    path: Optional[Path] = None,
) -> None:
    """Record a completed ingestion operation for a sub-collection."""
    resolved = resolve_dataset_key(dataset_key)
    if not resolved:
        raise ValueError(f"Unknown dataset key: {dataset_key}")

    manifest = load_manifest(path)
    entry = manifest.datasets[resolved]
    colls = entry.collections
    if collection_id not in colls:
        colls[collection_id] = {
            "collection_id": collection_id,
            "import_status": STATUS_NOT_DOWNLOADED,
            "files": {},
            "imported_row_counts": {},
            "rejected_counts": {},
            "last_successful_ingestion": None,
            "failure_record": None,
        }

    col = colls[collection_id]
    col["imported_row_counts"] = imported_counts
    col["rejected_counts"] = rejected_counts or {}
    col["import_status"] = STATUS_COMPLETED
    col["last_successful_ingestion"] = datetime.now(timezone.utc).isoformat()
    col["failure_record"] = None

    # Update parent dataset aggregation
    for table_name, count in imported_counts.items():
        entry.imported_row_counts[table_name] = entry.imported_row_counts.get(table_name, 0) + count

    # If all tracked collections are completed, mark parent completed, else partially_imported
    all_completed = (
        len(colls) > 0 and
        all(c.get("import_status") == STATUS_COMPLETED for c in colls.values())
    )
    entry.import_status = STATUS_COMPLETED if all_completed else STATUS_PARTIALLY_IMPORTED
    entry.last_successful_ingestion = datetime.now(timezone.utc).isoformat()
    entry.failure_record = None

    save_manifest(manifest, path)


def record_collection_failure(
    dataset_key: str,
    collection_id: str,
    step: str,
    error_message: str,
    path: Optional[Path] = None,
) -> None:
    """Record an ingestion failure for a sub-collection."""
    resolved = resolve_dataset_key(dataset_key)
    if not resolved:
        raise ValueError(f"Unknown dataset key: {dataset_key}")

    manifest = load_manifest(path)
    entry = manifest.datasets[resolved]
    colls = entry.collections
    if collection_id in colls:
        colls[collection_id]["import_status"] = STATUS_FAILED
        colls[collection_id]["failure_record"] = {
            "step": step,
            "error_message": error_message,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
    entry.import_status = STATUS_FAILED
    entry.failure_record = FailureRecord(
        step=f"{collection_id}:{step}",
        error_message=error_message,
        timestamp=datetime.now(timezone.utc).isoformat(),
    )
    save_manifest(manifest, path)


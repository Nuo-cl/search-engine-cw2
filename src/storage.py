"""Index persistence: save and load from JSON files."""

from __future__ import annotations

import hashlib
import json
import logging
from datetime import datetime, timezone
from pathlib import Path

from src.indexer import Indexer

logger = logging.getLogger(__name__)

DEFAULT_INDEX_PATH = Path("data/index.json")


def _compute_checksum(data: str) -> str:
    return "sha256:" + hashlib.sha256(data.encode("utf-8")).hexdigest()


class StorageError(Exception):
    pass


class Storage:
    def __init__(self, path: Path = DEFAULT_INDEX_PATH) -> None:
        self.path = path

    def save(self, indexer: Indexer) -> None:
        """Save the index to a JSON file with metadata and checksum."""
        index_data = indexer.to_dict()

        payload_str = json.dumps(index_data, ensure_ascii=False, sort_keys=True)
        checksum = _compute_checksum(payload_str)

        output = {
            "metadata": {
                "created_at": datetime.now(timezone.utc).isoformat(),
                "total_pages": indexer.stats.total_pages,
                "total_quotes": indexer.stats.total_quotes,
                "unique_words": indexer.stats.unique_words,
                "unique_authors": indexer.stats.unique_authors,
                "unique_tags": indexer.stats.unique_tags,
                "checksum": checksum,
            },
            **index_data,
        }

        self.path.parent.mkdir(parents=True, exist_ok=True)

        with open(self.path, "w", encoding="utf-8") as f:
            json.dump(output, f, ensure_ascii=False, indent=2)

        file_size = self.path.stat().st_size
        logger.info("Index saved to %s (%.1f KB)", self.path, file_size / 1024)

    def load(self, indexer: Indexer) -> None:
        """Load the index from a JSON file, verifying checksum integrity."""
        if not self.path.exists():
            raise StorageError(f"Index file not found: {self.path}")

        with open(self.path, "r", encoding="utf-8") as f:
            data = json.load(f)

        metadata = data.get("metadata", {})
        stored_checksum = metadata.get("checksum", "")

        index_data = {
            "pages": data.get("pages", {}),
            "index": data.get("index", {}),
            "authors": data.get("authors", {}),
            "tags": data.get("tags", {}),
        }

        payload_str = json.dumps(index_data, ensure_ascii=False, sort_keys=True)
        actual_checksum = _compute_checksum(payload_str)

        if stored_checksum and actual_checksum != stored_checksum:
            raise StorageError(
                "Index file integrity check failed: checksum mismatch. "
                "The file may be corrupted. Please rebuild the index."
            )

        indexer.from_dict(index_data)

        logger.info(
            "Index loaded from %s (built at %s)",
            self.path,
            metadata.get("created_at", "unknown"),
        )

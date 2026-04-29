"""Tests for index persistence (save/load)."""

from __future__ import annotations

import json
import pytest
from pathlib import Path

from src.indexer import Indexer
from src.storage import Storage, StorageError


class TestSaveAndLoad:
    def test_save_creates_file(self, built_indexer, tmp_path):
        path = tmp_path / "index.json"
        storage = Storage(path=path)
        storage.save(built_indexer)
        assert path.exists()
        assert path.stat().st_size > 0

    def test_load_restores_index(self, built_indexer, tmp_path):
        path = tmp_path / "index.json"
        storage = Storage(path=path)
        storage.save(built_indexer)

        new_indexer = Indexer()
        storage.load(new_indexer)

        assert new_indexer.stats.total_pages == built_indexer.stats.total_pages
        assert new_indexer.stats.unique_words == built_indexer.stats.unique_words
        assert new_indexer.stats.unique_authors == built_indexer.stats.unique_authors
        assert new_indexer.stats.unique_tags == built_indexer.stats.unique_tags

    def test_roundtrip_preserves_search(self, built_indexer, tmp_path):
        from src.search import SearchEngine

        path = tmp_path / "index.json"
        storage = Storage(path=path)
        storage.save(built_indexer)

        new_indexer = Indexer()
        storage.load(new_indexer)
        engine = SearchEngine(new_indexer)

        results = engine.find("love")
        assert len(results) > 0

    def test_save_creates_parent_dirs(self, built_indexer, tmp_path):
        path = tmp_path / "subdir" / "nested" / "index.json"
        storage = Storage(path=path)
        storage.save(built_indexer)
        assert path.exists()


class TestMetadata:
    def test_metadata_present(self, built_indexer, tmp_path):
        path = tmp_path / "index.json"
        storage = Storage(path=path)
        storage.save(built_indexer)

        with open(path, "r") as f:
            data = json.load(f)

        meta = data["metadata"]
        assert "created_at" in meta
        assert "checksum" in meta
        assert meta["total_pages"] == built_indexer.stats.total_pages
        assert meta["unique_words"] == built_indexer.stats.unique_words

    def test_checksum_format(self, built_indexer, tmp_path):
        path = tmp_path / "index.json"
        storage = Storage(path=path)
        storage.save(built_indexer)

        with open(path, "r") as f:
            data = json.load(f)

        checksum = data["metadata"]["checksum"]
        assert checksum.startswith("sha256:")
        assert len(checksum) == len("sha256:") + 64


class TestIntegrityCheck:
    def test_corrupted_file_raises(self, built_indexer, tmp_path):
        path = tmp_path / "index.json"
        storage = Storage(path=path)
        storage.save(built_indexer)

        with open(path, "r") as f:
            data = json.load(f)

        data["index"]["love"]["df"] = 9999
        with open(path, "w") as f:
            json.dump(data, f)

        new_indexer = Indexer()
        with pytest.raises(StorageError, match="checksum mismatch"):
            storage.load(new_indexer)

    def test_missing_file_raises(self, tmp_path):
        path = tmp_path / "nonexistent.json"
        storage = Storage(path=path)
        new_indexer = Indexer()

        with pytest.raises(StorageError, match="not found"):
            storage.load(new_indexer)


class TestEmptyIndex:
    def test_save_load_empty(self, tmp_path):
        indexer = Indexer()
        indexer.build([])

        path = tmp_path / "empty.json"
        storage = Storage(path=path)
        storage.save(indexer)

        new_indexer = Indexer()
        storage.load(new_indexer)
        assert new_indexer.stats.total_pages == 0
        assert new_indexer.stats.unique_words == 0

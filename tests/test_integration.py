"""Integration tests: full pipeline from crawl to search."""

from __future__ import annotations

import json
import responses
import pytest
from pathlib import Path

from src.crawler import Crawler
from src.indexer import Indexer
from src.search import SearchEngine
from src.storage import Storage
from src.trie import Trie
from src.spell import SpellChecker
from tests.conftest import SAMPLE_HTML_PAGE1, SAMPLE_HTML_PAGE2

BASE_URL = "https://quotes.toscrape.com/"


class TestFullPipeline:
    """End-to-end: crawl → index → save → load → search."""

    @responses.activate
    def test_crawl_index_save_load_search(self, tmp_path):
        responses.add(responses.GET, BASE_URL, body=SAMPLE_HTML_PAGE1, status=200)
        responses.add(responses.GET, BASE_URL + "page/2/", body=SAMPLE_HTML_PAGE2, status=200)

        # Crawl
        crawler = Crawler(base_url=BASE_URL, politeness_window=0)
        pages = crawler.crawl()
        assert len(pages) == 2

        # Index
        indexer = Indexer()
        indexer.build(pages)
        assert indexer.stats.unique_words > 0

        # Save
        path = tmp_path / "index.json"
        storage = Storage(path=path)
        storage.save(indexer)
        assert path.exists()

        # Load into fresh indexer
        new_indexer = Indexer()
        storage.load(new_indexer)
        assert new_indexer.stats.unique_words == indexer.stats.unique_words

        # Search
        engine = SearchEngine(new_indexer)

        results = engine.find("world")
        assert len(results) > 0

        results = engine.find("love")
        assert len(results) > 0

        results = engine.find("nonexistent")
        assert len(results) == 0

    @responses.activate
    def test_pipeline_with_print(self, tmp_path):
        responses.add(responses.GET, BASE_URL, body=SAMPLE_HTML_PAGE1, status=200)
        responses.add(responses.GET, BASE_URL + "page/2/", body=SAMPLE_HTML_PAGE2, status=200)

        crawler = Crawler(base_url=BASE_URL, politeness_window=0)
        pages = crawler.crawl()

        indexer = Indexer()
        indexer.build(pages)

        engine = SearchEngine(indexer)
        entry = engine.print_entry("world")
        assert entry is not None
        assert entry["df"] > 0

    @responses.activate
    def test_pipeline_with_advanced_queries(self, tmp_path):
        responses.add(responses.GET, BASE_URL, body=SAMPLE_HTML_PAGE1, status=200)
        responses.add(responses.GET, BASE_URL + "page/2/", body=SAMPLE_HTML_PAGE2, status=200)

        crawler = Crawler(base_url=BASE_URL, politeness_window=0)
        pages = crawler.crawl()

        indexer = Indexer()
        indexer.build(pages)
        engine = SearchEngine(indexer)

        # Tag filter
        results = engine.find("--tag love")
        assert len(results) > 0

        # Author filter
        results = engine.find("--author einstein")
        assert len(results) > 0

        # OR query
        results = engine.find("love OR life")
        assert len(results) > 0


class TestTrieIntegration:
    """Test Trie built from a real index."""

    def test_trie_from_built_index(self, built_indexer):
        trie = Trie.from_index(built_indexer.index)

        suggestions = trie.suggest("lo")
        words = [s[0] for s in suggestions]
        assert "love" in words

        suggestions = trie.suggest("fri")
        words = [s[0] for s in suggestions]
        assert any("friend" in w for w in words)

    def test_trie_vocabulary_complete(self, built_indexer):
        trie = Trie.from_index(built_indexer.index)
        for word in built_indexer.get_vocabulary():
            assert trie.search(word), f"{word} not in trie"


class TestSpellIntegration:
    """Test SpellChecker with real vocabulary."""

    def test_spell_from_index_vocabulary(self, built_indexer):
        vocab = built_indexer.get_vocabulary()
        checker = SpellChecker(vocab)

        suggestions = checker.suggest("lovee")
        words = [s[0] for s in suggestions]
        assert "love" in words

    def test_spell_check_all_vocab(self, built_indexer):
        vocab = built_indexer.get_vocabulary()
        checker = SpellChecker(vocab)
        for word in vocab:
            assert checker.check(word), f"{word} should be in vocabulary"


class TestEdgeCasePipeline:
    @responses.activate
    def test_empty_site(self, tmp_path):
        from tests.conftest import SAMPLE_HTML_EMPTY
        responses.add(responses.GET, BASE_URL, body=SAMPLE_HTML_EMPTY, status=200)

        crawler = Crawler(base_url=BASE_URL, politeness_window=0)
        pages = crawler.crawl()

        indexer = Indexer()
        indexer.build(pages)
        assert indexer.stats.total_pages == 1
        assert indexer.stats.total_quotes == 0

        engine = SearchEngine(indexer)
        results = engine.find("anything")
        assert len(results) == 0

    def test_search_before_load(self):
        indexer = Indexer()
        engine = SearchEngine(indexer)
        results = engine.find("love")
        assert len(results) == 0

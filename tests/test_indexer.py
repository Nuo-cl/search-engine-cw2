"""Tests for the inverted index builder."""

from __future__ import annotations

import math
import pytest

from src.crawler import CrawledPage, Quote
from src.indexer import Indexer


class TestTokenize:
    def test_basic(self):
        assert Indexer.tokenize("Hello World") == ["hello", "world"]

    def test_punctuation_removed(self):
        assert Indexer.tokenize("Hello, world! How's it?") == ["hello", "world", "how's", "it"]

    def test_numbers(self):
        assert Indexer.tokenize("test123 456") == ["test123", "456"]

    def test_empty(self):
        assert Indexer.tokenize("") == []
        assert Indexer.tokenize("   ") == []

    def test_case_insensitive(self):
        assert Indexer.tokenize("HELLO hello HeLLo") == ["hello", "hello", "hello"]

    def test_special_characters_only(self):
        assert Indexer.tokenize("!@#$%^&*()") == []


class TestIndexBuild:
    def test_basic_build(self, built_indexer):
        assert built_indexer.stats.total_pages == 3
        assert built_indexer.stats.unique_words > 0
        assert built_indexer.stats.unique_authors > 0
        assert built_indexer.stats.unique_tags > 0

    def test_word_in_index(self, built_indexer):
        entry = built_indexer.get_entry("love")
        assert entry is not None
        assert entry.df > 0

    def test_case_insensitive_lookup(self, built_indexer):
        entry_lower = built_indexer.get_entry("love")
        entry_upper = built_indexer.get_entry("LOVE")
        assert entry_lower is entry_upper

    def test_word_not_in_index(self, built_indexer):
        assert built_indexer.get_entry("nonexistent") is None

    def test_positions_recorded(self, built_indexer):
        entry = built_indexer.get_entry("love")
        assert entry is not None
        for page_url, posting in entry.postings.items():
            assert len(posting.positions) == posting.tf
            assert all(isinstance(p, int) for p in posting.positions)

    def test_tf_is_positive(self, built_indexer):
        for word, entry in built_indexer.index.items():
            for page_url, posting in entry.postings.items():
                assert posting.tf > 0

    def test_df_matches_postings(self, built_indexer):
        for word, entry in built_indexer.index.items():
            assert entry.df == len(entry.postings)

    def test_tfidf_computed(self, built_indexer):
        entry = built_indexer.get_entry("love")
        assert entry is not None
        for posting in entry.postings.values():
            assert isinstance(posting.tfidf, float)

    def test_tfidf_zero_when_in_all_docs(self):
        pages = [
            CrawledPage(url="/p1/", quotes=[Quote(text="hello world", author="A", tags=[])]),
            CrawledPage(url="/p2/", quotes=[Quote(text="hello there", author="B", tags=[])]),
        ]
        indexer = Indexer()
        indexer.build(pages)
        entry = indexer.get_entry("hello")
        # IDF = log(2/2) = 0, so TF-IDF = 0
        for posting in entry.postings.values():
            assert posting.tfidf == 0.0

    def test_tfidf_higher_for_rarer_words(self, built_indexer):
        common = built_indexer.get_entry("is")
        rare = built_indexer.get_entry("stupid")
        assert common is not None and rare is not None
        rare_max = max(p.tfidf for p in rare.postings.values())
        common_max = max(p.tfidf for p in common.postings.values()) if common.postings else 0
        assert rare_max >= common_max


class TestIndexAuthorsAndTags:
    def test_authors_mapped(self, built_indexer):
        assert "albert einstein" in built_indexer.authors
        assert "mark twain" in built_indexer.authors

    def test_tags_mapped(self, built_indexer):
        assert "love" in built_indexer.tags
        assert "life" in built_indexer.tags

    def test_author_pages(self, built_indexer):
        pages = built_indexer.authors.get("albert einstein", [])
        assert len(pages) >= 1

    def test_tag_pages(self, built_indexer):
        pages = built_indexer.tags.get("love", [])
        assert len(pages) >= 1


class TestIndexVocabulary:
    def test_get_vocabulary_sorted(self, built_indexer):
        vocab = built_indexer.get_vocabulary()
        assert vocab == sorted(vocab)
        assert len(vocab) == built_indexer.stats.unique_words


class TestIndexSerialization:
    def test_to_dict_and_from_dict(self, built_indexer):
        data = built_indexer.to_dict()

        new_indexer = Indexer()
        new_indexer.from_dict(data)

        assert new_indexer.stats.total_pages == built_indexer.stats.total_pages
        assert new_indexer.stats.unique_words == built_indexer.stats.unique_words
        assert new_indexer.stats.unique_authors == built_indexer.stats.unique_authors
        assert new_indexer.stats.unique_tags == built_indexer.stats.unique_tags

    def test_roundtrip_preserves_postings(self, built_indexer):
        data = built_indexer.to_dict()
        new_indexer = Indexer()
        new_indexer.from_dict(data)

        for word, entry in built_indexer.index.items():
            new_entry = new_indexer.get_entry(word)
            assert new_entry is not None
            assert new_entry.df == entry.df
            for url, posting in entry.postings.items():
                assert url in new_entry.postings
                assert new_entry.postings[url].tf == posting.tf
                assert new_entry.postings[url].positions == posting.positions
                assert new_entry.postings[url].tfidf == posting.tfidf

    def test_empty_index(self):
        indexer = Indexer()
        indexer.build([])
        assert indexer.stats.total_pages == 0
        assert indexer.stats.unique_words == 0

        data = indexer.to_dict()
        new_indexer = Indexer()
        new_indexer.from_dict(data)
        assert new_indexer.stats.total_pages == 0

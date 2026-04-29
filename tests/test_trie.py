"""Tests for the prefix tree (Trie)."""

from __future__ import annotations

import pytest

from src.trie import Trie


@pytest.fixture
def sample_trie() -> Trie:
    trie = Trie()
    words = {"friends": 15, "friendship": 2, "friday": 3, "love": 18, "life": 10, "lovely": 4, "live": 5}
    for w, f in words.items():
        trie.insert(w, f)
    return trie


class TestInsertAndSearch:
    def test_search_existing(self, sample_trie):
        assert sample_trie.search("love") is True
        assert sample_trie.search("friends") is True

    def test_search_missing(self, sample_trie):
        assert sample_trie.search("loving") is False
        assert sample_trie.search("xyz") is False

    def test_search_prefix_not_word(self, sample_trie):
        assert sample_trie.search("fri") is False

    def test_insert_updates_frequency(self):
        trie = Trie()
        trie.insert("hello", 5)
        trie.insert("hello", 10)
        assert trie.search("hello") is True
        results = trie.suggest("hello")
        assert results[0] == ("hello", 10)


class TestSuggest:
    def test_basic_prefix(self, sample_trie):
        results = sample_trie.suggest("fri")
        words = [r[0] for r in results]
        assert "friends" in words
        assert "friday" in words
        assert "friendship" in words

    def test_sorted_by_frequency(self, sample_trie):
        results = sample_trie.suggest("fri")
        assert results[0][0] == "friends"
        assert results[0][1] == 15

    def test_max_results(self, sample_trie):
        results = sample_trie.suggest("", max_results=3)
        assert len(results) == 3

    def test_no_match(self, sample_trie):
        results = sample_trie.suggest("xyz")
        assert results == []

    def test_exact_word_as_prefix(self, sample_trie):
        results = sample_trie.suggest("love")
        words = [r[0] for r in results]
        assert "love" in words
        assert "lovely" in words

    def test_single_char_prefix(self, sample_trie):
        results = sample_trie.suggest("l")
        words = [r[0] for r in results]
        assert "love" in words
        assert "life" in words
        assert "lovely" in words
        assert "live" in words

    def test_empty_prefix_returns_all(self, sample_trie):
        results = sample_trie.suggest("", max_results=100)
        assert len(results) == 7


class TestFromIndex:
    def test_from_index(self, built_indexer):
        trie = Trie.from_index(built_indexer.index)
        results = trie.suggest("lo")
        words = [r[0] for r in results]
        assert "love" in words

    def test_from_word_list(self):
        trie = Trie.from_word_list({"apple": 10, "app": 5, "banana": 3})
        results = trie.suggest("ap")
        assert len(results) == 2
        assert results[0][0] == "apple"


class TestEdgeCases:
    def test_empty_trie(self):
        trie = Trie()
        assert trie.suggest("a") == []
        assert trie.search("a") is False

    def test_single_word_trie(self):
        trie = Trie()
        trie.insert("hello", 1)
        assert trie.suggest("h") == [("hello", 1)]
        assert trie.suggest("he") == [("hello", 1)]
        assert trie.suggest("hello") == [("hello", 1)]
        assert trie.suggest("helloo") == []

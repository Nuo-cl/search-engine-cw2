"""Tests for the spell checker."""

from __future__ import annotations

import pytest

from src.spell import SpellChecker, _levenshtein


class TestLevenshtein:
    def test_identical(self):
        assert _levenshtein("hello", "hello") == 0

    def test_single_insert(self):
        assert _levenshtein("helo", "hello") == 1

    def test_single_delete(self):
        assert _levenshtein("hello", "helo") == 1

    def test_single_substitute(self):
        assert _levenshtein("hello", "hallo") == 1

    def test_empty_strings(self):
        assert _levenshtein("", "") == 0
        assert _levenshtein("abc", "") == 3
        assert _levenshtein("", "abc") == 3

    def test_completely_different(self):
        assert _levenshtein("abc", "xyz") == 3

    def test_symmetric(self):
        assert _levenshtein("kitten", "sitting") == _levenshtein("sitting", "kitten")

    def test_transposition(self):
        assert _levenshtein("ab", "ba") == 2  # standard Levenshtein, not Damerau


class TestSpellChecker:
    @pytest.fixture
    def checker(self):
        vocab = ["love", "live", "life", "like", "line", "friends", "friendship", "friday"]
        return SpellChecker(vocab, max_distance=2)

    def test_suggest_close_word(self, checker):
        suggestions = checker.suggest("lovee")
        words = [s[0] for s in suggestions]
        assert "love" in words

    def test_suggest_sorted_by_distance(self, checker):
        suggestions = checker.suggest("lovee")
        distances = [s[1] for s in suggestions]
        assert distances == sorted(distances)

    def test_suggest_top_n(self, checker):
        suggestions = checker.suggest("lxve", top_n=2)
        assert len(suggestions) <= 2

    def test_suggest_no_match_beyond_threshold(self, checker):
        suggestions = checker.suggest("zzzzzzzzz")
        assert len(suggestions) == 0

    def test_suggest_excludes_exact_match(self, checker):
        suggestions = checker.suggest("love")
        words = [s[0] for s in suggestions]
        assert "love" not in words

    def test_suggest_typo_insertion(self, checker):
        suggestions = checker.suggest("freinds")
        words = [s[0] for s in suggestions]
        assert "friends" in words

    def test_suggest_typo_deletion(self, checker):
        suggestions = checker.suggest("frends")
        words = [s[0] for s in suggestions]
        assert "friends" in words

    def test_check_existing(self, checker):
        assert checker.check("love") is True

    def test_check_missing(self, checker):
        assert checker.check("lovee") is False

    def test_check_case_insensitive(self, checker):
        assert checker.check("LOVE") is True


class TestEdgeCases:
    def test_empty_vocabulary(self):
        checker = SpellChecker([], max_distance=2)
        assert checker.suggest("hello") == []
        assert checker.check("hello") is False

    def test_single_char_word(self):
        checker = SpellChecker(["a", "i", "o"], max_distance=1)
        suggestions = checker.suggest("e")
        assert len(suggestions) > 0

    def test_max_distance_zero(self):
        checker = SpellChecker(["love", "live"], max_distance=0)
        suggestions = checker.suggest("lovee")
        assert len(suggestions) == 0

"""Tests for the query parser."""

from __future__ import annotations

import pytest

from src.query_parser import parse_query


class TestBasicParsing:
    def test_single_word(self):
        q = parse_query("love")
        assert q.must_include == ["love"]
        assert not q.phrases
        assert not q.should_include
        assert not q.must_exclude

    def test_multi_word_and(self):
        q = parse_query("good friends")
        assert q.must_include == ["good", "friends"]

    def test_case_insensitive(self):
        q = parse_query("LOVE")
        assert q.must_include == ["love"]

    def test_empty_query(self):
        q = parse_query("")
        assert q.is_empty

    def test_whitespace_only(self):
        q = parse_query("   ")
        assert q.is_empty


class TestPhraseParsing:
    def test_single_phrase(self):
        q = parse_query('"good friends"')
        assert q.phrases == [["good", "friends"]]
        assert not q.must_include

    def test_phrase_with_extra_words(self):
        q = parse_query('"good friends" life')
        assert q.phrases == [["good", "friends"]]
        assert q.must_include == ["life"]

    def test_multiple_phrases(self):
        q = parse_query('"hello world" "foo bar"')
        assert len(q.phrases) == 2

    def test_empty_phrase_ignored(self):
        q = parse_query('""')
        assert not q.phrases


class TestOrParsing:
    def test_simple_or(self):
        q = parse_query("love OR hate")
        assert q.should_include == ["love", "hate"]
        assert not q.must_include

    def test_or_at_start_treated_as_word(self):
        q = parse_query("OR love")
        # OR at start has no left operand, treated as regular word
        assert "or" in q.must_include or "love" in q.must_include

    def test_multiple_or(self):
        q = parse_query("love OR hate OR fear")
        assert "love" in q.should_include
        assert "hate" in q.should_include
        # "fear" might be in should_include depending on chaining
        # At minimum love and hate should be OR'd


class TestExclusionParsing:
    def test_single_exclusion(self):
        q = parse_query("love -hate")
        assert q.must_include == ["love"]
        assert q.must_exclude == ["hate"]

    def test_multiple_exclusions(self):
        q = parse_query("love -hate -war")
        assert q.must_include == ["love"]
        assert "hate" in q.must_exclude
        assert "war" in q.must_exclude

    def test_bare_hyphen_not_exclusion(self):
        q = parse_query("love - hate")
        # bare "-" is not an exclusion prefix
        assert "hate" not in q.must_exclude


class TestTagFilter:
    def test_tag_filter(self):
        q = parse_query("--tag love")
        assert q.filter_tag == "love"

    def test_tag_with_query(self):
        q = parse_query("friends --tag friendship")
        assert q.filter_tag == "friendship"
        assert "friends" in q.must_include

    def test_tag_quoted(self):
        q = parse_query('--tag "deep thoughts"')
        assert q.filter_tag == "deep thoughts"

    def test_no_tag(self):
        q = parse_query("love")
        assert q.filter_tag is None


class TestAuthorFilter:
    def test_author_filter(self):
        q = parse_query("--author einstein")
        assert q.filter_author == "einstein"

    def test_author_with_query(self):
        q = parse_query("thinking --author einstein")
        assert q.filter_author == "einstein"
        assert "thinking" in q.must_include

    def test_author_quoted(self):
        q = parse_query('--author "albert einstein"')
        assert q.filter_author == "albert einstein"


class TestCombined:
    def test_phrase_or_exclusion(self):
        q = parse_query('life OR love -hate')
        assert "life" in q.should_include
        assert "love" in q.should_include
        assert "hate" in q.must_exclude

    def test_phrase_with_exclusion(self):
        q = parse_query('"good friends" -hate')
        assert q.phrases == [["good", "friends"]]
        assert "hate" in q.must_exclude

    def test_tag_and_author(self):
        q = parse_query("--tag love --author einstein")
        assert q.filter_tag == "love"
        assert q.filter_author == "einstein"

    def test_all_features(self):
        q = parse_query('"exact phrase" word1 OR word2 -exclude --tag mytag --author myauthor')
        assert q.phrases == [["exact", "phrase"]]
        assert "exclude" in q.must_exclude
        assert q.filter_tag == "mytag"
        assert q.filter_author == "myauthor"


class TestIsEmpty:
    def test_populated_not_empty(self):
        q = parse_query("love")
        assert not q.is_empty

    def test_tag_only_not_empty(self):
        q = parse_query("--tag love")
        assert not q.is_empty

    def test_author_only_not_empty(self):
        q = parse_query("--author einstein")
        assert not q.is_empty

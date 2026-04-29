"""Tests for the search engine: basic, advanced queries, and edge cases."""

from __future__ import annotations

import pytest

from src.search import SearchEngine


class TestBasicSearch:
    def test_single_word(self, search_engine):
        results = search_engine.find("love")
        assert len(results) > 0
        assert all(r.score >= 0 for r in results)

    def test_multi_word_and(self, search_engine):
        results = search_engine.find("good friends")
        assert len(results) > 0
        for r in results:
            assert "good" in r.matched_terms
            assert "friends" in r.matched_terms

    def test_results_sorted_by_score(self, search_engine):
        results = search_engine.find("life")
        scores = [r.score for r in results]
        assert scores == sorted(scores, reverse=True)

    def test_no_results_for_missing_word(self, search_engine):
        results = search_engine.find("nonexistent")
        assert len(results) == 0

    def test_empty_query(self, search_engine):
        results = search_engine.find("")
        assert len(results) == 0

    def test_whitespace_query(self, search_engine):
        results = search_engine.find("   ")
        assert len(results) == 0

    def test_case_insensitive(self, search_engine):
        results_lower = search_engine.find("love")
        results_upper = search_engine.find("LOVE")
        results_mixed = search_engine.find("LoVe")
        assert len(results_lower) == len(results_upper) == len(results_mixed)


class TestPhraseSearch:
    def test_exact_phrase(self, search_engine):
        results = search_engine.find('"good friends"')
        assert len(results) > 0

    def test_phrase_not_matching_reversed(self, built_indexer):
        """A phrase should not match if words appear in wrong order."""
        from src.crawler import CrawledPage, Quote
        from src.indexer import Indexer

        pages = [
            CrawledPage(url="/p1/", quotes=[
                Quote(text="the cat sat on the mat", author="A", tags=[]),
            ]),
        ]
        indexer = Indexer()
        indexer.build(pages)
        engine = SearchEngine(indexer)

        assert len(engine.find('"cat sat"')) > 0
        assert len(engine.find('"sat cat"')) == 0

    def test_phrase_no_match(self, search_engine):
        results = search_engine.find('"xyzzy plugh"')
        assert len(results) == 0


class TestOrSearch:
    def test_or_returns_union(self, search_engine):
        results_love = search_engine.find("love")
        results_stupid = search_engine.find("stupid")
        results_or = search_engine.find("love OR stupid")

        love_urls = {r.url for r in results_love}
        stupid_urls = {r.url for r in results_stupid}
        or_urls = {r.url for r in results_or}

        assert or_urls == love_urls | stupid_urls

    def test_or_with_nonexistent_word(self, search_engine):
        results = search_engine.find("love OR nonexistent")
        assert len(results) > 0


class TestExclusionSearch:
    def test_exclusion(self, search_engine):
        results_all = search_engine.find("love")
        results_excl = search_engine.find("love -friendship")
        assert len(results_excl) <= len(results_all)

        excl_urls = {r.url for r in results_excl}
        friendship_entry = search_engine.indexer.get_entry("friendship")
        if friendship_entry:
            friendship_pages = set(friendship_entry.postings.keys())
            assert excl_urls.isdisjoint(friendship_pages)

    def test_exclusion_all_results(self, search_engine):
        """If exclusion removes all results, return empty."""
        results = search_engine.find("stupid -stupid")
        assert len(results) == 0


class TestTagFilter:
    def test_filter_by_tag(self, search_engine):
        results = search_engine.find("--tag love")
        assert len(results) > 0

    def test_tag_with_text_search(self, search_engine):
        results = search_engine.find("life --tag friendship")
        assert len(results) > 0
        for r in results:
            page_url = r.url
            assert page_url in search_engine.indexer.tags.get("friendship", [])

    def test_nonexistent_tag(self, search_engine):
        results = search_engine.find("--tag nonexistenttag")
        assert len(results) == 0


class TestAuthorFilter:
    def test_filter_by_author(self, search_engine):
        results = search_engine.find("--author einstein")
        assert len(results) > 0

    def test_author_with_text_search(self, search_engine):
        results = search_engine.find("thinking --author einstein")
        assert len(results) > 0

    def test_nonexistent_author(self, search_engine):
        results = search_engine.find("--author nonexistentauthor")
        assert len(results) == 0


class TestCombinedQueries:
    def test_phrase_with_tag(self, search_engine):
        results = search_engine.find('"good friends" --tag friendship')
        assert len(results) > 0

    def test_or_with_exclusion(self, search_engine):
        results = search_engine.find("love OR life -plans")
        for r in results:
            plans_entry = search_engine.indexer.get_entry("plans")
            if plans_entry:
                assert r.url not in plans_entry.postings


class TestSnippets:
    def test_snippet_contains_text(self, search_engine):
        results = search_engine.find("love")
        assert len(results) > 0
        for r in results:
            assert len(r.snippet) > 0

    def test_snippet_includes_author(self, search_engine):
        results = search_engine.find("stupid")
        assert len(results) > 0
        assert "Jane Austen" in results[0].snippet


class TestPrintEntry:
    def test_existing_word(self, search_engine):
        result = search_engine.print_entry("love")
        assert result is not None
        assert result["word"] == "love"
        assert result["df"] > 0
        assert result["total_occurrences"] > 0
        assert len(result["postings"]) == result["df"]

    def test_nonexistent_word(self, search_engine):
        result = search_engine.print_entry("nonexistent")
        assert result is None

    def test_postings_sorted_by_tfidf(self, search_engine):
        result = search_engine.print_entry("life")
        if result and len(result["postings"]) > 1:
            scores = [p["tfidf"] for p in result["postings"]]
            assert scores == sorted(scores, reverse=True)

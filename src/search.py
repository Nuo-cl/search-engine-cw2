"""Search engine with advanced query support: phrases, OR, exclusion, tag/author filters."""

from __future__ import annotations

import logging
from dataclasses import dataclass

from src.indexer import Indexer
from src.query_parser import Query, parse_query

logger = logging.getLogger(__name__)


@dataclass
class SearchResult:
    url: str
    score: float
    snippet: str
    matched_terms: list[str]


class SearchEngine:
    def __init__(self, indexer: Indexer) -> None:
        self.indexer = indexer

    # ------------------------------------------------------------------
    # Snippet generation
    # ------------------------------------------------------------------

    def _generate_snippet(self, page_url: str, query_terms: list[str]) -> str:
        page_data = self.indexer.pages.get(page_url, {})
        quotes = page_data.get("quotes", [])

        for quote in quotes:
            text_lower = quote["text"].lower()
            if any(term in text_lower for term in query_terms):
                text = quote["text"]
                if len(text) > 120:
                    for term in query_terms:
                        pos = text_lower.find(term)
                        if pos != -1:
                            start = max(0, pos - 40)
                            end = min(len(text), pos + len(term) + 40)
                            return "..." + text[start:end] + "..."
                return text if len(text) <= 120 else text[:120] + "..."

        if quotes:
            text = quotes[0]["text"]
            return text if len(text) <= 120 else text[:120] + "..."
        return ""

    # ------------------------------------------------------------------
    # Scoring
    # ------------------------------------------------------------------

    def _compute_score(self, page_url: str, terms: list[str]) -> float:
        total = 0.0
        for term in terms:
            entry = self.indexer.get_entry(term)
            if entry and page_url in entry.postings:
                total += entry.postings[page_url].tfidf
        return round(total, 6)

    # ------------------------------------------------------------------
    # Set operations on postings
    # ------------------------------------------------------------------

    def _pages_for_term(self, term: str) -> set[str] | None:
        entry = self.indexer.get_entry(term)
        if entry is None:
            return None
        return set(entry.postings.keys())

    def _intersect_terms(self, terms: list[str]) -> set[str] | None:
        """Return pages containing ALL terms, or None if any term is missing."""
        result: set[str] | None = None
        for term in terms:
            pages = self._pages_for_term(term)
            if pages is None:
                return set()
            result = pages if result is None else result & pages
        return result

    def _union_terms(self, terms: list[str]) -> set[str]:
        """Return pages containing ANY of the terms."""
        result: set[str] = set()
        for term in terms:
            pages = self._pages_for_term(term)
            if pages:
                result |= pages
        return result

    # ------------------------------------------------------------------
    # Phrase matching
    # ------------------------------------------------------------------

    def _check_phrase_on_page(self, page_url: str, phrase_words: list[str]) -> bool:
        """Check if phrase_words appear consecutively on the page using position data."""
        if not phrase_words:
            return True

        first_entry = self.indexer.get_entry(phrase_words[0])
        if not first_entry or page_url not in first_entry.postings:
            return False

        start_positions = first_entry.postings[page_url].positions

        for start_pos in start_positions:
            match = True
            for offset, word in enumerate(phrase_words[1:], start=1):
                entry = self.indexer.get_entry(word)
                if not entry or page_url not in entry.postings:
                    match = False
                    break
                if (start_pos + offset) not in entry.postings[page_url].positions:
                    match = False
                    break
            if match:
                return True
        return False

    def _pages_matching_phrase(self, phrase_words: list[str]) -> set[str]:
        """Return pages where phrase_words appear as a consecutive sequence."""
        candidates = self._intersect_terms(phrase_words)
        if not candidates:
            return set()
        return {p for p in candidates if self._check_phrase_on_page(p, phrase_words)}

    # ------------------------------------------------------------------
    # Tag / Author filters
    # ------------------------------------------------------------------

    def _pages_for_tag(self, tag: str) -> set[str]:
        tag_lower = tag.lower()
        # Support partial matching
        result: set[str] = set()
        for t, pages in self.indexer.tags.items():
            if tag_lower in t:
                result.update(pages)
        return result

    def _pages_for_author(self, author: str) -> set[str]:
        author_lower = author.lower()
        result: set[str] = set()
        for a, pages in self.indexer.authors.items():
            if author_lower in a:
                result.update(pages)
        return result

    # ------------------------------------------------------------------
    # Main search
    # ------------------------------------------------------------------

    def find(self, raw_query: str) -> list[SearchResult]:
        """Execute a search query with full advanced syntax support.

        Returns results sorted by TF-IDF score descending.
        """
        query = parse_query(raw_query)
        if query.is_empty:
            return []

        all_search_terms: list[str] = []
        candidate_pages: set[str] | None = None

        # 1. Phrase matching
        for phrase_words in query.phrases:
            phrase_pages = self._pages_matching_phrase(phrase_words)
            candidate_pages = phrase_pages if candidate_pages is None else candidate_pages & phrase_pages
            all_search_terms.extend(phrase_words)

        # 2. must_include (AND)
        if query.must_include:
            must_pages = self._intersect_terms(query.must_include)
            if must_pages is not None:
                candidate_pages = must_pages if candidate_pages is None else candidate_pages & must_pages
            else:
                candidate_pages = set()
            all_search_terms.extend(query.must_include)

        # 3. should_include (OR)
        if query.should_include:
            or_pages = self._union_terms(query.should_include)
            if candidate_pages is None:
                candidate_pages = or_pages
            else:
                candidate_pages = candidate_pages | or_pages
            all_search_terms.extend(query.should_include)

        # 4. must_exclude
        if query.must_exclude:
            exclude_pages = self._union_terms(query.must_exclude)
            if candidate_pages:
                candidate_pages -= exclude_pages

        # 5. Tag filter
        if query.filter_tag:
            tag_pages = self._pages_for_tag(query.filter_tag)
            if candidate_pages is None:
                candidate_pages = tag_pages
            else:
                candidate_pages &= tag_pages

        # 6. Author filter
        if query.filter_author:
            author_pages = self._pages_for_author(query.filter_author)
            if candidate_pages is None:
                candidate_pages = author_pages
            else:
                candidate_pages &= author_pages

        if not candidate_pages:
            return []

        # Deduplicate search terms for scoring
        unique_terms = list(dict.fromkeys(all_search_terms))

        results: list[SearchResult] = []
        for page_url in candidate_pages:
            score = self._compute_score(page_url, unique_terms)
            snippet = self._generate_snippet(page_url, unique_terms)
            results.append(SearchResult(
                url=page_url,
                score=score,
                snippet=snippet,
                matched_terms=unique_terms,
            ))

        results.sort(key=lambda r: r.score, reverse=True)
        return results

    # ------------------------------------------------------------------
    # Print entry (unchanged from P0)
    # ------------------------------------------------------------------

    def print_entry(self, word: str) -> dict | None:
        """Get the inverted index entry for a word, formatted for display."""
        entry = self.indexer.get_entry(word)
        if entry is None:
            return None

        postings_list = []
        for page_url, posting in entry.postings.items():
            postings_list.append({
                "url": page_url,
                "tf": posting.tf,
                "positions": posting.positions,
                "tfidf": posting.tfidf,
            })

        postings_list.sort(key=lambda p: p["tfidf"], reverse=True)
        total_occurrences = sum(p["tf"] for p in postings_list)

        return {
            "word": word.lower(),
            "df": entry.df,
            "total_occurrences": total_occurrences,
            "postings": postings_list,
        }

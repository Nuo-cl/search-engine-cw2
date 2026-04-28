"""Search engine with basic query support (P0: single and multi-word AND queries)."""

from __future__ import annotations

import logging
from dataclasses import dataclass

from src.indexer import Indexer

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

    def _generate_snippet(self, page_url: str, query_terms: list[str]) -> str:
        """Generate a text snippet highlighting matched terms."""
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

    def _compute_multi_term_score(
        self, page_url: str, terms: list[str]
    ) -> float:
        """Compute combined TF-IDF score for multiple terms on a page."""
        total = 0.0
        for term in terms:
            entry = self.indexer.get_entry(term)
            if entry and page_url in entry.postings:
                total += entry.postings[page_url].tfidf
        return round(total, 6)

    def find(self, query: str) -> list[SearchResult]:
        """Find pages matching the query (AND semantics for multiple words).

        Returns results sorted by TF-IDF score descending.
        """
        terms = self.indexer.tokenize(query)
        if not terms:
            return []

        candidate_pages: set[str] | None = None
        matched_terms: list[str] = []

        for term in terms:
            entry = self.indexer.get_entry(term)
            if entry is None:
                return []
            term_pages = set(entry.postings.keys())
            if candidate_pages is None:
                candidate_pages = term_pages
            else:
                candidate_pages &= term_pages
            matched_terms.append(term)

        if not candidate_pages:
            return []

        results: list[SearchResult] = []
        for page_url in candidate_pages:
            score = self._compute_multi_term_score(page_url, matched_terms)
            snippet = self._generate_snippet(page_url, matched_terms)
            results.append(SearchResult(
                url=page_url,
                score=score,
                snippet=snippet,
                matched_terms=matched_terms,
            ))

        results.sort(key=lambda r: r.score, reverse=True)
        return results

    def print_entry(self, word: str) -> dict | None:
        """Get the inverted index entry for a word, formatted for display.

        Returns None if the word is not in the index.
        """
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

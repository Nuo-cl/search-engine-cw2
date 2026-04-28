"""Inverted index builder with TF-IDF scoring."""

from __future__ import annotations

import math
import re
import logging
from dataclasses import dataclass, field

from src.crawler import CrawledPage

logger = logging.getLogger(__name__)

WORD_PATTERN = re.compile(r"[a-z0-9]+(?:'[a-z]+)?")


@dataclass
class PostingEntry:
    tf: int = 0
    positions: list[int] = field(default_factory=list)
    tfidf: float = 0.0


@dataclass
class IndexEntry:
    df: int = 0
    postings: dict[str, PostingEntry] = field(default_factory=dict)


@dataclass
class IndexStats:
    total_pages: int = 0
    total_quotes: int = 0
    unique_words: int = 0
    unique_authors: int = 0
    unique_tags: int = 0


class Indexer:
    def __init__(self) -> None:
        self.index: dict[str, IndexEntry] = {}
        self.pages: dict[str, dict] = {}
        self.authors: dict[str, list[str]] = {}
        self.tags: dict[str, list[str]] = {}
        self.stats = IndexStats()
        self._doc_word_counts: dict[str, int] = {}

    @staticmethod
    def tokenize(text: str) -> list[str]:
        return WORD_PATTERN.findall(text.lower())

    def _index_page(self, page: CrawledPage) -> None:
        page_url = page.url
        all_words: list[str] = []

        page_authors: set[str] = set()
        page_tags: set[str] = set()

        for quote in page.quotes:
            words = self.tokenize(quote.text)
            all_words.extend(words)

            author_lower = quote.author.lower()
            page_authors.add(author_lower)

            for tag in quote.tags:
                page_tags.add(tag.lower())

        self.pages[page_url] = {
            "url": page.url,
            "quotes": [
                {
                    "text": q.text,
                    "author": q.author,
                    "tags": q.tags,
                }
                for q in page.quotes
            ],
        }

        for author in page_authors:
            if author not in self.authors:
                self.authors[author] = []
            if page_url not in self.authors[author]:
                self.authors[author].append(page_url)

        for tag in page_tags:
            if tag not in self.tags:
                self.tags[tag] = []
            if page_url not in self.tags[tag]:
                self.tags[tag].append(page_url)

        self._doc_word_counts[page_url] = len(all_words)

        for position, word in enumerate(all_words):
            if word not in self.index:
                self.index[word] = IndexEntry()

            entry = self.index[word]

            if page_url not in entry.postings:
                entry.postings[page_url] = PostingEntry()
                entry.df += 1

            posting = entry.postings[page_url]
            posting.tf += 1
            posting.positions.append(position)

    def _compute_tfidf(self) -> None:
        total_docs = len(self.pages)
        if total_docs == 0:
            return

        for word, entry in self.index.items():
            idf = math.log(total_docs / entry.df) if entry.df > 0 else 0.0
            for page_url, posting in entry.postings.items():
                doc_length = self._doc_word_counts.get(page_url, 1)
                tf = posting.tf / doc_length
                posting.tfidf = round(tf * idf, 6)

    def _update_stats(self) -> None:
        self.stats = IndexStats(
            total_pages=len(self.pages),
            total_quotes=sum(
                len(page_data["quotes"]) for page_data in self.pages.values()
            ),
            unique_words=len(self.index),
            unique_authors=len(self.authors),
            unique_tags=len(self.tags),
        )

    def build(self, pages: list[CrawledPage]) -> None:
        """Build the inverted index from crawled pages."""
        self.index.clear()
        self.pages.clear()
        self.authors.clear()
        self.tags.clear()
        self._doc_word_counts.clear()

        for page in pages:
            self._index_page(page)
            logger.debug("Indexed page %s: %d quotes", page.url, len(page.quotes))

        self._compute_tfidf()
        self._update_stats()

        logger.info(
            "Index built: %d pages, %d words, %d authors, %d tags",
            self.stats.total_pages,
            self.stats.unique_words,
            self.stats.unique_authors,
            self.stats.unique_tags,
        )

    def get_entry(self, word: str) -> IndexEntry | None:
        return self.index.get(word.lower())

    def get_vocabulary(self) -> list[str]:
        return sorted(self.index.keys())

    def to_dict(self) -> dict:
        """Serialize the entire index to a dictionary."""
        index_data = {}
        for word, entry in self.index.items():
            postings_data = {}
            for page_url, posting in entry.postings.items():
                postings_data[page_url] = {
                    "tf": posting.tf,
                    "positions": posting.positions,
                    "tfidf": posting.tfidf,
                }
            index_data[word] = {
                "df": entry.df,
                "postings": postings_data,
            }

        return {
            "pages": self.pages,
            "index": index_data,
            "authors": self.authors,
            "tags": self.tags,
        }

    def from_dict(self, data: dict) -> None:
        """Deserialize the index from a dictionary."""
        self.index.clear()
        self.pages.clear()
        self.authors.clear()
        self.tags.clear()
        self._doc_word_counts.clear()

        self.pages = data.get("pages", {})
        self.authors = data.get("authors", {})
        self.tags = data.get("tags", {})

        for word, entry_data in data.get("index", {}).items():
            entry = IndexEntry(df=entry_data["df"])
            for page_url, posting_data in entry_data["postings"].items():
                entry.postings[page_url] = PostingEntry(
                    tf=posting_data["tf"],
                    positions=posting_data["positions"],
                    tfidf=posting_data["tfidf"],
                )
            self.index[word] = entry

        for page_url, page_data in self.pages.items():
            word_count = 0
            for quote in page_data.get("quotes", []):
                word_count += len(self.tokenize(quote["text"]))
            self._doc_word_counts[page_url] = word_count

        self._update_stats()
        logger.info(
            "Index loaded: %d pages, %d words",
            self.stats.total_pages,
            self.stats.unique_words,
        )

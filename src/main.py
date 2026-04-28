"""Main entry point: command-line interface for the search engine."""

from __future__ import annotations

import logging
import sys
import time
from pathlib import Path

from src.crawler import Crawler
from src.indexer import Indexer
from src.search import SearchEngine
from src.storage import Storage, StorageError

DEFAULT_INDEX_PATH = Path("data/index.json")

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger(__name__)


class SearchEngineCLI:
    def __init__(self, index_path: Path = DEFAULT_INDEX_PATH) -> None:
        self.indexer = Indexer()
        self.storage = Storage(path=index_path)
        self.search_engine = SearchEngine(self.indexer)
        self._index_loaded = False

    def _require_index(self) -> bool:
        if not self._index_loaded:
            print("No index loaded. Please run 'build' or 'load' first.")
            return False
        return True

    def cmd_build(self) -> None:
        print("Starting crawl of quotes.toscrape.com...")
        crawler = Crawler()
        start = time.time()

        def on_page(page_num: int, page) -> None:
            print(f"  Crawled page {page_num}: {len(page.quotes)} quotes")

        pages = crawler.crawl(on_page_crawled=on_page)
        crawl_time = time.time() - start
        print(f"Crawling complete: {len(pages)} pages in {crawl_time:.1f}s")

        print("Building index...")
        start = time.time()
        self.indexer.build(pages)
        build_time = time.time() - start
        print(
            f"Index built in {build_time:.2f}s: "
            f"{self.indexer.stats.unique_words} words, "
            f"{self.indexer.stats.unique_authors} authors, "
            f"{self.indexer.stats.unique_tags} tags"
        )

        print(f"Saving index to {self.storage.path}...")
        self.storage.save(self.indexer)
        self._index_loaded = True
        print("Done.")

    def cmd_load(self) -> None:
        try:
            self.storage.load(self.indexer)
            self.search_engine = SearchEngine(self.indexer)
            self._index_loaded = True
            print(
                f"Index loaded: "
                f"{self.indexer.stats.total_pages} pages, "
                f"{self.indexer.stats.unique_words} words, "
                f"{self.indexer.stats.unique_authors} authors, "
                f"{self.indexer.stats.unique_tags} tags"
            )
        except StorageError as e:
            print(f"Error: {e}")

    def cmd_print(self, word: str) -> None:
        if not self._require_index():
            return

        result = self.search_engine.print_entry(word)
        if result is None:
            print(f'Word "{word}" not found in index.')
            return

        print(f'\nWord: "{result["word"]}"')
        print(f"Document Frequency: {result['df']} pages")
        print(f"Total Occurrences: {result['total_occurrences']}")
        print()
        for posting in result["postings"]:
            positions_str = ", ".join(str(p) for p in posting["positions"])
            print(
                f"  {posting['url']}  — "
                f"TF: {posting['tf']}, "
                f"Positions: [{positions_str}], "
                f"TF-IDF: {posting['tfidf']:.4f}"
            )
        print()

    def cmd_find(self, query: str) -> None:
        if not self._require_index():
            return

        start = time.time()
        results = self.search_engine.find(query)
        elapsed = time.time() - start

        if not results:
            print(f'No results found for "{query}".')
            return

        print(f"\nFound {len(results)} results ({elapsed:.3f}s, ranked by TF-IDF):\n")
        for i, result in enumerate(results, 1):
            print(f"  {i}. [{result.score:.4f}] {result.url}")
            if result.snippet:
                print(f'     "{result.snippet}"')
            print()

    def cmd_tags(self) -> None:
        if not self._require_index():
            return
        if not self.indexer.tags:
            print("No tags found in index.")
            return
        sorted_tags = sorted(
            self.indexer.tags.items(),
            key=lambda item: len(item[1]),
            reverse=True,
        )
        print(f"\nAll Tags ({len(sorted_tags)}):")
        for tag, pages in sorted_tags:
            print(f"  {tag:<25} ({len(pages)} pages)")
        print()

    def cmd_authors(self) -> None:
        if not self._require_index():
            return
        if not self.indexer.authors:
            print("No authors found in index.")
            return
        sorted_authors = sorted(
            self.indexer.authors.items(),
            key=lambda item: len(item[1]),
            reverse=True,
        )
        print(f"\nAll Authors ({len(sorted_authors)}):")
        for author, pages in sorted_authors:
            print(f"  {author:<30} ({len(pages)} pages)")
        print()

    def _parse_and_dispatch(self, line: str) -> bool:
        """Parse a command line and dispatch to the appropriate handler.

        Returns False if the user wants to exit.
        """
        line = line.strip()
        if not line:
            return True

        parts = line.split(maxsplit=1)
        command = parts[0].lower()
        args = parts[1] if len(parts) > 1 else ""

        match command:
            case "build":
                self.cmd_build()
            case "load":
                self.cmd_load()
            case "print":
                if not args:
                    print("Usage: print <word>")
                else:
                    self.cmd_print(args.strip())
            case "find":
                if not args:
                    print("Usage: find <query>")
                else:
                    self.cmd_find(args.strip())
            case "tags":
                self.cmd_tags()
            case "authors":
                self.cmd_authors()
            case "stats":
                self._cmd_stats()
            case "help":
                self._cmd_help()
            case "exit" | "quit":
                print("Goodbye!")
                return False
            case _:
                print(f'Unknown command: "{command}". Type "help" for available commands.')

        return True

    def _cmd_stats(self) -> None:
        if not self._require_index():
            return
        s = self.indexer.stats
        print(f"\nIndex Statistics:")
        print(f"  Pages crawled:    {s.total_pages}")
        print(f"  Total quotes:     {s.total_quotes}")
        print(f"  Unique words:     {s.unique_words}")
        print(f"  Unique authors:   {s.unique_authors}")
        print(f"  Unique tags:      {s.unique_tags}")
        print()

    def _cmd_help(self) -> None:
        print(
            """
Available commands:
  build                  Crawl the website, build the index, and save to file
  load                   Load the index from file
  print <word>           Print the inverted index entry for a word
  find <query>           Search for pages matching the query
  tags                   List all tags
  authors                List all authors
  stats                  Show index statistics
  help                   Show this help message
  exit                   Exit the program

Query syntax:
  find love              Single word search
  find good friends      Multi-word AND (pages must contain all words)
  find "to be or not"    Exact phrase match (words must appear consecutively)
  find love OR hate      OR search (pages containing either word)
  find love -war         Exclude pages containing "war"
  find --tag love        Filter by tag
  find --author einstein Filter by author
  find love --tag life   Combine text search with tag filter
"""
        )

    def run(self) -> None:
        print("Search Engine Tool — XJCO3011 Coursework 2")
        print('Type "help" for available commands.\n')

        while True:
            try:
                line = input("Search Engine > ")
                if not self._parse_and_dispatch(line):
                    break
            except (EOFError, KeyboardInterrupt):
                print("\nGoodbye!")
                break


def main() -> None:
    index_path = DEFAULT_INDEX_PATH
    if len(sys.argv) > 1:
        index_path = Path(sys.argv[1])
    cli = SearchEngineCLI(index_path=index_path)
    cli.run()


if __name__ == "__main__":
    main()

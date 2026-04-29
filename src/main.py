"""Main entry point: interactive CLI for the search engine."""

from __future__ import annotations

import logging
import sys
import time
from pathlib import Path

from prompt_toolkit import PromptSession
from prompt_toolkit.history import FileHistory

from src.crawler import Crawler
from src.indexer import Indexer
from src.search import SearchEngine
from src.spell import SpellChecker
from src.storage import Storage, StorageError
from src.trie import Trie
from src.ui import RichUI, SearchCompleter

DEFAULT_INDEX_PATH = Path("data/index.json")
HISTORY_PATH = Path("data/.search_history")

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
        self.ui = RichUI()
        self.completer = SearchCompleter()
        self.spell_checker: SpellChecker | None = None
        self.trie: Trie | None = None
        self._index_loaded = False

        HISTORY_PATH.parent.mkdir(parents=True, exist_ok=True)
        self.session: PromptSession = PromptSession(
            history=FileHistory(str(HISTORY_PATH)),
            completer=self.completer,
            complete_while_typing=True,
        )

    def _rebuild_helpers(self) -> None:
        """Rebuild Trie and SpellChecker after index load/build."""
        self.trie = Trie.from_index(self.indexer.index)
        vocab = self.indexer.get_vocabulary()
        self.spell_checker = SpellChecker(vocab)

        tag_list = sorted(self.indexer.tags.keys())
        author_list = sorted(self.indexer.authors.keys())
        self.completer.update(self.trie, tag_list, author_list)

    def _require_index(self) -> bool:
        if not self._index_loaded:
            self.ui.print_no_index()
            return False
        return True

    # ------------------------------------------------------------------
    # Commands
    # ------------------------------------------------------------------

    def cmd_build(self) -> None:
        self.ui.print_warning("Starting crawl of quotes.toscrape.com...")
        crawler = Crawler()
        start = time.time()

        def on_page(page_num: int, page) -> None:
            self.ui.print_build_progress(page_num, len(page.quotes))

        pages = crawler.crawl(on_page_crawled=on_page)
        crawl_time = time.time() - start
        self.ui.print_build_complete(len(pages), crawl_time)

        start = time.time()
        self.indexer.build(pages)
        build_time = time.time() - start
        self.ui.print_index_built(
            self.indexer.stats.unique_words,
            self.indexer.stats.unique_authors,
            self.indexer.stats.unique_tags,
            build_time,
        )

        self.storage.save(self.indexer)
        self.ui.print_saved(str(self.storage.path))
        self._index_loaded = True
        self._rebuild_helpers()

    def cmd_load(self) -> None:
        try:
            self.storage.load(self.indexer)
            self.search_engine = SearchEngine(self.indexer)
            self._index_loaded = True
            self._rebuild_helpers()
            self.ui.print_loaded(
                self.indexer.stats.total_pages,
                self.indexer.stats.unique_words,
                self.indexer.stats.unique_authors,
                self.indexer.stats.unique_tags,
            )
        except StorageError as e:
            self.ui.print_error(str(e))

    def cmd_print(self, word: str) -> None:
        if not self._require_index():
            return

        result = self.search_engine.print_entry(word)
        if result is None:
            self._try_spell_suggest(word, context="print")
            return

        self.ui.print_index_entry(result)

    def cmd_find(self, query: str) -> None:
        if not self._require_index():
            return

        self.ui.record_query(query)

        start = time.time()
        results = self.search_engine.find(query)
        elapsed = time.time() - start

        if not results:
            terms = self.indexer.tokenize(query)
            suggested = False
            for term in terms:
                if not self.indexer.get_entry(term):
                    suggested = self._try_spell_suggest(term, context="find")
                    if suggested:
                        break
            if not suggested:
                self.ui.print_no_results(query)
            return

        self.ui.print_search_results(results, query, elapsed)

    def _try_spell_suggest(self, word: str, context: str = "find") -> bool:
        """Check spelling and show suggestions. Returns True if suggestions were shown."""
        if not self.spell_checker:
            self.ui.print_no_results(word)
            return False

        suggestions = self.spell_checker.suggest(word)
        if suggestions:
            suggested_words = [s[0] for s in suggestions]
            self.ui.print_spell_suggestion(word, suggested_words)
            return True

        if context == "print":
            self.ui.print_warning(f'Word "{word}" not found in index.')
        else:
            self.ui.print_no_results(word)
        return False

    def cmd_tags(self) -> None:
        if not self._require_index():
            return
        if not self.indexer.tags:
            self.ui.print_warning("No tags found in index.")
            return
        self.ui.print_tags(self.indexer.tags)

    def cmd_authors(self) -> None:
        if not self._require_index():
            return
        if not self.indexer.authors:
            self.ui.print_warning("No authors found in index.")
            return
        self.ui.print_authors(self.indexer.authors)

    def cmd_stats(self) -> None:
        if not self._require_index():
            return
        self.ui.print_stats(self.indexer.stats)

    def cmd_history(self) -> None:
        self.ui.print_history()

    # ------------------------------------------------------------------
    # Command dispatch
    # ------------------------------------------------------------------

    def _parse_and_dispatch(self, line: str) -> bool:
        """Returns False if the user wants to exit."""
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
                    self.ui.print_warning("Usage: print <word>")
                else:
                    self.cmd_print(args.strip())
            case "find":
                if not args:
                    self.ui.print_warning("Usage: find <query>")
                else:
                    self.cmd_find(args.strip())
            case "tags":
                self.cmd_tags()
            case "authors":
                self.cmd_authors()
            case "stats":
                self.cmd_stats()
            case "history":
                self.cmd_history()
            case "help":
                self.ui.print_help()
            case "exit" | "quit":
                self.ui.print_warning("Goodbye!")
                return False
            case _:
                self.ui.print_error(
                    f'Unknown command: "{command}". Type "help" for available commands.'
                )

        return True

    def run(self) -> None:
        self.ui.print_welcome()

        while True:
            try:
                line = self.session.prompt("Search Engine > ")
                if not self._parse_and_dispatch(line):
                    break
            except (EOFError, KeyboardInterrupt):
                self.ui.print_warning("\nGoodbye!")
                break


def main() -> None:
    index_path = DEFAULT_INDEX_PATH
    if len(sys.argv) > 1:
        index_path = Path(sys.argv[1])
    cli = SearchEngineCLI(index_path=index_path)
    cli.run()


if __name__ == "__main__":
    main()

"""Interactive terminal UI with real-time autocomplete and rich output."""

from __future__ import annotations

import time
from typing import TYPE_CHECKING

from prompt_toolkit import PromptSession
from prompt_toolkit.completion import Completer, Completion
from prompt_toolkit.history import FileHistory
from prompt_toolkit.formatted_text import HTML
from rich.console import Console
from rich.table import Table
from rich.text import Text
from rich import box

if TYPE_CHECKING:
    from src.indexer import Indexer
    from src.search import SearchEngine, SearchResult
    from src.trie import Trie
    from src.spell import SpellChecker

console = Console()

COMMANDS = ["build", "load", "print", "find", "tags", "authors", "stats", "history", "help", "exit"]


class SearchCompleter(Completer):
    """Context-aware completer: commands at start, words/tags/authors after flags."""

    def __init__(self) -> None:
        self.trie: Trie | None = None
        self.tag_list: list[str] = []
        self.author_list: list[str] = []

    def update(self, trie: Trie, tags: list[str], authors: list[str]) -> None:
        self.trie = trie
        self.tag_list = tags
        self.author_list = authors

    def get_completions(self, document, complete_event):
        text = document.text_before_cursor
        word = document.get_word_before_cursor()

        if " " not in text:
            for cmd in COMMANDS:
                if cmd.startswith(word.lower()):
                    yield Completion(cmd, start_position=-len(word))
            return

        text_lower = text.lower()

        if "--tag " in text_lower:
            prefix = word.lower()
            for tag in self.tag_list:
                if tag.startswith(prefix):
                    yield Completion(tag, start_position=-len(word))
            return

        if "--author " in text_lower:
            prefix = word.lower()
            for author in self.author_list:
                if author.startswith(prefix):
                    # Wrap multi-word names in quotes
                    display = author
                    completion = f'"{author}"' if " " in author else author
                    yield Completion(completion, start_position=-len(word), display=display)
            return

        parts = text.split()
        cmd = parts[0].lower() if parts else ""
        if cmd in ("find", "print") and self.trie and word:
            suggestions = self.trie.suggest(word.lower(), max_results=8)
            for suggestion_word, freq in suggestions:
                yield Completion(
                    suggestion_word,
                    start_position=-len(word),
                    display_meta=f"{freq} pages",
                )


class RichUI:
    """Rich-formatted output for search results and index data."""

    def __init__(self) -> None:
        self.query_history: list[str] = []

    def record_query(self, query: str) -> None:
        self.query_history.append(query)

    def print_welcome(self) -> None:
        console.print("\n[bold cyan]Search Engine Tool[/bold cyan] — XJCO3011 Coursework 2")
        console.print('Type [bold]help[/bold] for available commands.\n')

    def print_build_progress(self, page_num: int, quote_count: int) -> None:
        console.print(f"  [dim]Crawled page {page_num}:[/dim] {quote_count} quotes")

    def print_build_complete(self, pages: int, crawl_time: float) -> None:
        console.print(f"[green]Crawling complete:[/green] {pages} pages in {crawl_time:.1f}s")

    def print_index_built(self, words: int, authors: int, tags: int, build_time: float) -> None:
        console.print(
            f"[green]Index built[/green] in {build_time:.2f}s: "
            f"{words} words, {authors} authors, {tags} tags"
        )

    def print_saved(self, path: str) -> None:
        console.print(f"[green]Index saved to[/green] {path}")

    def print_loaded(self, pages: int, words: int, authors: int, tags: int) -> None:
        console.print(
            f"[green]Index loaded:[/green] {pages} pages, "
            f"{words} words, {authors} authors, {tags} tags"
        )

    def print_error(self, msg: str) -> None:
        console.print(f"[bold red]Error:[/bold red] {msg}")

    def print_warning(self, msg: str) -> None:
        console.print(f"[yellow]{msg}[/yellow]")

    def print_no_index(self) -> None:
        console.print("[yellow]No index loaded. Please run 'build' or 'load' first.[/yellow]")

    # ------------------------------------------------------------------
    # print command
    # ------------------------------------------------------------------

    def print_index_entry(self, data: dict) -> None:
        console.print()
        console.print(f'[bold]Word:[/bold] "{data["word"]}"')
        console.print(f"[bold]Document Frequency:[/bold] {data['df']} pages")
        console.print(f"[bold]Total Occurrences:[/bold] {data['total_occurrences']}")
        console.print()

        table = Table(box=box.SIMPLE_HEAVY)
        table.add_column("Page URL", style="cyan")
        table.add_column("TF", justify="right")
        table.add_column("Positions", style="dim")
        table.add_column("TF-IDF", justify="right", style="green")

        for posting in data["postings"]:
            positions_str = ", ".join(str(p) for p in posting["positions"])
            table.add_row(
                posting["url"],
                str(posting["tf"]),
                f"[{positions_str}]",
                f"{posting['tfidf']:.4f}",
            )

        console.print(table)
        console.print()

    # ------------------------------------------------------------------
    # find command
    # ------------------------------------------------------------------

    def print_search_results(
        self, results: list[SearchResult], query: str, elapsed: float
    ) -> None:
        console.print()
        console.print(
            f"[bold]Found {len(results)} results[/bold] "
            f"({elapsed:.3f}s, ranked by TF-IDF):"
        )
        console.print()

        for i, result in enumerate(results, 1):
            score_text = Text(f"[{result.score:.4f}]", style="green")
            url_text = Text(result.url, style="bold cyan")

            console.print(f"  {i}. ", end="")
            console.print(score_text, end=" ")
            console.print(url_text)

            if result.snippet:
                snippet = self._highlight_terms(result.snippet, result.matched_terms)
                console.print(f"     ", end="")
                console.print(snippet)
            console.print()

    def _highlight_terms(self, text: str, terms: list[str]) -> Text:
        """Highlight matched terms in the snippet using rich markup."""
        rich_text = Text(text)
        text_lower = text.lower()
        for term in terms:
            start = 0
            while True:
                pos = text_lower.find(term, start)
                if pos == -1:
                    break
                rich_text.stylize("bold yellow", pos, pos + len(term))
                start = pos + 1
        return rich_text

    def print_no_results(self, query: str) -> None:
        console.print(f'[yellow]No results found for "{query}".[/yellow]')

    def print_spell_suggestion(self, word: str, suggestions: list[str]) -> str | None:
        """Show spell suggestions and return chosen correction or None."""
        suggestion_str = ", ".join(f"[bold]{s}[/bold]" for s in suggestions)
        console.print(f'[yellow]"{word}" not found. Did you mean: {suggestion_str}?[/yellow]')
        return None

    # ------------------------------------------------------------------
    # tags / authors
    # ------------------------------------------------------------------

    def print_tags(self, tags: dict[str, list[str]]) -> None:
        sorted_tags = sorted(tags.items(), key=lambda x: len(x[1]), reverse=True)
        console.print()
        table = Table(title=f"All Tags ({len(sorted_tags)})", box=box.ROUNDED)
        table.add_column("Tag", style="cyan")
        table.add_column("Pages", justify="right", style="green")
        for tag, pages in sorted_tags:
            table.add_row(tag, str(len(pages)))
        console.print(table)
        console.print()

    def print_authors(self, authors: dict[str, list[str]]) -> None:
        sorted_authors = sorted(authors.items(), key=lambda x: len(x[1]), reverse=True)
        console.print()
        table = Table(title=f"All Authors ({len(sorted_authors)})", box=box.ROUNDED)
        table.add_column("Author", style="cyan")
        table.add_column("Pages", justify="right", style="green")
        for author, pages in sorted_authors:
            table.add_row(author, str(len(pages)))
        console.print(table)
        console.print()

    # ------------------------------------------------------------------
    # stats / history / help
    # ------------------------------------------------------------------

    def print_stats(self, stats) -> None:
        console.print()
        table = Table(title="Index Statistics", box=box.ROUNDED)
        table.add_column("Metric", style="bold")
        table.add_column("Value", justify="right", style="cyan")
        table.add_row("Pages crawled", str(stats.total_pages))
        table.add_row("Total quotes", str(stats.total_quotes))
        table.add_row("Unique words", str(stats.unique_words))
        table.add_row("Unique authors", str(stats.unique_authors))
        table.add_row("Unique tags", str(stats.unique_tags))
        console.print(table)
        console.print()

    def print_history(self) -> None:
        if not self.query_history:
            console.print("[dim]No query history yet.[/dim]")
            return
        console.print("\n[bold]Query History:[/bold]")
        for i, q in enumerate(self.query_history, 1):
            console.print(f"  {i}. {q}")
        console.print()

    def print_help(self) -> None:
        console.print()
        console.print("[bold]Available commands:[/bold]")

        cmd_table = Table(box=box.SIMPLE, show_header=False, padding=(0, 2))
        cmd_table.add_column("Command", style="bold cyan")
        cmd_table.add_column("Description")
        cmd_table.add_row("build", "Crawl the website, build the index, and save to file")
        cmd_table.add_row("load", "Load the index from file")
        cmd_table.add_row("print <word>", "Print the inverted index entry for a word")
        cmd_table.add_row("find <query>", "Search for pages matching the query")
        cmd_table.add_row("tags", "List all tags")
        cmd_table.add_row("authors", "List all authors")
        cmd_table.add_row("stats", "Show index statistics")
        cmd_table.add_row("history", "Show query history")
        cmd_table.add_row("help", "Show this help message")
        cmd_table.add_row("exit", "Exit the program")
        console.print(cmd_table)

        console.print("\n[bold]Query syntax:[/bold]")

        syntax_table = Table(box=box.SIMPLE, show_header=False, padding=(0, 2))
        syntax_table.add_column("Example", style="bold green")
        syntax_table.add_column("Description")
        syntax_table.add_row('find love', "Single word search")
        syntax_table.add_row('find good friends', "Multi-word AND search")
        syntax_table.add_row('find "to be or not"', "Exact phrase match")
        syntax_table.add_row('find love OR hate', "OR search (either word)")
        syntax_table.add_row('find love -war', "Exclude pages with 'war'")
        syntax_table.add_row('find --tag love', "Filter by tag")
        syntax_table.add_row('find --author einstein', "Filter by author (partial match)")
        syntax_table.add_row('find --author "albert einstein"', "Multi-word author (use quotes)")
        syntax_table.add_row('find love --tag life', "Combine text + tag filter")
        console.print(syntax_table)
        console.print()

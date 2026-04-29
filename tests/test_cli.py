"""Tests for the CLI command dispatch and main module."""

from __future__ import annotations

import pytest
from pathlib import Path
from unittest.mock import patch, MagicMock

from src.main import SearchEngineCLI


@pytest.fixture
def cli(tmp_path) -> SearchEngineCLI:
    return SearchEngineCLI(index_path=tmp_path / "test_index.json", interactive=False)


@pytest.fixture
def loaded_cli(cli, sample_pages) -> SearchEngineCLI:
    """A CLI with a pre-built index (no crawling needed)."""
    cli.indexer.build(sample_pages)
    cli.search_engine = __import__("src.search", fromlist=["SearchEngine"]).SearchEngine(cli.indexer)
    cli._index_loaded = True
    cli._rebuild_helpers()
    return cli


class TestCommandDispatch:
    def test_empty_input(self, cli):
        assert cli._parse_and_dispatch("") is True

    def test_whitespace_input(self, cli):
        assert cli._parse_and_dispatch("   ") is True

    def test_exit(self, cli):
        assert cli._parse_and_dispatch("exit") is False

    def test_quit(self, cli):
        assert cli._parse_and_dispatch("quit") is False

    def test_unknown_command(self, cli, capsys):
        cli._parse_and_dispatch("foobar")
        captured = capsys.readouterr()
        assert "Unknown command" in captured.out or "unknown" in captured.out.lower()

    def test_help(self, cli):
        assert cli._parse_and_dispatch("help") is True

    def test_history(self, cli):
        assert cli._parse_and_dispatch("history") is True


class TestRequireIndex:
    def test_print_without_index(self, cli, capsys):
        cli.cmd_print("love")
        captured = capsys.readouterr()
        assert "No index" in captured.out or "load" in captured.out.lower()

    def test_find_without_index(self, cli, capsys):
        cli.cmd_find("love")
        captured = capsys.readouterr()
        assert "No index" in captured.out or "load" in captured.out.lower()

    def test_stats_without_index(self, cli, capsys):
        cli.cmd_stats()
        captured = capsys.readouterr()
        assert "No index" in captured.out or "load" in captured.out.lower()

    def test_tags_without_index(self, cli, capsys):
        cli.cmd_tags()
        captured = capsys.readouterr()
        assert "No index" in captured.out or "load" in captured.out.lower()

    def test_authors_without_index(self, cli, capsys):
        cli.cmd_authors()
        captured = capsys.readouterr()
        assert "No index" in captured.out or "load" in captured.out.lower()


class TestPrintCommand:
    def test_print_missing_arg(self, cli, capsys):
        cli._parse_and_dispatch("print")
        captured = capsys.readouterr()
        assert "Usage" in captured.out or "usage" in captured.out.lower()

    def test_print_existing_word(self, loaded_cli, capsys):
        loaded_cli.cmd_print("love")
        captured = capsys.readouterr()
        assert "love" in captured.out

    def test_print_nonexistent_word(self, loaded_cli, capsys):
        loaded_cli.cmd_print("nonexistent")
        captured = capsys.readouterr()
        assert "not found" in captured.out.lower() or "Did you mean" in captured.out


class TestFindCommand:
    def test_find_missing_arg(self, cli, capsys):
        cli._parse_and_dispatch("find")
        captured = capsys.readouterr()
        assert "Usage" in captured.out or "usage" in captured.out.lower()

    def test_find_existing_word(self, loaded_cli, capsys):
        loaded_cli.cmd_find("love")
        captured = capsys.readouterr()
        assert "results" in captured.out.lower() or "Found" in captured.out

    def test_find_no_results(self, loaded_cli, capsys):
        loaded_cli.cmd_find("xyznonexistent")
        captured = capsys.readouterr()
        assert "No results" in captured.out or "not found" in captured.out.lower()

    def test_find_records_history(self, loaded_cli):
        loaded_cli.cmd_find("love")
        assert "love" in loaded_cli.ui.query_history


class TestTagsAuthorsCommands:
    def test_tags(self, loaded_cli, capsys):
        loaded_cli.cmd_tags()
        captured = capsys.readouterr()
        assert "love" in captured.out.lower() or "Tags" in captured.out

    def test_authors(self, loaded_cli, capsys):
        loaded_cli.cmd_authors()
        captured = capsys.readouterr()
        assert "einstein" in captured.out.lower() or "Authors" in captured.out


class TestStatsCommand:
    def test_stats(self, loaded_cli, capsys):
        loaded_cli.cmd_stats()
        captured = capsys.readouterr()
        assert "3" in captured.out  # 3 pages


class TestBuildAndLoad:
    def test_load_missing_file(self, cli, capsys):
        cli.cmd_load()
        captured = capsys.readouterr()
        assert "Error" in captured.out or "not found" in captured.out.lower()

    def test_save_and_load_roundtrip(self, loaded_cli, capsys):
        loaded_cli.storage.save(loaded_cli.indexer)
        loaded_cli._index_loaded = False

        loaded_cli.cmd_load()
        captured = capsys.readouterr()
        assert loaded_cli._index_loaded is True
        assert "loaded" in captured.out.lower()


class TestRebuildHelpers:
    def test_rebuild_creates_trie(self, loaded_cli):
        assert loaded_cli.trie is not None
        results = loaded_cli.trie.suggest("lo")
        assert any("love" == r[0] for r in results)

    def test_rebuild_creates_spell_checker(self, loaded_cli):
        assert loaded_cli.spell_checker is not None
        assert loaded_cli.spell_checker.check("love") is True

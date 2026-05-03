# Search Engine Tool

A command-line search engine for [quotes.toscrape.com](https://quotes.toscrape.com/), built for XJCO3011 Coursework 2.

Crawls the website, builds an inverted index with TF-IDF scoring, and provides advanced search with phrase matching, boolean operators, tag/author filters, autocomplete, and spell correction.

## Installation

**Prerequisites:** Python 3.10+

```bash
git clone https://github.com/Nuo-cl/search-engine-cw2.git
cd search-engine-cw2
pip install -r requirements.txt
```

## Quick Start

```bash
python -m src.main
```

A pre-built index is included in `data/index.json`. You can start searching immediately:

```
Search Engine > load
Search Engine > find love
```

To rebuild the index from scratch (takes ~60s due to 6-second politeness window):

```
Search Engine > build
```

## Commands

### Core Commands (Assignment Required)

| Command | Description |
|---|---|
| `build` | Crawl the website, build the inverted index, and save to file |
| `load` | Load the index from `data/index.json` |
| `print <word>` | Display the inverted index entry for a word (TF, positions, TF-IDF) |
| `find <query>` | Search for pages matching the query, ranked by TF-IDF |

### Additional Commands

| Command | Description |
|---|---|
| `tags` | List all tags with page counts |
| `authors` | List all authors with page counts |
| `stats` | Show index statistics (pages, words, authors, tags) |
| `history` | Show query history for the current session |
| `help` | Display help with full query syntax reference |
| `exit` | Exit the program |

## Query Syntax

```
find love                    Single word search
find good friends            Multi-word AND (pages must contain all words)
find "to be or not"          Exact phrase match (consecutive word positions)
find love OR hate            OR search (pages containing either word)
find love -war               Exclude pages containing "war"
find --tag inspirational     Filter by tag
find --author einstein       Filter by author (partial match)
find love --tag life         Combine text search with filters
```

## Usage Examples

### build
```
Search Engine > build
Starting crawl of quotes.toscrape.com...
  Crawled page 1: 10 quotes
  Crawled page 2: 10 quotes
  ...
Crawling complete: 10 pages in 61.2s
Index built in 0.01s: 682 words, 50 authors, 137 tags
Index saved to data/index.json
```

### load
```
Search Engine > load
Index loaded: 10 pages, 682 words, 50 authors, 137 tags
```

### print
```
Search Engine > print love

Word: "love"
Document Frequency: 7 pages
Total Occurrences: 14

  /page/1/  — TF: 3, Positions: [5, 18, 42], TF-IDF: 0.0034
  /page/3/  — TF: 2, Positions: [12, 31],    TF-IDF: 0.0028
  ...
```

### find
```
Search Engine > find love

Found 7 results (0.003s, ranked by TF-IDF):

  1. [0.0142] https://quotes.toscrape.com/page/5/
     "Love all, trust a few, do wrong to none. — William Shakespeare"

  2. [0.0098] https://quotes.toscrape.com/page/1/
     "The best thing to hold onto in life is each other. — Audrey Hepburn"
  ...
```

## Interactive Features

- **Real-time autocomplete**: Press `Tab` while typing to see word suggestions sorted by document frequency
- **Context-aware completion**: Automatically switches between word/tag/author suggestions based on `--tag` or `--author` flags
- **Spell correction**: If a search term is not found, suggests corrections (e.g., `lovee` → `love, loved, lover`)
- **Query history**: Use up/down arrow keys to navigate previous commands

## Project Structure

```
search-engine-cw2/
├── src/
│   ├── crawler.py          # Web crawler with politeness window and retry
│   ├── indexer.py          # Inverted index with TF-IDF scoring
│   ├── search.py           # Search engine with advanced query support
│   ├── storage.py          # JSON persistence with SHA256 integrity check
│   ├── query_parser.py     # Query syntax parser (phrases, OR, exclusion, filters)
│   ├── trie.py             # Prefix tree for autocomplete suggestions
│   ├── spell.py            # Levenshtein distance spell checker
│   ├── ui.py               # Rich terminal UI (colored output, tables)
│   └── main.py             # CLI entry point and command dispatch
├── tests/
│   ├── conftest.py         # Shared fixtures and sample HTML
│   ├── test_crawler.py     # Crawler parsing and mock HTTP tests
│   ├── test_indexer.py     # Index building, TF-IDF, serialization
│   ├── test_search.py      # All query types and edge cases
│   ├── test_storage.py     # Save/load, checksum, corruption
│   ├── test_query_parser.py # Query syntax parsing
│   ├── test_trie.py        # Trie insert, suggest, prefix matching
│   ├── test_spell.py       # Edit distance and spell suggestions
│   ├── test_integration.py # End-to-end pipeline tests
│   ├── test_cli.py         # CLI command dispatch tests
│   └── benchmark.py        # Performance benchmark script
├── data/
│   └── index.json          # Pre-built index (10 pages, 100 quotes)
├── docs/
│   ├── design_plan.md      # Architecture and feature design
│   ├── dev_log.md          # Development log
│   └── benchmark.md        # Benchmark results and complexity analysis
├── requirements.txt
└── README.md
```

## Testing

Run the full test suite:

```bash
python -m pytest tests/ -v
```

Run with coverage report:

```bash
python -m pytest tests/ --cov=src --cov-report=term-missing
```

Current status: **173 tests, 86% coverage**

Tests use the `responses` library to mock HTTP requests — no network connection needed.

## Benchmark

Run the performance benchmark:

```bash
python -m tests.benchmark
```

Measures search performance across real data (10 pages) and simulated large datasets (up to 500 pages, 10,000+ words). See [docs/benchmark.md](docs/benchmark.md) for detailed results and complexity analysis.

## Dependencies

| Package | Purpose |
|---|---|
| `requests` | HTTP requests for web crawling |
| `beautifulsoup4` + `lxml` | HTML parsing |
| `prompt-toolkit` | Interactive terminal with autocomplete and history |
| `rich` | Colored output, tables, keyword highlighting |
| `pytest` + `pytest-cov` | Testing and coverage |
| `responses` | HTTP request mocking for tests |

Install all dependencies:

```bash
pip install -r requirements.txt
```

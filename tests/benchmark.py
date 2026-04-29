"""Benchmark script: compare optimised vs unoptimised search operations.

Runs two benchmark suites:
  1. Real data (10 pages from quotes.toscrape.com)
  2. Simulated large dataset (mock 500 pages, 5000 quotes, ~15000 unique words)

Usage: python -m tests.benchmark
"""

from __future__ import annotations

import random
import string
import time
import statistics
from pathlib import Path

from src.crawler import CrawledPage, Quote
from src.indexer import Indexer
from src.search import SearchEngine
from src.storage import Storage
from src.trie import Trie
from src.spell import SpellChecker

INDEX_PATH = Path("data/index.json")
ITERATIONS = 500


def _time_fn(fn, iterations: int = ITERATIONS) -> dict:
    """Run fn() multiple times and return timing statistics in microseconds."""
    times: list[float] = []
    for _ in range(iterations):
        start = time.perf_counter()
        fn()
        elapsed = (time.perf_counter() - start) * 1_000_000
        times.append(elapsed)
    return {
        "mean": statistics.mean(times),
        "median": statistics.median(times),
        "min": min(times),
        "max": max(times),
        "stdev": statistics.stdev(times) if len(times) > 1 else 0,
    }


# ------------------------------------------------------------------
# Simulated large dataset generator
# ------------------------------------------------------------------

# Common English words to mix into generated quotes
_BASE_WORDS = [
    "the", "be", "to", "of", "and", "a", "in", "that", "have", "i",
    "it", "for", "not", "on", "with", "he", "as", "you", "do", "at",
    "this", "but", "his", "by", "from", "they", "we", "say", "her", "she",
    "or", "an", "will", "my", "one", "all", "would", "there", "their", "what",
    "love", "life", "world", "good", "friends", "time", "people", "way", "day",
    "man", "think", "mind", "heart", "soul", "truth", "power", "hope", "dream",
    "change", "work", "great", "never", "always", "happy", "believe", "fear",
    "courage", "wisdom", "knowledge", "beauty", "nature", "peace", "freedom",
    "justice", "light", "dark", "strength", "faith", "joy", "pain", "success",
    "failure", "future", "past", "present", "moment", "death", "live", "learn",
    "grow", "fight", "fall", "rise", "walk", "run", "speak", "listen", "read",
    "write", "create", "destroy", "build", "break", "open", "close", "begin",
    "end", "find", "lose", "give", "take", "hold", "keep", "trust", "doubt",
]

_AUTHORS = [
    "Albert Einstein", "Mark Twain", "Oscar Wilde", "Jane Austen",
    "Friedrich Nietzsche", "William Shakespeare", "Mahatma Gandhi",
    "Martin Luther King Jr.", "Nelson Mandela", "Maya Angelou",
    "Leo Tolstoy", "Charles Dickens", "Virginia Woolf", "Ernest Hemingway",
    "George Orwell", "Fyodor Dostoevsky", "Emily Dickinson", "Walt Whitman",
    "Rabindranath Tagore", "Confucius",
]

_TAGS = [
    "love", "life", "inspirational", "humor", "philosophy", "wisdom",
    "truth", "happiness", "courage", "friendship", "change", "nature",
    "death", "science", "art", "books", "faith", "hope", "freedom", "peace",
]


def _generate_quote(rng: random.Random, word_pool: list[str]) -> Quote:
    length = rng.randint(8, 30)
    words = [rng.choice(word_pool) for _ in range(length)]
    text = " ".join(words).capitalize() + "."
    author = rng.choice(_AUTHORS)
    num_tags = rng.randint(1, 4)
    tags = rng.sample(_TAGS, num_tags)
    return Quote(text=text, author=author, tags=tags)


def generate_large_dataset(
    num_pages: int = 500,
    quotes_per_page: int = 10,
    extra_vocab_size: int = 10000,
    seed: int = 42,
) -> list[CrawledPage]:
    """Generate a large mock dataset for benchmarking."""
    rng = random.Random(seed)

    extra_words = []
    for _ in range(extra_vocab_size):
        length = rng.randint(3, 12)
        word = "".join(rng.choices(string.ascii_lowercase, k=length))
        extra_words.append(word)

    word_pool = _BASE_WORDS + extra_words

    pages: list[CrawledPage] = []
    for i in range(num_pages):
        quotes = [_generate_quote(rng, word_pool) for _ in range(quotes_per_page)]
        page = CrawledPage(url=f"https://mock.example.com/page/{i+1}/", quotes=quotes)
        pages.append(page)

    return pages


# ------------------------------------------------------------------
# Benchmark runner
# ------------------------------------------------------------------

def _run_search_benchmark(engine: SearchEngine, indexer: Indexer, label: str) -> None:
    print(f"\n  Index stats: {indexer.stats.unique_words} words, "
          f"{indexer.stats.total_pages} pages, "
          f"{indexer.stats.total_quotes} quotes")

    # --- Single word search ---
    print("\n  --- Single Word Search ---")
    queries_single = ["love", "life", "world", "thinking", "good"]
    for q in queries_single:
        results = engine.find(q)
        if results:
            stats = _time_fn(lambda q=q: engine.find(q))
            print(f'    find("{q}"): {stats["mean"]:.1f} us mean, '
                  f'{stats["median"]:.1f} us median, {len(results)} results')

    # --- Multi-word AND search ---
    print("\n  --- Multi-word AND Search ---")
    queries_multi = ["good friends", "love life", "world thinking"]
    for q in queries_multi:
        results = engine.find(q)
        stats = _time_fn(lambda q=q: engine.find(q))
        print(f'    find("{q}"): {stats["mean"]:.1f} us mean, '
              f'{stats["median"]:.1f} us median, {len(results)} results')

    # --- Phrase search ---
    print("\n  --- Phrase Search ---")
    queries_phrase = ['"good friends"', '"the world"', '"love life"']
    for q in queries_phrase:
        results = engine.find(q)
        stats = _time_fn(lambda q=q: engine.find(q))
        print(f'    find({q}): {stats["mean"]:.1f} us mean, '
              f'{stats["median"]:.1f} us median, {len(results)} results')

    # --- OR / Exclusion ---
    print("\n  --- OR & Exclusion Search ---")
    queries_adv = ["love OR fear", "love -death", "life --tag inspirational"]
    for q in queries_adv:
        results = engine.find(q)
        stats = _time_fn(lambda q=q: engine.find(q))
        print(f'    find("{q}"): {stats["mean"]:.1f} us mean, '
              f'{stats["median"]:.1f} us median, {len(results)} results')

    # --- Optimised vs Unoptimised ---
    print(f"\n  --- Optimised vs Unoptimised ({label}) ---")

    # AND intersection
    test_terms = ["the", "love", "good"]
    stats_opt = _time_fn(lambda: engine._intersect_terms(test_terms))
    stats_unopt = _time_fn(lambda: engine._intersect_terms_unoptimized(test_terms))
    speedup = stats_unopt["mean"] / stats_opt["mean"] if stats_opt["mean"] > 0 else 0
    print(f'    AND intersection {test_terms}:')
    print(f'      Optimised (small-set-first): {stats_opt["mean"]:.1f} us')
    print(f'      Unoptimised (input-order):   {stats_unopt["mean"]:.1f} us')
    print(f'      Speedup:                     {speedup:.2f}x')

    # Phrase matching
    test_phrase = ["love", "life"]
    candidates = engine._intersect_terms(test_phrase)
    if candidates:
        test_page = next(iter(candidates))
        stats_opt = _time_fn(
            lambda: engine._check_phrase_on_page(test_page, test_phrase)
        )
        stats_unopt = _time_fn(
            lambda: engine._check_phrase_on_page_unoptimized(test_page, test_phrase)
        )
        speedup = stats_unopt["mean"] / stats_opt["mean"] if stats_opt["mean"] > 0 else 0
        print(f'    Phrase match {test_phrase}:')
        print(f'      Optimised (position_set):    {stats_opt["mean"]:.1f} us')
        print(f'      Unoptimised (position list):  {stats_unopt["mean"]:.1f} us')
        print(f'      Speedup:                     {speedup:.2f}x')

    # Trie
    print(f"\n  --- Trie Autocomplete ---")
    trie = Trie.from_index(indexer.index)
    for prefix in ["lo", "fri", "th", "a"]:
        stats = _time_fn(lambda p=prefix: trie.suggest(p))
        results = trie.suggest(prefix)
        print(f'    suggest("{prefix}"): {stats["mean"]:.1f} us mean, '
              f'{len(results)} suggestions')

    # Spell check
    print(f"\n  --- Spell Correction ---")
    vocab = indexer.get_vocabulary()
    checker = SpellChecker(vocab)
    for typo in ["lovee", "freinds", "wrold", "thinkng"]:
        stats = _time_fn(lambda t=typo: checker.suggest(t), iterations=50)
        suggestions = checker.suggest(typo)
        words = [s[0] for s in suggestions]
        print(f'    suggest("{typo}"): {stats["mean"]:.0f} us mean -> {words}')


def run_benchmark() -> None:
    print("=" * 70)
    print("Search Engine Benchmark")
    print("=" * 70)

    # ==================== Part 1: Real data ====================
    print("\n" + "=" * 70)
    print("PART 1: Real Data (quotes.toscrape.com)")
    print("=" * 70)

    indexer = Indexer()
    storage = Storage(path=INDEX_PATH)

    if INDEX_PATH.exists():
        print("\n  --- Index Load ---")
        load_stats = _time_fn(lambda: storage.load(indexer), iterations=20)
        storage.load(indexer)
        print(f"    Load time: {load_stats['mean']/1000:.2f} ms (mean over 20 runs)")

        engine = SearchEngine(indexer)
        _run_search_benchmark(engine, indexer, "real data")
    else:
        print("\n  [Skipped] No index file found. Run 'build' first.")

    # ==================== Part 2: Simulated large dataset ====================
    print("\n" + "=" * 70)
    print("PART 2: Simulated Large Dataset (500 pages, 5000 quotes)")
    print("=" * 70)

    print("\n  Generating mock data...")
    pages = generate_large_dataset(num_pages=500, quotes_per_page=10)

    print("  Building index...")
    start = time.time()
    large_indexer = Indexer()
    large_indexer.build(pages)
    build_time = time.time() - start
    print(f"    Index build time: {build_time:.2f}s")

    large_engine = SearchEngine(large_indexer)
    _run_search_benchmark(large_engine, large_indexer, "500 pages")

    # ==================== Part 3: Scale comparison ====================
    print("\n" + "=" * 70)
    print("PART 3: Scaling Comparison (50 / 200 / 500 pages)")
    print("=" * 70)

    for num_pages in [50, 200, 500]:
        pages = generate_large_dataset(num_pages=num_pages, quotes_per_page=10)
        idx = Indexer()

        start = time.time()
        idx.build(pages)
        build_time = time.time() - start

        eng = SearchEngine(idx)

        search_stats = _time_fn(lambda: eng.find("love life"))
        phrase_stats = _time_fn(lambda: eng.find('"love life"'))

        print(f"\n  {num_pages} pages ({idx.stats.unique_words} words):")
        print(f"    Build:          {build_time*1000:.1f} ms")
        print(f"    AND search:     {search_stats['mean']:.1f} us")
        print(f"    Phrase search:  {phrase_stats['mean']:.1f} us")

    print("\n" + "=" * 70)
    print("Benchmark complete.")
    print("=" * 70)


if __name__ == "__main__":
    run_benchmark()

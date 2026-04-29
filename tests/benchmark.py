"""Benchmark script: compare optimised vs unoptimised search operations.

Usage: python -m tests.benchmark
"""

from __future__ import annotations

import time
import statistics
from pathlib import Path

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
        elapsed = (time.perf_counter() - start) * 1_000_000  # us
        times.append(elapsed)
    return {
        "mean": statistics.mean(times),
        "median": statistics.median(times),
        "min": min(times),
        "max": max(times),
        "stdev": statistics.stdev(times) if len(times) > 1 else 0,
    }


def run_benchmark() -> None:
    print("=" * 70)
    print("Search Engine Benchmark")
    print("=" * 70)

    # Load index
    indexer = Indexer()
    storage = Storage(path=INDEX_PATH)

    print("\n--- Index Load ---")
    load_stats = _time_fn(lambda: storage.load(indexer), iterations=20)
    storage.load(indexer)
    print(f"  Load time:       {load_stats['mean']/1000:.2f} ms (mean over 20 runs)")

    engine = SearchEngine(indexer)

    print(f"\n  Index stats: {indexer.stats.unique_words} words, "
          f"{indexer.stats.total_pages} pages, "
          f"{indexer.stats.total_quotes} quotes")

    # --- Single word search ---
    print("\n--- Single Word Search ---")
    queries_single = ["love", "life", "world", "thinking", "good"]
    for q in queries_single:
        stats = _time_fn(lambda q=q: engine.find(q))
        results = engine.find(q)
        print(f'  find("{q}"): {stats["mean"]:.1f} us mean, '
              f'{stats["median"]:.1f} us median, {len(results)} results')

    # --- Multi-word AND search ---
    print("\n--- Multi-word AND Search ---")
    queries_multi = ["good friends", "love life", "world thinking"]
    for q in queries_multi:
        stats = _time_fn(lambda q=q: engine.find(q))
        results = engine.find(q)
        print(f'  find("{q}"): {stats["mean"]:.1f} us mean, '
              f'{stats["median"]:.1f} us median, {len(results)} results')

    # --- Phrase search ---
    print("\n--- Phrase Search ---")
    queries_phrase = ['"good friends"', '"the world"']
    for q in queries_phrase:
        stats = _time_fn(lambda q=q: engine.find(q))
        results = engine.find(q)
        print(f'  find({q}): {stats["mean"]:.1f} us mean, '
              f'{stats["median"]:.1f} us median, {len(results)} results')

    # --- OR / Exclusion ---
    print("\n--- OR & Exclusion Search ---")
    queries_adv = ["love OR hate", "love -war", "life --tag inspirational"]
    for q in queries_adv:
        stats = _time_fn(lambda q=q: engine.find(q))
        results = engine.find(q)
        print(f'  find("{q}"): {stats["mean"]:.1f} us mean, '
              f'{stats["median"]:.1f} us median, {len(results)} results')

    # --- Optimised vs Unoptimised comparison ---
    print("\n" + "=" * 70)
    print("Optimised vs Unoptimised Comparison")
    print("=" * 70)

    # AND intersection: optimised (small-set-first) vs unoptimised (input order)
    print("\n--- AND Intersection: small-set-first vs input-order ---")
    test_terms = ["the", "world", "thinking"]  # "the" is very common, "thinking" is rare
    stats_opt = _time_fn(lambda: engine._intersect_terms(test_terms))
    stats_unopt = _time_fn(lambda: engine._intersect_terms_unoptimized(test_terms))
    speedup = stats_unopt["mean"] / stats_opt["mean"] if stats_opt["mean"] > 0 else 0
    print(f'  Terms: {test_terms}')
    print(f'  Optimised:    {stats_opt["mean"]:.1f} us')
    print(f'  Unoptimised:  {stats_unopt["mean"]:.1f} us')
    print(f'  Speedup:      {speedup:.2f}x')

    # Phrase matching: position_set (O(1)) vs positions list (O(n))
    print("\n--- Phrase Match: set lookup vs list scan ---")
    test_phrase = ["good", "friends"]
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
        print(f'  Phrase: {test_phrase} on {test_page}')
        print(f'  Optimised (set):  {stats_opt["mean"]:.1f} us')
        print(f'  Unoptimised (list): {stats_unopt["mean"]:.1f} us')
        print(f'  Speedup:          {speedup:.2f}x')
    else:
        print("  (no matching pages for phrase benchmark)")

    # --- Trie suggest ---
    print("\n--- Trie Autocomplete ---")
    trie = Trie.from_index(indexer.index)
    prefixes = ["lo", "fri", "th", "a"]
    for prefix in prefixes:
        stats = _time_fn(lambda p=prefix: trie.suggest(p))
        results = trie.suggest(prefix)
        print(f'  suggest("{prefix}"): {stats["mean"]:.1f} us mean, '
              f'{len(results)} suggestions')

    # --- Spell check ---
    print("\n--- Spell Correction ---")
    vocab = indexer.get_vocabulary()
    checker = SpellChecker(vocab)
    typos = ["lovee", "freinds", "wrold", "thinkng"]
    for typo in typos:
        stats = _time_fn(lambda t=typo: checker.suggest(t), iterations=100)
        suggestions = checker.suggest(typo)
        words = [s[0] for s in suggestions]
        print(f'  suggest("{typo}"): {stats["mean"]:.0f} us mean → {words}')

    print("\n" + "=" * 70)
    print("Benchmark complete.")
    print("=" * 70)


if __name__ == "__main__":
    run_benchmark()

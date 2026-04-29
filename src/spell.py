"""Spelling correction using Levenshtein edit distance."""

from __future__ import annotations


def _levenshtein(a: str, b: str) -> int:
    if len(a) < len(b):
        return _levenshtein(b, a)

    if len(b) == 0:
        return len(a)

    prev_row = list(range(len(b) + 1))
    for i, ca in enumerate(a):
        curr_row = [i + 1]
        for j, cb in enumerate(b):
            cost = 0 if ca == cb else 1
            curr_row.append(min(
                prev_row[j + 1] + 1,      # deletion
                curr_row[j] + 1,           # insertion
                prev_row[j] + cost,        # substitution
            ))
        prev_row = curr_row

    return prev_row[-1]


class SpellChecker:
    def __init__(self, vocabulary: list[str], max_distance: int = 2) -> None:
        self.vocabulary = vocabulary
        self.max_distance = max_distance
        self._by_length: dict[int, list[str]] = {}
        for word in vocabulary:
            length = len(word)
            if length not in self._by_length:
                self._by_length[length] = []
            self._by_length[length].append(word)

    def suggest(self, word: str, top_n: int = 3) -> list[tuple[str, int]]:
        """Return the closest words from the vocabulary.

        Only considers words within max_distance edits.
        Optimisation: only compares words of similar length (±max_distance)
        and same first character when possible.

        Returns list of (word, distance) sorted by distance ascending.
        """
        word_lower = word.lower()
        candidates: list[tuple[str, int]] = []

        length = len(word_lower)
        check_lengths = range(
            max(1, length - self.max_distance),
            length + self.max_distance + 1,
        )

        checked: set[str] = set()
        for l in check_lengths:
            for vocab_word in self._by_length.get(l, []):
                if vocab_word in checked:
                    continue
                checked.add(vocab_word)
                dist = _levenshtein(word_lower, vocab_word)
                if dist <= self.max_distance and dist > 0:
                    candidates.append((vocab_word, dist))

        candidates.sort(key=lambda x: x[1])
        return candidates[:top_n]

    def check(self, word: str) -> bool:
        return word.lower() in set(self.vocabulary)

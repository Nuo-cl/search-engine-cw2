"""Prefix tree (Trie) for real-time autocomplete suggestions."""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class TrieNode:
    children: dict[str, TrieNode] = field(default_factory=dict)
    is_word: bool = False
    frequency: int = 0


class Trie:
    def __init__(self) -> None:
        self.root = TrieNode()

    def insert(self, word: str, frequency: int = 1) -> None:
        node = self.root
        for char in word:
            if char not in node.children:
                node.children[char] = TrieNode()
            node = node.children[char]
        node.is_word = True
        node.frequency = frequency

    def search(self, word: str) -> bool:
        node = self._find_node(word)
        return node is not None and node.is_word

    def _find_node(self, prefix: str) -> TrieNode | None:
        node = self.root
        for char in prefix:
            if char not in node.children:
                return None
            node = node.children[char]
        return node

    def suggest(self, prefix: str, max_results: int = 10) -> list[tuple[str, int]]:
        """Return words starting with prefix, sorted by frequency descending.

        Returns list of (word, frequency) tuples.
        """
        node = self._find_node(prefix)
        if node is None:
            return []

        results: list[tuple[str, int]] = []
        self._collect_words(node, prefix, results)
        results.sort(key=lambda x: x[1], reverse=True)
        return results[:max_results]

    def _collect_words(
        self, node: TrieNode, prefix: str, results: list[tuple[str, int]]
    ) -> None:
        if node.is_word:
            results.append((prefix, node.frequency))
        for char, child in node.children.items():
            self._collect_words(child, prefix + char, results)

    @classmethod
    def from_index(cls, index: dict, df_key: str = "df") -> Trie:
        """Build a Trie from an inverted index, using document frequency as weight."""
        trie = cls()
        for word, entry in index.items():
            df = entry.df if hasattr(entry, "df") else entry.get(df_key, 1)
            trie.insert(word, frequency=df)
        return trie

    @classmethod
    def from_word_list(cls, words: dict[str, int]) -> Trie:
        """Build a Trie from a {word: frequency} mapping."""
        trie = cls()
        for word, freq in words.items():
            trie.insert(word, frequency=freq)
        return trie

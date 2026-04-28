"""Query parser supporting advanced search syntax.

Supported syntax:
    word                    Basic search
    word1 word2             AND (default, intersection)
    "exact phrase"          Phrase matching (verifies word order via positions)
    word1 OR word2          OR (union)
    -word                   Exclude pages containing word
    --tag tagname           Filter by tag
    --author authorname     Filter by author
"""

from __future__ import annotations

import re
import shlex
from dataclasses import dataclass, field


@dataclass
class Query:
    must_include: list[str] = field(default_factory=list)
    phrases: list[list[str]] = field(default_factory=list)
    should_include: list[str] = field(default_factory=list)
    must_exclude: list[str] = field(default_factory=list)
    filter_tag: str | None = None
    filter_author: str | None = None

    @property
    def is_empty(self) -> bool:
        return (
            not self.must_include
            and not self.phrases
            and not self.should_include
            and not self.must_exclude
            and self.filter_tag is None
            and self.filter_author is None
        )


WORD_PATTERN = re.compile(r"[a-z0-9]+(?:'[a-z]+)?")


def _tokenize_words(text: str) -> list[str]:
    return WORD_PATTERN.findall(text.lower())


def parse_query(raw: str) -> Query:
    """Parse a raw query string into a structured Query object."""
    query = Query()
    raw = raw.strip()
    if not raw:
        return query

    # Extract --tag and --author flags first
    raw, query.filter_tag = _extract_flag(raw, "--tag")
    raw, query.filter_author = _extract_flag(raw, "--author")

    # Extract quoted phrases
    raw, phrases = _extract_phrases(raw)
    for phrase_text in phrases:
        words = _tokenize_words(phrase_text)
        if words:
            query.phrases.append(words)

    # Split remaining tokens, respecting OR operator
    tokens = raw.split()
    i = 0
    while i < len(tokens):
        token = tokens[i]

        if token == "OR" and i > 0 and i < len(tokens) - 1:
            # Move the previous must_include term to should_include
            if query.must_include:
                prev = query.must_include.pop()
                if prev not in query.should_include:
                    query.should_include.append(prev)
            # Next token goes to should_include
            i += 1
            if i < len(tokens):
                next_token = tokens[i]
                words = _tokenize_words(next_token)
                for w in words:
                    if w not in query.should_include:
                        query.should_include.append(w)
        elif token.startswith("-") and len(token) > 1 and token != "-":
            words = _tokenize_words(token[1:])
            query.must_exclude.extend(words)
        else:
            words = _tokenize_words(token)
            query.must_include.extend(words)

        i += 1

    return query


def _extract_flag(raw: str, flag: str) -> tuple[str, str | None]:
    """Extract a --flag value from the raw query string.

    Handles both --flag value and --flag "multi word value".
    Returns the remaining query string and the extracted value (or None).
    """
    pattern = re.compile(
        rf'{re.escape(flag)}\s+"([^"]+)"'  # --flag "multi word"
        rf'|{re.escape(flag)}\s+(\S+)',     # --flag single_word
        re.IGNORECASE,
    )
    match = pattern.search(raw)
    if match:
        value = (match.group(1) or match.group(2)).lower().strip()
        remaining = raw[:match.start()] + raw[match.end():]
        return remaining.strip(), value
    return raw, None


def _extract_phrases(raw: str) -> tuple[str, list[str]]:
    """Extract all "quoted phrases" from the query string.

    Returns the remaining query string and a list of phrase texts.
    """
    phrases: list[str] = []
    pattern = re.compile(r'"([^"]+)"')
    for match in pattern.finditer(raw):
        phrases.append(match.group(1))
    remaining = pattern.sub("", raw).strip()
    remaining = re.sub(r"\s+", " ", remaining)
    return remaining, phrases

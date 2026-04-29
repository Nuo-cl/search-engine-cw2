"""Shared fixtures for all test modules."""

from __future__ import annotations

import pytest

from src.crawler import CrawledPage, Quote
from src.indexer import Indexer
from src.search import SearchEngine


SAMPLE_HTML_PAGE1 = """
<html><head><title>Quotes to Scrape</title></head><body>
<div class="quote">
    <span class="text">“The world as we have created it is a process of our thinking. It cannot be changed without changing our thinking.”</span>
    <small class="author">Albert Einstein</small>
    <div class="tags"><a class="tag" href="/tag/change/">change</a><a class="tag" href="/tag/thinking/">thinking</a></div>
</div>
<div class="quote">
    <span class="text">“Love all, trust a few, do wrong to none.”</span>
    <small class="author">William Shakespeare</small>
    <div class="tags"><a class="tag" href="/tag/love/">love</a><a class="tag" href="/tag/trust/">trust</a></div>
</div>
<nav><ul class="pager"><li class="next"><a href="/page/2/">Next</a></li></ul></nav>
</body></html>
"""

SAMPLE_HTML_PAGE2 = """
<html><head><title>Quotes to Scrape</title></head><body>
<div class="quote">
    <span class="text">“Good friends, good books, and a sleepy conscience: this is the ideal life.”</span>
    <small class="author">Mark Twain</small>
    <div class="tags"><a class="tag" href="/tag/books/">books</a><a class="tag" href="/tag/friendship/">friendship</a><a class="tag" href="/tag/life/">life</a></div>
</div>
<div class="quote">
    <span class="text">“Life is what happens to us while we are making other plans.”</span>
    <small class="author">Allen Saunders</small>
    <div class="tags"><a class="tag" href="/tag/life/">life</a><a class="tag" href="/tag/plans/">plans</a></div>
</div>
<nav><ul class="pager"></ul></nav>
</body></html>
"""

SAMPLE_HTML_EMPTY = """
<html><head><title>Quotes to Scrape</title></head><body>
<nav><ul class="pager"></ul></nav>
</body></html>
"""


@pytest.fixture
def sample_pages() -> list[CrawledPage]:
    return [
        CrawledPage(url="https://quotes.toscrape.com/page/1/", quotes=[
            Quote(
                text="The world as we have created it is a process of our thinking. It cannot be changed without changing our thinking.",
                author="Albert Einstein",
                tags=["change", "thinking"],
            ),
            Quote(
                text="Love all, trust a few, do wrong to none.",
                author="William Shakespeare",
                tags=["love", "trust"],
            ),
            Quote(
                text="It is not a lack of love, but a lack of friendship that makes unhappy marriages.",
                author="Friedrich Nietzsche",
                tags=["love", "friendship"],
            ),
        ]),
        CrawledPage(url="https://quotes.toscrape.com/page/2/", quotes=[
            Quote(
                text="Good friends, good books, and a sleepy conscience: this is the ideal life.",
                author="Mark Twain",
                tags=["books", "friendship", "life"],
            ),
            Quote(
                text="Life is what happens to us while we are making other plans.",
                author="Allen Saunders",
                tags=["life", "plans"],
            ),
        ]),
        CrawledPage(url="https://quotes.toscrape.com/page/3/", quotes=[
            Quote(
                text="The person, be it gentleman or lady, who has not pleasure in a good novel, must be intolerably stupid.",
                author="Jane Austen",
                tags=["books", "humor"],
            ),
        ]),
    ]


@pytest.fixture
def built_indexer(sample_pages) -> Indexer:
    indexer = Indexer()
    indexer.build(sample_pages)
    return indexer


@pytest.fixture
def search_engine(built_indexer) -> SearchEngine:
    return SearchEngine(built_indexer)

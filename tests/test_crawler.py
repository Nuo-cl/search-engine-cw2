"""Tests for the web crawler module."""

from __future__ import annotations

import responses
import pytest

from src.crawler import Crawler, CrawlerError
from tests.conftest import SAMPLE_HTML_PAGE1, SAMPLE_HTML_PAGE2, SAMPLE_HTML_EMPTY

BASE_URL = "https://quotes.toscrape.com/"


class TestCrawlerParsing:
    """Test HTML parsing without network requests."""

    def test_parse_quotes(self):
        crawler = Crawler(base_url=BASE_URL, politeness_window=0)
        page = crawler._parse_page(BASE_URL, SAMPLE_HTML_PAGE1)

        assert page.url == BASE_URL
        assert len(page.quotes) == 2
        assert page.quotes[0].author == "Albert Einstein"
        assert "change" in page.quotes[0].tags
        assert "thinking" in page.quotes[0].tags

    def test_parse_quote_text_strips_smart_quotes(self):
        crawler = Crawler(base_url=BASE_URL, politeness_window=0)
        page = crawler._parse_page(BASE_URL, SAMPLE_HTML_PAGE1)

        text = page.quotes[0].text
        assert not text.startswith("“")
        assert not text.endswith("”")

    def test_parse_empty_page(self):
        crawler = Crawler(base_url=BASE_URL, politeness_window=0)
        page = crawler._parse_page(BASE_URL, SAMPLE_HTML_EMPTY)
        assert len(page.quotes) == 0

    def test_find_next_page(self):
        crawler = Crawler(base_url=BASE_URL, politeness_window=0)
        next_url = crawler._find_next_page(SAMPLE_HTML_PAGE1)
        assert next_url is not None
        assert "/page/2/" in next_url

    def test_find_next_page_none_on_last(self):
        crawler = Crawler(base_url=BASE_URL, politeness_window=0)
        next_url = crawler._find_next_page(SAMPLE_HTML_PAGE2)
        assert next_url is None


class TestCrawlerCrawl:
    """Test full crawl flow with mocked HTTP responses."""

    @responses.activate
    def test_crawl_two_pages(self):
        responses.add(responses.GET, BASE_URL, body=SAMPLE_HTML_PAGE1, status=200)
        responses.add(
            responses.GET, BASE_URL + "page/2/", body=SAMPLE_HTML_PAGE2, status=200
        )

        crawler = Crawler(base_url=BASE_URL, politeness_window=0)
        pages = crawler.crawl()

        assert len(pages) == 2
        assert len(pages[0].quotes) == 2
        assert len(pages[1].quotes) == 2

    @responses.activate
    def test_crawl_single_page(self):
        responses.add(responses.GET, BASE_URL, body=SAMPLE_HTML_PAGE2, status=200)

        crawler = Crawler(base_url=BASE_URL, politeness_window=0)
        pages = crawler.crawl()

        assert len(pages) == 1

    @responses.activate
    def test_crawl_callback(self):
        responses.add(responses.GET, BASE_URL, body=SAMPLE_HTML_PAGE2, status=200)

        crawler = Crawler(base_url=BASE_URL, politeness_window=0)
        callback_pages = []
        crawler.crawl(on_page_crawled=lambda num, page: callback_pages.append(num))

        assert callback_pages == [1]

    @responses.activate
    def test_crawl_no_duplicate_visits(self):
        responses.add(responses.GET, BASE_URL, body=SAMPLE_HTML_PAGE2, status=200)

        crawler = Crawler(base_url=BASE_URL, politeness_window=0)
        crawler.crawl()

        assert len(crawler.visited_urls) == 1

    @responses.activate
    def test_crawl_handles_server_error(self):
        responses.add(responses.GET, BASE_URL, status=500)
        responses.add(responses.GET, BASE_URL, status=500)
        responses.add(responses.GET, BASE_URL, status=500)

        crawler = Crawler(base_url=BASE_URL, politeness_window=0, max_retries=3, timeout=5)
        pages = crawler.crawl()

        assert len(pages) == 0

    @responses.activate
    def test_crawl_retries_then_succeeds(self):
        responses.add(responses.GET, BASE_URL, status=500)
        responses.add(responses.GET, BASE_URL, body=SAMPLE_HTML_PAGE2, status=200)

        crawler = Crawler(base_url=BASE_URL, politeness_window=0, max_retries=3, timeout=5)
        pages = crawler.crawl()

        assert len(pages) == 1


class TestCrawlerConfig:
    def test_base_url_trailing_slash(self):
        crawler = Crawler(base_url="https://example.com")
        assert crawler.base_url == "https://example.com/"

        crawler2 = Crawler(base_url="https://example.com/")
        assert crawler2.base_url == "https://example.com/"

    def test_custom_politeness(self):
        crawler = Crawler(politeness_window=10)
        assert crawler.politeness_window == 10

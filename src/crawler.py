"""Web crawler for quotes.toscrape.com."""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from urllib.parse import urljoin

import requests
from bs4 import BeautifulSoup

logger = logging.getLogger(__name__)

DEFAULT_BASE_URL = "https://quotes.toscrape.com/"
POLITENESS_WINDOW = 6
MAX_RETRIES = 3
REQUEST_TIMEOUT = 15


@dataclass
class Quote:
    text: str
    author: str
    tags: list[str]


@dataclass
class CrawledPage:
    url: str
    quotes: list[Quote]
    crawled_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))


class CrawlerError(Exception):
    pass


class Crawler:
    def __init__(
        self,
        base_url: str = DEFAULT_BASE_URL,
        politeness_window: float = POLITENESS_WINDOW,
        max_retries: int = MAX_RETRIES,
        timeout: float = REQUEST_TIMEOUT,
    ) -> None:
        self.base_url = base_url.rstrip("/") + "/"
        self.politeness_window = politeness_window
        self.max_retries = max_retries
        self.timeout = timeout
        self.session = requests.Session()
        self.session.headers.update({
            "User-Agent": "SearchEngineCW2/1.0 (University of Leeds Student Project)",
        })
        self.visited_urls: set[str] = set()
        self.pages: list[CrawledPage] = []
        self._last_request_time: float = 0.0

    def _wait_politeness(self) -> None:
        elapsed = time.monotonic() - self._last_request_time
        if elapsed < self.politeness_window:
            wait_time = self.politeness_window - elapsed
            logger.debug("Waiting %.1fs for politeness window", wait_time)
            time.sleep(wait_time)

    def _fetch(self, url: str) -> str:
        for attempt in range(1, self.max_retries + 1):
            self._wait_politeness()
            try:
                logger.info("Fetching %s (attempt %d/%d)", url, attempt, self.max_retries)
                response = self.session.get(url, timeout=self.timeout)
                self._last_request_time = time.monotonic()
                response.raise_for_status()
                return response.text
            except requests.exceptions.HTTPError as e:
                logger.warning("HTTP error for %s: %s", url, e)
                if response.status_code >= 500 and attempt < self.max_retries:
                    backoff = 2 ** attempt
                    logger.info("Retrying in %ds...", backoff)
                    time.sleep(backoff)
                    continue
                raise CrawlerError(f"HTTP error fetching {url}: {e}") from e
            except requests.exceptions.ConnectionError as e:
                logger.warning("Connection error for %s: %s", url, e)
                if attempt < self.max_retries:
                    backoff = 2 ** attempt
                    logger.info("Retrying in %ds...", backoff)
                    time.sleep(backoff)
                    continue
                raise CrawlerError(f"Connection error fetching {url}: {e}") from e
            except requests.exceptions.Timeout as e:
                logger.warning("Timeout for %s: %s", url, e)
                if attempt < self.max_retries:
                    backoff = 2 ** attempt
                    logger.info("Retrying in %ds...", backoff)
                    time.sleep(backoff)
                    continue
                raise CrawlerError(f"Timeout fetching {url}: {e}") from e
        raise CrawlerError(f"Failed to fetch {url} after {self.max_retries} attempts")

    def _parse_page(self, url: str, html: str) -> CrawledPage:
        soup = BeautifulSoup(html, "lxml")
        quotes: list[Quote] = []

        for quote_div in soup.select("div.quote"):
            text_elem = quote_div.select_one("span.text")
            author_elem = quote_div.select_one("small.author")
            tag_elems = quote_div.select("a.tag")

            if text_elem and author_elem:
                text = text_elem.get_text(strip=True)
                # Remove surrounding quotes (“ and ”)
                text = text.strip("“”")
                author = author_elem.get_text(strip=True)
                tags = [tag.get_text(strip=True) for tag in tag_elems]
                quotes.append(Quote(text=text, author=author, tags=tags))

        return CrawledPage(url=url, quotes=quotes)

    def _find_next_page(self, html: str) -> str | None:
        soup = BeautifulSoup(html, "lxml")
        next_li = soup.select_one("li.next > a")
        if next_li and next_li.get("href"):
            return urljoin(self.base_url, next_li["href"])
        return None

    def crawl(self, on_page_crawled: callable | None = None) -> list[CrawledPage]:
        """Crawl all pages starting from the base URL.

        Args:
            on_page_crawled: Optional callback called after each page is crawled,
                receives (page_number, page) as arguments.

        Returns:
            List of all crawled pages.
        """
        self.visited_urls.clear()
        self.pages.clear()
        current_url: str | None = self.base_url
        page_num = 0

        while current_url and current_url not in self.visited_urls:
            page_num += 1
            try:
                html = self._fetch(current_url)
                self.visited_urls.add(current_url)
                page = self._parse_page(current_url, html)
                self.pages.append(page)

                logger.info(
                    "Page %d: %s — %d quotes extracted",
                    page_num, current_url, len(page.quotes),
                )

                if on_page_crawled:
                    on_page_crawled(page_num, page)

                current_url = self._find_next_page(html)
            except CrawlerError as e:
                logger.error("Skipping page %s: %s", current_url, e)
                break

        logger.info(
            "Crawling complete: %d pages, %d total quotes",
            len(self.pages),
            sum(len(p.quotes) for p in self.pages),
        )
        return self.pages

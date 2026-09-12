"""Discover LRB articles and archive their full text as raw Markdown."""

from __future__ import annotations

import logging
import re
from pathlib import Path
from urllib.parse import urljoin

import requests
from bs4 import BeautifulSoup
from markdownify import markdownify

from scripts.raw_utils import count_paragraphs, get_existing_urls, save_raw_article
from scripts.utils import canonicalize_url


logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)

SOURCE = "LRB"
XML_FILE = Path("lrb_ai_enhanced.xml")
RAW_ROOT = Path("raw")
CURRENT_ISSUE_URL = "https://www.lrb.co.uk/the-paper"
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Referer": "https://www.google.com/",
}

_BODY_SELECTORS = (
    "[itemprop='articleBody']",
    ".article-body",
    ".article__body",
    ".article-page__body",
    ".entry-content",
    "article",
    "main",
)
_FURNITURE = re.compile(
    r"(?:subscribe|newsletter|related|recommended|promo|paywall|share|social|cookie|footer|navigation)",
    re.I,
)


def _meta(soup: BeautifulSoup, *selectors: str) -> str:
    for selector in selectors:
        node = soup.select_one(selector)
        if node and node.get("content"):
            return str(node["content"]).strip()
    return ""


def _visible_text(soup: BeautifulSoup, selectors: tuple[str, ...]) -> str:
    for selector in selectors:
        node = soup.select_one(selector)
        if node:
            return node.get_text(" ", strip=True)
    return ""


def _clean_body_markdown(soup: BeautifulSoup) -> str:
    body = next((node for selector in _BODY_SELECTORS if (node := soup.select_one(selector))), None)
    if body is None:
        return ""
    for node in body.select("script, style, nav, footer, aside, form, button, noscript, svg"):
        node.decompose()
    for node in reversed(body.find_all(True)):
        marker = " ".join(
            [str(node.get("id", "")), *[str(value) for value in node.get("class", [])]]
        )
        if marker and _FURNITURE.search(marker):
            node.decompose()
    text = markdownify(str(body), heading_style="ATX").strip()
    return re.sub(r"\n{3,}", "\n\n", text)


def parse_article_html(html: str, url: str) -> dict[str, str | int]:
    soup = BeautifulSoup(html, "html.parser")
    title = _visible_text(soup, ("h1",))
    if not title:
        title = _meta(soup, "meta[property='og:title']", "meta[name='twitter:title']")
    if not title:
        title = url.rstrip("/").rsplit("/", 1)[-1]
    author = _meta(soup, "meta[name='author']", "meta[property='article:author']")
    if not author:
        author = _visible_text(soup, ("[rel='author']", ".byline", ".author"))
        author = re.sub(r"^\s*by\s+", "", author, flags=re.I).strip()
    published = _meta(
        soup,
        "meta[property='article:published_time']",
        "meta[name='date']",
        "meta[name='pub_date']",
    )
    if not published:
        time_node = soup.select_one("time[datetime]")
        published = str(time_node.get("datetime", "")).strip() if time_node else ""
    body = _clean_body_markdown(soup)
    return {
        "source": SOURCE,
        "title": title,
        "author": author,
        "url": canonicalize_url(url),
        "article_date": published[:10] if re.match(r"\d{4}-\d{2}-\d{2}", published) else "",
        "image_url": _meta(soup, "meta[property='og:image']", "meta[name='twitter:image']"),
        "text": body,
        "raw_length": len(html),
        "paragraph_count": count_paragraphs(body),
    }


def parse_latest_article_urls(
    html: str, existing_urls: set[str], max_items: int = 50
) -> list[str]:
    urls: list[str] = []
    soup = BeautifulSoup(html, "html.parser")
    for anchor in soup.find_all("a", href=True):
        href = str(anchor["href"])
        if not re.match(r"^/the-paper/v\d+/n\d+/[^/]+/.+", href):
            continue
        try:
            url = canonicalize_url(urljoin("https://www.lrb.co.uk", href))
        except ValueError:
            continue
        if url not in existing_urls and url not in urls:
            urls.append(url)
            if len(urls) >= max_items:
                break
    return urls


def get_latest_article_urls(existing_urls: set[str], max_items: int = 50) -> list[str]:
    logger.info("Scanning the current LRB issue: %s", CURRENT_ISSUE_URL)
    try:
        response = requests.get(CURRENT_ISSUE_URL, headers=HEADERS, timeout=30)
        response.raise_for_status()
    except requests.RequestException as exc:
        logger.error("LRB discovery failed: %s", exc)
        return []
    urls = parse_latest_article_urls(response.text, existing_urls, max_items=max_items)
    logger.info("LRB discovery found %d unprocessed articles", len(urls))
    return urls


def scrape_article(url: str) -> dict[str, str | int] | None:
    try:
        response = requests.get(url, headers=HEADERS, timeout=30)
        status = response.status_code
        response.raise_for_status()
        article = parse_article_html(response.text, url)
        article["http_status"] = status
        return article
    except requests.RequestException as exc:
        logger.error("LRB fetch failed for %s: %s", url, exc)
        return None


def main() -> int:
    existing_urls = get_existing_urls(RAW_ROOT, XML_FILE)
    urls = get_latest_article_urls(existing_urls, max_items=50)
    saved = 0
    for url in urls:
        logger.info("Fetching LRB article: %s", url)
        article = scrape_article(url)
        if article and save_raw_article(article, RAW_ROOT):
            saved += 1
    logger.info("LRB run complete: discovered=%d saved=%d", len(urls), saved)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

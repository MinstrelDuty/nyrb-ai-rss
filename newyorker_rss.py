"""Collect the New Yorker *Under Review* section into the raw archive.

The New Yorker exposes a narrowly scoped section ItemList and article JSON-LD.
The collector deliberately uses those public representations instead of trying
to reconstruct article pages or bypass access controls.
"""

from __future__ import annotations

import json
import logging
import re
from pathlib import Path
from urllib.parse import urljoin, urlsplit

import requests
from bs4 import BeautifulSoup

from scripts.raw_utils import count_paragraphs, get_existing_urls, save_raw_article
from scripts.utils import canonicalize_url


logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)

SOURCE = "NEWYORKER"
SECTION_URL = "https://www.newyorker.com/books/under-review"
RAW_ROOT = Path("raw")
HEADERS = {
    "User-Agent": "Mozilla/5.0 (compatible; NYRB-AI-RSS/1.0; +https://github.com/MinstrelDuty/nyrb-ai-rss)",
    "Accept": "text/html,application/xhtml+xml",
}
_MARKER_RE = re.compile(r"\b(?:subscribe|sign\s+in|log\s+in|continue\s+reading)\b", re.I)


def _jsonld_objects(html: str):
    """Yield JSON-LD objects, including objects nested in @graph/lists."""

    soup = BeautifulSoup(html, "html.parser")

    def walk(value):
        if isinstance(value, list):
            for item in value:
                yield from walk(item)
        elif isinstance(value, dict):
            yield value
            if "@graph" in value:
                yield from walk(value["@graph"])

    for node in soup.select("script[type='application/ld+json']"):
        raw = node.string or node.get_text()
        try:
            yield from walk(json.loads(raw))
        except (TypeError, json.JSONDecodeError):
            continue


def _first(value):
    if isinstance(value, list):
        return value[0] if value else ""
    return value


def _author_name(value) -> str:
    values = value if isinstance(value, list) else [value]
    names = []
    for item in values:
        if isinstance(item, dict):
            item = item.get("name", "")
        if str(item).strip():
            names.append(str(item).strip())
    return ", ".join(names)


def _image_url(value) -> str:
    value = _first(value)
    if isinstance(value, dict):
        value = value.get("url", "")
    return str(value or "").strip()


def _date_only(value: str) -> str:
    match = re.match(r"(\d{4}-\d{2}-\d{2})", str(value or ""))
    return match.group(1) if match else ""


def _has_type(value, expected: str) -> bool:
    return value == expected or (isinstance(value, list) and expected in value)


def parse_section_urls(html: str, existing_urls: set[str], max_items: int = 20) -> list[str]:
    """Return new, strictly Under Review URLs from the section ItemList."""

    candidates: list[str] = []
    for obj in _jsonld_objects(html):
        if not _has_type(obj.get("@type"), "ItemList"):
            continue
        entries = obj.get("itemListElement", [])
        for entry in entries:
            value = entry.get("url") if isinstance(entry, dict) else entry
            if not value and isinstance(entry, dict):
                item = entry.get("item")
                value = item.get("@id") if isinstance(item, dict) else item
            if value:
                candidates.append(str(value))

    # A small HTML fallback keeps discovery resilient if the publisher removes
    # JSON-LD, while the path guard still prevents unrelated section links.
    if not candidates:
        soup = BeautifulSoup(html, "html.parser")
        candidates.extend(
            urljoin(SECTION_URL, str(anchor["href"]))
            for anchor in soup.find_all("a", href=True)
            if "/books/under-review/" in str(anchor["href"])
        )

    urls: list[str] = []
    for value in candidates:
        try:
            url = canonicalize_url(urljoin(SECTION_URL, value))
        except ValueError:
            continue
        parsed = urlsplit(url)
        if parsed.netloc != "www.newyorker.com" or not parsed.path.startswith("/books/under-review/"):
            continue
        if url in existing_urls or url in urls:
            continue
        urls.append(url)
        if len(urls) >= max_items:
            break
    return urls


def parse_article_html(html: str, url: str) -> dict[str, str | int] | None:
    """Parse a free, complete Under Review article from NewsArticle JSON-LD."""

    canonical = canonicalize_url(url)
    if not urlsplit(canonical).path.startswith("/books/under-review/"):
        return None
    article = next(
        (
            obj
            for obj in _jsonld_objects(html)
            if _has_type(obj.get("@type"), "NewsArticle") or _has_type(obj.get("@type"), "Article")
        ),
        None,
    )
    if not article or article.get("isAccessibleForFree") is False:
        return None
    section = str(article.get("articleSection", "")).lower()
    if section and "under review" not in section:
        return None
    body = str(article.get("articleBody", "")).strip()
    body = re.sub(r"\s+", " ", body)
    if len(body) < 800 or _MARKER_RE.search(body) or re.search(r"(?:…|\.\.\.)\s*$", body):
        return None
    title = str(article.get("headline", "")).strip()
    if not title:
        return None
    return {
        "source": SOURCE,
        "title": title,
        "author": _author_name(article.get("author", "")),
        "url": canonical,
        "article_date": _date_only(article.get("datePublished") or article.get("dateModified", "")),
        "image_url": _image_url(article.get("image", "")),
        "text": body,
        "raw_length": len(html),
        "paragraph_count": count_paragraphs(body),
    }


def get_latest_article_urls(existing_urls: set[str], max_items: int = 20) -> list[str]:
    try:
        response = requests.get(SECTION_URL, headers=HEADERS, timeout=30)
        response.raise_for_status()
    except requests.RequestException as exc:
        logger.error("New Yorker discovery failed: %s", exc)
        return []
    urls = parse_section_urls(response.text, existing_urls, max_items=max_items)
    logger.info("New Yorker discovery found %d unprocessed articles", len(urls))
    return urls


def scrape_article(url: str) -> dict[str, str | int] | None:
    try:
        response = requests.get(url, headers=HEADERS, timeout=30)
        response.raise_for_status()
        article = parse_article_html(response.text, url)
        if article:
            article["http_status"] = response.status_code
        return article
    except requests.RequestException as exc:
        logger.error("New Yorker fetch failed for %s: %s", url, exc)
        return None


def main() -> int:
    existing = get_existing_urls(RAW_ROOT)
    urls = get_latest_article_urls(existing, max_items=10)
    saved = 0
    for url in urls:
        article = scrape_article(url)
        if article and save_raw_article(article, RAW_ROOT):
            saved += 1
    logger.info("New Yorker run complete: discovered=%d saved=%d", len(urls), saved)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

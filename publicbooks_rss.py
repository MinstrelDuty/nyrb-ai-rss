"""Collect complete Public Books *Reviews* into the raw archive.

The publisher's general RSS feed is used only for scoped article discovery.
Article text is fetched through the same Jina Markdown reader used by the TLS
collector, then rejected unless it looks like a complete article.
"""

from __future__ import annotations

import logging
import re
import time
from email.utils import parsedate_to_datetime
from pathlib import Path
from xml.etree import ElementTree as ET

import requests

from scripts.raw_utils import count_paragraphs, get_existing_urls, save_raw_article
from scripts.utils import canonicalize_url


logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)

SOURCE = "PUBLICBOOKS"
FEED_URL = "https://www.publicbooks.org/feed/"
RAW_ROOT = Path("raw")
FEED_ATTEMPTS = 3
JINA_HEADERS = {"Accept": "text/markdown", "X-No-Cache": "true"}
FEED_HEADERS = {
    "User-Agent": "NYRB-AI-RSS/1.0 (+https://github.com/MinstrelDuty/nyrb-ai-rss)",
    "Accept": "application/rss+xml, application/xml;q=0.9, */*;q=0.1",
}
_DC_CREATOR = "{http://purl.org/dc/elements/1.1/}creator"
_MEDIA_CONTENT = "{http://search.yahoo.com/mrss/}content"
_BLOCKED_RE = re.compile(
    r"\b(?:sgcaptcha|captcha|verify you are human|access to this page is forbidden|access denied)\b",
    re.I,
)
_PREVIEW_RE = re.compile(r"\b(?:subscribe|sign\s+in|log\s+in|continue\s+reading|preview[- ]only)\b", re.I)


def _text(node: ET.Element | None) -> str:
    return (node.text or "").strip() if node is not None else ""


def _article_date(value: str) -> str:
    value = str(value or "").strip()
    match = re.match(r"(\d{4}-\d{2}-\d{2})", value)
    if match:
        return match.group(1)
    try:
        return parsedate_to_datetime(value).date().isoformat()
    except (TypeError, ValueError, OverflowError):
        return ""


def parse_review_feed(
    xml_text: str, existing_urls: set[str], max_items: int = 30
) -> list[dict[str, str]]:
    """Return new canonical URLs whose official feed category is Reviews."""

    known_urls: set[str] = set()
    for value in existing_urls:
        try:
            known_urls.add(canonicalize_url(value))
        except (TypeError, ValueError):
            continue
    try:
        root = ET.fromstring(xml_text)
    except ET.ParseError as exc:
        logger.warning("Public Books feed could not be parsed: %s", exc)
        return []

    articles: list[dict[str, str]] = []
    for item in root.findall("./channel/item"):
        categories = {_text(node).casefold() for node in item.findall("category")}
        if "reviews" not in categories:
            continue
        try:
            url = canonicalize_url(_text(item.find("link")))
        except (TypeError, ValueError):
            continue
        if url in known_urls or any(entry["url"] == url for entry in articles):
            continue
        title = _text(item.find("title"))
        if not title:
            continue
        image = item.find(_MEDIA_CONTENT)
        enclosure = item.find("enclosure")
        image_url = ""
        if image is not None:
            image_url = str(image.get("url", "")).strip()
        if not image_url and enclosure is not None:
            image_url = str(enclosure.get("url", "")).strip()
        articles.append(
            {
                "title": title,
                "author": _text(item.find(_DC_CREATOR)),
                "url": url,
                "article_date": _article_date(_text(item.find("pubDate"))),
                "image_url": image_url,
            }
        )
        if len(articles) >= max_items:
            break
    return articles


def _preamble_value(text: str, label: str) -> str:
    match = re.search(rf"(?mi)^{re.escape(label)}:\s*(.+?)\s*$", text)
    return match.group(1).strip() if match else ""


def _clean_jina_body(text: str) -> str:
    marker = re.search(r"(?mi)^Markdown Content:\s*$", text)
    body = text[marker.end() :] if marker else text
    body = body.strip()
    # Jina occasionally puts global Public Books navigation after the article.
    footer = re.search(
        r"\n\s*(?:##\s+)?(?:Support Public Books|Subscribe to Public Books|Related Posts|Copyright ©)",
        body,
        re.I,
    )
    return body[: footer.start()].strip() if footer else body


def _byline_from_body(body: str) -> tuple[str, str]:
    byline = re.search(r"(?mi)^By\s+([^\n]+?)\s*$", body)
    if not byline:
        return "", body
    author = byline.group(1).strip()
    cleaned = (body[: byline.start()] + body[byline.end() :]).strip()
    return author, re.sub(r"\n{3,}", "\n\n", cleaned)


def _image_from_body(body: str) -> str:
    match = re.search(r"!\[[^\]]*\]\((https?://[^\s)]+)", body)
    return match.group(1) if match else ""


def _is_complete(body: str, raw_text: str) -> bool:
    if len(body) < 800 or _BLOCKED_RE.search(raw_text):
        return False
    if re.search(r"(?:…|\.\.\.)\s*$", body):
        return False
    # A page may legitimately mention these words, but they should not be the
    # tail of a complete review.  Checking the tail avoids false positives.
    return not _PREVIEW_RE.search(body[-600:])


def parse_jina_article(
    text: str, url: str, fallback: dict[str, str] | None = None
) -> dict[str, str | int] | None:
    """Parse and validate Jina Markdown; return None for incomplete pages."""

    fallback = fallback or {}
    body = _clean_jina_body(text)
    if not _is_complete(body, text):
        logger.warning("Skipping Public Books incomplete or blocked response: %s", url)
        return None
    try:
        canonical = canonicalize_url(url)
    except (TypeError, ValueError):
        return None
    title = _preamble_value(text, "Title") or str(fallback.get("title", "")).strip()
    author = _preamble_value(text, "Author") or str(fallback.get("author", "")).strip()
    byline, body = _byline_from_body(body)
    if not author:
        author = byline
    if not title:
        heading = re.search(r"(?mi)^#\s+(.+?)\s*$", body)
        title = heading.group(1).strip() if heading else ""
    if not title:
        return None
    return {
        "source": SOURCE,
        "title": title,
        "author": author,
        "url": canonical,
        "article_date": _article_date(_preamble_value(text, "Published Time"))
        or str(fallback.get("article_date", "")).strip(),
        "image_url": _image_from_body(body) or str(fallback.get("image_url", "")).strip(),
        "text": body,
        "raw_length": len(text),
        "paragraph_count": count_paragraphs(body),
    }


def get_latest_reviews(existing_urls: set[str], max_items: int = 20) -> list[dict[str, str]]:
    last_error = ""
    for attempt in range(1, FEED_ATTEMPTS + 1):
        try:
            response = requests.get(FEED_URL, headers=FEED_HEADERS, timeout=30)
            if response.status_code == 200 and "<rss" in response.text[:500].lower():
                articles = parse_review_feed(response.text, existing_urls, max_items=max_items)
                logger.info("Public Books RSS discovery found %d unprocessed Reviews", len(articles))
                return articles
            last_error = "status=%s, content-type=%s" % (
                response.status_code,
                response.headers.get("content-type", ""),
            )
        except requests.RequestException as exc:
            last_error = str(exc)
        if attempt < FEED_ATTEMPTS:
            logger.warning("Public Books RSS unavailable (%s); retrying", last_error)
            time.sleep(2)
    logger.warning("Public Books RSS is unavailable as XML (%s); skipping this run", last_error)
    return []


def scrape_article_via_jina(metadata: dict[str, str]) -> dict[str, str | int] | None:
    url = metadata["url"]
    try:
        response = requests.get(f"https://r.jina.ai/{url}", headers=JINA_HEADERS, timeout=45)
        response.raise_for_status()
    except requests.RequestException as exc:
        logger.error("Public Books Jina fetch failed for %s: %s", url, exc)
        return None
    article = parse_jina_article(response.text, url, metadata)
    if article:
        article["http_status"] = response.status_code
    return article


def main() -> int:
    existing = get_existing_urls(RAW_ROOT)
    reviews = get_latest_reviews(existing)
    saved = 0
    for metadata in reviews:
        article = scrape_article_via_jina(metadata)
        if article and save_raw_article(article, RAW_ROOT):
            saved += 1
    logger.info("Public Books run complete: discovered=%d saved=%d", len(reviews), saved)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

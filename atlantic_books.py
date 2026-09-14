"""Collect The Atlantic's official Books Atom feed into the raw archive."""

from __future__ import annotations

import html as html_lib
import logging
import re
from pathlib import Path
from urllib.parse import urlsplit
from xml.etree import ElementTree as ET

import requests
from bs4 import BeautifulSoup
from markdownify import markdownify

from scripts.raw_utils import count_paragraphs, get_existing_urls, save_raw_article
from scripts.utils import canonicalize_url


logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)

SOURCE = "ATLANTIC"
FEED_URL = "https://www.theatlantic.com/feed/books/"
RAW_ROOT = Path("raw")
HEADERS = {
    "User-Agent": "Mozilla/5.0 (compatible; NYRB-AI-RSS/1.0; +https://github.com/MinstrelDuty/nyrb-ai-rss)",
    "Accept": "application/atom+xml,application/xml,text/xml",
}
ATOM = "http://www.w3.org/2005/Atom"
MEDIA = "http://search.yahoo.com/mrss/"
_MARKER_RE = re.compile(r"\b(?:subscribe|sign\s+in|log\s+in|continue\s+reading)\b", re.I)


def _text(node: ET.Element | None) -> str:
    if node is None:
        return ""
    return "".join(node.itertext()).strip()


def _date_only(value: str) -> str:
    match = re.match(r"(\d{4}-\d{2}-\d{2})", str(value or ""))
    return match.group(1) if match else ""


def _clean_content(content: str) -> tuple[str, str]:
    decoded = html_lib.unescape(content or "")
    soup = BeautifulSoup(decoded, "html.parser")
    for node in soup.select("script, style, noscript, form, nav, footer, aside"):
        node.decompose()
    markdown = markdownify(str(soup), heading_style="ATX")
    markdown = re.sub(r"\n{3,}", "\n\n", markdown).strip()
    visible = re.sub(r"\s+", " ", soup.get_text(" ", strip=True)).strip()
    return markdown, visible


def _complete(body: str, visible: str) -> bool:
    if len(visible) < 1200:
        return False
    if _MARKER_RE.search(visible):
        return False
    return not re.search(r"(?:…|\.\.\.)\s*$", visible)


def parse_feed_entries(
    xml_text: str, existing_urls: set[str], max_items: int = 50
) -> list[dict[str, str | int]]:
    """Parse only substantial entries from the official Books Atom feed."""

    try:
        root = ET.fromstring(xml_text)
    except ET.ParseError:
        return []

    entries: list[dict[str, str | int]] = []
    for entry in root.findall(f"{{{ATOM}}}entry"):
        link = next(
            (
                str(node.get("href", "")).strip()
                for node in entry.findall(f"{{{ATOM}}}link")
                if node.get("rel", "alternate") == "alternate" and node.get("href")
            ),
            "",
        )
        if not link:
            continue
        try:
            url = canonicalize_url(link)
        except ValueError:
            continue
        path = urlsplit(url).path
        # The Books feed occasionally carries a very short poem/newsletter;
        # never widen this to unrelated Atlantic channels.
        if not (path.startswith("/books/") or path.startswith("/magazine/")):
            continue
        if url in existing_urls or any(item["url"] == url for item in entries):
            continue
        markdown, visible = _clean_content(_text(entry.find(f"{{{ATOM}}}content")))
        if not _complete(markdown, visible):
            continue
        author = _text(entry.find(f"{{{ATOM}}}author/{{{ATOM}}}name"))
        published = _text(entry.find(f"{{{ATOM}}}published")) or _text(
            entry.find(f"{{{ATOM}}}updated")
        )
        media = entry.find(f"{{{MEDIA}}}content")
        if media is None:
            media = entry.find(f"{{{MEDIA}}}thumbnail")
        image_url = str(media.get("url", "")).strip() if media is not None else ""
        entries.append(
            {
                "source": SOURCE,
                "title": _text(entry.find(f"{{{ATOM}}}title")),
                "author": author,
                "url": url,
                "article_date": _date_only(published),
                "image_url": image_url,
                "text": markdown,
                "raw_length": len(xml_text),
                "paragraph_count": count_paragraphs(markdown),
            }
        )
        if len(entries) >= max_items:
            break
    return entries


def get_latest_articles(existing_urls: set[str], max_items: int = 20) -> list[dict[str, str | int]]:
    try:
        response = requests.get(FEED_URL, headers=HEADERS, timeout=30)
        response.raise_for_status()
    except requests.RequestException as exc:
        logger.error("Atlantic Books feed failed: %s", exc)
        return []
    articles = parse_feed_entries(response.text, existing_urls, max_items=max_items)
    logger.info("Atlantic Books feed found %d unprocessed complete articles", len(articles))
    return articles


def main() -> int:
    existing = get_existing_urls(RAW_ROOT)
    articles = get_latest_articles(existing, max_items=10)
    saved = sum(bool(save_raw_article(article, RAW_ROOT, min_body_chars=1200)) for article in articles)
    logger.info("Atlantic Books run complete: discovered=%d saved=%d", len(articles), saved)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

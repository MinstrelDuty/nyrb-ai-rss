"""Discover TLS articles through sitemaps and archive Jina Markdown."""

from __future__ import annotations

import logging
import re
from datetime import datetime, timedelta
from email.utils import parsedate_to_datetime
from pathlib import Path

import requests

from scripts.raw_utils import count_paragraphs, get_existing_urls, save_raw_article
from scripts.utils import canonicalize_url


logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)

SOURCE = "TLS"
XML_FILE = Path("tls_ai_enhanced.xml")
RAW_ROOT = Path("raw")
SITEMAP_SHARDS = ("26", "25")
BLACKLIST = (
    "/author/", "/tag/", "/topics/", "/category/", "/issues/", "/feed/",
    "wp-json", "wp-content", "/crossword-quiz/", "/letters-to-the-editor/", "/highlights/",
)


def parse_sitemap_text(
    text: str,
    existing_urls: set[str],
    *,
    time_threshold: datetime,
) -> list[str]:
    found: list[str] = []
    matches = re.findall(
        r"(https://www\.the-tls\.com/[^\s<\"'\)]+).*?(\d{4}-\d{2}-\d{2})",
        text,
        re.DOTALL,
    )
    for link, lastmod in matches:
        clean_link = link.split("]", 1)[0].split(")", 1)[0]
        if len(clean_link.split("/")) <= 4 or any(value in clean_link for value in BLACKLIST):
            continue
        try:
            url = canonicalize_url(clean_link)
            modified = datetime.strptime(lastmod, "%Y-%m-%d")
        except ValueError:
            continue
        if modified >= time_threshold and url not in existing_urls and url not in found:
            found.append(url)
    return found


def get_latest_article_urls(existing_urls: set[str], max_items: int = 80) -> list[str]:
    time_threshold = datetime.now() - timedelta(days=8)
    found: list[str] = []
    headers = {"Accept": "text/plain", "X-No-Cache": "true"}
    logger.info("Scanning TLS sitemap window beginning %s", time_threshold.date())
    for shard in SITEMAP_SHARDS:
        sitemap_url = f"https://www.the-tls.com/tls_articles-sitemap{shard}.xml"
        try:
            response = requests.get(f"https://r.jina.ai/{sitemap_url}", headers=headers, timeout=40)
            response.raise_for_status()
        except requests.RequestException as exc:
            logger.error("TLS sitemap shard %s failed: %s", shard, exc)
            continue
        for url in parse_sitemap_text(
            response.text,
            existing_urls | set(found),
            time_threshold=time_threshold,
        ):
            found.append(url)
    found.reverse()
    logger.info("TLS discovery found %d unprocessed articles", len(found))
    return found[:max_items]


def _preamble_value(text: str, label: str) -> str:
    match = re.search(rf"(?mi)^{re.escape(label)}:\s*(.+?)\s*$", text)
    return match.group(1).strip() if match else ""


def _article_date(value: str) -> str:
    if re.match(r"\d{4}-\d{2}-\d{2}", value):
        return value[:10]
    try:
        return parsedate_to_datetime(value).date().isoformat()
    except (TypeError, ValueError, OverflowError):
        return ""


def _clean_jina_body(text: str, title: str, marker: re.Match[str] | None) -> str:
    body = text[marker.end() :].strip() if marker else text.strip()
    if marker:
        return body
    preamble = re.search(r"(?ms)^Title:.*?^URL Source:.*?$\s*", body)
    if preamble:
        body = body[preamble.end() :].strip()
    heading = re.search(rf"(?mi)^#\s+{re.escape(title)}\s*$", body)
    if heading:
        return body[heading.start() :].strip()
    blocks = [block.strip() for block in re.split(r"\n\s*\n", body) if block.strip()]
    while blocks and (
        blocks[0].startswith("[")
        or blocks[0].startswith("![](")
        or re.search(r"(?i)current issue|subscribe|log in|newsletter", blocks[0])
    ):
        blocks.pop(0)
    return "\n\n".join(blocks).strip()


def _strip_tls_footer(body: str) -> str:
    markers = (
        r"\n\s*\[(?:Terms & Conditions|Privacy|Do not sell or share)",
        r"\n\s*Copyright\s+©\s+The Times Literary Supplement Limited",
        r"\n\s*!\[[^\]]*\]\(https://pixel\.wp\.com/",
        r"\n\s*###\s+(?:Follow us on|Subscribe to the podcast)",
        r"\n\s*\*\s+\[About us\]",
        r"\n\s*\*\s+\[(?:The Archive|Explore|Categories)\]",
        r"\n\s*\*\s+\[Home\]\(https://www\.the-tls\.com/\)",
        r"\n\s*##\s+The TLS Newsletter",
        r"\n\s*##\s+(?:Enjoy unlimited digital access|Keep reading)",
    )
    positions = [match.start() for pattern in markers if (match := re.search(pattern, body, re.I))]
    trimmed = body[: min(positions)] if positions else body
    return re.sub(r"(?:\n\s*\*\s*)+$", "", trimmed).rstrip()


def _is_truncated_preview(body: str, url: str, marker: re.Match[str] | None) -> bool:
    if marker is None or not re.search(r"(?:…|\.{3})$", body.rstrip()):
        return False
    if re.search(r"(?:poem|poetry|verse|original-poems)", url, re.I):
        return False
    last_block = re.split(r"\n\s*\n", body.rstrip())[-1].strip()
    return len(last_block) >= 40


def parse_jina_article(text: str, url: str) -> dict[str, str | int] | None:
    if len(text) < 1500 and re.search(r"\b(?:subscribe|log in)\b", text, re.I):
        logger.warning("TLS Jina response appears to be a short paywall page: %s", url)
        return None

    title = _preamble_value(text, "Title")
    published = _preamble_value(text, "Published Time")
    marker = re.search(r"(?mi)^Markdown Content:\s*$", text)
    body = _strip_tls_footer(_clean_jina_body(text, title, marker))
    if _is_truncated_preview(body, url, marker):
        logger.warning("Skipping TLS partial preview ending in ellipsis: %s", url)
        return None
    if not title:
        heading = re.search(r"(?m)^#\s+(.+?)\s*$", body)
        title = heading.group(1).strip() if heading else url.rstrip("/").rsplit("/", 1)[-1]

    author = _preamble_value(text[: marker.start() if marker else len(text)], "Author")
    if not author:
        byline = re.search(r"(?mi)^By\s+([^\n]+?)\s*$", body)
        if byline:
            author = byline.group(1).strip()
            body = (body[: byline.start()] + body[byline.end() :]).strip()
            body = re.sub(r"\n{3,}", "\n\n", body)

    image_match = re.search(r"!\[[^\]]*\]\((https://[^\s\)]+)", body)
    return {
        "source": SOURCE,
        "title": title,
        "author": author,
        "url": canonicalize_url(url),
        "article_date": _article_date(published),
        "image_url": image_match.group(1) if image_match else "",
        "text": body,
        "raw_length": len(text),
        "paragraph_count": count_paragraphs(body),
    }


def scrape_article_via_jina(url: str) -> dict[str, str | int] | None:
    logger.info("Fetching TLS article through Jina: %s", url)
    try:
        response = requests.get(
            f"https://r.jina.ai/{url}",
            headers={"Accept": "text/markdown", "X-No-Cache": "true"},
            timeout=40,
        )
        status = response.status_code
        response.raise_for_status()
    except requests.RequestException as exc:
        logger.error("TLS Jina fetch failed for %s: %s", url, exc)
        return None
    article = parse_jina_article(response.text, url)
    if article:
        article["http_status"] = status
    return article


def main() -> int:
    existing_urls = get_existing_urls(RAW_ROOT, XML_FILE)
    urls = get_latest_article_urls(existing_urls, max_items=60)
    saved = 0
    for url in urls:
        article = scrape_article_via_jina(url)
        if article and save_raw_article(article, RAW_ROOT):
            saved += 1
    logger.info("TLS run complete: discovered=%d saved=%d", len(urls), saved)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

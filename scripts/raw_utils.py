"""Shared helpers for the NYRB/LRB/TLS raw article archive."""

from __future__ import annotations

import logging
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Mapping
from urllib.parse import unquote, urlsplit
from xml.etree import ElementTree as ET

from .utils import canonicalize_url, parse_frontmatter, render_frontmatter, stable_article_id


logger = logging.getLogger(__name__)
RAW_SOURCES = ("nyrb", "lrb", "tls")


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")


def count_paragraphs(text: str) -> int:
    return len([block for block in re.split(r"\n\s*\n", str(text or "").strip()) if block.strip()])


def slugify(value: str, *, fallback_url: str = "", max_length: int = 90) -> str:
    candidate = str(value or "").strip()
    if not candidate and fallback_url:
        candidate = unquote(urlsplit(fallback_url).path.rstrip("/").rsplit("/", 1)[-1])
    candidate = candidate.lower().replace("_", "-")
    candidate = re.sub(r"[^\w-]+", "-", candidate, flags=re.UNICODE)
    candidate = re.sub(r"-+", "-", candidate).strip("-_")
    return candidate[:max_length].rstrip("-_")


def _canonical_if_valid(url: str) -> str | None:
    try:
        return canonicalize_url(url)
    except (TypeError, ValueError):
        return None


def get_existing_raw_urls(raw_root: Path = Path("raw")) -> set[str]:
    urls: set[str] = set()
    root = Path(raw_root)
    if not root.exists():
        return urls
    for source in RAW_SOURCES:
        for path in (root / source).glob("*.md"):
            try:
                metadata, _ = parse_frontmatter(path.read_text(encoding="utf-8"))
            except (OSError, ValueError) as exc:
                logger.warning("Cannot index raw file %s: %s", path, exc)
                continue
            normalized = _canonical_if_valid(metadata.get("url", ""))
            if normalized:
                urls.add(normalized)
    return urls


def get_legacy_xml_urls(xml_path: Path | None) -> set[str]:
    if xml_path is None or not Path(xml_path).exists():
        return set()
    path = Path(xml_path)
    try:
        root = ET.parse(path).getroot()
        candidates = [str(node.text or "").strip() for node in root.findall(".//item/link")]
    except (OSError, ET.ParseError) as exc:
        logger.warning("Could not parse legacy XML %s with ElementTree: %s", path, exc)
        try:
            text = path.read_text(encoding="utf-8")
        except OSError:
            return set()
        candidates = re.findall(r"<item>.*?<link>(.*?)</link>.*?</item>", text, re.DOTALL)
    return {url for value in candidates if (url := _canonical_if_valid(value))}


def get_existing_urls(raw_root: Path = Path("raw"), xml_path: Path | None = None) -> set[str]:
    return get_existing_raw_urls(raw_root) | get_legacy_xml_urls(xml_path)


def _article_filename(article: Mapping[str, str], captured_at: str) -> str:
    article_date = str(article.get("article_date", "")).strip()
    if not re.fullmatch(r"\d{4}-\d{2}-\d{2}", article_date):
        article_date = captured_at[:10]
    slug = slugify(
        str(article.get("title", "")),
        fallback_url=str(article.get("url", "")),
    )
    if not slug:
        slug = stable_article_id(str(article["source"]), str(article["url"])).split("-", 1)[1]
    return f"{article_date}-{slug}.md"


def save_raw_article(
    article: Mapping[str, str],
    raw_root: Path = Path("raw"),
    *,
    captured_at: str | None = None,
    min_body_chars: int = 100,
) -> Path | None:
    source = str(article.get("source", "")).strip().upper()
    title = str(article.get("title", "")).strip()
    url = canonicalize_url(str(article.get("url", "")))
    body = str(article.get("text", "")).strip()
    captured = str(captured_at or utc_now_iso())
    paragraph_count = count_paragraphs(body)
    raw_length = article.get("raw_length", "")
    http_status = article.get("http_status", "")

    logger.info(
        "%s fetch metrics: status=%s raw_length=%s body_chars=%d paragraphs=%d",
        source,
        http_status,
        raw_length,
        len(body),
        paragraph_count,
    )
    if not source or not title:
        raise ValueError("source and title are required")
    if len(body) < min_body_chars:
        logger.warning("Rejecting %s because cleaned body has only %d characters", url, len(body))
        return None

    root = Path(raw_root)
    if url in get_existing_raw_urls(root):
        logger.info("Skipping already archived URL: %s", url)
        return None

    target_dir = root / source.lower()
    target = target_dir / _article_filename({**article, "source": source, "url": url}, captured)
    if target.exists():
        suffix = stable_article_id(source, url).split("-", 1)[1]
        target = target.with_name(f"{target.stem}-{suffix}{target.suffix}")

    metadata = {
        "source": source,
        "title": title,
        "author": str(article.get("author", "")).strip(),
        "url": url,
        "article_date": str(article.get("article_date", "")).strip(),
        "captured_at": captured,
        "image_url": str(article.get("image_url", "")).strip(),
        "status": "raw",
    }
    markdown = render_frontmatter(metadata, f"# 正文\n\n{body}")
    target_dir.mkdir(parents=True, exist_ok=True)
    target.write_text(markdown, encoding="utf-8", newline="\n")
    logger.info("Saved raw article: %s", target)
    return target

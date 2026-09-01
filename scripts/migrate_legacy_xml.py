"""Migrate legacy RSS items into the canonical Markdown archive."""

from __future__ import annotations

import argparse
import logging
import re
from dataclasses import dataclass
from datetime import timezone
from email.utils import format_datetime, parsedate_to_datetime
from pathlib import Path
from typing import Mapping
from xml.etree import ElementTree as ET

from bs4 import BeautifulSoup
from markdownify import markdownify

try:
    from .utils import article_filename, canonicalize_url, parse_frontmatter, render_frontmatter, stable_article_id
except ImportError:  # direct invocation: python scripts/migrate_legacy_xml.py
    from utils import article_filename, canonicalize_url, parse_frontmatter, render_frontmatter, stable_article_id


CONTENT_NAMESPACE = "http://purl.org/rss/1.0/modules/content/"
logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class MigrationStats:
    items_seen: int = 0
    urls_seen: int = 0
    created: int = 0
    duplicates: int = 0
    invalid: int = 0


def _section_map(description: str) -> dict[str, str]:
    matches = list(re.finditer(r"(?m)^\s*(?:#+\s*)?【([^】]+)】\s*", description))
    sections: dict[str, str] = {}
    for index, match in enumerate(matches):
        end = matches[index + 1].start() if index + 1 < len(matches) else len(description)
        sections[match.group(1).strip()] = description[match.end() : end].strip()
    return sections


def _published_values(pub_date: str) -> tuple[str, str]:
    if not pub_date:
        return "", ""
    parsed = parsedate_to_datetime(pub_date)
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    normalized = parsed.astimezone(timezone.utc)
    return normalized.date().isoformat(), normalized.isoformat()


def _content_html(item: ET.Element) -> str:
    content = item.find(f"{{{CONTENT_NAMESPACE}}}encoded")
    return (content.text or "").strip() if content is not None else ""


def legacy_item_to_article(item: ET.Element, source: str) -> dict[str, str]:
    source_key = str(source or "").upper()
    if not source_key:
        raise ValueError("source is required")
    url_text = (item.findtext("link") or "").strip()
    if not url_text:
        raise ValueError("legacy item has no link")
    url = canonicalize_url(url_text)
    original_title = (item.findtext("title") or "").strip()
    if not original_title:
        raise ValueError("legacy item has no title")

    description = item.findtext("description") or ""
    description = description.strip()
    title_zh = ""
    author_subject = ""
    hook = ""
    tagged_body = ""
    if "|||" in description:
        title_zh, author_subject, hook = (description.split("|||", 2) + ["", "", ""])[:3]
        title_zh, author_subject, hook = title_zh.strip(), author_subject.strip(), hook.strip()
    else:
        sections = _section_map(description)
        title_zh = sections.get("中文标题", "").strip()
        author_subject = sections.get("作者与对象", "").strip()
        hook = sections.get("一句话破题", "").strip()
        tagged_body = sections.get("正文", "").strip()

    content_html = _content_html(item)
    body_markdown = markdownify(content_html, heading_style="ATX").strip() if content_html else tagged_body
    if not body_markdown:
        body_markdown = description
    image_url = ""
    if content_html:
        image = BeautifulSoup(content_html, "html.parser").find("img", src=True)
        image_url = str(image.get("src", "")).strip() if image else ""
    article_date, published_at = _published_values((item.findtext("pubDate") or "").strip())
    return {
        "source": source_key,
        "url": url,
        "original_title": original_title,
        "title_zh": title_zh or original_title,
        "author_subject": author_subject,
        "hook": hook,
        "body_markdown": body_markdown,
        "article_date": article_date,
        "processed_at": published_at,
        "published_at": published_at,
        "image_url": image_url,
        "status": "published",
    }


def _existing_urls(archive_root: Path) -> set[str]:
    urls: set[str] = set()
    if not archive_root.exists():
        return urls
    for path in archive_root.rglob("*.md"):
        try:
            metadata, _ = parse_frontmatter(path.read_text(encoding="utf-8"))
            if metadata.get("url"):
                urls.add(canonicalize_url(metadata["url"]))
        except (OSError, ValueError) as exc:
            logger.warning("cannot index %s: %s", path, exc)
    return urls


def _article_markdown(article: Mapping[str, str]) -> str:
    metadata = {
        "id": stable_article_id(article["source"], article["url"]),
        "source": article["source"],
        "url": article["url"],
        "original_title": article["original_title"],
        "title_zh": article["title_zh"],
        "author_subject": article["author_subject"],
        "hook": article["hook"],
        "article_date": article["article_date"],
        "processed_at": article["processed_at"],
        "published_at": article["published_at"],
        "image_url": article["image_url"],
        "status": "published",
    }
    return render_frontmatter(metadata, article["body_markdown"])


def migrate_feed(
    xml_path: Path, source: str, archive_root: Path, dry_run: bool = False
) -> MigrationStats:
    root = ET.parse(xml_path).getroot()
    existing = _existing_urls(Path(archive_root))
    stats = MigrationStats()
    for item in root.findall(".//item"):
        stats = MigrationStats(**{**stats.__dict__, "items_seen": stats.items_seen + 1})
        try:
            article = legacy_item_to_article(item, source)
        except (TypeError, ValueError) as exc:
            logger.warning("skipping %s item: %s", xml_path, exc)
            stats = MigrationStats(**{**stats.__dict__, "invalid": stats.invalid + 1})
            continue
        stats = MigrationStats(**{**stats.__dict__, "urls_seen": stats.urls_seen + 1})
        if article["url"] in existing:
            stats = MigrationStats(**{**stats.__dict__, "duplicates": stats.duplicates + 1})
            continue
        target = Path(archive_root) / source.lower() / article_filename(
            source, article["article_date"], article["url"]
        )
        if target.exists():
            suffix = stable_article_id(source, article["url"]).split("-", 1)[1]
            target = target.with_name(f"{target.stem}-{suffix}{target.suffix}")
        if not dry_run:
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text(_article_markdown(article), encoding="utf-8", newline="\n")
        existing.add(article["url"])
        stats = MigrationStats(**{**stats.__dict__, "created": stats.created + 1})
    return stats


def migrate_feeds(
    feed_paths: Mapping[str, Path], archive_root: Path, dry_run: bool = False
) -> dict[str, MigrationStats]:
    return {
        source: migrate_feed(path, source, archive_root, dry_run=dry_run)
        for source, path in feed_paths.items()
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--archive-root", type=Path, default=Path("data/articles"))
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()
    feeds = {
        "NYRB": Path("nyrb_ai_enhanced.xml"),
        "LRB": Path("lrb_ai_enhanced.xml"),
        "TLS": Path("tls_ai_enhanced.xml"),
        "NYT": Path("nyt_ai_enhanced.xml"),
    }
    for source, path in feeds.items():
        if not path.exists():
            logger.warning("%s does not exist; skipping", path)
            continue
        stats = migrate_feed(path, source, args.archive_root, dry_run=args.dry_run)
        print(
            f"{source}: items={stats.items_seen} urls={stats.urls_seen} "
            f"created={stats.created} duplicates={stats.duplicates} invalid={stats.invalid}"
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

"""Canonical article archive helpers for deterministic Sheet publishing."""

from __future__ import annotations

import csv
import io
import json
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any, Iterable

try:
    from .utils import article_filename, canonicalize_url, parse_frontmatter, render_frontmatter
except ImportError:  # Supports `python scripts/<tool>.py` as well as package imports.
    from utils import article_filename, canonicalize_url, parse_frontmatter, render_frontmatter


REQUIRED_COLUMNS = (
    "source", "url", "raw_path", "original_title", "author", "article_date",
    "image_url", "title_zh", "subject", "hook", "keywords", "body_markdown",
    "processed_at", "status",
)
SUPPORTED_SOURCES = {"nyrb", "lrb", "tls", "nyt"}


def parse_processed_at(value: str) -> datetime:
    """Parse a timezone-aware ISO-8601 processing timestamp."""

    timestamp = str(value or "").strip()
    if "T" not in timestamp:
        raise ValueError("processed_at must be an ISO 8601 datetime")
    try:
        parsed = datetime.fromisoformat(timestamp.replace("Z", "+00:00"))
    except ValueError as exc:
        raise ValueError(f"processed_at is not ISO 8601: {value!r}") from exc
    if parsed.tzinfo is None:
        raise ValueError("processed_at must include a timezone")
    return parsed.astimezone(timezone.utc)


def _parse_keywords(value: str) -> list[str]:
    try:
        parsed = json.loads(str(value or ""))
    except json.JSONDecodeError as exc:
        raise ValueError("keywords must be a JSON array of strings") from exc
    if not isinstance(parsed, list) or any(not isinstance(keyword, str) for keyword in parsed):
        raise ValueError("keywords must be a JSON array of strings")
    return [keyword.strip() for keyword in parsed]


def _validate_article_date(value: str) -> str:
    article_date = str(value or "").strip()
    if not article_date:
        return ""
    try:
        date.fromisoformat(article_date)
    except ValueError as exc:
        raise ValueError(f"article_date is not ISO 8601 date: {value!r}") from exc
    if len(article_date) != 10:
        raise ValueError(f"article_date is not ISO 8601 date: {value!r}")
    return article_date


def _normalize_published_row(row: dict[str, str], row_number: int) -> tuple[dict[str, Any], datetime]:
    source = str(row["source"] or "").strip().lower()
    if source not in SUPPORTED_SOURCES:
        raise ValueError(f"row {row_number}: unsupported source {row['source']!r}")
    try:
        url = canonicalize_url(row["url"])
    except ValueError as exc:
        raise ValueError(f"row {row_number}: invalid url") from exc
    processed_at = str(row["processed_at"] or "").strip()
    processed_timestamp = parse_processed_at(processed_at)
    record: dict[str, Any] = {
        "source": source,
        "url": url,
        "raw_path": str(row["raw_path"] or "").strip(),
        "original_title": str(row["original_title"] or "").strip(),
        "author": str(row["author"] or "").strip(),
        "article_date": _validate_article_date(row["article_date"]),
        "image_url": str(row["image_url"] or "").strip(),
        "title_zh": str(row["title_zh"] or "").strip(),
        "subject": str(row["subject"] or "").strip(),
        "hook": str(row["hook"] or "").strip(),
        "keywords": _parse_keywords(row["keywords"]),
        "body_markdown": str(row["body_markdown"] or "").replace("\r\n", "\n"),
        "processed_at": processed_at,
        "status": "published",
    }
    return record, processed_timestamp


def published_records_from_csv(csv_text: str) -> list[dict[str, Any]]:
    """Return the newest published row per canonical URL from a Sheet CSV."""

    reader = csv.DictReader(io.StringIO(str(csv_text), newline=""))
    if reader.fieldnames:
        reader.fieldnames[0] = reader.fieldnames[0].lstrip("\ufeff")
    headers = list(reader.fieldnames or [])
    if headers != list(REQUIRED_COLUMNS):
        raise ValueError(f"CSV columns must exactly be: {', '.join(REQUIRED_COLUMNS)}")

    newest: dict[str, tuple[dict[str, Any], datetime]] = {}
    for row_number, raw_row in enumerate(reader, start=2):
        row = {key: "" if value is None else value for key, value in raw_row.items()}
        status = str(row["status"] or "").strip().lower()
        if status == "review":
            continue
        if status != "published":
            raise ValueError(f"row {row_number}: status must be review or published")
        record, processed_timestamp = _normalize_published_row(row, row_number)
        previous = newest.get(record["url"])
        if previous is None or processed_timestamp >= previous[1]:
            newest[record["url"]] = (record, processed_timestamp)
    return [newest[url][0] for url in sorted(newest)]


def _canonical_files_by_url(root: Path) -> dict[str, list[Path]]:
    matches: dict[str, list[Path]] = {}
    if not root.exists():
        return matches
    for path in sorted(root.rglob("*.md")):
        try:
            metadata, _ = parse_frontmatter(path.read_text(encoding="utf-8"))
            url = canonicalize_url(str(metadata.get("url", "")))
        except (OSError, ValueError):
            continue
        matches.setdefault(url, []).append(path)
    return matches


def _render_article(record: dict[str, Any]) -> str:
    metadata = {key: record[key] for key in REQUIRED_COLUMNS if key != "body_markdown"}
    return render_frontmatter(metadata, record["body_markdown"])


def write_canonical_articles(records: Iterable[dict[str, Any]], articles_root: Path) -> list[Path]:
    """Write one stable canonical Markdown file for every selected URL."""

    root = Path(articles_root)
    existing = _canonical_files_by_url(root)
    written: list[Path] = []
    for record in records:
        source_dir = root / record["source"]
        prior = existing.get(record["url"], [])
        target = next((path for path in prior if path.parent == source_dir), None)
        if target is None:
            target = source_dir / article_filename(record["source"], record["article_date"], record["url"])
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(_render_article(record), encoding="utf-8", newline="\n")
        for old_path in prior:
            if old_path != target and old_path.exists():
                old_path.unlink()
        existing[record["url"]] = [target]
        written.append(target)
    return written


def import_csv_text(csv_text: str, articles_root: Path = Path("data/articles")) -> list[Path]:
    return write_canonical_articles(published_records_from_csv(csv_text), Path(articles_root))


def _record_from_file(path: Path) -> dict[str, Any] | None:
    metadata, body = parse_frontmatter(path.read_text(encoding="utf-8"))
    if str(metadata.get("status", "")).strip().lower() != "published":
        return None
    missing = [field for field in REQUIRED_COLUMNS if field not in metadata and field != "body_markdown"]
    if missing:
        raise ValueError(f"{path}: missing frontmatter fields: {', '.join(missing)}")
    keywords = metadata["keywords"]
    if not isinstance(keywords, list) or any(not isinstance(keyword, str) for keyword in keywords):
        raise ValueError(f"{path}: keywords must be a JSON array of strings")
    record = {key: metadata[key] for key in REQUIRED_COLUMNS if key != "body_markdown"}
    record["source"] = str(record["source"]).strip().lower()
    if record["source"] not in SUPPORTED_SOURCES:
        raise ValueError(f"{path}: unsupported source")
    record["url"] = canonicalize_url(str(record["url"]))
    record["article_date"] = _validate_article_date(str(record["article_date"]))
    parse_processed_at(str(record["processed_at"]))
    record["keywords"] = list(keywords)
    record["body_markdown"] = body
    record["status"] = "published"
    return record


def load_articles(articles_root: Path = Path("data/articles")) -> list[dict[str, Any]]:
    """Read published canonical files and return the newest record per URL."""

    newest: dict[str, tuple[dict[str, Any], datetime]] = {}
    root = Path(articles_root)
    if not root.exists():
        return []
    for path in sorted(root.rglob("*.md")):
        record = _record_from_file(path)
        if record is None:
            continue
        processed_timestamp = parse_processed_at(str(record["processed_at"]))
        previous = newest.get(record["url"])
        if previous is None or processed_timestamp >= previous[1]:
            newest[record["url"]] = (record, processed_timestamp)
    return [newest[url][0] for url in sorted(newest)]

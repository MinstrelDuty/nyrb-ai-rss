"""Import published Google Sheet rows into the canonical Markdown archive."""

from __future__ import annotations

import argparse
import csv
import io
import logging
import os
from dataclasses import dataclass
from datetime import date, datetime
from pathlib import Path
from typing import Iterable, Mapping

import requests

try:
    from .utils import article_filename, canonicalize_url, render_frontmatter, stable_article_id
except ImportError:  # direct invocation: python scripts/import_sheet.py
    from utils import article_filename, canonicalize_url, render_frontmatter, stable_article_id


logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
logger = logging.getLogger(__name__)

REQUIRED_COLUMNS = (
    "source",
    "url",
    "original_title",
    "title_zh",
    "author_subject",
    "hook",
    "body_markdown",
    "processed_at",
)
OPTIONAL_COLUMNS = ("article_date", "image_url", "status")
ALLOWED_SOURCES = frozenset(
    {"NYRB", "LRB", "TLS", "NYT", "NEWYORKER", "ATLANTIC", "LARB", "PUBLICBOOKS"}
)


class CsvFetchError(RuntimeError):
    """Raised when the published CSV cannot be downloaded."""


@dataclass(frozen=True)
class ImportStats:
    fetched_rows: int = 0
    valid_rows: int = 0
    new_articles: int = 0
    duplicate_rows: int = 0
    invalid_rows: int = 0


def fetch_csv(url: str, session: requests.Session | None = None) -> str:
    if not str(url or "").strip():
        raise CsvFetchError("SHEET_CSV_URL is empty")
    client = session or requests
    try:
        response = client.get(url, timeout=30)
    except requests.RequestException as exc:
        raise CsvFetchError(f"CSV download failed: {exc}") from exc
    if response.status_code < 200 or response.status_code >= 300:
        raise CsvFetchError(f"CSV download failed with HTTP {response.status_code}")
    return response.text


def _is_iso_datetime(value: str) -> bool:
    try:
        datetime.fromisoformat(value.strip().replace("Z", "+00:00"))
        return True
    except ValueError:
        return False


def _is_iso_date(value: str) -> bool:
    try:
        date.fromisoformat(value.strip())
        return True
    except ValueError:
        return False


def _existing_urls(archive_root: Path) -> set[str]:
    urls: set[str] = set()
    if not archive_root.exists():
        return urls
    try:
        from .utils import parse_frontmatter
    except ImportError:  # direct invocation: python scripts/import_sheet.py
        from utils import parse_frontmatter

    for path in archive_root.rglob("*.md"):
        try:
            metadata, _ = parse_frontmatter(path.read_text(encoding="utf-8"))
            if metadata.get("url"):
                urls.add(canonicalize_url(metadata["url"]))
        except (OSError, ValueError) as exc:
            logger.warning("cannot index %s: %s", path, exc)
    return urls


def _validate_row(row: Mapping[str, str], row_number: int) -> tuple[dict[str, str] | None, str | None]:
    values = {str(key): str(value or "") for key, value in row.items()}
    source = values.get("source", "").strip()
    if source not in ALLOWED_SOURCES:
        return None, f"row {row_number}: unsupported source {source!r}"

    missing = [column for column in REQUIRED_COLUMNS if not values.get(column, "").strip()]
    if missing:
        return None, f"row {row_number}: missing required fields {', '.join(missing)}"

    try:
        normalized_url = canonicalize_url(values["url"])
    except ValueError as exc:
        return None, f"row {row_number}: {exc}"
    if not _is_iso_datetime(values["processed_at"]):
        return None, f"row {row_number}: processed_at is not ISO-8601"
    if values.get("article_date", "").strip() and not _is_iso_date(values["article_date"]):
        return None, f"row {row_number}: article_date is not YYYY-MM-DD"

    status = values.get("status", "").strip().lower() or "published"
    values.update(
        {
            "source": source,
            "url": normalized_url,
            "status": status,
            "article_date": values.get("article_date", "").strip(),
            "image_url": values.get("image_url", "").strip(),
        }
    )
    return values, None


def _target_path(archive_root: Path, row: Mapping[str, str]) -> Path:
    filename = article_filename(row["source"], row.get("article_date", ""), row["url"])
    path = archive_root / row["source"].lower() / filename
    if path.exists():
        stable_id = stable_article_id(row["source"], row["url"])
        path = path.with_name(f"{path.stem}-{stable_id.split('-', 1)[1]}{path.suffix}")
    return path


def _render_article(row: Mapping[str, str]) -> str:
    metadata = {
        "id": stable_article_id(row["source"], row["url"]),
        "source": row["source"],
        "url": row["url"],
        "original_title": row["original_title"].strip(),
        "title_zh": row["title_zh"].strip(),
        "author_subject": row["author_subject"].strip(),
        "hook": row["hook"].strip(),
        "article_date": row.get("article_date", ""),
        "processed_at": row["processed_at"].strip(),
        "image_url": row.get("image_url", ""),
        "status": "published",
    }
    return render_frontmatter(metadata, row["body_markdown"])


def import_rows(rows: Iterable[Mapping[str, str]], archive_root: Path) -> ImportStats:
    archive_root = Path(archive_root)
    existing = _existing_urls(archive_root)
    stats = ImportStats()

    for row_number, row in enumerate(rows, start=2):
        stats = ImportStats(
            fetched_rows=stats.fetched_rows + 1,
            valid_rows=stats.valid_rows,
            new_articles=stats.new_articles,
            duplicate_rows=stats.duplicate_rows,
            invalid_rows=stats.invalid_rows,
        )
        normalized, error = _validate_row(row, row_number)
        if error:
            logger.warning(error)
            stats = ImportStats(**{**stats.__dict__, "invalid_rows": stats.invalid_rows + 1})
            continue
        if normalized["status"] != "published":
            logger.warning("row %s skipped because status=%s", row_number, normalized["status"])
            continue

        stats = ImportStats(**{**stats.__dict__, "valid_rows": stats.valid_rows + 1})
        if normalized["url"] in existing:
            stats = ImportStats(**{**stats.__dict__, "duplicate_rows": stats.duplicate_rows + 1})
            continue

        target = _target_path(archive_root, normalized)
        target.parent.mkdir(parents=True, exist_ok=True)
        try:
            target.write_text(_render_article(normalized), encoding="utf-8", newline="\n")
        except OSError as exc:
            logger.warning("row %s could not be written: %s", row_number, exc)
            stats = ImportStats(**{**stats.__dict__, "invalid_rows": stats.invalid_rows + 1})
            continue
        existing.add(normalized["url"])
        stats = ImportStats(**{**stats.__dict__, "new_articles": stats.new_articles + 1})

    logger.info(
        "fetched rows=%d valid rows=%d new articles=%d duplicate rows=%d invalid rows=%d",
        stats.fetched_rows,
        stats.valid_rows,
        stats.new_articles,
        stats.duplicate_rows,
        stats.invalid_rows,
    )
    return stats


def _read_rows(csv_text: str) -> list[dict[str, str]]:
    reader = csv.DictReader(io.StringIO(csv_text))
    fieldnames = tuple(reader.fieldnames or ())
    missing = [column for column in REQUIRED_COLUMNS if column not in fieldnames]
    if missing:
        raise ValueError(f"CSV is missing required columns: {', '.join(missing)}")
    return list(reader)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--csv-url", default=os.getenv("SHEET_CSV_URL", ""))
    parser.add_argument("--archive-root", type=Path, default=Path("data/articles"))
    args = parser.parse_args()
    if not args.csv_url:
        logger.error("SHEET_CSV_URL is not configured")
        return 2
    try:
        stats = import_rows(_read_rows(fetch_csv(args.csv_url)), args.archive_root)
    except (CsvFetchError, ValueError) as exc:
        logger.error("%s", exc)
        return 1
    return 0 if stats.invalid_rows == 0 else 0


if __name__ == "__main__":
    raise SystemExit(main())

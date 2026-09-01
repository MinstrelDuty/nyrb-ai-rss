import csv
from pathlib import Path
from unittest.mock import Mock

import pytest
import requests

from scripts.import_sheet import CsvFetchError, fetch_csv, import_rows


FIXTURE = Path(__file__).parent / "fixtures" / "sample_sheet.csv"


def load_fixture_rows():
    with FIXTURE.open(newline="", encoding="utf-8") as handle:
        return list(csv.DictReader(handle))


def test_import_rows_writes_published_articles_and_multiline_body(tmp_path):
    archive_root = tmp_path / "data" / "articles"
    stats = import_rows(load_fixture_rows(), archive_root)

    files = sorted(archive_root.rglob("*.md"))
    assert stats.fetched_rows == 6
    assert stats.valid_rows == 3
    assert stats.new_articles == 2
    assert len(files) == 2
    contents = "\n".join(path.read_text(encoding="utf-8") for path in files)
    assert "第一行\n第二行" in contents
    assert "NYT" in contents


def test_import_rows_skips_duplicate_invalid_and_partial_rows(tmp_path, caplog):
    stats = import_rows(load_fixture_rows(), tmp_path / "articles")

    assert stats.duplicate_rows == 1
    assert stats.invalid_rows == 2
    assert "partial" in caplog.text
    assert "unsupported source" in caplog.text


def test_import_rows_is_idempotent(tmp_path):
    archive_root = tmp_path / "articles"
    first = import_rows(load_fixture_rows(), archive_root)
    second = import_rows(load_fixture_rows(), archive_root)

    assert first.new_articles == 2
    assert second.new_articles == 0
    assert second.duplicate_rows == 3


def test_fetch_csv_rejects_http_failure(monkeypatch):
    response = Mock(status_code=503, text="unavailable")
    monkeypatch.setattr(requests, "get", lambda *args, **kwargs: response)

    with pytest.raises(CsvFetchError, match="503"):
        fetch_csv("https://example.invalid/feed.csv")

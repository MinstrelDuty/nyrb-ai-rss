import csv
import json
from pathlib import Path
from xml.etree import ElementTree as ET

from scripts.build_rss import FEEDS, write_feeds
from scripts.import_sheet import import_rows


FIXTURE = Path(__file__).parent / "fixtures" / "sample_sheet.csv"
EXPECTED = json.loads(
    (Path(__file__).parent / "fixtures" / "expected_feed_checks.json").read_text(encoding="utf-8")
)


def load_fixture_rows():
    with FIXTURE.open(newline="", encoding="utf-8") as handle:
        return list(csv.DictReader(handle))


def test_fixture_pipeline_creates_archive_and_all_eight_valid_feeds(tmp_path):
    archive = tmp_path / "data" / "articles"
    output = tmp_path / "site"

    stats = import_rows(load_fixture_rows(), archive)
    counts = write_feeds(archive, output)

    assert stats.new_articles == 2
    assert counts["NYRB"] == 1
    assert counts["NYT"] == 1
    for source, config in FEEDS.items():
        root = ET.parse(output / config["file"]).getroot()
        assert root.tag == "rss"
        assert len(root.findall("./channel/item")) == EXPECTED[source]["items"]


def test_fixture_pipeline_is_idempotent(tmp_path):
    archive = tmp_path / "articles"
    output = tmp_path / "site"
    rows = load_fixture_rows()

    first = import_rows(rows, archive)
    second = import_rows(rows, archive)
    write_feeds(archive, output)

    assert first.new_articles == 2
    assert second.new_articles == 0
    assert second.duplicate_rows == 3
    assert len(list(archive.rglob("*.md"))) == 2

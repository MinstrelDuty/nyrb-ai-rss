"""Import approved rows from a published Google Sheet CSV URL."""

from __future__ import annotations

import argparse
import os
from pathlib import Path

import requests

try:
    from scripts.publishing import import_csv_text, import_new_csv_text
except ModuleNotFoundError:  # Supports direct script execution from the repository root.
    from publishing import import_csv_text, import_new_csv_text


def import_sheet(
    csv_url: str,
    articles_root: Path = Path("data/articles"),
    *,
    only_new: bool = False,
) -> list[Path]:
    response = requests.get(csv_url, timeout=30)
    response.raise_for_status()
    importer = import_new_csv_text if only_new else import_csv_text
    return importer(response.text, articles_root)


def _write_github_output(name: str, value: int) -> None:
    output_path = os.environ.get("GITHUB_OUTPUT", "").strip()
    if output_path:
        with Path(output_path).open("a", encoding="utf-8", newline="\n") as output:
            output.write(f"{name}={value}\n")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--new-only",
        action="store_true",
        help="Import only published rows whose canonical URL is not already archived.",
    )
    args = parser.parse_args()
    csv_url = os.environ.get("SHEET_CSV_URL", "").strip()
    if not csv_url:
        raise SystemExit("SHEET_CSV_URL is required")
    written = import_sheet(csv_url, only_new=args.new_only)
    _write_github_output("new_articles", len(written))
    print(f"Imported {len(written)} published article(s).")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

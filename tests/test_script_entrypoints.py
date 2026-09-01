import subprocess
import sys
from pathlib import Path


REPO_ROOT = Path(__file__).parents[1]


def test_archive_scripts_can_be_invoked_directly():
    for script in (
        "scripts/import_sheet.py",
        "scripts/build_rss.py",
        "scripts/migrate_legacy_xml.py",
    ):
        result = subprocess.run(
            [sys.executable, script, "--help"],
            cwd=REPO_ROOT,
            capture_output=True,
            text=True,
        )
        assert result.returncode == 0, f"{script}: {result.stderr}"

from datetime import datetime, timedelta, timezone
from pathlib import Path
import re


WORKFLOW = Path(__file__).parents[1] / ".github" / "workflows" / "publish.yml"


def _workflow_text() -> str:
    return WORKFLOW.read_text(encoding="utf-8")


def test_publish_schedule_covers_only_monday_and_thursday_beijing_05_to_08():
    workflow = _workflow_text()
    cron_lines = re.findall(r"- cron: '([^']+)'", workflow)

    assert cron_lines == ["*/15 21-23 * * 0,3", "0 0 * * 1,4"]
    assert "0 22 * * 0,3" not in workflow

    utc_runs = []
    for weekday in (0, 3):
        for hour in (21, 22, 23):
            utc_runs.extend(
                datetime(2026, 9, 13 + weekday, hour, 0, tzinfo=timezone.utc)
                + timedelta(minutes=15 * minute)
                for minute in range(4)
            )
    utc_runs.extend(
        datetime(2026, 9, 14 + weekday, 0, 0, tzinfo=timezone.utc)
        for weekday in (0, 3)
    )
    beijing_runs = [run.astimezone(timezone(timedelta(hours=8))) for run in utc_runs]

    assert {run.weekday() for run in beijing_runs} == {0, 3}
    assert min(run.hour for run in beijing_runs) == 5
    assert max(run.hour for run in beijing_runs) == 8
    assert all(5 <= run.hour <= 8 for run in beijing_runs)


def test_publish_workflow_keeps_manual_runs_and_serializes_publishers():
    workflow = _workflow_text()

    assert "  workflow_dispatch:\n" in workflow
    assert "concurrency:" in workflow
    assert "group: publish-reviewed-articles" in workflow
    assert "cancel-in-progress: false" in workflow
    assert "python scripts/import_sheet.py --new-only" in workflow
    assert "git commit -m \"Publish reviewed articles\"" in workflow


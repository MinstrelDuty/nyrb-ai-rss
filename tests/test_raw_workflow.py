from pathlib import Path


WORKFLOW = Path(".github/workflows/main.yml")


def test_raw_workflow_has_no_ai_secret_and_only_stages_raw_archive():
    text = WORKFLOW.read_text(encoding="utf-8")

    assert "DEEPSEEK_API_KEY" not in text
    assert "openai" not in text.lower()
    assert "git add raw/" in text
    assert "git add *.xml" not in text


def test_raw_workflow_installs_project_requirements_and_avoids_empty_commits():
    text = WORKFLOW.read_text(encoding="utf-8")

    assert "pip install -r requirements.txt" in text
    assert "git diff --cached --quiet" in text
    assert 'git commit -m "Update raw article archive"' in text

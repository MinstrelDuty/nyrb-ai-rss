from pathlib import Path


WORKFLOW = Path(".github/workflows/v2-validation.yml")


def test_v2_workflow_has_no_ai_api_dependency():
    text = WORKFLOW.read_text(encoding="utf-8")
    assert "DEEPSEEK_API_KEY" not in text
    assert "openai" not in text.lower()
    assert "workflow_dispatch" in text


def test_v2_workflow_runs_python_and_javascript_validation():
    text = WORKFLOW.read_text(encoding="utf-8")
    assert "pip install -r requirements.txt" in text
    assert "python -m pytest" in text
    assert "node --test" in text
    assert "build_rss.py" in text

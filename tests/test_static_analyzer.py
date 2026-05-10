"""Unit tests for the rule-based static analyzer.

These run without a database or LLM and exercise the regex-based detectors
directly.
"""

from __future__ import annotations

from app.agents.state import FileBlob
from app.agents.static_analyzer import _scan_file


def _scan(content: str, language: str = "python", path: str = "app.py") -> list:
    return _scan_file(FileBlob(path=path, content=content, language=language))


def test_detects_aws_key():
    findings = _scan('AWS_KEY = "AKIAIOSFODNN7EXAMPLE"')
    assert any(f["category"] == "secret" for f in findings)
    assert any(f["severity"] == "critical" for f in findings)


def test_detects_pickle_loads():
    findings = _scan("import pickle\ndata = pickle.loads(payload)\n")
    titles = [f["title"] for f in findings]
    assert any("pickle" in t.lower() for t in titles)


def test_detects_subprocess_shell_true():
    findings = _scan(
        "import subprocess\nsubprocess.run(cmd, shell=True)\n",
    )
    assert any(f["category"] == "command-injection" for f in findings)


def test_detects_sql_string_format():
    code = 'cursor.execute(f"SELECT * FROM users WHERE id = {user_id}")\n'
    findings = _scan(code)
    assert any(f["category"] == "sql-injection" for f in findings)


def test_detects_yaml_unsafe_load():
    findings = _scan("import yaml\ny = yaml.load(stream)\n")
    assert any(f["cwe_id"] == "CWE-502" for f in findings)


def test_detects_innerhtml_in_js():
    findings = _scan(
        "document.getElementById('x').innerHTML = userInput;",
        language="javascript",
        path="ui.js",
    )
    assert any(f["category"] == "xss" for f in findings)


def test_no_false_positives_on_clean_code():
    code = (
        "def add(a: int, b: int) -> int:\n"
        "    return a + b\n"
    )
    assert _scan(code) == []


def test_language_filtering():
    # Python-only rules should not fire on JS code.
    code = "pickle.loads(buf)"
    findings = _scan(code, language="javascript", path="x.js")
    assert all(f["category"] != "deserialization" for f in findings)

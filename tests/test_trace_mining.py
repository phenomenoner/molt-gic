from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path


def cli(cwd: Path, *args: str, check: bool = True):
    proc = subprocess.run([sys.executable, "-m", "molt_gic.cli", *args], cwd=cwd, text=True, capture_output=True)
    if check and proc.returncode != 0:
        raise AssertionError(f"failed {args}\nstdout={proc.stdout}\nstderr={proc.stderr}")
    return proc


def setup_artifact(tmp_path: Path):
    skill = tmp_path / "SKILL.md"
    skill.write_text("# Skill\n", encoding="utf-8")
    db = tmp_path / "db.sqlite"
    cli(tmp_path, "init", "--db", str(db), "--json")
    cli(tmp_path, "artifact", "add", "--db", str(db), "--type", "skill", "--path", str(skill), "--name", "skill", "--json")
    return db


def test_trace_mine_import_redacts_and_dedupes(tmp_path: Path):
    db = setup_artifact(tmp_path)
    trace = tmp_path / "traces.jsonl"
    secret = "sk-" + "abcdefghijklmnopqrstuvwxyz"
    row = {"id": "trace_ex_1", "input": f"please improve text with api_key={secret}", "expected_behavior": "redact secrets", "risk": "medium"}
    trace.write_text(json.dumps(row) + "\n" + json.dumps(row) + "\n", encoding="utf-8")
    result = json.loads(cli(tmp_path, "trace", "mine", "import", "--db", str(db), "--artifact", "skill:skill", "--file", str(trace), "--json").stdout)
    assert result["imported"] == 1
    assert result["deduped"] == 1
    assert result["redacted"] == 1
    export = tmp_path / "export.json"
    cli(tmp_path, "db", "export", "--db", str(db), "--out", str(export), "--json")
    data = json.loads(export.read_text())
    assert data["trace_sources"]
    example = [e for e in data["eval_examples"] if e["id"] == "trace_ex_1"][0]
    assert "[REDACTED]" in example["input"]
    assert example["source"] == "trace_mined"


def test_trace_mined_cannot_silently_promote_without_reviewer(tmp_path: Path):
    db = setup_artifact(tmp_path)
    trace = tmp_path / "traces.jsonl"
    trace.write_text(json.dumps({"id": "trace_ex_2", "input": "hello", "expected_behavior": "answer"}) + "\n", encoding="utf-8")
    cli(tmp_path, "trace", "mine", "import", "--db", str(db), "--artifact", "skill:skill", "--file", str(trace), "--json")
    # Existing command requires reviewer/reason at argparse level; without them it is a usage error.
    proc = cli(tmp_path, "dataset", "promote", "--db", str(db), "--example", "trace_ex_2", check=False)
    assert proc.returncode == 2

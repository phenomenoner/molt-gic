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


def test_dashboard_export_and_render_are_read_only(tmp_path: Path):
    skill = tmp_path / "SKILL.md"
    skill.write_text("# Skill\n", encoding="utf-8")
    data = tmp_path / "golden.jsonl"
    rows = [{"id": f"ex_{i}", "input": "hi", "expected_behavior": "reply", "axis_tags": ["action"], "risk": "low", "source": "golden"} for i in range(10)]
    data.write_text("\n".join(json.dumps(r) for r in rows), encoding="utf-8")
    db = tmp_path / "db.sqlite"
    cli(tmp_path, "init", "--db", str(db), "--json")
    cli(tmp_path, "artifact", "add", "--db", str(db), "--type", "skill", "--path", str(skill), "--name", "skill", "--json")
    cli(tmp_path, "dataset", "import", "--db", str(db), "--artifact", "skill:skill", "--source", "golden", "--file", str(data), "--json")
    cli(tmp_path, "eval", "run", "--db", str(db), "--artifact", "skill:skill", "--mode", "baseline", "--baseline", str(skill), "--json")
    snap = tmp_path / "dashboard.json"
    out = json.loads(cli(tmp_path, "dashboard", "export", "--db", str(db), "--out", str(snap), "--json").stdout)
    assert out["read_only"] is True
    payload = json.loads(snap.read_text())
    assert payload["read_only"] is True
    assert payload["runs"] and "gates" in payload
    html = tmp_path / "dashboard.html"
    rendered = json.loads(cli(tmp_path, "dashboard", "render", "--snapshot", str(snap), "--out", str(html), "--json").stdout)
    assert rendered["read_only"] is True
    text = html.read_text()
    assert "molt-gic dashboard" in text
    assert "<form" not in text.lower()

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


def seed(cwd: Path):
    skill = cwd / "SKILL.md"
    skill.write_text("# Skill\n\n## Workflow\nPreserve meaning.\n\n## Output rules\nReturn text.\n", encoding="utf-8")
    rows = []
    for i in range(10):
        rows.append({"id": f"ex_{i}", "input": f"input {i}", "expected_behavior": "preserve meaning", "axis_tags": ["foundation", "action", "closure"], "risk": "high" if i == 0 else "low", "source": "golden", "trust_weight": 1.0})
    data = cwd / "golden.jsonl"
    data.write_text("\n".join(json.dumps(r) for r in rows), encoding="utf-8")
    db = cwd / "db.sqlite"
    cli(cwd, "init", "--db", str(db), "--json")
    cli(cwd, "artifact", "add", "--db", str(db), "--type", "skill", "--path", str(skill), "--name", "skill", "--json")
    cli(cwd, "dataset", "import", "--db", str(db), "--artifact", "skill:skill", "--source", "golden", "--file", str(data), "--json")
    cli(cwd, "eval", "run", "--db", str(db), "--artifact", "skill:skill", "--mode", "baseline", "--baseline", str(skill), "--json")
    cand = json.loads(cli(cwd, "evolve", "propose", "--db", str(db), "--artifact", "skill:skill", "--json").stdout)["candidate_path"]
    run_id = json.loads(cli(cwd, "eval", "run", "--db", str(db), "--artifact", "skill:skill", "--mode", "candidate", "--baseline", str(skill), "--candidate", cand, "--json").stdout)["run_id"]
    packet = json.loads(cli(cwd, "packet", "build", "--db", str(db), "--run", run_id, "--json").stdout)
    packet_id = Path(packet["packet_json"]).stem
    return db, skill, run_id, packet_id


def test_p8_p10_p12_p14_surfaces(tmp_path: Path):
    db, skill, run_id, packet_id = seed(tmp_path)
    (tmp_path / "nested").mkdir()
    (tmp_path / "nested" / "SKILL.md").write_text("# Nested", encoding="utf-8")
    discovered = json.loads(cli(tmp_path, "adapter", "discover", "--root", str(tmp_path), "--json").stdout)
    assert discovered["skills"]
    clean = json.loads(cli(tmp_path, "security", "scan", "--path", str(skill), "--json").stdout)
    assert clean["status"] == "pass"
    bad = tmp_path / "secret.txt"
    bad.write_text("api_key = '" + "sk-" + "abcdefghijklmnopqrstuvwxyz'", encoding="utf-8")
    proc = cli(tmp_path, "security", "scan", "--path", str(bad), "--json", check=False)
    assert proc.returncode == 7
    replay = json.loads(cli(tmp_path, "replay", "packet", "--db", str(db), "--packet", packet_id, "--json").stdout)
    assert replay["status"] == "ok" and Path(tmp_path / replay["receipt"]).exists()
    pilot = json.loads(cli(tmp_path, "pilot", "verify", "--db", str(db), "--artifact", "skill:skill", "--json").stdout)
    assert pilot["status"] == "pass"


def test_p13_run_resume_cancel(tmp_path: Path):
    db, _skill, run_id, _packet_id = seed(tmp_path)
    resume = json.loads(cli(tmp_path, "run", "resume", "--db", str(db), "--run", run_id, "--json").stdout)
    assert resume["run_id"] == run_id
    # Completed runs cannot be cancelled; this proves bounded lifecycle protection.
    proc = cli(tmp_path, "run", "cancel", "--db", str(db), "--run", run_id, "--json", check=False)
    assert proc.returncode == 3

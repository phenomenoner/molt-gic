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


def test_artifact_rules_show_for_all_v1_types(tmp_path: Path):
    expected = {
        "skill": "confirm_apply",
        "prompt": "review_only",
        "tool_description": "review_only",
        "route": "review_only",
    }
    for typ, policy in expected.items():
        out = json.loads(cli(tmp_path, "artifact", "rules", "show", "--type", typ, "--json").stdout)
        assert out["enabled"] is True
        assert out["apply_policy"] == policy
        assert out["mutation_masks"]


def test_non_skill_artifact_can_register_but_apply_is_review_only(tmp_path: Path):
    artifact = tmp_path / "prompt.md"
    artifact.write_text("# Prompt\n\nAnswer briefly.\n", encoding="utf-8")
    data = tmp_path / "golden.jsonl"
    rows = []
    for i in range(10):
        rows.append({"id": f"ex_{i}", "input": "hello", "expected_behavior": "brief answer", "axis_tags": ["action"], "risk": "low", "source": "golden", "trust_weight": 1.0})
    data.write_text("\n".join(json.dumps(r) for r in rows), encoding="utf-8")
    db = tmp_path / "db.sqlite"
    cli(tmp_path, "init", "--db", str(db), "--json")
    add = json.loads(cli(tmp_path, "artifact", "add", "--db", str(db), "--type", "prompt", "--path", str(artifact), "--name", "demo", "--json").stdout)
    assert add["artifact_id"] == "prompt:demo"
    cli(tmp_path, "dataset", "import", "--db", str(db), "--artifact", "prompt:demo", "--source", "golden", "--file", str(data), "--json")
    cli(tmp_path, "eval", "run", "--db", str(db), "--artifact", "prompt:demo", "--mode", "baseline", "--baseline", str(artifact), "--json")
    cand = json.loads(cli(tmp_path, "evolve", "propose", "--db", str(db), "--artifact", "prompt:demo", "--json").stdout)["candidate_path"]
    run_id = json.loads(cli(tmp_path, "eval", "run", "--db", str(db), "--artifact", "prompt:demo", "--mode", "candidate", "--baseline", str(artifact), "--candidate", cand, "--json").stdout)["run_id"]
    packet = json.loads(cli(tmp_path, "packet", "build", "--db", str(db), "--run", run_id, "--json").stdout)
    packet_id = Path(packet["packet_json"]).stem
    cli(tmp_path, "decision", "record", "--db", str(db), "--packet", packet_id, "--decision", "promote", "--reviewer", "tester", "--rationale", "test", "--json")
    proc = cli(tmp_path, "apply", "local", "--db", str(db), "--packet", packet_id, "--reviewer", "tester", "--confirm", "--json", check=False)
    assert proc.returncode == 7
    assert "artifact_type_review_only" in proc.stderr

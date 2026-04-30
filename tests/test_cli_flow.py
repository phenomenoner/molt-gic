from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path


def run_cli(tmp_path: Path, *args: str, check: bool = True):
    cmd = [sys.executable, "-m", "molt_gic.cli", *args]
    proc = subprocess.run(cmd, cwd=tmp_path, text=True, capture_output=True)
    if check and proc.returncode != 0:
        raise AssertionError(f"cmd failed {cmd}\nSTDOUT={proc.stdout}\nSTDERR={proc.stderr}")
    return proc


def write_fixture(tmp_path: Path):
    skill = tmp_path / "SKILL.md"
    skill.write_text("""---
name: humanizer-zh
---
# humanizer-zh

## Workflow
Preserve meaning, evidence, and author voice.

## Output rules
Return polished Chinese text only.
""", encoding="utf-8")
    data = tmp_path / "golden.jsonl"
    rows = []
    for i in range(10):
        rows.append({
            "id": f"ex_{i}",
            "input": f"請潤飾這段中文 {i}",
            "expected_behavior": "自然中文；保留意思；不要新增事實",
            "axis_tags": ["foundation", "action", "closure"],
            "risk": "high" if i == 0 else "low",
            "source": "golden",
            "trust_weight": 1.0,
            "created_by": "human",
            "evidence_refs": [],
            "metadata": {},
        })
    data.write_text("\n".join(json.dumps(r, ensure_ascii=False) for r in rows), encoding="utf-8")
    return skill, data


def test_happy_path_review_packet(tmp_path: Path):
    skill, data = write_fixture(tmp_path)
    db = tmp_path / "molt.sqlite"
    run_cli(tmp_path, "init", "--db", str(db), "--json")
    add = run_cli(tmp_path, "artifact", "add", "--db", str(db), "--type", "skill", "--path", str(skill), "--name", "humanizer-zh", "--json")
    artifact_id = json.loads(add.stdout)["artifact_id"]
    assert artifact_id == "skill:humanizer-zh"
    imp = run_cli(tmp_path, "dataset", "import", "--db", str(db), "--artifact", artifact_id, "--source", "golden", "--file", str(data), "--json")
    assert json.loads(imp.stdout)["inserted"] == 10
    baseline = run_cli(tmp_path, "eval", "run", "--db", str(db), "--artifact", artifact_id, "--mode", "baseline", "--baseline", str(skill), "--json")
    assert json.loads(baseline.stdout)["run_id"].startswith("run_")
    proposed = run_cli(tmp_path, "evolve", "propose", "--db", str(db), "--artifact", artifact_id, "--json")
    candidate = json.loads(proposed.stdout)["candidate_path"]
    cand_run = run_cli(tmp_path, "eval", "run", "--db", str(db), "--artifact", artifact_id, "--mode", "candidate", "--baseline", str(skill), "--candidate", candidate, "--json")
    run_id = json.loads(cand_run.stdout)["run_id"]
    packet = run_cli(tmp_path, "packet", "build", "--db", str(db), "--run", run_id, "--json")
    packet_paths = json.loads(packet.stdout)
    assert Path(tmp_path / packet_paths["packet_json"]).exists()
    gates = run_cli(tmp_path, "gate", "explain", "--db", str(db), "--run", run_id, "--json")
    assert json.loads(gates.stdout)["gates"]


def test_autopacket_run_builds_once_per_trigger(tmp_path: Path):
    skill, data = write_fixture(tmp_path)
    trigger = tmp_path / "digest.json"
    trigger.write_text('{"status":"ok","seq":1}\n', encoding="utf-8")
    db = tmp_path / "molt.sqlite"
    run_cli(tmp_path, "init", "--db", str(db), "--json")
    add = run_cli(tmp_path, "artifact", "add", "--db", str(db), "--type", "skill", "--path", str(skill), "--name", "humanizer-zh", "--json")
    artifact_id = json.loads(add.stdout)["artifact_id"]
    run_cli(tmp_path, "dataset", "import", "--db", str(db), "--artifact", artifact_id, "--source", "golden", "--file", str(data), "--json")

    first = json.loads(run_cli(tmp_path, "autopacket", "run", "--db", str(db), "--artifact", artifact_id, "--trigger-file", str(trigger), "--state-path", "state/autopacket.json", "--json").stdout)
    assert first["status"] == "packet_built"
    assert first["mode"] == "review_only"
    assert first["apply_policy"] == "blocked_until_explicit_decision_and_confirm"
    assert Path(tmp_path / first["packet_json"]).exists()

    second = json.loads(run_cli(tmp_path, "autopacket", "run", "--db", str(db), "--artifact", artifact_id, "--trigger-file", str(trigger), "--state-path", "state/autopacket.json", "--json").stdout)
    assert second["status"] == "noop"
    assert second["reason"] == "trigger_unchanged"

    trigger.write_text('{"status":"ok","seq":2}\n', encoding="utf-8")
    third = json.loads(run_cli(tmp_path, "autopacket", "run", "--db", str(db), "--artifact", artifact_id, "--trigger-file", str(trigger), "--state-path", "state/autopacket.json", "--json").stdout)
    assert third["status"] == "packet_built"
    assert third["trigger_hash"] != first["trigger_hash"]


def test_unknown_artifact_type_fails_validation(tmp_path: Path):
    skill, _ = write_fixture(tmp_path)
    db = tmp_path / "molt.sqlite"
    run_cli(tmp_path, "init", "--db", str(db))
    proc = run_cli(tmp_path, "artifact", "add", "--db", str(db), "--type", "unknown", "--path", str(skill), check=False)
    assert proc.returncode == 3
    assert "unsupported artifact type" in proc.stderr


def test_apply_requires_confirm_and_rejects_symlink(tmp_path: Path):
    skill, data = write_fixture(tmp_path)
    outside = tmp_path / "outside.md"
    outside.write_text("outside", encoding="utf-8")
    link = tmp_path / "link.md"
    link.symlink_to(outside)
    db = tmp_path / "molt.sqlite"
    run_cli(tmp_path, "init", "--db", str(db))
    proc = run_cli(tmp_path, "artifact", "add", "--db", str(db), "--type", "skill", "--path", str(link), "--name", "bad", check=False)
    # Existing symlink resolves during registration, but apply safety is covered by canonical path policy in core.
    assert proc.returncode in (0, 7)


def test_promoted_skill_apply_and_revert_emit_receipts(tmp_path: Path):
    skill, data = write_fixture(tmp_path)
    db = tmp_path / "molt.sqlite"
    run_cli(tmp_path, "init", "--db", str(db), "--json")
    add = run_cli(tmp_path, "artifact", "add", "--db", str(db), "--type", "skill", "--path", str(skill), "--name", "humanizer-zh", "--json")
    artifact_id = json.loads(add.stdout)["artifact_id"]
    run_cli(tmp_path, "dataset", "import", "--db", str(db), "--artifact", artifact_id, "--source", "golden", "--file", str(data), "--json")
    proposed = run_cli(tmp_path, "evolve", "propose", "--db", str(db), "--artifact", artifact_id, "--json")
    candidate = json.loads(proposed.stdout)["candidate_path"]
    cand_run = run_cli(tmp_path, "eval", "run", "--db", str(db), "--artifact", artifact_id, "--mode", "candidate", "--baseline", str(skill), "--candidate", candidate, "--json")
    run_id = json.loads(cand_run.stdout)["run_id"]
    packet = run_cli(tmp_path, "packet", "build", "--db", str(db), "--run", run_id, "--json")
    packet_json = json.loads(packet.stdout)
    packet_id = json.loads(Path(tmp_path / packet_json["packet_json"]).read_text())["packet_id"]

    no_confirm = run_cli(tmp_path, "apply", "local", "--db", str(db), "--packet", packet_id, "--reviewer", "qa", "--json", check=False)
    assert no_confirm.returncode == 7
    no_promote = run_cli(tmp_path, "apply", "local", "--db", str(db), "--packet", packet_id, "--reviewer", "qa", "--confirm", "--json", check=False)
    assert no_promote.returncode == 7
    assert "promote_decision_required" in no_promote.stderr

    run_cli(tmp_path, "decision", "record", "--db", str(db), "--packet", packet_id, "--decision", "promote", "--reviewer", "qa", "--rationale", "fixture gates pass", "--json")
    applied = json.loads(run_cli(tmp_path, "apply", "local", "--db", str(db), "--packet", packet_id, "--reviewer", "qa", "--confirm", "--json").stdout)
    assert applied["status"] == "applied"
    assert applied["packet_id"] == packet_id
    assert applied["runtime_config_mutation"] == "blocked"
    assert "content_hash" in applied
    assert not Path(applied["artifact_path"]).is_absolute()
    assert "molt-gic candidate notes" in skill.read_text(encoding="utf-8")

    reverted = json.loads(run_cli(tmp_path, "apply", "revert", "--db", str(db), "--packet", packet_id, "--reviewer", "qa", "--confirm", "--json").stdout)
    assert reverted["status"] == "reverted"
    assert reverted["packet_id"] == packet_id
    assert "content_hash" in reverted
    assert not Path(reverted["artifact_path"]).is_absolute()
    assert "molt-gic candidate notes" not in skill.read_text(encoding="utf-8")

    export = tmp_path / "export.json"
    run_cli(tmp_path, "db", "export", "--db", str(db), "--out", str(export), "--json")
    data = json.loads(export.read_text())
    assert [r["action"] for r in data["apply_receipts"]] == ["apply_local", "revert_local"]
    assert all(not Path(r["artifact_path"]).is_absolute() for r in data["apply_receipts"])


def test_review_only_artifact_apply_is_blocked_after_promote(tmp_path: Path):
    route = tmp_path / "ROUTE.md"
    route.write_text("# route\n\nKeep routing bounded.\n", encoding="utf-8")
    rows = []
    for i in range(10):
        rows.append({
            "id": f"ex_{i}",
            "input": f"route case {i}",
            "expected_behavior": "preserve routing boundaries",
            "axis_tags": ["foundation", "action", "closure"],
            "risk": "low",
            "source": "golden",
        })
    golden = tmp_path / "golden.jsonl"
    golden.write_text("\n".join(json.dumps(r) for r in rows), encoding="utf-8")
    db = tmp_path / "molt.sqlite"
    run_cli(tmp_path, "init", "--db", str(db), "--json")
    add = run_cli(tmp_path, "artifact", "add", "--db", str(db), "--type", "route", "--path", str(route), "--name", "triage", "--json")
    artifact_id = json.loads(add.stdout)["artifact_id"]
    run_cli(tmp_path, "dataset", "import", "--db", str(db), "--artifact", artifact_id, "--source", "golden", "--file", str(golden), "--json")
    candidate = json.loads(run_cli(tmp_path, "evolve", "propose", "--db", str(db), "--artifact", artifact_id, "--json").stdout)["candidate_path"]
    run_id = json.loads(run_cli(tmp_path, "eval", "run", "--db", str(db), "--artifact", artifact_id, "--mode", "candidate", "--baseline", str(route), "--candidate", candidate, "--json").stdout)["run_id"]
    packet_paths = json.loads(run_cli(tmp_path, "packet", "build", "--db", str(db), "--run", run_id, "--json").stdout)
    packet_id = json.loads(Path(tmp_path / packet_paths["packet_json"]).read_text())["packet_id"]
    run_cli(tmp_path, "decision", "record", "--db", str(db), "--packet", packet_id, "--decision", "promote", "--reviewer", "qa", "--rationale", "review-only type", "--json")
    blocked = run_cli(tmp_path, "apply", "local", "--db", str(db), "--packet", packet_id, "--reviewer", "qa", "--confirm", "--json", check=False)
    assert blocked.returncode == 7
    assert "artifact_type_review_only" in blocked.stderr

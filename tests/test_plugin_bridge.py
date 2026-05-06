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


def test_plugin_dry_run_and_live_receipts_are_distinct(tmp_path: Path):
    db = tmp_path / "db.sqlite"
    cli(tmp_path, "init", "--db", str(db), "--json")
    dry = json.loads(cli(tmp_path, "plugin", "dry-run", "--db", str(db), "--route", "test", "--json").stdout)
    live = json.loads(cli(tmp_path, "plugin", "smoke", "--db", str(db), "--route", "test", "--confirm", "--json").stdout)
    assert dry["mode"] == "dry_run"
    assert live["mode"] == "live"
    assert dry["receipt_id"] != live["receipt_id"]
    assert dry["live"] is False
    assert live["live"] is True
    export = tmp_path / "export.json"
    cli(tmp_path, "db", "export", "--db", str(db), "--out", str(export), "--json")
    data = json.loads(export.read_text())
    assert len(data["plugin_events"]) == 2


def test_plugin_smoke_requires_confirm_and_blocks_runtime_mutation(tmp_path: Path):
    db = tmp_path / "db.sqlite"
    cli(tmp_path, "init", "--db", str(db), "--json")
    no_confirm = cli(tmp_path, "plugin", "smoke", "--db", str(db), "--json", check=False)
    assert no_confirm.returncode == 7
    blocked = cli(tmp_path, "plugin", "smoke", "--db", str(db), "--confirm", "--mutate-runtime-config", "--json", check=False)
    assert blocked.returncode == 7
    assert "runtime_config_mutation_blocked" in blocked.stderr


def test_openclaw_apply_receipt_is_explicitly_blocked():
    source = Path("openclaw-extension/index.ts").read_text(encoding="utf-8")
    assert 'status: "blocked"' in source
    assert 'reason: "packet_backed_adapter_required"' in source
    assert 'runtime_config_mutation: "blocked_for_molt_gic_apply_surface"' in source
    assert 'next_safe_action' in source


def test_openclaw_prompt_digest_policy_is_scoped_not_global():
    source = Path("openclaw-extension/index.ts").read_text(encoding="utf-8")
    assert "not a global OpenClaw runtime policy" in source
    assert "molt-gic apply policy" in source
    assert "runtime config mutation remains blocked" not in source

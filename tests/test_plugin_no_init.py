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


def test_plugin_dry_run_initializes_default_db(tmp_path: Path):
    db = tmp_path / "fresh.sqlite"
    out = json.loads(cli(tmp_path, "plugin", "dry-run", "--db", str(db), "--json").stdout)
    assert out["mode"] == "dry_run"
    assert db.exists()


def test_plugin_smoke_initializes_default_db(tmp_path: Path):
    db = tmp_path / "fresh.sqlite"
    out = json.loads(cli(tmp_path, "plugin", "smoke", "--db", str(db), "--confirm", "--json").stdout)
    assert out["mode"] == "live"
    assert db.exists()

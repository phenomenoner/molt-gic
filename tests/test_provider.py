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


def test_fixture_provider_doctor(tmp_path: Path):
    out = cli(tmp_path, "provider", "doctor", "--provider", "fixture", "--json").stdout
    payload = json.loads(out)
    assert payload["provider"] == "fixture"
    assert payload["status"] == "ok"
    assert payload["model_version"] == "v1-fixture"


def test_unknown_provider_is_typed_config_error(tmp_path: Path):
    proc = cli(tmp_path, "provider", "doctor", "--provider", "missing", "--json", check=False)
    assert proc.returncode == 4
    assert "provider error [config]" in proc.stderr


def test_bad_configured_real_provider_is_typed_config_error(tmp_path: Path):
    proc = cli(tmp_path, "provider", "doctor", "--provider", "openai", "--json", check=False)
    assert proc.returncode == 4
    assert "requires credentials" in proc.stderr

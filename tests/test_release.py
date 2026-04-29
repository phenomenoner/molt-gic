from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path


def test_release_dry_run_receipt(tmp_path: Path):
    root = Path(__file__).resolve().parents[1]
    out = tmp_path / "release.json"
    proc = subprocess.run([sys.executable, str(root / "tools" / "release_dry_run.py"), "--out", str(out)], cwd=root, text=True, capture_output=True)
    assert proc.returncode == 0, proc.stderr
    payload = json.loads(out.read_text())
    assert payload["status"] == "ok"
    assert payload["publish"] is False
    assert not payload["missing"]

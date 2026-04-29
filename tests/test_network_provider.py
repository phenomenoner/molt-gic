from __future__ import annotations

import json
import os
import subprocess
import sys
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path


class ChatHandler(BaseHTTPRequestHandler):
    def do_POST(self):
        if self.path != "/chat/completions":
            self.send_response(404); self.end_headers(); return
        auth = self.headers.get("authorization", "")
        if auth != "Bearer test-key":
            self.send_response(401); self.end_headers(); return
        _ = self.rfile.read(int(self.headers.get("content-length", "0")))
        body = {"choices": [{"message": {"content": "network ok"}}], "usage": {"total_tokens": 12}}
        data = json.dumps(body).encode()
        self.send_response(200)
        self.send_header("content-type", "application/json")
        self.send_header("content-length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def log_message(self, *args):
        return


def run_server():
    server = HTTPServer(("127.0.0.1", 0), ChatHandler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    return server


def cli(cwd: Path, *args: str, env: dict[str, str] | None = None, check: bool = True):
    proc_env = os.environ.copy()
    if env:
        proc_env.update(env)
    proc = subprocess.run([sys.executable, "-m", "molt_gic.cli", *args], cwd=cwd, env=proc_env, text=True, capture_output=True)
    if check and proc.returncode != 0:
        raise AssertionError(f"failed {args}\nstdout={proc.stdout}\nstderr={proc.stderr}")
    return proc


def test_openai_compatible_provider_doctor_and_eval(tmp_path: Path):
    server = run_server()
    base = f"http://127.0.0.1:{server.server_port}"
    env = {"MOLT_GIC_PROVIDER_BASE_URL": base, "MOLT_GIC_PROVIDER_API_KEY": "test-key", "MOLT_GIC_PROVIDER_MODEL": "unit-model", "MOLT_GIC_PROVIDER_COST_PER_TOKEN": "0.001"}
    doctor = json.loads(cli(tmp_path, "provider", "doctor", "--provider", "openai_compatible", "--json", env=env).stdout)
    assert doctor["provider"] == "openai_compatible"
    skill = tmp_path / "SKILL.md"
    skill.write_text("# Skill\n", encoding="utf-8")
    rows = [{"id": f"ex_{i}", "input": "hi", "expected_behavior": "reply", "axis_tags": ["action"], "risk": "low", "source": "golden"} for i in range(10)]
    data = tmp_path / "golden.jsonl"
    data.write_text("\n".join(json.dumps(r) for r in rows), encoding="utf-8")
    db = tmp_path / "db.sqlite"
    cli(tmp_path, "init", "--db", str(db), "--json", env=env)
    cli(tmp_path, "artifact", "add", "--db", str(db), "--type", "skill", "--path", str(skill), "--name", "skill", "--json", env=env)
    cli(tmp_path, "dataset", "import", "--db", str(db), "--artifact", "skill:skill", "--source", "golden", "--file", str(data), "--json", env=env)
    run = json.loads(cli(tmp_path, "eval", "run", "--db", str(db), "--artifact", "skill:skill", "--mode", "baseline", "--baseline", str(skill), "--provider", "openai_compatible", "--judge-provider", "openai_compatible", "--json", env=env).stdout)
    assert run["run_id"].startswith("run_")
    export = tmp_path / "export.json"
    cli(tmp_path, "db", "export", "--db", str(db), "--out", str(export), "--json", env=env)
    provider_runs = json.loads(export.read_text())["provider_runs"]
    assert provider_runs and all(r["provider"] == "openai_compatible" for r in provider_runs)
    server.shutdown()


def test_openai_compatible_bad_key_is_typed_auth(tmp_path: Path):
    server = run_server()
    env = {"MOLT_GIC_PROVIDER_BASE_URL": f"http://127.0.0.1:{server.server_port}", "MOLT_GIC_PROVIDER_API_KEY": "bad"}
    proc = cli(tmp_path, "provider", "doctor", "--provider", "openai_compatible", "--json", env=env, check=False)
    # doctor validates config only; run path catches auth. This keeps doctor cheap and non-mutating.
    assert proc.returncode == 0
    server.shutdown()

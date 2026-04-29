from __future__ import annotations

import json
import subprocess
import sys
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path


class GatewayHandler(BaseHTTPRequestHandler):
    calls = []

    def do_POST(self):
        body = self.rfile.read(int(self.headers.get("content-length", "0")))
        GatewayHandler.calls.append(json.loads(body.decode()))
        data = b'{"ok":true}'
        self.send_response(200)
        self.send_header("content-type", "application/json")
        self.send_header("content-length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def log_message(self, *args):
        return


def run_server():
    GatewayHandler.calls = []
    server = HTTPServer(("127.0.0.1", 0), GatewayHandler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    return server


def cli(cwd: Path, *args: str, check: bool = True):
    proc = subprocess.run([sys.executable, "-m", "molt_gic.cli", *args], cwd=cwd, text=True, capture_output=True)
    if check and proc.returncode != 0:
        raise AssertionError(f"failed {args}\nstdout={proc.stdout}\nstderr={proc.stderr}")
    return proc


def test_plugin_hook_spec_and_gateway_live_smoke(tmp_path: Path):
    db = tmp_path / "db.sqlite"
    cli(tmp_path, "init", "--db", str(db), "--json")
    spec = json.loads(cli(tmp_path, "plugin", "hook-spec", "--route", "unit", "--json").stdout)
    assert spec["schema"] == "molt-gic.gateway-hook.v1"
    server = run_server()
    url = f"http://127.0.0.1:{server.server_port}/hook"
    live = json.loads(cli(tmp_path, "plugin", "smoke", "--db", str(db), "--route", "unit", "--gateway-url", url, "--confirm", "--json").stdout)
    assert live["mode"] == "live"
    assert live["gateway_status"] == 200
    assert GatewayHandler.calls and GatewayHandler.calls[0]["kind"] == "molt_gic_smoke"
    server.shutdown()

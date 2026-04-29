from __future__ import annotations

import json
import os
import shutil
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DB = ROOT / ".smoke.sqlite"


def run(*args: str) -> dict:
    proc = subprocess.run(["uv", "run", "molt-gic", *args], cwd=ROOT, text=True, capture_output=True)
    if proc.returncode != 0:
        raise SystemExit(f"failed: {' '.join(args)}\nstdout={proc.stdout}\nstderr={proc.stderr}")
    print(proc.stdout.strip())
    return json.loads(proc.stdout)


def main() -> None:
    for path in [ROOT / ".molt-gic", DB, ROOT / "smoke-export.json"]:
        if path.is_dir():
            shutil.rmtree(path)
        elif path.exists():
            path.unlink()
    run("init", "--db", str(DB), "--json")
    run("provider", "doctor", "--provider", "fixture", "--json")
    run("artifact", "add", "--db", str(DB), "--type", "skill", "--path", "examples/humanizer-zh/SKILL.md", "--name", "humanizer-zh", "--json")
    run("dataset", "import", "--db", str(DB), "--artifact", "skill:humanizer-zh", "--source", "golden", "--file", "examples/humanizer-zh/golden.jsonl", "--json")
    run("eval", "run", "--db", str(DB), "--artifact", "skill:humanizer-zh", "--mode", "baseline", "--baseline", "examples/humanizer-zh/SKILL.md", "--json")
    cand = run("evolve", "propose", "--db", str(DB), "--artifact", "skill:humanizer-zh", "--strategy", "hybrid", "--json")["candidate_path"]
    run_id = run("eval", "run", "--db", str(DB), "--artifact", "skill:humanizer-zh", "--mode", "candidate", "--baseline", "examples/humanizer-zh/SKILL.md", "--candidate", cand, "--json")["run_id"]
    gates = run("gate", "explain", "--db", str(DB), "--run", run_id, "--json")
    packet = run("packet", "build", "--db", str(DB), "--run", run_id, "--json")
    packet_id = Path(packet["packet_json"]).stem
    run("replay", "packet", "--db", str(DB), "--packet", packet_id, "--json")
    run("pilot", "verify", "--db", str(DB), "--artifact", "skill:humanizer-zh", "--json")
    run("security", "scan", "--path", "examples/humanizer-zh", "--json")
    run("adapter", "discover", "--root", "examples", "--json")
    run("plugin", "dry-run", "--db", str(DB), "--route", "local", "--json")
    run("plugin", "smoke", "--db", str(DB), "--route", "local", "--confirm", "--json")
    run("db", "export", "--db", str(DB), "--out", "smoke-export.json", "--json")
    assert gates["gates"]
    assert (ROOT / packet["packet_md"]).exists()
    assert (ROOT / packet["packet_json"]).exists()
    export = json.loads((ROOT / "smoke-export.json").read_text())
    assert export["artifacts"] and export["runs"] and export["gates"]
    print(f"SMOKE_OK run={run_id} packet_md={packet['packet_md']} packet_json={packet['packet_json']} gates={len(gates['gates'])}")
    if os.environ.get("MOLT_GIC_KEEP_SMOKE") != "1":
        for path in [ROOT / ".molt-gic", DB, ROOT / "smoke-export.json"]:
            if path.is_dir():
                shutil.rmtree(path)
            elif path.exists():
                path.unlink()


if __name__ == "__main__":
    main()

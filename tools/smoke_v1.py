from __future__ import annotations

import json
import shutil
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DB = ROOT / ".smoke-v1.sqlite"

ARTIFACTS = [
    ("skill", "humanizer-zh", "examples/humanizer-zh/SKILL.md", "examples/humanizer-zh/golden.jsonl"),
    ("prompt", "brief-summarizer", "examples/brief-summarizer/PROMPT.md", "examples/brief-summarizer/golden.jsonl"),
    ("route", "route-triage", "examples/route-triage/ROUTE.md", "examples/route-triage/golden.jsonl"),
]


def run(*args: str, check: bool = True) -> dict:
    proc = subprocess.run(["uv", "run", "molt-gic", *args], cwd=ROOT, text=True, capture_output=True)
    if check and proc.returncode != 0:
        raise SystemExit(f"failed: {' '.join(args)}\nstdout={proc.stdout}\nstderr={proc.stderr}")
    if proc.stdout.strip():
        print(proc.stdout.strip())
        return json.loads(proc.stdout)
    return {"returncode": proc.returncode, "stderr": proc.stderr}


def cleanup() -> None:
    for path in [ROOT / ".molt-gic", DB, ROOT / "v1-pilot-report.md"]:
        if path.is_dir():
            shutil.rmtree(path)
        elif path.exists():
            path.unlink()


def main() -> None:
    cleanup()
    run("init", "--db", str(DB), "--json")
    packets = []
    review_only_checked = False
    for typ, name, path, dataset in ARTIFACTS:
        artifact_id = f"{typ}:{name}"
        run("artifact", "add", "--db", str(DB), "--type", typ, "--path", path, "--name", name, "--json")
        run("dataset", "import", "--db", str(DB), "--artifact", artifact_id, "--source", "golden", "--file", dataset, "--json")
        run("eval", "run", "--db", str(DB), "--artifact", artifact_id, "--mode", "baseline", "--baseline", path, "--json")
        candidate = run("evolve", "propose", "--db", str(DB), "--artifact", artifact_id, "--json")["candidate_path"]
        run_id = run("eval", "run", "--db", str(DB), "--artifact", artifact_id, "--mode", "candidate", "--baseline", path, "--candidate", candidate, "--json")["run_id"]
        packet = run("packet", "build", "--db", str(DB), "--run", run_id, "--json")
        packets.append((artifact_id, run_id, packet))
        if typ != "skill" and not review_only_checked:
            packet_id = Path(packet["packet_json"]).stem
            run("decision", "record", "--db", str(DB), "--packet", packet_id, "--decision", "promote", "--reviewer", "pilot", "--rationale", "review-only boundary check", "--json")
            blocked = run("apply", "local", "--db", str(DB), "--packet", packet_id, "--reviewer", "pilot", "--confirm", "--json", check=False)
            if blocked["returncode"] != 7:
                raise SystemExit("expected review-only apply to exit 7")
            review_only_checked = True
    report = ROOT / "v1-pilot-report.md"
    report.write_text("# v1 pilot report\n\n" + "\n".join(f"- {a}: run `{r}`, packet `{p['packet_md']}`" for a, r, p in packets) + "\n\nReview-only non-skill apply boundary: PASS\n", encoding="utf-8")
    assert len(packets) == 3
    print(f"SMOKE_V1_OK artifacts={len(packets)} report={report.name}")
    cleanup()


if __name__ == "__main__":
    main()

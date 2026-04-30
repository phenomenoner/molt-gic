#!/usr/bin/env python3
"""Sync the OpenClaw molt-gic autonomy digest and build a review-only packet.

Cron contract:
- prints NO_REPLY when the digest has already been packeted
- prints one compact JSON object when a packet is built
- exits non-zero on gateway/ledger/config failures
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
SRC_ROOT = REPO_ROOT / "src"
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

from molt_gic.core import autopacket_run, json_dumps


def gateway_digest() -> dict:
    proc = subprocess.run(
        ["openclaw", "gateway", "call", "moltGic.autonomyDigest", "--json"],
        text=True,
        capture_output=True,
        timeout=30,
    )
    if proc.returncode != 0:
        raise RuntimeError(f"gateway autonomyDigest failed exit={proc.returncode} stderr={proc.stderr.strip()[:500]}")
    try:
        payload = json.loads(proc.stdout)
    except json.JSONDecodeError as exc:
        raise RuntimeError(f"gateway autonomyDigest returned invalid JSON: {exc}") from exc
    if payload.get("schema") != "molt-gic.autonomy.digest.v1":
        raise RuntimeError(f"unexpected digest schema: {payload.get('schema')!r}")
    return payload


def write_trigger(path: Path, digest: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json_dumps(digest) + "\n", encoding="utf-8")
    tmp.replace(path)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--db", default=str(REPO_ROOT / ".molt-gic.sqlite"))
    parser.add_argument("--artifact", default="skill:molt-gic-autopacket")
    parser.add_argument("--trigger-file", default=str(REPO_ROOT / ".molt-gic/triggers/openclaw-autonomy-digest.json"))
    parser.add_argument("--out-dir", default=str(REPO_ROOT / ".molt-gic/packets"))
    parser.add_argument("--state-path", default=str(REPO_ROOT / ".molt-gic/autopacket-state.json"))
    parser.add_argument("--provider", default="fixture")
    parser.add_argument("--judge-provider", default="fixture")
    args = parser.parse_args(argv)

    digest = gateway_digest()
    trigger_path = Path(args.trigger_file)
    write_trigger(trigger_path, digest)

    result = autopacket_run(
        db=args.db,
        artifact_id=args.artifact,
        trigger_files=[str(trigger_path)],
        out_dir=args.out_dir,
        state_path=args.state_path,
        provider_id=args.provider,
        judge_provider_id=args.judge_provider,
    )
    if result.get("status") == "noop":
        print("NO_REPLY")
        return 0
    print(json_dumps(result))
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as exc:  # noqa: BLE001 - cron should get a concise stderr
        print(f"autopacket_openclaw_digest: {exc}", file=sys.stderr)
        raise SystemExit(1)

#!/usr/bin/env python3
"""Sync the OpenClaw molt-gic autonomy digest and build a review-only packet.

Cron contract:
- prints NO_REPLY when the digest has already been packeted
- prints a concise human review notice when a packet is built by default
- exits non-zero on gateway/ledger/config failures
"""

from __future__ import annotations

import argparse
import json
import os
import shlex
import subprocess
import sys
from collections import Counter
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
SRC_ROOT = REPO_ROOT / "src"
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

from molt_gic.core import autopacket_run, json_dumps


SEMANTIC_DIGEST_SCHEMA = "molt-gic.autopacket.openclaw-digest-trigger.v1"


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


def normalize_digest_for_trigger(digest: dict) -> dict:
    """Return a stable trigger payload from a volatile OpenClaw digest.

    The raw digest contains `updated_at` and per-receipt timestamps that can
    churn every agent-end without changing the underlying recommendation.  The
    autopacket trigger should move on semantic changes, not clock drift.
    """
    receipt_counts = Counter(
        (str(r.get("schema", "unknown")), str(r.get("status", "unknown")))
        for r in digest.get("receipts", [])
        if isinstance(r, dict)
    )
    return {
        "schema": SEMANTIC_DIGEST_SCHEMA,
        "source_schema": digest.get("schema"),
        "status": digest.get("status"),
        "last_action": digest.get("last_action"),
        "evaluation": digest.get("evaluation"),
        "suggested_evolution": digest.get("suggested_evolution"),
        "next_safe_action": digest.get("next_safe_action"),
        "apply_policy": digest.get("apply_policy"),
        "receipt_summary": [
            {"schema": schema, "status": status}
            for (schema, status), _count in sorted(receipt_counts.items())
        ],
    }


def packet_id_from_path(packet_json: str | None) -> str:
    if not packet_json:
        return "<packet_id>"
    return Path(packet_json).stem


def add_human_review_handoff(result: dict, db: str, reviewer: str) -> dict:
    if result.get("status") != "packet_built":
        return result
    packet_id = packet_id_from_path(result.get("packet_json"))
    q_db = shlex.quote(db)
    q_packet = shlex.quote(packet_id)
    q_reviewer = shlex.quote(reviewer)
    q_promote_rationale = shlex.quote(f"reviewed packet {packet_id}")
    q_reject_rationale = shlex.quote("not accepted")
    decision_command = (
        f"molt-gic decision record --db {q_db} --packet {q_packet} "
        f"--decision promote --reviewer {q_reviewer} --rationale {q_promote_rationale} --json"
    )
    apply_command = (
        f"molt-gic apply local --db {q_db} --packet {q_packet} "
        f"--reviewer {q_reviewer} --confirm --json"
    )
    reject_command = (
        f"molt-gic decision record --db {q_db} --packet {q_packet} "
        f"--decision reject --reviewer {q_reviewer} --rationale {q_reject_rationale} --json"
    )
    enriched = dict(result)
    enriched["human_review"] = {
        "required": True,
        "reason": "review_only_packet_built",
        "review_packet": result.get("packet_md"),
        "review_packet_json": result.get("packet_json"),
        "blocked_until": "human_review_and_confirm",
        "decision_command": decision_command,
        "apply_command": apply_command,
        "reject_command": reject_command,
        "scheduled_job_policy": "must_not_run_decision_or_apply",
    }
    return enriched


def _resolve_existing_path(path_value: str | None) -> Path | None:
    if not path_value:
        return None
    raw = Path(path_value)
    if raw.is_absolute():
        candidates = [raw]
    else:
        candidates = [REPO_ROOT / raw, REPO_ROOT.parent / raw, raw]
    for p in candidates:
        if p.is_file():
            return p
    return None


def _read_packet_payload(packet_json: str | None) -> dict:
    p = _resolve_existing_path(packet_json)
    if not p:
        return {}
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except Exception:  # noqa: BLE001 - review summary is best-effort
        return {}


def _candidate_adds_only_generic_notes(candidate_text: str, artifact_text: str) -> bool:
    marker = "\n## molt-gic candidate notes\n"
    if marker not in candidate_text:
        return False
    before, after = candidate_text.rsplit(marker, 1)
    expected_lines = {
        "- Preserve scope and authority boundaries.",
        "- Add a verifier pass before final output.",
        "- Keep non-changing sections byte-identical where possible.",
    }
    actual_lines = {line.strip() for line in after.splitlines() if line.strip()}
    return actual_lines == expected_lines and before.rstrip() == artifact_text.rstrip()


def build_executive_review(result: dict) -> dict:
    """Create an operator-facing pre-review summary before human confirm.

    This is intentionally conservative and deterministic.  It gives the human a
    first-pass marshal recommendation but does not record a decision or apply.
    """
    packet = _read_packet_payload(result.get("packet_json"))
    gates = packet.get("gates", []) if isinstance(packet.get("gates"), list) else []
    failing = [g.get("name") for g in gates if g.get("status") != "pass"]
    non_waivable_failing = [g.get("name") for g in gates if g.get("status") != "pass" and g.get("non_waivable")]
    recommendation = str(result.get("recommendation_status") or packet.get("recommendation_status") or "unknown")

    candidate_path = _resolve_existing_path(result.get("candidate_path"))
    candidate_text = candidate_path.read_text(encoding="utf-8") if candidate_path else ""
    rollback = packet.get("rollback", {}) if isinstance(packet.get("rollback"), dict) else {}
    artifact_path = rollback.get("restore_path")
    artifact_file = _resolve_existing_path(artifact_path)
    artifact_text = artifact_file.read_text(encoding="utf-8") if artifact_file else ""

    generic_only = bool(candidate_text and artifact_text and _candidate_adds_only_generic_notes(candidate_text, artifact_text))
    if non_waivable_failing:
        decision = "reject"
        reason = f"non-waivable gates failed: {', '.join(map(str, non_waivable_failing))}"
    elif generic_only:
        decision = "reject"
        reason = "candidate appears to add only generic molt-gic notes; low product value"
    elif failing:
        decision = "revise"
        reason = f"some gates failed or need attention: {', '.join(map(str, failing))}"
    elif recommendation == "recommend":
        decision = "approve"
        reason = "all gates passed and candidate does not look like a generic smoke-only patch"
    else:
        decision = "revise"
        reason = f"packet recommendation is {recommendation!r}; inspect before promote"

    gate_summary = f"{len(gates) - len(failing)}/{len(gates)} gates pass" if gates else "no gate details found"
    return {
        "summary": f"{packet.get('artifact_id', result.get('artifact_id'))} packet {packet.get('packet_id', packet_id_from_path(result.get('packet_json')))}: {gate_summary}; recommendation={recommendation}.",
        "suggested_decision": decision,
        "rationale": reason,
        "candidate_path": str(candidate_path) if candidate_path else result.get("candidate_path"),
        "generic_smoke_candidate": generic_only,
        "failing_gates": failing,
        "non_waivable_failing_gates": non_waivable_failing,
    }


def render_human_review_notice(result: dict) -> str:
    review = result.get("human_review", {})
    if result.get("status") != "packet_built" or not review:
        return json_dumps(result)
    lines = [
        "MOLT-GIC REVIEW REQUIRED",
        f"status={result.get('status')}",
        f"recommendation={result.get('recommendation_status')}",
        f"executive_suggests={result.get('executive_review', {}).get('suggested_decision')}",
        f"summary={result.get('executive_review', {}).get('summary')}",
        f"rationale={result.get('executive_review', {}).get('rationale')}",
        f"run_id={result.get('run_id')}",
        f"packet_md={review.get('review_packet')}",
        f"packet_json={review.get('review_packet_json')}",
        f"blocked_until={review.get('blocked_until')}",
        "",
        "Review first. Cron/job must not apply.",
        "Reject:",
        str(review.get("reject_command")),
        "Promote decision:",
        str(review.get("decision_command")),
        "Apply after promote only:",
        str(review.get("apply_command")),
    ]
    return "\n".join(lines)


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
    parser.add_argument("--raw-digest-file", default=str(REPO_ROOT / ".molt-gic/triggers/openclaw-autonomy-digest.raw.json"))
    parser.add_argument("--out-dir", default=str(REPO_ROOT / ".molt-gic/packets"))
    parser.add_argument("--state-path", default=str(REPO_ROOT / ".molt-gic/autopacket-state.json"))
    parser.add_argument("--provider", default="fixture")
    parser.add_argument("--judge-provider", default="fixture")
    parser.add_argument("--reviewer", default="human")
    parser.add_argument("--format", choices=["human", "json"], default="human")
    args = parser.parse_args(argv)

    os.chdir(REPO_ROOT)

    digest = gateway_digest()
    raw_digest_path = Path(args.raw_digest_file)
    write_trigger(raw_digest_path, digest)
    semantic_trigger = normalize_digest_for_trigger(digest)
    trigger_path = Path(args.trigger_file)
    write_trigger(trigger_path, semantic_trigger)

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
    enriched = add_human_review_handoff(result, args.db, args.reviewer)
    if enriched.get("status") == "packet_built":
        enriched["executive_review"] = build_executive_review(enriched)
    if args.format == "json":
        print(json_dumps(enriched))
    else:
        print(render_human_review_notice(enriched))
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as exc:  # noqa: BLE001 - cron should get a concise stderr
        print(f"autopacket_openclaw_digest: {exc}", file=sys.stderr)
        raise SystemExit(1)

from __future__ import annotations

import importlib.util
from pathlib import Path


SCRIPT = Path(__file__).resolve().parents[1] / "tools" / "autopacket_openclaw_digest.py"
spec = importlib.util.spec_from_file_location("autopacket_openclaw_digest", SCRIPT)
mod = importlib.util.module_from_spec(spec)
assert spec and spec.loader
spec.loader.exec_module(mod)


def test_normalize_digest_ignores_volatile_timestamps():
    base = {
        "schema": "molt-gic.autonomy.digest.v1",
        "status": "ok",
        "updated_at": "2026-04-30T01:00:00Z",
        "last_action": "agent_end passive evaluation",
        "evaluation": "latest receipt status=ok, schema=molt-gic.agent-end.receipt.v1",
        "suggested_evolution": "propose review-only packet",
        "next_safe_action": "/molt-gic evolve --review-only",
        "apply_policy": "packet-backed apply with confirm",
        "receipts": [
            {"status": "ok", "schema": "molt-gic.agent-end.receipt.v1", "ts": "2026-04-30T01:00:00Z"},
            {"status": "ok", "schema": "molt-gic.agent-end.receipt.v1", "ts": "2026-04-30T01:01:00Z"},
        ],
    }
    changed_clock = dict(base)
    changed_clock["updated_at"] = "2026-04-30T02:00:00Z"
    changed_clock["receipts"] = [
        {"status": "ok", "schema": "molt-gic.agent-end.receipt.v1", "ts": "2026-04-30T02:00:00Z"},
        {"status": "ok", "schema": "molt-gic.agent-end.receipt.v1", "ts": "2026-04-30T02:01:00Z"},
    ]

    assert mod.normalize_digest_for_trigger(base) == mod.normalize_digest_for_trigger(changed_clock)


def test_normalize_digest_ignores_receipt_volume_churn():
    base = {
        "schema": "molt-gic.autonomy.digest.v1",
        "status": "ok",
        "last_action": "agent_end passive evaluation",
        "evaluation": "latest receipt status=ok, schema=molt-gic.agent-end.receipt.v1",
        "suggested_evolution": "propose review-only packet",
        "next_safe_action": "/molt-gic evolve --review-only",
        "apply_policy": "packet-backed apply with confirm",
        "receipts": [{"status": "ok", "schema": "molt-gic.agent-end.receipt.v1", "ts": "x"}],
    }
    more_receipts = dict(base)
    more_receipts["receipts"] = [
        {"status": "ok", "schema": "molt-gic.agent-end.receipt.v1", "ts": "x"},
        {"status": "ok", "schema": "molt-gic.agent-end.receipt.v1", "ts": "y"},
    ]

    assert mod.normalize_digest_for_trigger(base) == mod.normalize_digest_for_trigger(more_receipts)


def test_normalize_digest_moves_on_semantic_change():
    base = {
        "schema": "molt-gic.autonomy.digest.v1",
        "status": "ok",
        "last_action": "agent_end passive evaluation",
        "evaluation": "latest receipt status=ok, schema=molt-gic.agent-end.receipt.v1",
        "suggested_evolution": "propose review-only packet",
        "next_safe_action": "/molt-gic evolve --review-only",
        "apply_policy": "packet-backed apply with confirm",
        "receipts": [{"status": "ok", "schema": "molt-gic.agent-end.receipt.v1", "ts": "x"}],
    }
    changed = dict(base)
    changed["apply_policy"] = "runtime config mutation blocked"

    assert mod.normalize_digest_for_trigger(base) != mod.normalize_digest_for_trigger(changed)


def test_human_review_handoff_names_review_and_confirm_commands():
    result = {
        "status": "packet_built",
        "packet_md": "/tmp/packet_abc.md",
        "packet_json": "/tmp/packet_abc.json",
    }
    enriched = mod.add_human_review_handoff(result, ".molt-gic.sqlite", "ck")

    review = enriched["human_review"]
    assert review["required"] is True
    assert review["blocked_until"] == "human_review_and_confirm"
    assert review["review_packet"] == "/tmp/packet_abc.md"
    assert "decision record" in review["decision_command"]
    assert "--packet packet_abc" in review["decision_command"]
    assert "apply local" in review["apply_command"]
    assert "--confirm" in review["apply_command"]
    assert "decision record" in review["reject_command"]
    assert "--decision reject" in review["reject_command"]
    assert review["scheduled_job_policy"] == "must_not_run_decision_or_apply"


def test_human_review_handoff_shell_quotes_commands():
    enriched = mod.add_human_review_handoff(
        {"status": "packet_built", "packet_json": "/tmp/packet_abc.json"},
        "/tmp/db with spaces.sqlite",
        "reviewer name; rm -rf /",
    )

    review = enriched["human_review"]
    assert "'/tmp/db with spaces.sqlite'" in review["decision_command"]
    assert "'reviewer name; rm -rf /'" in review["decision_command"]
    assert "'reviewer name; rm -rf /'" in review["apply_command"]
    assert "'reviewer name; rm -rf /'" in review["reject_command"]

from __future__ import annotations

import importlib.util
from pathlib import Path


SCRIPT = Path(__file__).resolve().parents[1] / "tools" / "autopacket_openclaw_digest.py"
spec = importlib.util.spec_from_file_location("autopacket_openclaw_digest", SCRIPT)
mod = importlib.util.module_from_spec(spec)
assert spec and spec.loader
spec.loader.exec_module(mod)


def test_gateway_timeout_defaults_to_30s(monkeypatch):
    monkeypatch.delenv("MOLT_GIC_OPENCLAW_GATEWAY_TIMEOUT_MS", raising=False)
    monkeypatch.delenv("OPENCLAW_GATEWAY_TIMEOUT_MS", raising=False)

    assert mod._gateway_timeout_ms() == 30_000


def test_gateway_timeout_can_be_overridden(monkeypatch):
    monkeypatch.setenv("MOLT_GIC_OPENCLAW_GATEWAY_TIMEOUT_MS", "45000")

    assert mod._gateway_timeout_ms() == 45_000


def test_gateway_timeout_rejects_too_small(monkeypatch):
    monkeypatch.setenv("MOLT_GIC_OPENCLAW_GATEWAY_TIMEOUT_MS", "999")

    try:
        mod._gateway_timeout_ms()
    except RuntimeError as exc:
        assert "too small" in str(exc)
    else:  # pragma: no cover - explicit assertion keeps this pytest-version agnostic
        raise AssertionError("expected RuntimeError")


def test_gateway_attempts_default_and_override(monkeypatch):
    monkeypatch.delenv("MOLT_GIC_OPENCLAW_GATEWAY_ATTEMPTS", raising=False)
    assert mod._gateway_attempts() == 3

    monkeypatch.setenv("MOLT_GIC_OPENCLAW_GATEWAY_ATTEMPTS", "5")
    assert mod._gateway_attempts() == 5


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


def test_render_human_review_notice_is_operator_readable():
    enriched = mod.add_human_review_handoff(
        {
            "status": "packet_built",
            "recommendation_status": "recommend",
            "run_id": "run_123",
            "packet_md": "/tmp/packet_abc.md",
            "packet_json": "/tmp/packet_abc.json",
        },
        ".molt-gic.sqlite",
        "human",
    )
    enriched["executive_review"] = {
        "suggested_decision": "reject",
        "summary": "skill:molt-gic-autopacket packet packet_abc: 6/6 gates pass; recommendation=recommend.",
        "rationale": "candidate appears to add only generic molt-gic notes; low product value",
    }

    notice = mod.render_human_review_notice(enriched)
    assert notice.startswith("MOLT-GIC REVIEW REQUIRED")
    assert "executive_suggests=reject" in notice
    assert "summary=" in notice
    assert "rationale=" in notice
    assert "packet_md=/tmp/packet_abc.md" in notice
    assert "Review first. Cron/job must not apply." in notice
    assert "Reject:" in notice
    assert "Promote decision:" in notice
    assert "Apply after promote only:" in notice
    assert "--confirm" in notice


def test_build_executive_review_rejects_generic_smoke_candidate(tmp_path, monkeypatch):
    artifact = tmp_path / "examples/molt-gic-autopacket/SKILL.md"
    artifact.parent.mkdir(parents=True)
    artifact.write_text("# skill\n", encoding="utf-8")
    candidate = tmp_path / ".molt-gic/candidates/candidate.md"
    candidate.parent.mkdir(parents=True)
    candidate.write_text(
        "# skill\n\n## molt-gic candidate notes\n\n"
        "- Preserve scope and authority boundaries.\n"
        "- Add a verifier pass before final output.\n"
        "- Keep non-changing sections byte-identical where possible.\n",
        encoding="utf-8",
    )
    packet = tmp_path / ".molt-gic/packets/packet_test.json"
    packet.parent.mkdir(parents=True)
    packet.write_text(
        '{"packet_id":"packet_test","artifact_id":"skill:molt-gic-autopacket","recommendation_status":"recommend",'
        '"gates":[{"name":"artifact_scope","status":"pass","non_waivable":1}],'
        '"rollback":{"restore_path":"examples/molt-gic-autopacket/SKILL.md"}}',
        encoding="utf-8",
    )
    monkeypatch.setattr(mod, "REPO_ROOT", tmp_path)

    review = mod.build_executive_review(
        {
            "status": "packet_built",
            "artifact_id": "skill:molt-gic-autopacket",
            "candidate_path": ".molt-gic/candidates/candidate.md",
            "packet_json": str(packet),
            "recommendation_status": "recommend",
        }
    )

    assert review["suggested_decision"] == "reject"
    assert review["generic_smoke_candidate"] is True
    assert "low product value" in review["rationale"]

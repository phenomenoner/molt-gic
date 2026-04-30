# Autopacket human review contract

Status: v1

## Goal

When an unattended OpenClaw cron builds a `molt-gic` review-only packet, a human/operator must know:

1. a packet exists,
2. where to review it,
3. what is intentionally blocked,
4. the exact commands for approve/apply if they choose to proceed.

## Notification path

```text
cron schedule
  -> isolated cron worker
  -> python3 tools/autopacket_openclaw_digest.py
  -> OpenClaw gateway moltGic.autonomyDigest
  -> normalized trigger file
  -> molt-gic autopacket_run
  -> packet_built JSON with human_review block
  -> Telegram delivery to operator
```

If the normalized trigger is unchanged, the helper prints `NO_REPLY` and the operator is not interrupted.

If a packet is built, the helper prints JSON containing:

```json
{
  "status": "packet_built",
  "packet_md": "...",
  "packet_json": "...",
  "human_review": {
    "required": true,
    "reason": "review_only_packet_built",
    "review_packet": "...",
    "decision_command": "molt-gic decision record ...",
    "apply_command": "molt-gic apply local ... --confirm",
    "blocked_until": "human_review_and_confirm"
  }
}
```

The notification is a review request, not permission to apply. The scheduled job must never run the decision/apply commands.

## Semantic trigger normalization

The OpenClaw autonomy digest contains volatile fields such as timestamps and recent receipt timestamps. Those fields are useful evidence but should not cause a new packet by themselves.

The OpenClaw helper writes two files:

- `.molt-gic/triggers/openclaw-autonomy-digest.raw.json` — raw digest evidence
- `.molt-gic/triggers/openclaw-autonomy-digest.json` — semantic trigger used for packet gating

The semantic trigger keeps stable decision fields:

- `schema`
- `status`
- `last_action`
- `evaluation`
- `suggested_evolution`
- `next_safe_action`
- `apply_policy`
- receipt summary grouped by `schema` + `status`

It drops volatile receipt timestamps and receipt counts. Therefore ordinary timestamp/window churn returns `NO_REPLY`; a changed recommendation, status, policy, receipt kind, or receipt status can still build a new packet.

## Human operator flow

1. Open `packet_md` from the notification.
2. Inspect recommendation, diffs, gates, and rollback note.
3. If rejected: no action is required, or record a reject decision.
4. If accepted:

```bash
molt-gic decision record --db .molt-gic.sqlite --packet <packet_id> --decision promote --reviewer <name> --rationale "..." --json
molt-gic apply local --db .molt-gic.sqlite --packet <packet_id> --reviewer <name> --confirm --json
```

Rollback remains:

```bash
molt-gic apply revert --db .molt-gic.sqlite --packet <packet_id> --reviewer <name> --confirm --json
```

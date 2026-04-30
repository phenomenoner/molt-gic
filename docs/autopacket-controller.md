# Review-only autopacket controller

Status: v1 installable pattern

The autopacket controller is the safe "auto-unsheath" layer for `molt-gic`.
It turns fresh self-improvement signal into a review packet, but it never applies the packet.

```text
signal file / digest / receipt changes
  -> review-only candidate
  -> candidate eval
  -> packet build
  -> operator review
  -> optional explicit decision + packet-backed apply
```

## Goal

Produce the next smallest review-only packet automatically when a configured signal changes.

Good signals include:

- an OpenClaw passive autonomy digest
- a local self-improvement digest
- a trace-mining import receipt
- a human-authored queue file
- any deterministic JSON/Markdown receipt that means "new evidence is ready"

## Non-goals

- no runtime configuration mutation
- no direct OpenClaw apply
- no packet-backed `apply local`
- no external posting
- no secret-bearing artifact export
- no automatic promotion decision

## Controller contract

Run:

```bash
molt-gic autopacket run \
  --db .molt-gic.sqlite \
  --artifact skill:my-skill \
  --trigger-file memory/molt-gic-autonomy-digest.json \
  --out-dir .molt-gic/packets \
  --state-path .molt-gic/autopacket-state.json \
  --json
```

Behavior:

- If the artifact hash plus trigger-file hashes are unchanged since the last successful packet, return `status: "noop"`.
- If the trigger changed, create a review-only candidate, evaluate it, build packet Markdown + JSON, and write state.
- The command exits non-zero for missing artifact/config/model/safety failures.
- The command does not call `decision record`, `apply local`, or any OpenClaw runtime mutation path.

## Expected JSON fields

```json
{
  "status": "packet_built",
  "mode": "review_only",
  "artifact_id": "skill:my-skill",
  "candidate_path": ".molt-gic/candidates/...md",
  "run_id": "run_...",
  "packet_md": ".molt-gic/packets/packet_....md",
  "packet_json": ".molt-gic/packets/packet_....json",
  "state_path": ".molt-gic/autopacket-state.json",
  "apply_policy": "blocked_until_explicit_decision_and_confirm"
}
```

No-op example:

```json
{
  "status": "noop",
  "reason": "trigger_unchanged",
  "mode": "review_only",
  "artifact_id": "skill:my-skill"
}
```

## OpenClaw cron pattern

Use a deterministic scheduled command when possible. Example agent-readable job text:

```text
Run exactly one command:
uv run molt-gic autopacket run --db .molt-gic.sqlite --artifact skill:my-skill --trigger-file memory/molt-gic-autonomy-digest.json --out-dir .molt-gic/packets --state-path .molt-gic/autopacket-state.json --json

Reply rules:
- If JSON status is noop: reply exactly NO_REPLY.
- If JSON status is packet_built: reply with packet_md, packet_json, run_id, and recommendation status.
- If command fails: reply BLOCKED with command, exit code, stderr summary, and next action.
- Do not run apply. Do not mutate runtime config.
```

## Human review and apply

After a packet is built, a human or authorized operator may inspect the packet.
Only then may they choose:

```bash
molt-gic decision record --packet <packet_id> --decision promote|revise|reject --reviewer <name> --rationale "..."
molt-gic apply local --packet <packet_id> --reviewer <name> --confirm
```

`apply local` remains packet-backed, confirmed, and constrained to the registered artifact path.

## Rollback

Disable the scheduler/controller that invokes `autopacket run`.
The generated candidate and packet files are inert review artifacts. If a later packet was applied, use:

```bash
molt-gic apply revert --packet <packet_id> --reviewer <name> --confirm
```

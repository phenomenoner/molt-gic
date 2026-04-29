# molt-gic v1 packets

v1 extends the public v0 packet set with P15-P22.

## P15 — Provider adapter contract

Scope:

- provider interface
- fixture provider
- real provider configuration surface
- typed error taxonomy
- provider receipt schema

Acceptance:

- `provider doctor --provider fixture` passes
- bad provider config returns typed error
- provider receipt records provider/model/version/latency/cost/retries

## P16 — Judge stack

Scope:

- primary judge
- opposite critic
- adversarial judge
- strict JSON result schema
- judge prompt/version hashing

Acceptance:

- malformed judge output retries once then fails bounded
- judge disagreement is visible in gates/packet
- opposite critic has a public prompt/output contract

## P17 — Trace miner

Scope:

- explicit trace import
- redaction
- dedupe
- provenance hash
- promotion gate from trace-mined to golden

Acceptance:

- secret trace blocked/redacted
- duplicate trace deduped
- promotion requires reviewer and reason

## P18 — Artifact family expansion

Scope:

- `prompt`
- `tool_description`
- `route`
- type-specific masks and safety policies

Acceptance:

- all types can be registered and evaluated
- unsafe apply is blocked
- non-skill artifacts can remain review-only

## P19 — OpenClaw plugin and gateway bridge

Scope:

- plugin command mapping
- gateway dry-run
- bounded live smoke
- receipt id and route readback

Acceptance:

- dry-run receipt differs from live receipt
- runtime config mutation attempt exits 7
- one bounded smoke proves enabled path when confirmed

## P20 — Dashboard export and read-only UI

Scope:

- dashboard export JSON
- local/static read-only UI
- runs/gates/packets/decisions/lineage views

Acceptance:

- failed gate state visible
- no write action in UI
- dashboard export is reproducible from DB

## P21 — CI/CD release lane

Scope:

- GitHub Actions
- tests and smoke
- package build
- release dry-run
- changelog and migration notes

Acceptance:

- CI green
- release dry-run creates artifacts without publishing
- v0 smoke remains a blocker

## P22 — Multi-skill pilot closure

Scope:

- at least three real artifacts
- golden sets
- packet reports
- public closure report

Acceptance:

- all pilot artifacts have packets
- one failure keeps pilot non-passing
- closure report cites machine receipts

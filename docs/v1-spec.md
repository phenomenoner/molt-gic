# molt-gic v1 product spec

Status: public planning contract

## Goal

v1 makes molt-gic usable against real provider-backed runner/judge flows, real trace inputs, multiple artifact families, OpenClaw integration, a read-only dashboard, and a release-grade public package.

## Non-goals

v1 still does not auto-promote, mutate live runtimes without explicit human confirmation, run a background mining daemon, or provide hosted multi-tenant service controls.

## Required capabilities

### Provider runner and judge adapters

- Provider contract exposes runner, primary judge, opposite critic, and adversarial judge roles.
- Every provider call records provider id, model id, model version if known, latency, cost estimate, retry count, and error class.
- Deterministic fixture provider remains available for offline tests.
- Bad key, timeout, and provider unavailable must produce typed errors, not generic crashes.

### Trace mining

- Trace import is explicit, not a daemon.
- Imported traces are normalized, redacted, deduped, and provenance-hashed.
- Trace-mined examples cannot become golden without reviewer and rationale.

### Artifact expansion

v1 enables review/eval/packet support for:

- `skill`
- `prompt`
- `tool_description`
- `route`

Apply policy differs by type. `skill` may keep local apply behind confirmation. Higher-risk artifact families may stay review-only until their apply boundaries are proven.

### OpenClaw plugin and gateway bridge

- Plugin bridge shells or calls the portable CLI.
- Dry-run is mandatory before live smoke.
- Dry-run and live receipts have distinct fields.
- Runtime config mutation attempts remain safety violations.

### Dashboard

- v1 dashboard is read-only.
- It shows runs, gates, packets, decisions, lineage, provider receipts, and failed states.
- Dashboard data comes from export/snapshot APIs, not direct mutation endpoints.

### CI/CD

- CI runs tests, smoke, lint/type checks where available, package build, and release dry-run.
- Public release artifacts include changelog, migration notes, known risks, and verifier summary.

### Multi-skill pilot

- v1 pilot uses at least three real artifacts.
- Each artifact has a golden set and packet report.
- At least one pilot exercises a non-skill artifact family in review-only mode if apply is not yet safe.

## Invariants

- Human decision remains mandatory before apply.
- Secret scanning and redaction are non-waivable for public artifacts.
- v0 CLI commands remain backward-compatible unless a documented major change is made.
- v0 smoke remains a release blocker.
- Public docs must avoid local machine paths, internal review transcripts, and operator-only routing terms.

## Schema impact

v1 migrations are additive:

- `provider_runs`
- `trace_sources`
- artifact type policy fields
- `plugin_events`
- dashboard snapshot views or export tables

v0 rows remain readable.

# Autonomy loop: action -> evaluate -> evolve -> action

Status: v1 operator pattern

`molt-gic` is designed to support an autonomy loop without hiding control-plane decisions:

```text
action -> evaluate -> evolve -> action
```

The loop is intentionally split into bounded surfaces so each step can be verified, replayed, and rolled back.

## Step 1: Action

An action produces a reviewable artifact or receipt.

Examples:

- run a CLI command
- call an OpenClaw Gateway RPC method
- produce a candidate packet
- export a dashboard
- run a smoke test

Current OpenClaw bridge action surfaces:

- HTTP smoke route: `POST /molt-gic/hook`
- Gateway RPC smoke: `moltGic.smoke`
- Command smoke: `/molt-gic smoke`
- Gateway RPC evolve/apply receipts: `moltGic.evolve`, `moltGic.apply`
- Command evolve/apply receipts: `/molt-gic evolve`, `/molt-gic apply`

These surfaces are bounded. They do not mutate OpenClaw runtime configuration. Evolve/apply update the passive autonomy digest and emit receipts.

## Step 2: Evaluate

Evaluation decides whether the last action is acceptable.

Evaluation should use receipts, not vibes:

- SQLite ledger rows
- JSON smoke receipts
- packet JSON / markdown
- dashboard JSON / HTML
- replay receipts
- test output

A good evaluator answers:

- Did the action complete?
- Did it change only the intended surface?
- Did it produce the expected fields?
- What would prove this false?
- Should the next loop continue, pause, or rollback?

## Step 3: Evolve

Evolution proposes a bounded next change.

Examples:

- refine a candidate packet
- add a verifier
- change a route from HTTP-only to RPC
- add a read-only command surface
- update documentation after a verified behavior change

Evolution must produce a reviewable artifact before live enable. In this repo, candidate and packet artifacts are the preferred handoff shape.

## Step 4: Action again

The next action applies the smallest safe slice and emits a new receipt. The loop repeats only while all gates remain inside the approved authority and risk envelope.

## Control gates

The loop should stop when any of these are true:

- the next action would mutate runtime configuration without an explicit approval gate
- a verifier is missing
- the same failure mode repeats after bounded retries
- the required rollback path is unclear
- an external side effect would occur without authorization

## How this maps to OpenClaw

OpenClaw provides the runtime and operator surfaces:

- Gateway HTTP route for protected smoke receipts
- Gateway RPC methods for OpenClaw-native status/smoke calls
- command surface for operator-facing status/smoke
- plugin install/enable/inspect for durable activation
- gateway restart/reload as the live activation boundary

`molt-gic` provides the artifact discipline:

- ledger-backed CLI commands
- packet and replay artifacts
- dashboard exports
- dry-run vs live receipt separation
- bounded install and smoke guides

Together, the system implements autonomy as a controlled loop:

```text
OpenClaw invokes bounded action
molt-gic records receipt
verifier evaluates artifact
candidate/packet evolves next slice
operator or authorized controller triggers next bounded action
```

## Current v1 safety posture

The v1 live bridge exposes inspect/smoke plus bounded evolve/apply receipt surfaces:

- `moltGic.status`
- `moltGic.smoke`
- `moltGic.evolve`
- `moltGic.apply`
- `moltGic.autonomyDigest`
- `/molt-gic status`
- `/molt-gic smoke`
- `/molt-gic evolve`
- `/molt-gic apply`
- `/molt-gic autonomy`

Runtime config mutation remains blocked. Packet-backed local writes remain governed by the core CLI artifact policy.

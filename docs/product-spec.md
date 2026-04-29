# molt-gic public product spec

Status: v0 implementation contract

## Goal

`molt-gic` is a review-first skill evolution lab. It evaluates one registered skill artifact against golden examples, proposes a bounded candidate, produces an auditable packet, and applies the change locally only after an explicit human decision.

## Non-goals

v0 did not mutate live runtimes, auto-merge changes, post externally, train models, or manage secrets. v1 enables additional artifact families for review and evaluation while keeping higher-risk apply paths gated.

## Core loop

1. `init` creates a local SQLite ledger.
2. `artifact add` registers a skill markdown file as a baseline.
3. `dataset import` loads JSONL eval examples.
4. `eval run --mode baseline` evaluates the baseline.
5. `evolve propose` writes a bounded candidate markdown file.
6. `eval run --mode candidate` evaluates baseline and candidate together.
7. `packet build` writes `packet.md` and `packet.json`.
8. `decision record` stores promote/revise/reject.
9. `apply local --confirm` writes only the registered file and verifies hash readback.
10. `apply revert --confirm` restores the baseline hash.

## Six GIC axes

1. Foundation — scope, role, non-goals, authority boundaries
2. Context — grounding and input discipline
3. Planning — decomposition, verifier, stop-loss
4. Tools — tool choice, execution discipline, side effects
5. Action — primary output quality
6. Closure — receipts, rollback, and no overreach

The classifier runs per axis. The six axis states form a six-line signature. `changing_lines` uses 1-indexed line numbers: 1=foundation through 6=closure.

## Scoring

Each example receives six axis scores. Example scores are weighted by axis, trust, and risk. Candidate high-risk regression is computed per axis, then aggregated as the run-level minimum. A candidate with high-risk regression at or below the threshold is forced into changing-line review and cannot silently promote.

## Gates

v0 gates include artifact scope, golden example minimum, high-risk regression, trace-health, opposite critic, and significance. Non-waivable gate failure blocks promotion.

## Runner and replay policy

The runner does not execute markdown as code. It template-evaluates the skill body with an example input and records deterministic fixture trace events. Live mode replays imported, pre-recorded traces only. It never performs fresh tool execution.

## Safety policy

- Future artifact types are rejected with exit code 7.
- `apply local` requires a promote decision and `--confirm`.
- Paths are canonicalized; symlink escapes and unregistered cross-repo writes are rejected.
- Raw secrets in artifacts or replay traces are blocked/redacted before insertion.
- `artifacts.current_hash` changes only after verified local apply or revert.

## Public CLI exit codes

| Code | Meaning |
|---:|---|
| 0 | success |
| 1 | generic runtime error |
| 2 | usage error |
| 3 | validation error |
| 4 | missing dependency or config error |
| 5 | model/judge error |
| 6 | budget exceeded |
| 7 | safety policy violation |
| 10 | gate failure |

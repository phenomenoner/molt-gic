# Trace mining

Status: Phase 2 public contract

v1 trace mining is explicit. It is not a background daemon.

## Import

```bash
molt-gic trace mine import --artifact skill:humanizer-zh --file traces.jsonl --json
```

Each JSONL row may include:

- `id`
- `input` or `prompt` or `message`
- `expected_behavior` or `expected`
- `axis_tags`
- `risk`
- `trust_weight`

## Safety

During import, molt-gic:

1. computes a provenance hash for dedupe,
2. redacts secret-like text from imported examples,
3. records a `trace_sources` row,
4. creates examples as `trace_mined`, not `golden`.

Trace-mined examples require reviewer and reason before promotion to golden.

## Receipt

The import command returns:

- imported count,
- deduped count,
- redacted count,
- blocked count.

## Counterfactual checks

- duplicate trace rows must dedupe,
- secret-like trace content must be redacted or blocked,
- trace-mined examples cannot silently become golden.

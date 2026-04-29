# molt-gic v1 verifier plan

## Rule

Every v1 phase must leave machine-readable receipts and a human-readable report. `exit 0` alone is not a verifier.

## Global release blockers

```bash
uv run --with pytest pytest -q
python3 tools/smoke.py
```

Both must pass before any v1 release candidate.

## Phase verifiers

### Phase 0 — contract freeze

Artifacts:

- `docs/v1-spec.md`
- `docs/v1-roadmap.md`
- `docs/v1-packets.md`
- `docs/v1-verifier-plan.md`

Checks:

- public sanitize scan
- docs mention every required v1 scope item
- v0 smoke still passes

### Phase 1 — provider runner and judge adapters

Commands:

```bash
uv run --with pytest pytest -q -k "provider or judge"
uv run molt-gic provider doctor --provider fixture --json
uv run molt-gic eval run --provider fixture --judge-provider fixture --json ...
```

Counterfactuals:

- bad provider key returns typed config/model error
- timeout returns typed timeout error
- fixture and provider receipts include model/version/cost/latency/retries

Artifacts:

- provider receipt JSON
- judge receipt JSON
- human phase report

### Phase 2 — trace mining

Commands:

```bash
uv run molt-gic trace mine import --file traces.jsonl --json
uv run molt-gic dataset promote --example EX_ID --reviewer NAME --reason TEXT --json
```

Counterfactuals:

- secret-like trace is blocked or redacted
- duplicate trace is deduped
- trace-mined example cannot silently become golden

### Phase 3 — artifact expansion

Commands:

```bash
uv run --with pytest pytest -q -k "artifact_type or mutation"
uv run molt-gic artifact rules show --type route --json
```

Counterfactuals:

- disabled/unsafe apply path exits 7
- route/tool changes are review-only unless explicitly enabled

### Phase 4 — OpenClaw plugin and gateway bridge

Commands:

```bash
uv run molt-gic plugin dry-run --json
uv run molt-gic plugin smoke --confirm --json
```

Counterfactuals:

- dry-run receipt cannot be mistaken for live receipt
- runtime config mutation attempt exits 7

### Phase 5 — dashboard

Commands:

```bash
uv run molt-gic dashboard export --out dashboard.json --json
uv run --with pytest pytest -q -k dashboard
```

Counterfactuals:

- failed gates are visible
- dashboard has no write endpoints/actions

### Phase 6 — CI/CD release package

Commands:

```bash
uv build
uv run --with pytest pytest -q
python3 tools/smoke.py
```

Counterfactuals:

- release dry-run succeeds without publishing
- missing changelog blocks release

### Phase 7 — multi-skill pilot

Commands:

```bash
python3 tools/smoke_v1.py
uv run molt-gic pilot verify --artifact ARTIFACT_ID --json
```

Counterfactuals:

- one artifact failure keeps pilot report non-passing
- non-skill artifact remains review-only unless apply gate is proven

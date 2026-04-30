# molt-gic

`molt-gic` is a review-first agent skill evolution lab. It helps teams evaluate a skill artifact, propose bounded improvements, build an auditable review packet, and apply a local change only after an explicit human decision.

The v0 scope is intentionally narrow:

- artifact type: `skill` markdown only
- storage: local SQLite ledger
- mutation: markdown section templates and changing-line masks
- adoption: review packet + explicit human approval + reversible local apply
- safety: no live runtime mutation, no auto-merge, no external posting, no secret exposure

The GIC engine uses six engineering axes to produce a compact change signature:

1. Foundation — scope and authority boundaries
2. Context — grounding and inputs
3. Planning — decomposition and verifiers
4. Tools — tool discipline and side effects
5. Action — primary task quality
6. Closure — receipts, rollback, and summaries

## Quick start

Recommended with `uv`:

```bash
uv sync --dev
uv run molt-gic init --db .molt-gic.sqlite
uv run molt-gic artifact add --db .molt-gic.sqlite --type skill --path examples/humanizer-zh/SKILL.md --name humanizer-zh
uv run molt-gic dataset import --db .molt-gic.sqlite --artifact skill:humanizer-zh --source golden --file examples/humanizer-zh/golden.jsonl
uv run molt-gic eval run --db .molt-gic.sqlite --artifact skill:humanizer-zh --mode baseline --baseline examples/humanizer-zh/SKILL.md
uv run molt-gic evolve propose --db .molt-gic.sqlite --artifact skill:humanizer-zh --strategy hybrid
uv run molt-gic packet build --db .molt-gic.sqlite --run latest --format md,json
```

To install a safe automatic review-packet loop, use `autopacket run` with one or more deterministic trigger files:

```bash
uv run molt-gic autopacket run \
  --db .molt-gic.sqlite \
  --artifact skill:humanizer-zh \
  --trigger-file memory/molt-gic-autonomy-digest.json \
  --out-dir .molt-gic/packets \
  --state-path .molt-gic/autopacket-state.json \
  --json
```

`autopacket run` creates review-only candidate/eval/packet artifacts when the trigger changes and returns `status=noop` when it has already processed the same trigger. It never records a promote decision, never applies a packet, and never mutates runtime configuration. See `docs/autopacket-controller.md` and `examples/molt-gic-autopacket/SKILL.md`; the skill folder also includes `golden.jsonl` so installers can prepare a target ledger before scheduling the loop.



Alternative with standard Python:

```bash
python -m venv .venv
. .venv/bin/activate
pip install -e .
molt-gic --help
```

## Test and smoke

```bash
uv run --with pytest pytest -q
python3 tools/smoke.py
```

The smoke script creates a temporary local SQLite ledger, candidate, packet, and export, then removes runtime artifacts from the tracked repository surface. Generated packet output may contain local artifact paths by design; do not publish smoke outputs if your paths are private.

## Safety model

`molt-gic` does not modify a live agent runtime. `apply local` can write only to the registered artifact path after a `promote` decision and `--confirm`. Paths are canonicalized, symlink escapes are rejected, and the file hash is read back before an adoption state is recorded.

See `docs/product-spec.md` and `docs/dispatch-packets.md` for the public v0 contract.

## Roadmap

The public v1 plan is tracked in:

- `CHANGELOG.md`
- `docs/v1-spec.md`
- `docs/v1-roadmap.md`
- `docs/v1-packets.md`
- `docs/v1-verifier-plan.md`
- `docs/provider-adapters.md`
- `docs/trace-mining.md`
- `docs/artifact-types.md`
- `docs/openclaw-plugin-gateway.md`
- `docs/openclaw-install-guide.md`
- `docs/autonomy-loop.md`
- `docs/dashboard.md`
- `docs/release.md`
- `docs/v1-pilot-report.md`

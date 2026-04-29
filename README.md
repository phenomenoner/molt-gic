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

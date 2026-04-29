# Release process

Status: Phase 6 public contract

v1 releases require CI, smoke, build, and release dry-run receipts.

## Local checks

```bash
uv run --with pytest pytest -q
python3 tools/smoke.py
uv build
python3 tools/release_dry_run.py --out release-dry-run.json
```

## CI

GitHub Actions runs:

1. dependency sync,
2. tests,
3. smoke,
4. build,
5. release dry-run,
6. dry-run artifact upload.

## Release dry-run

The dry-run does not publish. It verifies required public release files and emits a JSON receipt with missing files, publish=false, and expected artifact classes.

## Required public files

- README
- changelog
- v1 spec
- v1 verifier plan
- package metadata

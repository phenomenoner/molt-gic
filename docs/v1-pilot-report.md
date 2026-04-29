# molt-gic v1 pilot report

Status: public pilot closure template

The v1 pilot uses three artifact families:

1. `skill:humanizer-zh`
2. `prompt:brief-summarizer`
3. `route:route-triage`

## Gate

The pilot is passing only when every artifact has:

- 10 golden examples,
- baseline eval,
- candidate eval,
- review packet,
- gate receipts,
- rollback path,
- public-safe report entry.

At least one non-skill artifact must prove the review-only apply boundary.

## Verifier

```bash
python3 tools/smoke_v1.py
```

Expected receipt:

```text
SMOKE_V1_OK artifacts=3
```

## Rollback

The pilot smoke uses a local temporary SQLite ledger and generated packet files. It removes generated runtime artifacts after success.

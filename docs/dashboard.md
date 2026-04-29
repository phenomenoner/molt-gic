# Dashboard

Status: Phase 5 public contract

The v1 dashboard is read-only. It is generated from database snapshots and does not expose write actions.

## Export

```bash
molt-gic dashboard export --out dashboard.json --json
```

The JSON snapshot includes:

- runs
- gates
- packets
- decisions
- lineage
- provider receipts
- plugin events
- summary counts

## Render

```bash
molt-gic dashboard render --snapshot dashboard.json --out dashboard.html --json
```

The rendered HTML is a static read-only view. It must show failed gates when they exist and must not contain write forms or mutation actions.

## Safety

Dashboard data is derived from ledger state. It is for operator visibility and public reports, not a control plane.

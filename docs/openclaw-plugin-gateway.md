# OpenClaw plugin and gateway bridge

Status: Phase 4 public contract

The v1 bridge keeps the core CLI portable. Plugin and gateway surfaces call the CLI and record receipts; they do not mutate runtime configuration as part of normal operation.

## Commands

```bash
molt-gic plugin dry-run --route local --json
molt-gic plugin smoke --route local --confirm --json
molt-gic plugin hook-spec --route local --json
```

## Dry-run before live

Dry-run receipts use `mode=dry_run` and `live=false`.

Live smoke receipts use `mode=live` and `live=true`.

The two receipt classes are intentionally distinct so a dry-run cannot be mistaken for a live smoke.

## Safety

Runtime configuration mutation is blocked by policy. A command attempting it exits with a safety error.

## Live gateway smoke

`plugin smoke` can call a bounded gateway hook when `--gateway-url` is supplied:

```bash
molt-gic plugin smoke --route local --gateway-url http://127.0.0.1:8080/hook --confirm --json
```

The command posts a small smoke payload and records the gateway status plus response hash. It does not mutate runtime configuration.

## Receipt fields

- mode
- gateway route
- receipt id
- status
- live boolean
- bounded boolean for live smoke

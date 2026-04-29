# OpenClaw plugin and gateway bridge

Status: v1 live-enabled bridge

The v1 bridge keeps the core CLI portable. Plugin and gateway surfaces call the CLI and record receipts; they do not mutate runtime configuration as part of normal operation.

## Commands

```bash
molt-gic plugin dry-run --route local --json
molt-gic plugin smoke --route local --confirm --json
molt-gic plugin hook-spec --route local --json
```

Install and enable instructions live in [`openclaw-install-guide.md`](openclaw-install-guide.md).

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

## Gateway RPC methods

The optional OpenClaw extension also registers two Gateway RPC methods:

- `moltGic.status` — read-only status and registered-surface summary.
- `moltGic.smoke` — bounded RPC smoke receipt.
- `moltGic.evolve` — bounded evolve receipt that updates the passive autonomy digest.
- `moltGic.apply` — bounded apply receipt that updates the passive autonomy digest.
- `moltGic.autonomyDigest` — current passive autonomy digest.

Example:

```bash
openclaw gateway call moltGic.status --json --token "$MOLT_GIC_GATEWAY_TOKEN"
openclaw gateway call moltGic.smoke --json --token "$MOLT_GIC_GATEWAY_TOKEN" \
  --params '{"route":"openclaw-gateway","receipt_id":"manual_rpc_smoke"}'
openclaw gateway call moltGic.evolve --json --token "$MOLT_GIC_GATEWAY_TOKEN"
openclaw gateway call moltGic.apply --json --token "$MOLT_GIC_GATEWAY_TOKEN"
openclaw gateway call moltGic.autonomyDigest --json --token "$MOLT_GIC_GATEWAY_TOKEN"
```

## Command surface

The extension also registers an authorized command surface for operator-facing checks:

```text
/molt-gic status
/molt-gic smoke
/molt-gic evolve
/molt-gic apply
/molt-gic autonomy
```

The command surface exposes bounded evolve/apply receipts and passive digest updates. Runtime config mutation remains blocked.

## Receipt fields

- mode
- gateway route
- receipt id
- status
- live boolean
- bounded boolean for live smoke

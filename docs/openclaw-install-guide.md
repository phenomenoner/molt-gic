# OpenClaw install and live enable guide

This guide installs the `molt-gic` CLI plus the optional OpenClaw gateway extension.

## Scope

The extension exposes bounded smoke/inspection surfaces only:

- HTTP smoke route: `POST /molt-gic/hook`
- Gateway RPC: `moltGic.status`
- Gateway RPC: `moltGic.smoke`
- Gateway RPC: `moltGic.evolve`
- Gateway RPC: `moltGic.apply`
- Gateway RPC: `moltGic.autonomyDigest`
- command: `/molt-gic status`
- command: `/molt-gic smoke`
- command: `/molt-gic evolve`
- command: `/molt-gic apply`
- command: `/molt-gic autonomy`

It does not mutate OpenClaw runtime configuration. Evolve/apply surfaces emit bounded receipts and update the passive autonomy digest; packet-backed local writes remain constrained by the core CLI artifact policy.

## Prerequisites

- OpenClaw gateway is installed and reachable.
- `uv` is available.
- You can restart or reload the OpenClaw gateway after plugin install.

## Install the CLI

From a checkout:

```bash
uv tool install .
molt-gic --version
```

Expected:

```text
molt-gic 0.1.2
```

## Dry-run before gateway enable

```bash
molt-gic provider doctor --provider fixture --json
molt-gic plugin dry-run --db .molt-gic-install.sqlite --route openclaw-gateway --json
molt-gic plugin smoke --db .molt-gic-install.sqlite --route openclaw-gateway --confirm --json
rm -f .molt-gic-install.sqlite .molt-gic-install.sqlite-shm .molt-gic-install.sqlite-wal
```

Expected receipts include:

- `provider=fixture`, `status=ok`
- dry-run receipt with `mode=dry_run`, `live=false`
- local live smoke receipt with `mode=live`, `live=true`

## Install the OpenClaw extension

```bash
openclaw plugins install ./openclaw-extension
openclaw plugins enable molt-gic-openclaw-extension
openclaw plugins inspect molt-gic-openclaw-extension
```

Enable the passive digest hook access:

```bash
openclaw config set plugins.entries.molt-gic-openclaw-extension.hooks.allowConversationAccess true --strict-json
```

Expected inspect summary:

- `Status: loaded`
- `HTTP routes: 1`
- source path points at the installed extension

Restart the gateway after install/enable so the running gateway loads the route and RPC methods.

## Verify HTTP smoke route

Unauthenticated requests should fail with `401 Unauthorized` when gateway auth is enabled. That proves the route exists and is protected.

For an authenticated smoke, export the gateway token without printing it:

```bash
export MOLT_GIC_GATEWAY_TOKEN="..."
MOLT_GIC_GATEWAY_TOKEN="$MOLT_GIC_GATEWAY_TOKEN" \
  molt-gic plugin smoke \
  --db .molt-gic-live.sqlite \
  --route openclaw-gateway \
  --gateway-url http://127.0.0.1:18789/molt-gic/hook \
  --confirm \
  --json
rm -f .molt-gic-live.sqlite .molt-gic-live.sqlite-shm .molt-gic-live.sqlite-wal
```

Expected fields:

```json
{
  "mode": "live",
  "live": true,
  "gateway_status": 200,
  "status": "ok"
}
```

## Verify Gateway RPC

Use `openclaw gateway call` after restart:

```bash
openclaw gateway call moltGic.status --json --token "$MOLT_GIC_GATEWAY_TOKEN"
openclaw gateway call moltGic.smoke --json --token "$MOLT_GIC_GATEWAY_TOKEN" \
  --params '{"route":"openclaw-gateway","receipt_id":"manual_rpc_smoke"}'
openclaw gateway call moltGic.evolve --json --token "$MOLT_GIC_GATEWAY_TOKEN"
openclaw gateway call moltGic.apply --json --token "$MOLT_GIC_GATEWAY_TOKEN"
openclaw gateway call moltGic.autonomyDigest --json --token "$MOLT_GIC_GATEWAY_TOKEN"
```

Expected:

- `moltGic.status` returns `schema=molt-gic.gateway-rpc.status.v1`
- `moltGic.smoke` returns `schema=molt-gic.gateway-hook.receipt.v1` and `status=ok`
- `moltGic.evolve` returns `schema=molt-gic.evolve.receipt.v1` and updates the digest.
- `moltGic.apply` returns `schema=molt-gic.apply.receipt.v1` and updates the digest.
- `moltGic.autonomyDigest` returns `schema=molt-gic.autonomy.digest.v1`.

## Verify command surface

After gateway restart, send these from an authorized OpenClaw chat surface:

```text
/molt-gic status
/molt-gic smoke
/molt-gic evolve
/molt-gic apply
/molt-gic autonomy
```

Expected:

- status reports the HTTP route, Gateway RPC methods, and blocked runtime config mutation.
- smoke returns a bounded JSON receipt with `surface=command` and `status=ok`.
- evolve/apply return bounded JSON receipts and update the passive autonomy digest.
- autonomy returns the current passive digest.

## Rollback

```bash
openclaw plugins disable molt-gic-openclaw-extension
# or
openclaw plugins uninstall molt-gic-openclaw-extension
```

Restart the gateway after rollback.

Expected rollback proof:

- `POST /molt-gic/hook` returns `404` or is absent.
- `openclaw gateway call moltGic.status` fails as unknown/unavailable.

## Artifacts you can inspect

- `.molt-gic*.sqlite` local ledgers when you keep smoke DBs
- `.molt-gic/packets/*.json` and `.molt-gic/packets/*.md` for review packets
- `.molt-gic/replay/*.json` for replay receipts
- `dashboard.json` and `dashboard.html` for dashboard exports
- OpenClaw plugin install path reported by `openclaw plugins inspect molt-gic-openclaw-extension`

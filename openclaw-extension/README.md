# molt-gic OpenClaw Extension

This extension exposes the bounded OpenClaw bridge for `molt-gic`:

- HTTP smoke route
- Gateway RPC methods
- `/molt-gic` command surface
- optional passive autonomy digest

## Policy scope

The extension does **not** own global OpenClaw runtime policy.

Any runtime-config wording emitted by this extension is scoped only to the
`molt-gic` bridge/apply surface. In particular:

- `moltGic.apply` is receipt-only and blocked from mutating runtime config.
- local `molt-gic apply local` remains packet-backed and requires explicit confirmation.
- passive autonomy digest text is status/context for the self-improvement loop; it is not a global security policy, operator policy, or session-wide mutation gate.

## Prompt-context digest

By default, recent digest status may be injected into prompt context so the
self-improvement loop can see its latest receipts. Operators can disable only the
prompt-context injection while keeping digest storage/API available:

```bash
openclaw config set plugins.entries.molt-gic-openclaw-extension.config.autonomyDigest.promptContextEnabled false --strict-json
```

This does not disable the extension or its digest RPC; it only stops the
`before_prompt_build` context prepend.

## Apply behavior

`moltGic.apply` intentionally returns a blocked receipt. This is a boundary for
the extension's own apply surface, not a statement about what an authorized
operator may do through OpenClaw's normal config tools.

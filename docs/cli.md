# CLI reference

Global default DB path: `.molt-gic.sqlite`.

```bash
molt-gic init [--db PATH] [--json]
molt-gic artifact add --type skill --path PATH [--name NAME] [--json]
molt-gic artifact list [--json]
molt-gic artifact rules show --type skill|prompt|tool_description|route [--json]
molt-gic dataset validate --file FILE [--json]
molt-gic dataset import --artifact ID --source golden|trace_mined|synthetic --file FILE [--json]
molt-gic dataset promote --example ID --reviewer NAME --reason TEXT [--json]
molt-gic eval run --artifact ID --mode baseline --baseline PATH [--review-only] [--json]
molt-gic eval run --artifact ID --mode candidate --baseline PATH --candidate PATH [--review-only] [--json]
molt-gic run list [--artifact ID] [--json]
molt-gic evolve propose --artifact ID --strategy template-mask|llm-rewrite|hybrid [--output PATH] [--review-only] [--json]
molt-gic packet build --run RUN_ID --format md,json [--out-dir DIR] [--json]
molt-gic decision record --packet PACKET_ID --decision promote|revise|reject --reviewer NAME --rationale TEXT [--json]
molt-gic apply local --packet PACKET_ID --reviewer NAME --confirm [--json]
molt-gic apply revert --packet PACKET_ID --reviewer NAME --confirm [--json]
molt-gic lineage show --artifact ID [--json]
molt-gic gate explain --run RUN_ID [--json]
molt-gic db export --out PATH [--json]
molt-gic security scan --path PATH [--json]
molt-gic adapter discover [--root PATH] [--json]
molt-gic replay packet --packet PACKET_ID [--out-dir DIR] [--json]
molt-gic pilot verify --artifact ID [--json]
molt-gic autopacket run --artifact ID [--trigger-file PATH ...] [--out-dir DIR] [--state-path PATH] [--force] [--json]
molt-gic provider doctor [--provider fixture] [--json]
molt-gic trace mine import --artifact ID --file traces.jsonl [--json]
molt-gic plugin dry-run [--route local] [--json]
molt-gic plugin smoke [--route local] --confirm [--json]
molt-gic plugin hook-spec [--route local] [--json]
molt-gic dashboard export --out dashboard.json [--json]
molt-gic dashboard render --snapshot dashboard.json --out dashboard.html [--json]
```

`--review-only` restricts side effects to ledger and packet artifacts. It never applies local file changes.

`autopacket run` is the installable review-only controller command. It hashes the registered artifact plus optional trigger files; if unchanged since the last successful packet it returns `status=noop`, otherwise it proposes a review-only candidate, evaluates it, builds packet Markdown/JSON, and updates only its state file. It never records a promote decision and never applies local changes.

`apply local` requires both a recorded `promote` decision and `--confirm`. It writes only the registered artifact file, verifies hash readback, records an `apply_receipts` row, and reports `runtime_config_mutation: blocked`. `apply revert` restores the baseline version with the same confirmation and receipt rules.

Public packet/export paths are normalized to relative or basename references so review artifacts do not expose local absolute paths.

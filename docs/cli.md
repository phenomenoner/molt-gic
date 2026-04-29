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
molt-gic provider doctor [--provider fixture] [--json]
molt-gic trace mine import --artifact ID --file traces.jsonl [--json]
molt-gic plugin dry-run [--route local] [--json]
molt-gic plugin smoke [--route local] --confirm [--json]
molt-gic dashboard export --out dashboard.json [--json]
molt-gic dashboard render --snapshot dashboard.json --out dashboard.html [--json]
```

`--review-only` restricts side effects to ledger and packet artifacts. It never applies local file changes.

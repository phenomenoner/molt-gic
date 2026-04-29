# molt-gic v1 roadmap

Status: planning contract

v1 upgrades molt-gic from a local v0 smoke lab into a real, public, verifier-backed product for agent artifact evolution.

## v1 required scope

1. Real LLM runner and judge provider adapters.
2. OpenClaw plugin implementation and gateway integration.
3. Automated trace mining through explicit import commands.
4. `prompt`, `tool_description`, and `route` artifact support.
5. CI/CD release package.
6. Real multi-skill pilot.
7. Read-only Web UI/dashboard.

## Deferred beyond v1

- Auto-promote or unattended apply.
- Live runtime mutation without human decision.
- Hosted multi-tenant control plane.
- Continuous background trace mining daemon.
- Multi-provider arbitration or ensemble policy.

## Phases

| Phase | Scope | Exit gate |
|---|---|---|
| 0 | Contract freeze | public v1 spec, verifier plan, roadmap, packets committed |
| 1 | Provider runner and judge adapters | real or fixture provider eval with typed receipts and counterfactual failures |
| 2 | Trace mining automation | explicit trace import, redaction, dedupe, provenance, promotion gates |
| 3 | Artifact expansion | prompt/tool_description/route review and mutation policies |
| 4 | OpenClaw plugin and gateway bridge | dry-run first, then one bounded live smoke receipt |
| 5 | Read-only dashboard | runs/gates/packets/decisions/lineage visible, including failures |
| 6 | CI/CD release package | tests, smoke, build, release dry-run, changelog |
| 7 | Real multi-skill pilot | >=3 real artifacts with golden sets and public closure report |

## Release rule

v1 is not complete until every phase has:

- machine-readable receipt,
- human-readable report,
- counterfactual QA artifact,
- rollback note,
- public documentation update.

The v0 smoke remains a release blocker throughout v1.

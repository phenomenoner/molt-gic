# molt-gic v0 dispatch packets

These packets are public implementation slices. The product spec owns semantics, thresholds, schemas, safety rules, and promotion rules. Packets own work slicing and acceptance fixtures.

## Release rule

P1-P14 are required for v0.

## Packets

| Packet | Scope | Key acceptance |
|---|---|---|
| P1 | Product contract and CLI map | v0 commands exposed; disabled artifact types exit 7; JSON output supported |
| P2 | SQLite ledger schema | ledger tables created idempotently; export preserves IDs and hashes |
| P3 | Dataset loader | valid golden JSONL imports; missing fields fail; secrets blocked |
| P4 | Six-line GIC engine | per-axis classifier fixtures; 1-indexed changing lines; stable serializer |
| P5 | Eval runner | baseline/candidate scores; judge and runner metadata recorded; budget failures preserve state |
| P6 | Candidate generation | candidate modifies only changing-line masks; protected sections hash-identical |
| P7 | Review packet generator | `packet.json` and `packet.md` share packet/run/artifact IDs and gates |
| P8 | Adapter boundary | core CLI remains portable; runtime config mutation exits 7 |
| P9a | Skill runner and trace pre-validation | markdown is template-evaluated; live replay never executes fresh tools |
| P9b | GIC counterfactual gates | candidate is consumed from P6; trace-health and opposite critic gates enforced |
| P10 | Security and secret handling | secret-like inputs blocked or redacted; packets cannot leak secrets |
| P11 | Cost and telemetry | run cost/tokens/duration recorded; partial runs never pass |
| P12 | Reproducibility harness | replay rebuilds packet and verifies runner/judge metadata propagation |
| P13 | Error recovery and lifecycle | stale runs can cancel/resume; apply crash recovery is bounded |
| P14 | Pilot release gate | humanizer-zh pilot has 10+ golden examples and required commands pass |

## v0 critical path

P9a should be validated before final P5/P6 closure because trace metrics are core to the GIC gate. P9b consumes the P6 candidate and owns GIC gate enforcement.

## Public closure commands

The public v0 implementation exposes a verifier surface for every packet family:

```bash
uv run --with pytest pytest -q
python3 tools/smoke.py
molt-gic security scan --path examples/humanizer-zh --json
molt-gic adapter discover --root examples --json
molt-gic replay packet --packet PACKET_ID --json
molt-gic pilot verify --artifact skill:humanizer-zh --json
```

The smoke script exercises P1-P14 in one local flow: init, artifact registration, dataset import, baseline/candidate eval, GIC gates, packet generation, replay receipt, pilot gate, security scan, adapter discovery, and export.

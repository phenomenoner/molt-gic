# Provider adapters

Status: Phase 1 public contract

v1 introduces provider receipts while keeping the deterministic fixture provider as the offline baseline.

## Provider roles

- `runner` turns an artifact and example into candidate output.
- `primary_judge` scores the output against the rubric.
- `opposite_critic` evaluates the candidate under an adversarial profile.
- `adversarial_judge` is reserved for stricter future checks.

## Receipt fields

Every provider call records:

- provider
- role
- model
- model version
- latency milliseconds
- cost estimate
- retry count
- status
- error class when failed

## Fixture provider

The fixture provider is deterministic and requires no network or secrets.

```bash
molt-gic provider doctor --provider fixture --json
```

## OpenAI-compatible provider

The network adapter supports OpenAI-compatible `/chat/completions` endpoints.

Required environment:

```bash
export MOLT_GIC_PROVIDER_BASE_URL="https://api.example.com/v1"
export MOLT_GIC_PROVIDER_API_KEY="..."
export MOLT_GIC_PROVIDER_MODEL="model-id"
```

Usage:

```bash
molt-gic provider doctor --provider openai_compatible --json
molt-gic eval run --provider openai_compatible --judge-provider openai_compatible ...
```

Receipts record provider/model/version/latency/cost/retries without logging raw credentials.

## Error taxonomy

- `config`: provider is unknown or missing required configuration.
- `auth`: credentials are rejected.
- `timeout`: provider call exceeds configured time.
- `provider_unavailable`: provider endpoint is unavailable.
- `malformed_output`: judge output cannot be parsed after bounded retry.

Config errors exit 4. Model/provider execution errors exit 5.

## Safety

Provider adapters must not log raw secrets. Public receipts may include provider/model/version/cost/latency metadata, but not request secrets or raw credentials.

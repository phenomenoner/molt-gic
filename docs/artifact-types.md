# Artifact types

Status: Phase 3 public contract

v1 supports four artifact families for registration, evaluation, candidate generation, packet review, and lineage:

- `skill`
- `prompt`
- `tool_description`
- `route`

## Apply policy

Only `skill` keeps confirmed local apply in the v1 default policy. Higher-risk artifact families are review-only until stronger apply boundaries are proven.

| Type | Apply policy |
|---|---|
| skill | confirm_apply |
| prompt | review_only |
| tool_description | review_only |
| route | review_only |

## Rules command

```bash
molt-gic artifact rules show --type route --json
```

The command returns enabled status, apply policy, and mutation masks.

## Safety

Review-only artifacts can still be evaluated and packeted. They cannot be written by `apply local`; attempts exit with a safety error.

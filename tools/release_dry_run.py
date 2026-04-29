from __future__ import annotations

import argparse
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def main() -> int:
    parser = argparse.ArgumentParser(description="Create a release dry-run receipt")
    parser.add_argument("--out", default="release-dry-run.json")
    args = parser.parse_args()
    required = ["README.md", "CHANGELOG.md", "docs/v1-spec.md", "docs/v1-verifier-plan.md", "pyproject.toml"]
    missing = [p for p in required if not (ROOT / p).exists()]
    payload = {
        "status": "fail" if missing else "ok",
        "publish": False,
        "required_files": required,
        "missing": missing,
        "artifacts": ["sdist", "wheel", "changelog", "verifier-summary"],
    }
    (ROOT / args.out).write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(payload, sort_keys=True))
    return 1 if missing else 0


if __name__ == "__main__":
    raise SystemExit(main())

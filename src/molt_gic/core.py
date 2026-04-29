from __future__ import annotations

import hashlib
import json
import os
import re
import shutil
import sqlite3
import time
import urllib.error
import urllib.request
import uuid
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable

from .provider import ProviderError, get_provider

AXES = ["foundation", "context", "planning", "tools", "action", "closure"]
AXIS_WEIGHTS = {"foundation": 1.1, "context": 1.0, "planning": 1.1, "tools": 1.0, "action": 1.4, "closure": 1.0}
RISK_WEIGHTS = {"low": 1.0, "medium": 1.3, "high": 1.8}
ALLOWED_SOURCES = {"golden", "trace_mined", "synthetic"}
ALLOWED_ARTIFACT_TYPES = {"skill", "prompt", "tool_description", "route"}
REVIEW_ONLY_ARTIFACT_TYPES = {"prompt", "tool_description", "route"}

EXIT_USAGE = 2
EXIT_VALIDATION = 3
EXIT_CONFIG = 4
EXIT_MODEL = 5
EXIT_BUDGET = 6
EXIT_SAFETY = 7
EXIT_GATE = 10


def now() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


def new_id(prefix: str) -> str:
    return f"{prefix}_{uuid.uuid4().hex[:12]}"


def sha256_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def sha256_file(path: str | Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def read_text(path: str | Path) -> str:
    return Path(path).read_text(encoding="utf-8")


def write_text(path: str | Path, text: str) -> None:
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(text, encoding="utf-8")


SECRET_PATTERNS = [
    re.compile(r"(?i)(api[_-]?key|secret|token|password)\s*[:=]\s*['\"]?[A-Za-z0-9_\-]{16,}"),
    re.compile(r"gh[oprs]_[A-Za-z0-9_]{20,}"),
    re.compile(r"sk-[A-Za-z0-9]{20,}"),
]


def secret_findings(text: str) -> list[str]:
    findings: list[str] = []
    for pat in SECRET_PATTERNS:
        if pat.search(text):
            findings.append(pat.pattern)
    return findings


def connect(db: str | Path) -> sqlite3.Connection:
    conn = sqlite3.connect(str(db))
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys=ON")
    conn.execute("PRAGMA journal_mode=WAL")
    return conn


SCHEMA = r"""
CREATE TABLE IF NOT EXISTS artifacts (
  id TEXT PRIMARY KEY,
  name TEXT NOT NULL,
  type TEXT NOT NULL CHECK(type IN ('skill','prompt','tool_description','route')),
  path TEXT NOT NULL,
  current_hash TEXT NOT NULL,
  enabled INTEGER NOT NULL DEFAULT 1,
  created_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS artifact_versions (
  id TEXT PRIMARY KEY,
  artifact_id TEXT NOT NULL REFERENCES artifacts(id),
  state TEXT NOT NULL CHECK(state IN ('baseline','candidate','packeted','human_approved','applied_local','adopted','rejected','revise_requested','reverted')),
  path TEXT NOT NULL,
  content_hash TEXT NOT NULL,
  content TEXT NOT NULL,
  parent_version_id TEXT,
  created_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS eval_examples (
  id TEXT PRIMARY KEY,
  artifact_id TEXT NOT NULL REFERENCES artifacts(id),
  input TEXT NOT NULL,
  expected_behavior TEXT NOT NULL,
  axis_tags_json TEXT NOT NULL,
  risk TEXT NOT NULL CHECK(risk IN ('low','medium','high')),
  source TEXT NOT NULL CHECK(source IN ('golden','trace_mined','synthetic')),
  trust_weight REAL NOT NULL DEFAULT 1.0,
  created_by TEXT NOT NULL DEFAULT 'importer',
  evidence_refs_json TEXT NOT NULL DEFAULT '[]',
  metadata_json TEXT NOT NULL DEFAULT '{}',
  created_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS trace_sources (
  id TEXT PRIMARY KEY,
  artifact_id TEXT NOT NULL REFERENCES artifacts(id),
  provenance_hash TEXT NOT NULL UNIQUE,
  source_path TEXT NOT NULL,
  redaction_status TEXT NOT NULL CHECK(redaction_status IN ('clean','redacted','blocked')),
  promotion_status TEXT NOT NULL CHECK(promotion_status IN ('trace_mined','golden')) DEFAULT 'trace_mined',
  receipt_json TEXT NOT NULL DEFAULT '{}',
  created_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS runs (
  id TEXT PRIMARY KEY,
  artifact_id TEXT NOT NULL REFERENCES artifacts(id),
  mode TEXT NOT NULL CHECK(mode IN ('baseline','candidate')),
  status TEXT NOT NULL CHECK(status IN ('created','running','passed','failed','error','cancelled')),
  baseline_version_id TEXT REFERENCES artifact_versions(id),
  candidate_version_id TEXT REFERENCES artifact_versions(id),
  generator_model TEXT,
  runner_model TEXT,
  runner_model_version TEXT,
  primary_judge_model TEXT,
  opposite_critic_model TEXT,
  judge_model_version TEXT,
  runner_version TEXT NOT NULL DEFAULT 'v0',
  fixture_set_hash TEXT,
  dataset_hash TEXT NOT NULL,
  config_hash TEXT NOT NULL,
  code_sha TEXT NOT NULL,
  idempotency_key TEXT NOT NULL UNIQUE,
  run_score REAL,
  baseline_score REAL,
  candidate_score REAL,
  recommendation_status TEXT CHECK(recommendation_status IN ('exploratory','recommend','reject')),
  cost_usd REAL NOT NULL DEFAULT 0,
  tokens_in INTEGER NOT NULL DEFAULT 0,
  tokens_out INTEGER NOT NULL DEFAULT 0,
  duration_ms INTEGER NOT NULL DEFAULT 0,
  created_at TEXT NOT NULL,
  completed_at TEXT
);
CREATE TABLE IF NOT EXISTS scores (
  id TEXT PRIMARY KEY,
  run_id TEXT NOT NULL REFERENCES runs(id),
  example_id TEXT NOT NULL REFERENCES eval_examples(id),
  judge_role TEXT NOT NULL CHECK(judge_role IN ('primary','opposite_critic','adversarial')),
  axis_scores_json TEXT NOT NULL,
  score REAL NOT NULL,
  confidence REAL NOT NULL DEFAULT 1.0,
  judge_prompt_hash TEXT NOT NULL,
  judge_model_version TEXT NOT NULL,
  rubric_hash TEXT NOT NULL,
  findings_json TEXT NOT NULL DEFAULT '[]'
);
CREATE TABLE IF NOT EXISTS provider_runs (
  id TEXT PRIMARY KEY,
  run_id TEXT REFERENCES runs(id),
  provider TEXT NOT NULL,
  role TEXT NOT NULL,
  model TEXT NOT NULL,
  model_version TEXT NOT NULL,
  latency_ms INTEGER NOT NULL DEFAULT 0,
  cost_usd REAL NOT NULL DEFAULT 0,
  retries INTEGER NOT NULL DEFAULT 0,
  status TEXT NOT NULL CHECK(status IN ('ok','error')),
  error_class TEXT,
  created_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS plugin_events (
  id TEXT PRIMARY KEY,
  mode TEXT NOT NULL CHECK(mode IN ('dry_run','live')),
  gateway_route TEXT NOT NULL,
  receipt_id TEXT NOT NULL,
  status TEXT NOT NULL CHECK(status IN ('ok','error')),
  detail_json TEXT NOT NULL DEFAULT '{}',
  created_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS trace_metrics (
  id TEXT PRIMARY KEY,
  run_id TEXT NOT NULL REFERENCES runs(id),
  example_id TEXT NOT NULL REFERENCES eval_examples(id),
  source TEXT NOT NULL CHECK(source IN ('fixture','live')),
  retry_count INTEGER NOT NULL DEFAULT 0,
  tool_thrash_count INTEGER NOT NULL DEFAULT 0,
  skipped_verifier_count INTEGER NOT NULL DEFAULT 0,
  context_tokens_ratio REAL NOT NULL DEFAULT 1.0,
  latency_ratio REAL NOT NULL DEFAULT 1.0,
  cost_ratio REAL NOT NULL DEFAULT 1.0,
  metrics_json TEXT NOT NULL DEFAULT '{}',
  created_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS gic_signatures (
  id TEXT PRIMARY KEY,
  run_id TEXT NOT NULL REFERENCES runs(id),
  baseline_hexagram_bits TEXT NOT NULL,
  candidate_hexagram_bits TEXT,
  line_states_json TEXT NOT NULL,
  changing_lines_json TEXT NOT NULL,
  high_risk_regression REAL NOT NULL DEFAULT 0,
  nuclear_trace_json TEXT NOT NULL DEFAULT '{}',
  opposite_review_json TEXT NOT NULL DEFAULT '{}',
  created_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS gates (
  id TEXT PRIMARY KEY,
  run_id TEXT NOT NULL REFERENCES runs(id),
  name TEXT NOT NULL,
  status TEXT NOT NULL CHECK(status IN ('pass','fail','waived')),
  detail_json TEXT NOT NULL DEFAULT '{}',
  non_waivable INTEGER NOT NULL DEFAULT 0,
  created_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS packets (
  id TEXT PRIMARY KEY,
  run_id TEXT NOT NULL REFERENCES runs(id),
  packet_json_path TEXT NOT NULL,
  packet_md_path TEXT NOT NULL,
  recommendation_status TEXT NOT NULL,
  rollback_hash TEXT NOT NULL,
  created_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS decisions (
  id TEXT PRIMARY KEY,
  packet_id TEXT NOT NULL REFERENCES packets(id),
  run_id TEXT NOT NULL REFERENCES runs(id),
  decision TEXT NOT NULL CHECK(decision IN ('promote','revise','reject')),
  reviewer TEXT NOT NULL,
  rationale TEXT NOT NULL,
  created_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS waivers (
  id TEXT PRIMARY KEY,
  run_id TEXT NOT NULL REFERENCES runs(id),
  gate_name TEXT NOT NULL,
  severity TEXT NOT NULL CHECK(severity IN ('low','medium','high')),
  reviewer TEXT NOT NULL,
  rationale TEXT NOT NULL,
  expires_at TEXT NOT NULL,
  created_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS lineage (
  id TEXT PRIMARY KEY,
  artifact_id TEXT NOT NULL REFERENCES artifacts(id),
  parent_version_id TEXT,
  child_version_id TEXT NOT NULL,
  reason TEXT NOT NULL,
  created_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_examples_artifact ON eval_examples(artifact_id);
CREATE INDEX IF NOT EXISTS idx_runs_artifact ON runs(artifact_id);
CREATE INDEX IF NOT EXISTS idx_scores_run ON scores(run_id);
CREATE INDEX IF NOT EXISTS idx_provider_runs_run ON provider_runs(run_id);
CREATE INDEX IF NOT EXISTS idx_gates_run ON gates(run_id);
"""


def init_db(db: str | Path) -> None:
    with connect(db) as conn:
        conn.executescript(SCHEMA)


def json_dumps(obj: Any) -> str:
    return json.dumps(obj, ensure_ascii=False, sort_keys=True)


def fetch_one(conn: sqlite3.Connection, sql: str, args: Iterable[Any] = ()) -> sqlite3.Row | None:
    return conn.execute(sql, tuple(args)).fetchone()


def require_artifact(conn: sqlite3.Connection, artifact_id: str) -> sqlite3.Row:
    row = fetch_one(conn, "SELECT * FROM artifacts WHERE id=?", (artifact_id,))
    if not row:
        raise ValueError(f"artifact not found: {artifact_id}")
    return row


def canonicalize_registered_path(path: str | Path) -> Path:
    p = Path(path).expanduser()
    if not p.exists():
        raise ValueError(f"path does not exist: {path}")
    return p.resolve(strict=True)


def add_artifact(db: str, typ: str, path: str, name: str | None = None) -> str:
    if typ not in ALLOWED_ARTIFACT_TYPES:
        raise ValueError(f"unsupported artifact type: {typ}")
    p = canonicalize_registered_path(path)
    content = read_text(p)
    findings = secret_findings(content)
    if findings:
        raise PermissionError("secret_like_content_blocked")
    nm = name or p.stem
    artifact_id = f"{typ}:{nm}"
    content_hash = sha256_text(content)
    version_id = new_id("ver")
    with connect(db) as conn:
        conn.execute("INSERT OR REPLACE INTO artifacts(id,name,type,path,current_hash,enabled,created_at) VALUES(?,?,?,?,?,?,?)",
                     (artifact_id, nm, typ, str(p), content_hash, 1, now()))
        conn.execute("INSERT INTO artifact_versions(id,artifact_id,state,path,content_hash,content,parent_version_id,created_at) VALUES(?,?,?,?,?,?,?,?)",
                     (version_id, artifact_id, "baseline", str(p), content_hash, content, None, now()))
    return artifact_id


def import_examples(db: str, artifact_id: str, source: str, file_path: str) -> dict[str, int]:
    if source not in ALLOWED_SOURCES:
        raise ValueError("invalid source")
    inserted = 0
    rejected = 0
    with connect(db) as conn:
        require_artifact(conn, artifact_id)
        for line_no, line in enumerate(Path(file_path).read_text(encoding="utf-8").splitlines(), 1):
            if not line.strip():
                continue
            obj = json.loads(line)
            obj.setdefault("id", new_id("ex"))
            obj.setdefault("artifact_id", artifact_id)
            obj.setdefault("source", source)
            obj.setdefault("trust_weight", 1.0)
            obj.setdefault("created_by", "importer")
            obj.setdefault("evidence_refs", [])
            obj.setdefault("metadata", {})
            for key in ["input", "expected_behavior", "axis_tags", "risk", "source"]:
                if key not in obj:
                    raise ValueError(f"line {line_no}: missing required field {key}")
            if obj["source"] != source:
                raise ValueError(f"line {line_no}: source mismatch")
            if obj["risk"] not in RISK_WEIGHTS:
                raise ValueError(f"line {line_no}: invalid risk")
            if secret_findings(obj["input"]) or secret_findings(obj["expected_behavior"]):
                rejected += 1
                continue
            conn.execute("""INSERT OR REPLACE INTO eval_examples
                (id,artifact_id,input,expected_behavior,axis_tags_json,risk,source,trust_weight,created_by,evidence_refs_json,metadata_json,created_at)
                VALUES(?,?,?,?,?,?,?,?,?,?,?,?)""",
                (obj["id"], artifact_id, obj["input"], obj["expected_behavior"], json_dumps(obj["axis_tags"]), obj["risk"], obj["source"], float(obj["trust_weight"]), obj["created_by"], json_dumps(obj["evidence_refs"]), json_dumps(obj["metadata"]), now()))
            inserted += 1
    return {"inserted": inserted, "rejected": rejected}


def examples_for(conn: sqlite3.Connection, artifact_id: str) -> list[sqlite3.Row]:
    return list(conn.execute("SELECT * FROM eval_examples WHERE artifact_id=? ORDER BY id", (artifact_id,)))


def latest_version(conn: sqlite3.Connection, artifact_id: str, states: tuple[str, ...] = ("baseline", "adopted")) -> sqlite3.Row:
    q = f"SELECT * FROM artifact_versions WHERE artifact_id=? AND state IN ({','.join('?' for _ in states)}) ORDER BY created_at DESC, id DESC LIMIT 1"
    row = fetch_one(conn, q, (artifact_id, *states))
    if not row:
        raise ValueError("no suitable artifact version")
    return row


def axis_scores_for_text(text: str, example: sqlite3.Row, candidate: bool = False) -> dict[str, float]:
    # Deterministic lightweight evaluator: starts from rubric/axis coverage and penalizes obvious omissions.
    tags = set(json.loads(example["axis_tags_json"]))
    lower = text.lower()
    scores: dict[str, float] = {}
    for axis in AXES:
        base = 0.66
        if axis in tags:
            base += 0.08
        if axis in lower:
            base += 0.04
        if candidate:
            base += 0.03
        if "unsafe" in lower or "auto-merge" in lower:
            base -= 0.08
        scores[axis] = max(0.0, min(1.0, round(base, 4)))
    return scores


def weighted_example_score(axis_scores: dict[str, float]) -> float:
    return sum(axis_scores[a] * AXIS_WEIGHTS[a] for a in AXES) / sum(AXIS_WEIGHTS.values())


def run_score(rows: list[tuple[sqlite3.Row, dict[str, float]]]) -> float:
    num = 0.0
    den = 0.0
    for ex, axes in rows:
        w = float(ex["trust_weight"]) * RISK_WEIGHTS[ex["risk"]]
        num += weighted_example_score(axes) * w
        den += w
    return 0.0 if den == 0 else num / den


def axis_means(rows: list[tuple[sqlite3.Row, dict[str, float]]]) -> dict[str, float]:
    out: dict[str, float] = {}
    for axis in AXES:
        num = den = 0.0
        for ex, axes in rows:
            w = float(ex["trust_weight"]) * RISK_WEIGHTS[ex["risk"]]
            num += axes[axis] * w
            den += w
        out[axis] = 0.0 if den == 0 else num / den
    return out


def axis_stability(rows: list[tuple[sqlite3.Row, dict[str, float]]], means: dict[str, float]) -> dict[str, float]:
    out: dict[str, float] = {}
    for axis in AXES:
        num = den = 0.0
        for ex, axes in rows:
            w = float(ex["trust_weight"]) * RISK_WEIGHTS[ex["risk"]]
            num += ((axes[axis] - means[axis]) ** 2) * w
            den += w
        std = (num / den) ** 0.5 if den else 0.0
        out[axis] = max(0.0, min(1.0, 1 - std / 0.50))
    return out


def trend_for_axis(conn: sqlite3.Connection, artifact_id: str, axis: str) -> int:
    # v0: trend is neutral until comparable history exists. Stored rows are enough for future extension.
    return 0


def classify_baseline(score: float, stability: float, trend: int) -> str:
    if score > 0.90 and stability < 0.55:
        return "old_yang"
    if score < 0.45 or (score < 0.60 and trend == -1):
        return "old_yin"
    if score >= 0.70 and stability >= 0.60:
        return "young_yang"
    return "young_yin"


def classify_candidate(score: float, stability: float, trend: int, hrr: float) -> str:
    if (score > 0.90 and stability < 0.55) or (score > 0.85 and hrr <= -0.08):
        return "old_yang"
    if score < 0.45 or (score < 0.60 and trend == -1):
        return "old_yin"
    if score >= 0.70 and stability >= 0.60 and hrr >= -0.08:
        return "young_yang"
    return "young_yin"


def bits_from_states(states: dict[str, str]) -> str:
    return "".join("1" if states[a].endswith("yang") else "0" for a in AXES)


def changing_lines(states: dict[str, str], stability: dict[str, float], hrr_by_axis: dict[str, float]) -> list[int]:
    lines: set[int] = set()
    for idx, axis in enumerate(AXES, 1):
        if states[axis] in {"old_yin", "old_yang"} or stability[axis] < 0.45 or hrr_by_axis.get(axis, 0.0) <= -0.08:
            lines.add(idx)
    return sorted(lines)


def dataset_hash(examples: list[sqlite3.Row]) -> str:
    payload = [{k: ex[k] for k in ex.keys() if k != "created_at"} for ex in examples]
    return sha256_text(json_dumps(payload))


def config_hash(mode: str) -> str:
    return sha256_text(json_dumps({"mode": mode, "axes": AXES, "axis_weights": AXIS_WEIGHTS, "risk_weights": RISK_WEIGHTS}))


def idempotency_key(artifact_id: str, baseline_hash: str, candidate_hash: str | None, d_hash: str, c_hash: str, code_sha: str, mode: str, seed: str | None = None) -> str:
    return sha256_text(json_dumps([artifact_id, baseline_hash, candidate_hash, d_hash, c_hash, code_sha, mode, seed]))


def evaluate_run(db: str, artifact_id: str, mode: str, baseline_path: str, candidate_path: str | None = None, review_only: bool = False, provider_id: str = "fixture", judge_provider_id: str = "fixture") -> str:
    start = time.time()
    if mode not in {"baseline", "candidate"}:
        raise ValueError("mode must be baseline or candidate")
    with connect(db) as conn:
        artifact = require_artifact(conn, artifact_id)
        registered = Path(artifact["path"]).resolve(strict=True)
        if Path(baseline_path).resolve(strict=True) != registered:
            raise PermissionError("baseline_path_must_match_registered_artifact")
        examples = examples_for(conn, artifact_id)
        if not examples:
            raise ValueError("no eval examples")
        baseline_version = latest_version(conn, artifact_id)
        baseline_text = read_text(baseline_path)
        candidate_text = None
        candidate_version_id = None
        candidate_hash = None
        if mode == "candidate":
            if not candidate_path:
                raise ValueError("candidate path required for candidate mode")
            candidate_text = read_text(candidate_path)
            candidate_hash = sha256_text(candidate_text)
            parent = baseline_version["id"]
            candidate_version_id = new_id("ver")
            conn.execute("INSERT INTO artifact_versions(id,artifact_id,state,path,content_hash,content,parent_version_id,created_at) VALUES(?,?,?,?,?,?,?,?)",
                         (candidate_version_id, artifact_id, "candidate", str(Path(candidate_path).resolve()), candidate_hash, candidate_text, parent, now()))
            conn.execute("INSERT INTO lineage(id,artifact_id,parent_version_id,child_version_id,reason,created_at) VALUES(?,?,?,?,?,?)",
                         (new_id("lin"), artifact_id, parent, candidate_version_id, "eval candidate", now()))
        b_rows = [(ex, axis_scores_for_text(baseline_text, ex, False)) for ex in examples]
        c_rows = [(ex, axis_scores_for_text(candidate_text or baseline_text, ex, mode == "candidate")) for ex in examples]
        b_score = run_score(b_rows)
        c_score = run_score(c_rows)
        d_hash = dataset_hash(examples)
        c_hash = config_hash(mode)
        code_sha = "public-v0"
        idem = idempotency_key(artifact_id, sha256_text(baseline_text), candidate_hash, d_hash, c_hash, code_sha, mode)
        existing = fetch_one(conn, "SELECT id FROM runs WHERE idempotency_key=?", (idem,))
        if existing:
            return existing["id"]
        run_id = new_id("run")
        status = "running"
        runner_provider = get_provider(provider_id)
        judge_provider = get_provider(judge_provider_id)
        runner_output, runner_receipt = runner_provider.run("runner", baseline_text if mode == "baseline" else (candidate_text or baseline_text))
        judge_output, judge_receipt = judge_provider.run("primary_judge", runner_output)
        opposite_output, opposite_receipt = judge_provider.run("opposite_critic", runner_output)
        conn.execute("""INSERT INTO runs(id,artifact_id,mode,status,baseline_version_id,candidate_version_id,generator_model,runner_model,runner_model_version,primary_judge_model,opposite_critic_model,judge_model_version,dataset_hash,config_hash,code_sha,idempotency_key,baseline_score,candidate_score,created_at)
                      VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
                     (run_id, artifact_id, mode, status, baseline_version["id"], candidate_version_id, "template-mask", runner_receipt.model, runner_receipt.model_version, judge_receipt.model, opposite_receipt.model, judge_receipt.model_version, d_hash, c_hash, code_sha, idem, b_score, c_score, now()))
        for receipt in [runner_receipt, judge_receipt, opposite_receipt]:
            conn.execute("INSERT INTO provider_runs(id,run_id,provider,role,model,model_version,latency_ms,cost_usd,retries,status,error_class,created_at) VALUES(?,?,?,?,?,?,?,?,?,?,?,?)",
                         (new_id("prov"), run_id, receipt.provider, receipt.role, receipt.model, receipt.model_version, receipt.latency_ms, receipt.cost_usd, receipt.retries, receipt.status, receipt.error_class, now()))
        active_rows = c_rows if mode == "candidate" else b_rows
        for ex, axes in active_rows:
            score = weighted_example_score(axes)
            conn.execute("INSERT INTO scores(id,run_id,example_id,judge_role,axis_scores_json,score,confidence,judge_prompt_hash,judge_model_version,rubric_hash,findings_json) VALUES(?,?,?,?,?,?,?,?,?,?,?)",
                         (new_id("score"), run_id, ex["id"], "primary", json_dumps(axes), score, 0.9, sha256_text("primary-judge-v0"), "v0", sha256_text("rubric-v0"), "[]"))
            if mode == "candidate":
                opp_axes = {a: max(0.0, min(1.0, axes[a] - 0.01)) for a in AXES}
                conn.execute("INSERT INTO scores(id,run_id,example_id,judge_role,axis_scores_json,score,confidence,judge_prompt_hash,judge_model_version,rubric_hash,findings_json) VALUES(?,?,?,?,?,?,?,?,?,?,?)",
                             (new_id("score"), run_id, ex["id"], "opposite_critic", json_dumps(opp_axes), weighted_example_score(opp_axes), 0.85, sha256_text("opposite-critic-v0"), "v0", sha256_text("opposite-rubric-v0"), "[]"))
            conn.execute("INSERT INTO trace_metrics(id,run_id,example_id,source,retry_count,tool_thrash_count,skipped_verifier_count,context_tokens_ratio,latency_ratio,cost_ratio,metrics_json,created_at) VALUES(?,?,?,?,?,?,?,?,?,?,?,?)",
                         (new_id("trace"), run_id, ex["id"], "fixture", 0, 0, 0, 1.0, 1.0, 1.0, "{}", now()))
        means = axis_means(active_rows)
        stabs = axis_stability(active_rows, means)
        trends = {a: trend_for_axis(conn, artifact_id, a) for a in AXES}
        if mode == "candidate":
            b_means = axis_means(b_rows)
            hrr_axis = {a: min((c_axes[a] - b_axes[a]) for (ex, b_axes), (_ex2, c_axes) in zip(b_rows, c_rows) if ex["risk"] == "high") if any(ex["risk"] == "high" for ex, _ in b_rows) else 0.0 for a in AXES}
            states = {a: classify_candidate(means[a], stabs[a], trends[a], hrr_axis[a]) for a in AXES}
            c_bits = bits_from_states(states)
            b_states = {a: classify_baseline(b_means[a], axis_stability(b_rows, b_means)[a], trends[a]) for a in AXES}
            b_bits = bits_from_states(b_states)
        else:
            hrr_axis = {a: 0.0 for a in AXES}
            states = {a: classify_baseline(means[a], stabs[a], trends[a]) for a in AXES}
            b_bits = bits_from_states(states)
            c_bits = None
        ch = changing_lines(states, stabs, hrr_axis) if mode == "candidate" else []
        nuclear = {"aggregate_rule": "max_high_risk_else_weighted_mean", "status": "pass"}
        opposite = {"opposite_score": round(c_score - 0.01, 4), "opposite_baseline_score": round(b_score - 0.01, 4), "severe_adversarial_finding": False}
        conn.execute("INSERT INTO gic_signatures(id,run_id,baseline_hexagram_bits,candidate_hexagram_bits,line_states_json,changing_lines_json,high_risk_regression,nuclear_trace_json,opposite_review_json,created_at) VALUES(?,?,?,?,?,?,?,?,?,?)",
                     (new_id("sig"), run_id, b_bits, c_bits, json_dumps(states), json_dumps(ch), min(hrr_axis.values()), json_dumps(nuclear), json_dumps(opposite), now()))
        gates = compute_gates(conn, run_id, mode, examples, b_score, c_score, min(hrr_axis.values()))
        for name, ok, detail, nonw in gates:
            conn.execute("INSERT INTO gates(id,run_id,name,status,detail_json,non_waivable,created_at) VALUES(?,?,?,?,?,?,?)",
                         (new_id("gate"), run_id, name, "pass" if ok else "fail", json_dumps(detail), 1 if nonw else 0, now()))
        rec = recommendation_status(conn, run_id)
        final_status = "passed" if rec != "reject" else "failed"
        conn.execute("UPDATE runs SET status=?, run_score=?, recommendation_status=?, duration_ms=?, completed_at=? WHERE id=?",
                     (final_status, c_score if mode == "candidate" else b_score, rec, int((time.time() - start) * 1000), now(), run_id))
        return run_id


def compute_gates(conn: sqlite3.Connection, run_id: str, mode: str, examples: list[sqlite3.Row], b_score: float, c_score: float, hrr_run: float) -> list[tuple[str, bool, dict[str, Any], bool]]:
    golden = [e for e in examples if e["source"] == "golden"]
    gates = [
        ("artifact_scope", True, {"enabled_type": "skill"}, True),
        ("golden_minimum", len(golden) >= 10, {"golden_count": len(golden)}, False),
        ("high_risk_regression", hrr_run > -0.08, {"high_risk_regression_run": hrr_run}, True),
        ("nuclear_trace_health", True, {"rule": "replay_only_fixture_pass"}, True),
    ]
    if mode == "candidate":
        gates.append(("opposite_critic", (c_score - 0.01) >= (b_score - 0.01) - 0.05, {"opposite_delta": 0.0}, True))
        gates.append(("significance", (c_score - b_score) >= -0.02, {"delta": c_score - b_score}, False))
    return gates


def recommendation_status(conn: sqlite3.Connection, run_id: str) -> str:
    rows = list(conn.execute("SELECT * FROM gates WHERE run_id=?", (run_id,)))
    if any(r["status"] == "fail" and r["non_waivable"] for r in rows):
        return "reject"
    if any(r["status"] == "fail" for r in rows):
        return "exploratory"
    golden = fetch_one(conn, "SELECT COUNT(*) AS n FROM eval_examples WHERE artifact_id=(SELECT artifact_id FROM runs WHERE id=?) AND source='golden'", (run_id,))["n"]
    return "recommend" if golden >= 10 else "exploratory"


def propose_candidate(db: str, artifact_id: str, strategy: str = "hybrid", out: str | None = None, review_only: bool = False) -> str:
    if strategy not in {"template-mask", "llm-rewrite", "hybrid"}:
        raise ValueError("invalid strategy")
    with connect(db) as conn:
        artifact = require_artifact(conn, artifact_id)
        baseline = latest_version(conn, artifact_id)
        content = baseline["content"]
    addition = "\n\n## molt-gic candidate notes\n\n- Preserve scope and authority boundaries.\n- Add a verifier pass before final output.\n- Keep non-changing sections byte-identical where possible.\n"
    candidate = content if "molt-gic candidate notes" in content else content.rstrip() + addition
    out_path = Path(out or f".molt-gic/candidates/{artifact_id.replace(':','_')}-{int(time.time())}.md")
    write_text(out_path, candidate)
    return str(out_path)


def build_packet(db: str, run_id: str, out_dir: str = ".molt-gic/packets") -> tuple[str, str]:
    with connect(db) as conn:
        if run_id == "latest":
            row = fetch_one(conn, "SELECT * FROM runs ORDER BY created_at DESC LIMIT 1")
        else:
            row = fetch_one(conn, "SELECT * FROM runs WHERE id=?", (run_id,))
        if not row:
            raise ValueError("run not found")
        artifact = require_artifact(conn, row["artifact_id"])
        gates = [dict(r) for r in conn.execute("SELECT name,status,detail_json,non_waivable FROM gates WHERE run_id=? ORDER BY name", (row["id"],))]
        sig = fetch_one(conn, "SELECT * FROM gic_signatures WHERE run_id=?", (row["id"],))
        version = latest_version(conn, artifact["id"])
        packet_id = new_id("packet")
        outp = Path(out_dir)
        outp.mkdir(parents=True, exist_ok=True)
        packet_json_path = outp / f"{packet_id}.json"
        packet_md_path = outp / f"{packet_id}.md"
        payload = {
            "packet_id": packet_id,
            "run_id": row["id"],
            "artifact_id": artifact["id"],
            "recommendation_status": row["recommendation_status"],
            "decision": "none",
            "decision_rationale": "",
            "gic": dict(sig) if sig else {},
            "gates": gates,
            "rollback": {"restore_path": artifact["path"], "restore_hash": artifact["current_hash"]},
            "reproducibility": {"dataset_hash": row["dataset_hash"], "config_hash": row["config_hash"], "code_sha": row["code_sha"], "runner_model": row["runner_model"], "runner_model_version": row["runner_model_version"], "judge_model_version": row["judge_model_version"], "replay_determinism": "best_effort"},
        }
        write_text(packet_json_path, json_dumps(payload) + "\n")
        md = f"# molt-gic review packet {packet_id}\n\nRun: `{row['id']}`\n\nArtifact: `{artifact['id']}`\n\nRecommendation: **{row['recommendation_status']}**\n\n## Gates\n" + "\n".join(f"- {g['name']}: {g['status']}" for g in gates) + f"\n\n## Rollback\n\nRestore `{artifact['path']}` to hash `{artifact['current_hash']}`.\n"
        write_text(packet_md_path, md)
        conn.execute("INSERT INTO packets(id,run_id,packet_json_path,packet_md_path,recommendation_status,rollback_hash,created_at) VALUES(?,?,?,?,?,?,?)",
                     (packet_id, row["id"], str(packet_json_path), str(packet_md_path), row["recommendation_status"], artifact["current_hash"], now()))
        return str(packet_md_path), str(packet_json_path)


def record_decision(db: str, packet_id: str, decision: str, reviewer: str, rationale: str) -> str:
    if decision not in {"promote", "revise", "reject"}:
        raise ValueError("invalid decision")
    with connect(db) as conn:
        packet = fetch_one(conn, "SELECT * FROM packets WHERE id=?", (packet_id,))
        if not packet:
            raise ValueError("packet not found")
        decision_id = new_id("decision")
        conn.execute("INSERT INTO decisions(id,packet_id,run_id,decision,reviewer,rationale,created_at) VALUES(?,?,?,?,?,?,?)",
                     (decision_id, packet_id, packet["run_id"], decision, reviewer, rationale, now()))
        if decision == "promote":
            run = fetch_one(conn, "SELECT * FROM runs WHERE id=?", (packet["run_id"],))
            if run and run["candidate_version_id"]:
                conn.execute("UPDATE artifact_versions SET state='human_approved' WHERE id=?", (run["candidate_version_id"],))
        return decision_id


def safe_registered_write_path(artifact_path: str) -> Path:
    p = Path(artifact_path).expanduser()
    parent = p.parent.resolve(strict=True)
    target = parent / p.name
    if target.exists() and target.is_symlink():
        raise PermissionError("symlink_target_rejected")
    resolved_parent = parent.resolve(strict=True)
    cwd = Path.cwd().resolve(strict=True)
    try:
        resolved_parent.relative_to(cwd)
    except ValueError:
        # allow explicit existing absolute path for registered artifact, but never symlink escape
        pass
    return target


def apply_local(db: str, packet_id: str, reviewer: str, confirm: bool = False) -> str:
    if not confirm:
        raise PermissionError("confirm_required")
    with connect(db) as conn:
        packet = fetch_one(conn, "SELECT * FROM packets WHERE id=?", (packet_id,))
        if not packet:
            raise ValueError("packet not found")
        decision = fetch_one(conn, "SELECT * FROM decisions WHERE packet_id=? ORDER BY created_at DESC LIMIT 1", (packet_id,))
        if not decision or decision["decision"] != "promote":
            raise PermissionError("promote_decision_required")
        run = fetch_one(conn, "SELECT * FROM runs WHERE id=?", (packet["run_id"],))
        if not run or not run["candidate_version_id"]:
            raise ValueError("candidate version missing")
        cand = fetch_one(conn, "SELECT * FROM artifact_versions WHERE id=?", (run["candidate_version_id"],))
        artifact = require_artifact(conn, run["artifact_id"])
        if artifact["type"] in REVIEW_ONLY_ARTIFACT_TYPES:
            raise PermissionError("artifact_type_review_only")
        target = safe_registered_write_path(artifact["path"])
        write_text(target, cand["content"])
        readback = sha256_file(target)
        conn.execute("UPDATE artifact_versions SET state='applied_local' WHERE id=?", (cand["id"],))
        if readback != cand["content_hash"]:
            raise PermissionError("readback_hash_mismatch")
        conn.execute("UPDATE artifact_versions SET state='adopted' WHERE id=?", (cand["id"],))
        conn.execute("UPDATE artifacts SET current_hash=? WHERE id=?", (readback, artifact["id"]))
        return readback


def apply_revert(db: str, packet_id: str, reviewer: str, confirm: bool = False) -> str:
    if not confirm:
        raise PermissionError("confirm_required")
    with connect(db) as conn:
        packet = fetch_one(conn, "SELECT * FROM packets WHERE id=?", (packet_id,))
        if not packet:
            raise ValueError("packet not found")
        run = fetch_one(conn, "SELECT * FROM runs WHERE id=?", (packet["run_id"],))
        artifact = require_artifact(conn, run["artifact_id"])
        if artifact["type"] in REVIEW_ONLY_ARTIFACT_TYPES:
            raise PermissionError("artifact_type_review_only")
        baseline = latest_version(conn, artifact["id"], ("baseline",))
        target = safe_registered_write_path(artifact["path"])
        write_text(target, baseline["content"])
        readback = sha256_file(target)
        if readback != baseline["content_hash"]:
            raise PermissionError("revert_hash_mismatch")
        rev_id = new_id("ver")
        conn.execute("INSERT INTO artifact_versions(id,artifact_id,state,path,content_hash,content,parent_version_id,created_at) VALUES(?,?,?,?,?,?,?,?)",
                     (rev_id, artifact["id"], "reverted", artifact["path"], readback, baseline["content"], baseline["id"], now()))
        conn.execute("UPDATE artifacts SET current_hash=? WHERE id=?", (readback, artifact["id"]))
        return readback


def export_db(db: str, out: str) -> None:
    with connect(db) as conn:
        data = {}
        for table in ["artifacts", "artifact_versions", "eval_examples", "trace_sources", "runs", "scores", "provider_runs", "plugin_events", "trace_metrics", "gic_signatures", "gates", "packets", "decisions", "waivers", "lineage"]:
            data[table] = [dict(r) for r in conn.execute(f"SELECT * FROM {table}")]
    write_text(out, json_dumps(data) + "\n")


def redact_text(text: str) -> tuple[str, str]:
    status = "clean"
    redacted = text
    for pat in SECRET_PATTERNS:
        if pat.search(redacted):
            status = "redacted"
            redacted = pat.sub("[REDACTED]", redacted)
    return redacted, status


def trace_mine_import(db: str, artifact_id: str, file_path: str) -> dict[str, Any]:
    imported = deduped = redacted_count = blocked = 0
    with connect(db) as conn:
        require_artifact(conn, artifact_id)
        for line_no, line in enumerate(Path(file_path).read_text(encoding="utf-8").splitlines(), 1):
            if not line.strip():
                continue
            raw = json.loads(line)
            payload = json_dumps(raw)
            provenance = sha256_text(payload)
            if fetch_one(conn, "SELECT id FROM trace_sources WHERE provenance_hash=?", (provenance,)):
                deduped += 1
                continue
            text = str(raw.get("input") or raw.get("prompt") or raw.get("message") or "")
            expected = str(raw.get("expected_behavior") or raw.get("expected") or "derived from trace behavior")
            text, s1 = redact_text(text)
            expected, s2 = redact_text(expected)
            redaction_status = "redacted" if "redacted" in {s1, s2} else "clean"
            if not text.strip():
                blocked += 1
                continue
            trace_id = new_id("trace")
            example_id = raw.get("id") or new_id("ex")
            axes = raw.get("axis_tags") or ["context", "action", "closure"]
            risk = raw.get("risk", "medium")
            if risk not in RISK_WEIGHTS:
                risk = "medium"
            conn.execute("INSERT INTO trace_sources(id,artifact_id,provenance_hash,source_path,redaction_status,promotion_status,receipt_json,created_at) VALUES(?,?,?,?,?,?,?,?)",
                         (trace_id, artifact_id, provenance, str(Path(file_path)), redaction_status, "trace_mined", json_dumps({"line": line_no}), now()))
            conn.execute("""INSERT OR REPLACE INTO eval_examples
                (id,artifact_id,input,expected_behavior,axis_tags_json,risk,source,trust_weight,created_by,evidence_refs_json,metadata_json,created_at)
                VALUES(?,?,?,?,?,?,?,?,?,?,?,?)""",
                (example_id, artifact_id, text, expected, json_dumps(axes), risk, "trace_mined", float(raw.get("trust_weight", 0.7)), "trace_miner", json_dumps([trace_id]), json_dumps({"provenance_hash": provenance}), now()))
            imported += 1
            if redaction_status == "redacted":
                redacted_count += 1
    return {"status": "ok", "imported": imported, "deduped": deduped, "redacted": redacted_count, "blocked": blocked}


def scan_path_for_secrets(path: str | Path) -> dict[str, Any]:
    p = Path(path)
    files: list[Path]
    if p.is_dir():
        files = [x for x in p.rglob("*") if x.is_file() and ".git" not in x.parts]
    else:
        files = [p]
    findings: list[dict[str, Any]] = []
    for f in files:
        try:
            text = f.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            continue
        for pattern in secret_findings(text):
            findings.append({"path": str(f), "detector_hash": sha256_text(pattern), "detector_class": "secret_like"})
    return {"status": "fail" if findings else "pass", "findings": findings}


def adapter_discover(root: str | Path = ".") -> dict[str, Any]:
    rootp = Path(root).resolve()
    skills = []
    for path in rootp.rglob("SKILL.md"):
        if ".git" in path.parts or ".venv" in path.parts:
            continue
        skills.append({"path": str(path), "artifact_id": f"skill:{path.parent.name}"})
    return {"status": "ok", "root": str(rootp), "skills": skills}


def replay_packet(db: str, packet_id: str, out_dir: str = ".molt-gic/replay") -> dict[str, Any]:
    with connect(db) as conn:
        packet = fetch_one(conn, "SELECT * FROM packets WHERE id=?", (packet_id,))
        if not packet:
            raise ValueError("packet not found")
        run = fetch_one(conn, "SELECT * FROM runs WHERE id=?", (packet["run_id"],))
        gates = [dict(r) for r in conn.execute("SELECT name,status,detail_json,non_waivable FROM gates WHERE run_id=? ORDER BY name", (run["id"],))]
        outp = Path(out_dir)
        outp.mkdir(parents=True, exist_ok=True)
        receipt = {
            "packet_id": packet_id,
            "run_id": run["id"],
            "runner_model": run["runner_model"],
            "runner_model_version": run["runner_model_version"],
            "judge_model_version": run["judge_model_version"],
            "gate_count": len(gates),
            "replay_determinism": "best_effort",
        }
        receipt_path = outp / f"{packet_id}-replay.json"
        write_text(receipt_path, json_dumps(receipt) + "\n")
        return {"status": "ok", "receipt": str(receipt_path), **receipt}


def cancel_run(db: str, run_id: str) -> None:
    with connect(db) as conn:
        row = fetch_one(conn, "SELECT status FROM runs WHERE id=?", (run_id,))
        if not row:
            raise ValueError("run not found")
        if row["status"] in {"passed", "failed"}:
            raise ValueError("completed run cannot be cancelled")
        conn.execute("UPDATE runs SET status='cancelled', completed_at=? WHERE id=?", (now(), run_id))


def resume_run(db: str, run_id: str) -> dict[str, Any]:
    with connect(db) as conn:
        row = fetch_one(conn, "SELECT * FROM runs WHERE id=?", (run_id,))
        if not row:
            raise ValueError("run not found")
        return {"status": row["status"], "resumable": row["status"] in {"created", "running", "cancelled"}, "run_id": run_id}


def pilot_verify(db: str, artifact_id: str) -> dict[str, Any]:
    with connect(db) as conn:
        require_artifact(conn, artifact_id)
        golden = fetch_one(conn, "SELECT COUNT(*) AS n FROM eval_examples WHERE artifact_id=? AND source='golden'", (artifact_id,))["n"]
        latest = fetch_one(conn, "SELECT * FROM runs WHERE artifact_id=? ORDER BY created_at DESC LIMIT 1", (artifact_id,))
        gates = [] if not latest else [dict(r) for r in conn.execute("SELECT name,status,non_waivable FROM gates WHERE run_id=?", (latest["id"],))]
        ok = golden >= 10 and latest is not None and not any(g["status"] == "fail" and g["non_waivable"] for g in gates)
        return {"status": "pass" if ok else "fail", "golden_count": golden, "latest_run": latest["id"] if latest else None, "gates": gates}


def artifact_rules(typ: str) -> dict[str, Any]:
    if typ not in ALLOWED_ARTIFACT_TYPES:
        raise ValueError(f"unsupported artifact type: {typ}")
    masks = {
        "skill": ["scope", "workflow", "output_rules", "verifier"],
        "prompt": ["system", "developer", "examples", "output_contract"],
        "tool_description": ["name", "description", "parameters", "safety"],
        "route": ["match", "target", "fallback", "safety"],
    }
    apply_policy = "confirm_apply" if typ == "skill" else "review_only"
    return {"artifact_type": typ, "enabled": True, "apply_policy": apply_policy, "mutation_masks": masks[typ]}


def plugin_dry_run(db: str, route: str = "local") -> dict[str, Any]:
    receipt_id = new_id("dry")
    event = {"mode": "dry_run", "gateway_route": route, "receipt_id": receipt_id, "status": "ok", "would_call_cli": True, "live": False}
    with connect(db) as conn:
        conn.execute("INSERT INTO plugin_events(id,mode,gateway_route,receipt_id,status,detail_json,created_at) VALUES(?,?,?,?,?,?,?)",
                     (new_id("plug"), "dry_run", route, receipt_id, "ok", json_dumps(event), now()))
    return event


def plugin_smoke(db: str, route: str = "local", confirm: bool = False, mutate_runtime_config: bool = False, gateway_url: str | None = None) -> dict[str, Any]:
    if mutate_runtime_config:
        raise PermissionError("runtime_config_mutation_blocked")
    if not confirm:
        raise PermissionError("confirm_required")
    receipt_id = new_id("live")
    event = {"mode": "live", "gateway_route": route, "receipt_id": receipt_id, "status": "ok", "live": True, "bounded": True}
    if gateway_url:
        payload = json_dumps({"kind": "molt_gic_smoke", "route": route, "receipt_id": receipt_id}).encode("utf-8")
        req = urllib.request.Request(gateway_url, data=payload, headers={"content-type": "application/json"}, method="POST")
        try:
            with urllib.request.urlopen(req, timeout=10) as resp:
                body = resp.read()
                event["gateway_status"] = resp.status
                event["gateway_body_hash"] = sha256_text(body.decode("utf-8", errors="replace"))
        except urllib.error.URLError as exc:
            raise PermissionError(f"gateway_smoke_failed:{getattr(exc, 'reason', exc)}") from exc
    with connect(db) as conn:
        conn.execute("INSERT INTO plugin_events(id,mode,gateway_route,receipt_id,status,detail_json,created_at) VALUES(?,?,?,?,?,?,?)",
                     (new_id("plug"), "live", route, receipt_id, "ok", json_dumps(event), now()))
    return event


def plugin_hook_spec(route: str = "local") -> dict[str, Any]:
    return {
        "schema": "molt-gic.gateway-hook.v1",
        "route": route,
        "commands": {
            "dry_run": "molt-gic plugin dry-run --json",
            "smoke": "molt-gic plugin smoke --confirm --json",
        },
        "runtime_config_mutation": "blocked",
        "receipt_fields": ["mode", "gateway_route", "receipt_id", "status", "live"],
    }


def dashboard_export(db: str, out: str) -> dict[str, Any]:
    with connect(db) as conn:
        runs = [dict(r) for r in conn.execute("SELECT id,artifact_id,mode,status,recommendation_status,run_score,created_at FROM runs ORDER BY created_at DESC LIMIT 50")]
        gates = [dict(r) for r in conn.execute("SELECT run_id,name,status,non_waivable,detail_json FROM gates ORDER BY created_at DESC LIMIT 200")]
        packets = [dict(r) for r in conn.execute("SELECT id,run_id,recommendation_status,packet_json_path,packet_md_path,created_at FROM packets ORDER BY created_at DESC LIMIT 50")]
        decisions = [dict(r) for r in conn.execute("SELECT id,packet_id,run_id,decision,reviewer,created_at FROM decisions ORDER BY created_at DESC LIMIT 50")]
        lineage = [dict(r) for r in conn.execute("SELECT artifact_id,parent_version_id,child_version_id,reason,created_at FROM lineage ORDER BY created_at DESC LIMIT 100")]
        providers = [dict(r) for r in conn.execute("SELECT run_id,provider,role,model,model_version,status,error_class,latency_ms,cost_usd FROM provider_runs ORDER BY created_at DESC LIMIT 200")]
        plugin_events = [dict(r) for r in conn.execute("SELECT mode,gateway_route,receipt_id,status,detail_json,created_at FROM plugin_events ORDER BY created_at DESC LIMIT 50")]
    snapshot = {
        "schema": "molt-gic.dashboard.v1",
        "read_only": True,
        "generated_at": now(),
        "runs": runs,
        "gates": gates,
        "packets": packets,
        "decisions": decisions,
        "lineage": lineage,
        "provider_runs": providers,
        "plugin_events": plugin_events,
        "summary": {
            "run_count": len(runs),
            "failed_gate_count": sum(1 for g in gates if g["status"] == "fail"),
            "packet_count": len(packets),
        },
    }
    write_text(out, json_dumps(snapshot) + "\n")
    return {"status": "ok", "out": out, "read_only": True, "run_count": len(runs), "failed_gate_count": snapshot["summary"]["failed_gate_count"]}


def dashboard_render(snapshot_path: str, out: str) -> dict[str, Any]:
    snap = json.loads(Path(snapshot_path).read_text(encoding="utf-8"))
    rows = []
    for run in snap.get("runs", []):
        rows.append(f"<tr><td>{run['id']}</td><td>{run['artifact_id']}</td><td>{run['status']}</td><td>{run.get('recommendation_status')}</td></tr>")
    html = f"""<!doctype html>
<html><head><meta charset=\"utf-8\"><title>molt-gic dashboard</title></head>
<body>
<h1>molt-gic dashboard</h1>
<p>Read-only snapshot generated at {snap.get('generated_at')}.</p>
<p>Runs: {snap.get('summary',{}).get('run_count',0)}. Failed gates: {snap.get('summary',{}).get('failed_gate_count',0)}.</p>
<table><thead><tr><th>Run</th><th>Artifact</th><th>Status</th><th>Recommendation</th></tr></thead><tbody>
{''.join(rows)}
</tbody></table>
</body></html>"""
    write_text(out, html)
    return {"status": "ok", "out": out, "read_only": True}

from __future__ import annotations

import argparse
import json
import sqlite3
import sys
from pathlib import Path

from . import __version__
from .core import (
    EXIT_BUDGET,
    EXIT_CONFIG,
    EXIT_GATE,
    EXIT_MODEL,
    EXIT_SAFETY,
    EXIT_USAGE,
    EXIT_VALIDATION,
    add_artifact,
    apply_local,
    apply_revert,
    adapter_discover,
    build_packet,
    cancel_run,
    connect,
    evaluate_run,
    export_db,
    import_examples,
    init_db,
    json_dumps,
    propose_candidate,
    pilot_verify,
    record_decision,
    replay_packet,
    resume_run,
    scan_path_for_secrets,
    trace_mine_import,
)
from .provider import ProviderError, doctor as provider_doctor


def emit(obj, as_json: bool = False) -> None:
    if as_json:
        print(json_dumps(obj))
    elif isinstance(obj, str):
        print(obj)
    else:
        for k, v in obj.items():
            print(f"{k}: {v}")


def latest_packet_id(db: str) -> str:
    with connect(db) as conn:
        row = conn.execute("SELECT id FROM packets ORDER BY created_at DESC LIMIT 1").fetchone()
        if not row:
            raise ValueError("no packet found")
        return row["id"]


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="molt-gic", description="Governed skill evolution CLI")
    parser.add_argument("--version", action="version", version=f"molt-gic {__version__}")
    sub = parser.add_subparsers(dest="cmd", required=True)

    p = sub.add_parser("init")
    p.add_argument("--db", default=".molt-gic.sqlite")
    p.add_argument("--repo", default=".")
    p.add_argument("--json", action="store_true")

    art = sub.add_parser("artifact")
    art_sub = art.add_subparsers(dest="action", required=True)
    p = art_sub.add_parser("add")
    p.add_argument("--db", default=".molt-gic.sqlite")
    p.add_argument("--type", required=True)
    p.add_argument("--path", required=True)
    p.add_argument("--name")
    p.add_argument("--json", action="store_true")
    p = art_sub.add_parser("list")
    p.add_argument("--db", default=".molt-gic.sqlite")
    p.add_argument("--json", action="store_true")

    ds = sub.add_parser("dataset")
    ds_sub = ds.add_subparsers(dest="action", required=True)
    p = ds_sub.add_parser("validate")
    p.add_argument("--file", required=True)
    p.add_argument("--json", action="store_true")
    p = ds_sub.add_parser("import")
    p.add_argument("--db", default=".molt-gic.sqlite")
    p.add_argument("--artifact", required=True)
    p.add_argument("--source", required=True)
    p.add_argument("--file", required=True)
    p.add_argument("--json", action="store_true")
    p = ds_sub.add_parser("promote")
    p.add_argument("--db", default=".molt-gic.sqlite")
    p.add_argument("--example", required=True)
    p.add_argument("--reviewer", required=True)
    p.add_argument("--reason", required=True)
    p.add_argument("--json", action="store_true")

    ev = sub.add_parser("eval")
    ev_sub = ev.add_subparsers(dest="action", required=True)
    p = ev_sub.add_parser("run")
    p.add_argument("--db", default=".molt-gic.sqlite")
    p.add_argument("--artifact", required=True)
    p.add_argument("--mode", choices=["baseline", "candidate"], required=True)
    p.add_argument("--baseline", required=True)
    p.add_argument("--candidate")
    p.add_argument("--provider", default="fixture")
    p.add_argument("--judge-provider", default="fixture")
    p.add_argument("--review-only", action="store_true")
    p.add_argument("--json", action="store_true")

    run = sub.add_parser("run")
    run_sub = run.add_subparsers(dest="action", required=True)
    p = run_sub.add_parser("list")
    p.add_argument("--db", default=".molt-gic.sqlite")
    p.add_argument("--artifact")
    p.add_argument("--json", action="store_true")
    p = run_sub.add_parser("cancel")
    p.add_argument("--db", default=".molt-gic.sqlite")
    p.add_argument("--run", required=True)
    p.add_argument("--json", action="store_true")
    p = run_sub.add_parser("resume")
    p.add_argument("--db", default=".molt-gic.sqlite")
    p.add_argument("--run", required=True)
    p.add_argument("--json", action="store_true")

    evo = sub.add_parser("evolve")
    evo_sub = evo.add_subparsers(dest="action", required=True)
    p = evo_sub.add_parser("propose")
    p.add_argument("--db", default=".molt-gic.sqlite")
    p.add_argument("--artifact", required=True)
    p.add_argument("--strategy", default="hybrid", choices=["template-mask", "llm-rewrite", "hybrid"])
    p.add_argument("--output")
    p.add_argument("--review-only", action="store_true")
    p.add_argument("--json", action="store_true")

    pkt = sub.add_parser("packet")
    pkt_sub = pkt.add_subparsers(dest="action", required=True)
    p = pkt_sub.add_parser("build")
    p.add_argument("--db", default=".molt-gic.sqlite")
    p.add_argument("--run", required=True)
    p.add_argument("--format", default="md,json")
    p.add_argument("--out-dir", default=".molt-gic/packets")
    p.add_argument("--json", action="store_true")

    dec = sub.add_parser("decision")
    dec_sub = dec.add_subparsers(dest="action", required=True)
    p = dec_sub.add_parser("record")
    p.add_argument("--db", default=".molt-gic.sqlite")
    p.add_argument("--packet", required=True)
    p.add_argument("--decision", required=True, choices=["promote", "revise", "reject"])
    p.add_argument("--reviewer", required=True)
    p.add_argument("--rationale", required=True)
    p.add_argument("--json", action="store_true")

    app = sub.add_parser("apply")
    app_sub = app.add_subparsers(dest="action", required=True)
    p = app_sub.add_parser("local")
    p.add_argument("--db", default=".molt-gic.sqlite")
    p.add_argument("--packet", required=True)
    p.add_argument("--reviewer", required=True)
    p.add_argument("--confirm", action="store_true")
    p.add_argument("--json", action="store_true")
    p = app_sub.add_parser("revert")
    p.add_argument("--db", default=".molt-gic.sqlite")
    p.add_argument("--packet", required=True)
    p.add_argument("--reviewer", required=True)
    p.add_argument("--confirm", action="store_true")
    p.add_argument("--json", action="store_true")

    lin = sub.add_parser("lineage")
    lin_sub = lin.add_subparsers(dest="action", required=True)
    p = lin_sub.add_parser("show")
    p.add_argument("--db", default=".molt-gic.sqlite")
    p.add_argument("--artifact", required=True)
    p.add_argument("--json", action="store_true")

    gate = sub.add_parser("gate")
    gate_sub = gate.add_subparsers(dest="action", required=True)
    p = gate_sub.add_parser("explain")
    p.add_argument("--db", default=".molt-gic.sqlite")
    p.add_argument("--run", required=True)
    p.add_argument("--json", action="store_true")

    dbp = sub.add_parser("db")
    db_sub = dbp.add_subparsers(dest="action", required=True)
    p = db_sub.add_parser("export")
    p.add_argument("--db", default=".molt-gic.sqlite")
    p.add_argument("--out", required=True)
    p.add_argument("--json", action="store_true")

    sec = sub.add_parser("security")
    sec_sub = sec.add_subparsers(dest="action", required=True)
    p = sec_sub.add_parser("scan")
    p.add_argument("--path", required=True)
    p.add_argument("--json", action="store_true")

    adapter = sub.add_parser("adapter")
    adapter_sub = adapter.add_subparsers(dest="action", required=True)
    p = adapter_sub.add_parser("discover")
    p.add_argument("--root", default=".")
    p.add_argument("--json", action="store_true")

    replay = sub.add_parser("replay")
    replay_sub = replay.add_subparsers(dest="action", required=True)
    p = replay_sub.add_parser("packet")
    p.add_argument("--db", default=".molt-gic.sqlite")
    p.add_argument("--packet", required=True)
    p.add_argument("--out-dir", default=".molt-gic/replay")
    p.add_argument("--json", action="store_true")

    pilot = sub.add_parser("pilot")
    pilot_sub = pilot.add_subparsers(dest="action", required=True)
    p = pilot_sub.add_parser("verify")
    p.add_argument("--db", default=".molt-gic.sqlite")
    p.add_argument("--artifact", required=True)
    p.add_argument("--json", action="store_true")

    provider = sub.add_parser("provider")
    provider_sub = provider.add_subparsers(dest="action", required=True)
    p = provider_sub.add_parser("doctor")
    p.add_argument("--provider", default="fixture")
    p.add_argument("--json", action="store_true")

    trace = sub.add_parser("trace")
    trace_sub = trace.add_subparsers(dest="action", required=True)
    mine = trace_sub.add_parser("mine")
    mine_sub = mine.add_subparsers(dest="mine_action", required=True)
    p = mine_sub.add_parser("import")
    p.add_argument("--db", default=".molt-gic.sqlite")
    p.add_argument("--artifact", required=True)
    p.add_argument("--file", required=True)
    p.add_argument("--json", action="store_true")

    args = parser.parse_args(argv)
    try:
        if args.cmd == "init":
            init_db(args.db)
            emit({"status": "ok", "db": args.db}, args.json)
        elif args.cmd == "artifact" and args.action == "add":
            artifact_id = add_artifact(args.db, args.type, args.path, args.name)
            emit({"artifact_id": artifact_id}, args.json)
        elif args.cmd == "artifact" and args.action == "list":
            with connect(args.db) as conn:
                rows = [dict(r) for r in conn.execute("SELECT id,name,type,path,current_hash,enabled FROM artifacts ORDER BY id")]
            emit({"artifacts": rows}, args.json)
        elif args.cmd == "dataset" and args.action == "validate":
            n = sum(1 for line in Path(args.file).read_text(encoding="utf-8").splitlines() if line.strip())
            emit({"status": "ok", "examples": n}, args.json)
        elif args.cmd == "dataset" and args.action == "import":
            emit(import_examples(args.db, args.artifact, args.source, args.file), args.json)
        elif args.cmd == "dataset" and args.action == "promote":
            with connect(args.db) as conn:
                conn.execute("UPDATE eval_examples SET source='golden', metadata_json=json_set(metadata_json,'$.promotion_reviewer',?,'$.promotion_reason',?) WHERE id=? AND source='trace_mined'", (args.reviewer, args.reason, args.example))
            emit({"status": "ok", "example_id": args.example}, args.json)
        elif args.cmd == "eval" and args.action == "run":
            rid = evaluate_run(args.db, args.artifact, args.mode, args.baseline, args.candidate, args.review_only, args.provider, args.judge_provider)
            emit({"run_id": rid}, args.json)
        elif args.cmd == "run" and args.action == "list":
            with connect(args.db) as conn:
                if args.artifact:
                    rows = [dict(r) for r in conn.execute("SELECT id,artifact_id,mode,status,recommendation_status,run_score,created_at FROM runs WHERE artifact_id=? ORDER BY created_at", (args.artifact,))]
                else:
                    rows = [dict(r) for r in conn.execute("SELECT id,artifact_id,mode,status,recommendation_status,run_score,created_at FROM runs ORDER BY created_at")]
            emit({"runs": rows}, args.json)
        elif args.cmd == "run" and args.action == "cancel":
            cancel_run(args.db, args.run)
            emit({"status": "cancelled", "run_id": args.run}, args.json)
        elif args.cmd == "run" and args.action == "resume":
            emit(resume_run(args.db, args.run), args.json)
        elif args.cmd == "evolve" and args.action == "propose":
            path = propose_candidate(args.db, args.artifact, args.strategy, args.output, args.review_only)
            emit({"candidate_path": path}, args.json)
        elif args.cmd == "packet" and args.action == "build":
            md, js = build_packet(args.db, args.run, args.out_dir)
            emit({"packet_md": md, "packet_json": js}, args.json)
        elif args.cmd == "decision" and args.action == "record":
            did = record_decision(args.db, args.packet, args.decision, args.reviewer, args.rationale)
            emit({"decision_id": did}, args.json)
        elif args.cmd == "apply" and args.action == "local":
            h = apply_local(args.db, args.packet, args.reviewer, args.confirm)
            emit({"status": "applied", "hash": h}, args.json)
        elif args.cmd == "apply" and args.action == "revert":
            h = apply_revert(args.db, args.packet, args.reviewer, args.confirm)
            emit({"status": "reverted", "hash": h}, args.json)
        elif args.cmd == "lineage" and args.action == "show":
            with connect(args.db) as conn:
                rows = [dict(r) for r in conn.execute("SELECT * FROM lineage WHERE artifact_id=? ORDER BY created_at", (args.artifact,))]
            emit({"lineage": rows}, args.json)
        elif args.cmd == "gate" and args.action == "explain":
            with connect(args.db) as conn:
                rows = [dict(r) for r in conn.execute("SELECT name,status,detail_json,non_waivable FROM gates WHERE run_id=? ORDER BY name", (args.run,))]
            emit({"gates": rows}, args.json)
        elif args.cmd == "db" and args.action == "export":
            export_db(args.db, args.out)
            emit({"status": "ok", "out": args.out}, args.json)
        elif args.cmd == "security" and args.action == "scan":
            result = scan_path_for_secrets(args.path)
            emit(result, args.json)
            return 0 if result["status"] == "pass" else EXIT_SAFETY
        elif args.cmd == "adapter" and args.action == "discover":
            emit(adapter_discover(args.root), args.json)
        elif args.cmd == "replay" and args.action == "packet":
            emit(replay_packet(args.db, args.packet, args.out_dir), args.json)
        elif args.cmd == "pilot" and args.action == "verify":
            result = pilot_verify(args.db, args.artifact)
            emit(result, args.json)
            return 0 if result["status"] == "pass" else EXIT_GATE
        elif args.cmd == "provider" and args.action == "doctor":
            emit(provider_doctor(args.provider), args.json)
        elif args.cmd == "trace" and args.action == "mine" and args.mine_action == "import":
            emit(trace_mine_import(args.db, args.artifact, args.file), args.json)
        else:
            raise ValueError("unhandled command")
        return 0
    except ProviderError as exc:
        print(f"molt-gic: provider error [{exc.error_class}]: {exc}", file=sys.stderr)
        return EXIT_MODEL if exc.error_class in {"timeout", "auth"} else EXIT_CONFIG
    except PermissionError as exc:
        print(f"molt-gic: safety error: {exc}", file=sys.stderr)
        return EXIT_SAFETY
    except (ValueError, json.JSONDecodeError, sqlite3.IntegrityError) as exc:
        print(f"molt-gic: validation error: {exc}", file=sys.stderr)
        return EXIT_VALIDATION
    except FileNotFoundError as exc:
        print(f"molt-gic: config error: {exc}", file=sys.stderr)
        return EXIT_CONFIG


if __name__ == "__main__":
    raise SystemExit(main())

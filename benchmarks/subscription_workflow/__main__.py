"""Run a synthetic subscription-state comparison without API keys."""

import argparse
import json
import sys
from pathlib import Path

from .contract import PROFILES, read, write
from .data import SPLITS, build, load
from .runner import audit, evaluate, freeze, import_adapter, verify_freeze


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    commands.add_parser("validate")
    commands.add_parser("freeze")
    replay = commands.add_parser("audit")
    replay.add_argument("report", type=Path)
    run = commands.add_parser("run")
    run.add_argument("--split", choices=SPLITS, default="development")
    run.add_argument("--profiles", nargs="+", choices=PROFILES, default=list(PROFILES))
    run.add_argument("--candidate-factory", help="Explicit trusted Python module:factory")
    run.add_argument("--gate", help="Explicit trusted Python module:gate")
    run.add_argument("--out", type=Path, required=True)
    run.add_argument("--html", type=Path)
    run.add_argument("--markdown", type=Path)
    run.add_argument("--require-invariants", action="store_true",
                     help="Fail if invariant-profile task handling or mutation safety regresses")
    args = parser.parse_args()
    try:
        if args.command == "validate":
            build(check=True)
            verify_freeze()
            print(json.dumps({split: len(load(split)[0]) for split in SPLITS}))
            return 0
        if args.command == "freeze":
            print(json.dumps(freeze()))
            return 0
        if args.command == "audit":
            print(json.dumps(audit(read(args.report))))
            return 0
        if args.require_invariants and "invariants" not in args.profiles:
            raise ValueError("--require-invariants requires the invariants profile")
        candidate, gate, identity = None, None, {}
        if args.candidate_factory:
            candidate, identity["candidate"] = import_adapter(args.candidate_factory)
        if args.gate:
            gate, identity["gate"] = import_adapter(args.gate)
        report = evaluate(args.split, args.profiles, candidate, gate, identity or None)
        write(args.out, report)
        if args.html or args.markdown:
            from .reporting import render_html, render_markdown
            for path, text in ((args.html, render_html(report) if args.html else None),
                               (args.markdown, render_markdown(report) if args.markdown else None)):
                if path:
                    path.parent.mkdir(parents=True, exist_ok=True)
                    path.write_text(text, encoding="utf-8")
        metrics = {name: config["metrics"] for name, config in report["configurations"].items()}
        print(json.dumps({"report_hash": report["report_hash"], "metrics": metrics}))
        if any(value["candidate_errors"] for value in metrics.values()):
            return 3
        if args.require_invariants:
            value = metrics["invariants"]
            if value["unsafe_effects"] or value["task_success"]["rate"] != 1:
                return 1
        return 0
    except (OSError, ValueError, KeyError, ImportError, AttributeError) as exc:
        print(f"Subscription evaluation: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())

"""Source-checkout CLI for the executed support-workflow benchmark."""

import argparse
import json
from pathlib import Path

from .data import load
from .runner import calibration, compare, evaluate, fit_gate


def read(path):
    return json.loads(path.read_text(encoding="utf-8"))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    commands.add_parser("validate")
    replay = commands.add_parser("audit")
    replay.add_argument("report", type=Path)
    for name in ("calibration", "run"):
        command = commands.add_parser(name)
        command.add_argument("--candidate", choices=["rules", "majority", "random", "naive_bayes", "strands", "laya"], required=True)
        command.add_argument("--device", choices=["cpu", "mps", "cuda"], default="cpu")
        command.add_argument("--out", type=Path, required=True)
        if name == "run":
            command.add_argument("--split", choices=["development", "test"], default="test")
            command.add_argument("--strategy", choices=["direct", "gated_rules"], default="direct")
            command.add_argument("--gate", type=Path)
    gate = commands.add_parser("fit-gate")
    gate.add_argument("report", type=Path)
    gate.add_argument("--out", type=Path, required=True)
    matched = commands.add_parser("compare")
    matched.add_argument("reports", nargs="+", type=Path)
    matched.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    if args.command == "validate":
        for split in ("development", "calibration", "test"):
            cases, manifest = load(split)
            print(split, len(cases), "episodes;", len(manifest["files"][split]["families"]), "wording families")
        return
    if args.command == "audit":
        from .audit import audit
        print(json.dumps(audit(read(args.report))))
        return
    if args.command == "calibration":
        report = calibration(args.candidate, args.device)
    elif args.command == "fit-gate":
        report = fit_gate(read(args.report))
    elif args.command == "compare":
        report = compare([read(path) for path in args.reports])
    else:
        report = evaluate(args.candidate, args.split, args.device, args.strategy,
                          read(args.gate) if args.gate else None)
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(report, indent=2, ensure_ascii=False, allow_nan=False) + "\n", encoding="utf-8")
    print(json.dumps({"kind": report["kind"], "hash": report["report_hash"],
                      "threshold": report.get("threshold"), "metrics": report.get("metrics")}))
    if report.get("errors") or report.get("metrics", {}).get("primary_errors"):
        raise SystemExit(3)


if __name__ == "__main__":
    main()

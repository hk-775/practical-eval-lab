"""Source-checkout entry point: python -m benchmarks.decision_models."""

import argparse
import json
import sys
from pathlib import Path

from .adapters import CandidateError
from .contract import load_dataset, read_json, write_json
from .runner import calibrate, compare, markdown, run


def main():
    parser = argparse.ArgumentParser(description="Frozen Choice benchmark, separate from the six teaching suites.")
    commands = parser.add_subparsers(dest="command", required=True)
    commands.add_parser("validate")
    execute = commands.add_parser("run")
    execute.add_argument("--candidate", choices=["baseline", "strands", "laya", "jev"], required=True)
    execute.add_argument("--split", choices=["calibration", "holdout"], default="holdout")
    execute.add_argument("--device", choices=["cpu", "mps", "cuda"], default="cpu")
    execute.add_argument("--trials", type=int, default=1)
    execute.add_argument("--threshold", type=float, default=0.9)
    execute.add_argument("--gate", type=Path)
    execute.add_argument("--input-usd-per-million", type=float)
    execute.add_argument("--compute-usd-per-hour", type=float)
    execute.add_argument("--out", type=Path, required=True)
    fit = commands.add_parser("calibrate")
    fit.add_argument("report", type=Path)
    fit.add_argument("--max-error", type=float, default=.05)
    fit.add_argument("--min-accepted", type=int, default=10)
    fit.add_argument("--out", type=Path, required=True)
    paired = commands.add_parser("compare")
    paired.add_argument("reports", type=Path, nargs="+")
    paired.add_argument("--out", type=Path, required=True)
    paired.add_argument("--markdown", type=Path)
    args = parser.parse_args()
    try:
        if args.command == "validate":
            for split in ("calibration", "holdout"):
                cases, _ = load_dataset(split)
                print(f"{split}: {len(cases)} requests, {sum(len(c['questions']) for c in cases)} decisions")
            return 0
        if args.command == "run":
            report = run(args.candidate, args.split, device=args.device, trials=args.trials,
                         threshold=args.threshold, gate=read_json(args.gate) if args.gate else None,
                         input_price=args.input_usd_per_million, hourly_cost=args.compute_usd_per_hour)
        elif args.command == "calibrate":
            report = calibrate(read_json(args.report), args.max_error, args.min_accepted)
        else:
            report = compare([read_json(path) for path in args.reports])
            if args.markdown:
                args.markdown.parent.mkdir(parents=True, exist_ok=True)
                args.markdown.write_text(markdown(report), encoding="utf-8")
        write_json(args.out, report)
        print(json.dumps({"kind": report["kind"], "report_hash": report["report_hash"],
                          "metrics": report.get("metrics"), "threshold": report.get("threshold")}))
        return 3 if report.get("metrics", {}).get("errors") else 0
    except CandidateError as exc:
        print(f"Not run: {exc}", file=sys.stderr)
        return 2
    except (ValueError, OSError) as exc:
        # Exception bodies may contain private paths or provider data.
        print(f"Benchmark failed ({type(exc).__name__}); check inputs and the documented contract.", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())

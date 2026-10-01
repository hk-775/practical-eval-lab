from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from .core import compare_reports, load_cases, run_eval
from .suites import CATALOG


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description="Practical Eval Lab")
    commands = parser.add_subparsers(dest="command", required=True)
    for name in ("run", "compare"):
        command = commands.add_parser(name)
        command.add_argument("--suite", choices=CATALOG, default="classification")
        command.add_argument("--split", choices=("dev", "holdout"), default="dev")
        command.add_argument("--min-score", type=float, default=.8)
        command.add_argument("--cases", type=Path)
        command.add_argument("--report", type=Path)
        command.add_argument("--config", type=Path, help="Tuning profile exported by the webpage")
        if name == "run":
            command.add_argument("--candidate", choices=("baseline", "improved", "openai"), default="baseline")
            command.add_argument("--provider", choices=("heuristic", "openai"), help="Legacy alias")
            command.add_argument("--model")
            command.add_argument("--prompt", type=Path)
    commands.add_parser("serve")
    args = parser.parse_args(argv)
    if args.command == "serve":
        from .server import main as serve
        return serve([])
    try:
        options = {"threshold": args.min_score}
        if args.config:
            from .store import validate_config
            config = validate_config(args.suite, json.loads(args.config.read_text()))
            if args.split != "dev" or args.cases:
                raise ValueError("--config is a development profile; do not combine it with --cases or --split holdout")
            options.update(config)
        elif args.cases:
            options["cases"] = load_cases(args.suite, args.split, args.cases)
        if args.command == "compare":
            before = run_eval(args.suite, "baseline", args.split, **options)
            after = run_eval(args.suite, "improved", args.split, **options)
            output = compare_reports(before, after)
            print(f"{args.suite}: {before['score']:.1%} → {after['score']:.1%}")
            print(f"Improved: {output['improved']}  Regressed: {output['regressed']}")
            report = after
        else:
            candidate = args.candidate
            if args.provider:
                candidate = "baseline" if args.provider == "heuristic" else "openai"
            report = output = run_eval(args.suite, candidate, args.split, model=args.model,
                                      prompt=args.prompt.read_text() if args.prompt else None, **options)
        for result in report["results"]:
            failed = ", ".join(c["name"] for c in result["checks"] if not c["passed"])
            print(f"{'PASS' if result['passed'] else 'FAIL'} {result['id']}" + (f" [{failed}]" if failed else ""))
        print(f"\n{report['passed']}/{report['total']} = {report['score']:.1%}; gate {report['threshold']:.0%}: {'PASS' if report['passed_gate'] else 'FAIL'}")
        for tag, score in report["slices"].items():
            print(f"  {tag}: {score['passed']}/{score['total']} ({score['accuracy']:.0%})")
        if args.report:
            args.report.parent.mkdir(parents=True, exist_ok=True)
            args.report.write_text(json.dumps(output, indent=2, ensure_ascii=False) + "\n")
            print(f"Saved {args.report}")
        return 0 if report["passed_gate"] else 1
    except (ValueError, OSError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2

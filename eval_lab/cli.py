from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from .core import compare_reports, load_cases, run_eval
from .integrations import load_project
from .reports import html_report, validate_report
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
        command.add_argument("--html", type=Path, help="Write a standalone, shareable HTML report")
        command.add_argument("--config", type=Path, help="Tuning profile exported by the webpage")
        command.add_argument("--project", type=Path, help="Trusted named candidate registrations")
        command.add_argument("--trials", type=int, default=1)
        command.add_argument("--critical-tag", action="append", default=[])
        command.add_argument("--min-slice", action="append", default=[], metavar="TAG=SCORE")
        command.add_argument("--swap-pairs", action="store_true", help="Swap A/B positions in response_quality")
        if name == "run":
            command.add_argument("--candidate", default="baseline")
            command.add_argument("--provider", choices=("heuristic", "openai"), help="Legacy alias")
            command.add_argument("--model")
            command.add_argument("--prompt", type=Path)
        else:
            command.add_argument("--before", default="baseline")
            command.add_argument("--after", default="improved")
            command.add_argument("--fail-on-regression", action="store_true")
    server = commands.add_parser("serve")
    server.add_argument("--port", type=int, default=8000)
    server.add_argument("--state-dir", type=Path)
    server.add_argument("--project", type=Path)
    export = commands.add_parser("export", help="Export a saved JSON report as HTML")
    export.add_argument("input", type=Path)
    export.add_argument("--html", type=Path, required=True)
    saved = commands.add_parser("compare-reports", help="Compare compatible saved runs")
    saved.add_argument("before", type=Path)
    saved.add_argument("after", type=Path)
    saved.add_argument("--report", type=Path)
    saved.add_argument("--html", type=Path)
    args = parser.parse_args(argv)
    if args.command == "serve":
        from .server import main as serve
        flags = ["--port", str(args.port)]
        if args.state_dir:
            flags += ["--state-dir", str(args.state_dir)]
        if args.project:
            flags += ["--project", str(args.project)]
        return serve(flags)
    try:
        if args.command == "export":
            write_outputs(args, validate_report(json.loads(args.input.read_text(encoding="utf-8"))))
            return 0
        if args.command == "compare-reports":
            reports = [validate_report(json.loads(p.read_text(encoding="utf-8"))) for p in (args.before, args.after)]
            output = compare_reports(*(r.get("after", r) for r in reports))
            write_outputs(args, output)
            print(f"Change: {output['delta']:+.1%}; regressions: {output['regressed']}")
            return exit_code(output)
        slices = {}
        for entry in args.min_slice:
            tag, separator, raw = entry.rpartition("=")
            if not separator or not tag:
                raise ValueError("--min-slice must be TAG=SCORE")
            slices[tag] = float(raw)
        options = {"threshold": args.min_score, "project": load_project(args.project), "trials": args.trials,
                   "swap_pairs": args.swap_pairs, "gates": {
                       "critical_tags": args.critical_tag, "min_slices": slices,
                       "fail_on_regression": getattr(args, "fail_on_regression", False)}}
        if args.config:
            from .store import validate_config
            config = validate_config(args.suite, json.loads(args.config.read_text(encoding="utf-8")))
            if args.split != "dev" or args.cases:
                raise ValueError("--config is a development profile; do not combine it with --cases or --split holdout")
            options.update({k: config[k] for k in ("cases", "settings", "threshold")})
        elif args.cases:
            options["cases"] = load_cases(args.suite, args.split, args.cases)
        if args.command == "compare":
            before = run_eval(args.suite, args.before, args.split, **options)
            after = run_eval(args.suite, args.after, args.split, **options)
            output = compare_reports(before, after)
            print(f"{args.suite}: {before['score']:.1%} → {after['score']:.1%}")
            print(f"Improved: {output['improved']}  Regressed: {output['regressed']}")
            report = after
        else:
            candidate = args.candidate
            if args.provider:
                candidate = "baseline" if args.provider == "heuristic" else "openai"
            report = output = run_eval(args.suite, candidate, args.split, model=args.model,
                                      prompt=args.prompt.read_text(encoding="utf-8") if args.prompt else None, **options)
        for result in report["results"]:
            failed = ", ".join(c["name"] for c in result["checks"] if not c["passed"])
            print(f"{'PASS' if result['passed'] else 'FAIL'} {result['id']}" + (f" [{failed}]" if failed else ""))
        print(f"\n{report['passed']}/{report['total']} = {report['score']:.1%}; gate {report['threshold']:.0%}: {'PASS' if report['passed_gate'] else 'FAIL'}")
        for tag, score in report["slices"].items():
            print(f"  {tag}: {score['passed']}/{score['total']} ({score['accuracy']:.0%})")
        for gate in output.get("gates", report["gates"]):
            print(f"  Gate {gate['name']}: {'PASS' if gate['passed'] else 'FAIL'} — {gate['detail']}")
        print(f"Execution errors: {report['execution_errors']}; candidate latency p95: {report['metrics']['candidate_latency_ms']['p95']:.3f} ms")
        write_outputs(args, output)
        return exit_code(output)
    except (ValueError, OSError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2


def exit_code(output):
    reports = [output["before"], output["after"]] if "before" in output else [output]
    if any(report["execution_errors"] for report in reports):
        return 3
    return 0 if output["passed_gate"] else 1


def write_outputs(args, output):
    for flag, content in (("report", lambda: json.dumps(output, indent=2, ensure_ascii=False, allow_nan=False) + "\n"),
                          ("html", lambda: html_report(output))):
        path = getattr(args, flag, None)
        if path:
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(content(), encoding="utf-8")
            print(f"Saved {path}")

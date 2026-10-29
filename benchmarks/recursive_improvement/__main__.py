"""Source-checkout CLI; no commands execute user-supplied code or contact a provider."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from . import data
from .artifacts import BASELINE, changes, read_json, write_json
from .experiment import (
    DEFAULT_GENERATIONS, DEFAULT_SEEDS, audit, evaluate, freeze, plan, search, verify_freeze,
)
from .reporting import render_html, render_markdown


def parser():
    result = argparse.ArgumentParser(description="Bounded recursive workflow improvement")
    commands = result.add_subparsers(dest="command", required=True)
    commands.add_parser("validate", help="Check authored data and the frozen protocol")
    commands.add_parser("freeze", help="Create the immutable protocol commitment once")
    tune = commands.add_parser("search", help="Search development; select on validation")
    tune.add_argument("--seeds", default=",".join(map(str, DEFAULT_SEEDS)))
    tune.add_argument("--generations", type=int, default=DEFAULT_GENERATIONS)
    tune.add_argument("--out", type=Path, required=True)
    test = commands.add_parser("evaluate", help="Verify selection, then execute the final split")
    test.add_argument("--search", type=Path, required=True)
    test.add_argument("--out-dir", type=Path, required=True)
    replay = commands.add_parser("audit", help="Reconstruct search, actions, state and metrics")
    replay.add_argument("report", type=Path)
    render = commands.add_parser("render", help="Render existing evidence without rerunning it")
    render.add_argument("report", type=Path)
    render.add_argument("--html", type=Path, required=True)
    render.add_argument("--markdown", type=Path)
    return result


def main(argv=None):
    args = parser().parse_args(argv)
    try:
        if args.command == "freeze":
            print(json.dumps(freeze(), indent=2))
        elif args.command == "validate":
            print(json.dumps({"dataset": data.validate(), "freeze": verify_freeze()["sha256"]}, indent=2))
        elif args.command == "search":
            if args.out.exists():
                raise ValueError("Refusing to overwrite an existing search record")
            seeds = [int(value) for value in args.seeds.split(",")]
            record = search(plan(seeds, args.generations))
            write_json(args.out, record)
            print(json.dumps({"search": str(args.out), "sha256": record["sha256"],
                              "selection_commitment": record["selection_commitment"]}, indent=2))
        elif args.command == "evaluate":
            if args.out_dir.exists():
                raise ValueError("Use a new output directory; existing evidence is never overwritten")
            report = evaluate(read_json(args.search))
            args.out_dir.mkdir(parents=True, exist_ok=False)
            write_json(args.out_dir / "comparison.json", report)
            (args.out_dir / "comparison.html").write_text(render_html(report), encoding="utf-8")
            (args.out_dir / "comparison.md").write_text(render_markdown(report), encoding="utf-8")
            for row in report["search"]["state"]["runs"]:
                target = args.out_dir / "candidates" / f'{row["seed"]}-{row["arm"]}.json'
                write_json(target, row["selected_artifact"])
                write_json(target.with_suffix(".changes.json"),
                           changes(BASELINE, row["selected_artifact"]))
            print(json.dumps({"report": str(args.out_dir / "comparison.html"),
                              "sha256": report["sha256"], "comparison": report["comparison"]}, indent=2))
        elif args.command == "audit":
            print(json.dumps(audit(read_json(args.report)), indent=2))
        elif args.command == "render":
            report = read_json(args.report)
            if args.html.exists() or (args.markdown and args.markdown.exists()):
                raise ValueError("Render to new files; existing artifacts are not overwritten")
            # Rendering verifies the report seal but does not execute an experiment.
            args.html.parent.mkdir(parents=True, exist_ok=True)
            args.html.write_text(render_html(report), encoding="utf-8")
            if args.markdown:
                args.markdown.parent.mkdir(parents=True, exist_ok=True)
                args.markdown.write_text(render_markdown(report), encoding="utf-8")
        return 0
    except (ValueError, TypeError, KeyError, OSError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())

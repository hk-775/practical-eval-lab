"""Build, search, separately evaluate, and replay the stage fault corpus."""

import argparse
import json
import sys
from pathlib import Path

from benchmarks.recursive_improvement.artifacts import read_json, write_json

from . import data, engine, reporting


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("validate")
    sub.add_parser("freeze")
    search = sub.add_parser("search")
    search.add_argument("--out-dir", type=Path, required=True)
    search.add_argument("--seeds", default=",".join(map(str, engine.SEEDS)))
    search.add_argument("--generations", type=int, default=8)
    evaluate = sub.add_parser("evaluate")
    evaluate.add_argument("--search-dir", type=Path, required=True)
    evaluate.add_argument("--out-dir", type=Path, required=True)
    audit = sub.add_parser("audit")
    audit.add_argument("directory", type=Path)
    inspect = sub.add_parser("inspect")
    inspect.add_argument("directory", type=Path)
    inspect.add_argument("--batch", required=True)
    inspect.add_argument("--case", required=True)
    inspect.add_argument("--out", type=Path, required=True)
    args = parser.parse_args(argv)
    try:
        if args.command == "validate":
            print(json.dumps({"dataset": data.validate(), "freeze": engine.verify_freeze()["sha256"]},
                             indent=2))
        elif args.command == "freeze":
            print(json.dumps(engine.freeze(), indent=2))
        elif args.command == "search":
            if args.out_dir.exists():
                raise ValueError("Use a fresh output directory")
            record, store = engine.search(engine.plan(
                [int(seed) for seed in args.seeds.split(",")], args.generations))
            engine.write_bundle(args.out_dir, record, store, "search.json")
            print(json.dumps({"search": str(args.out_dir), "sha256": record["sha256"],
                              "physical_episodes": store.physical_episodes}, indent=2))
        elif args.command == "evaluate":
            if args.out_dir.exists():
                raise ValueError("Use a fresh output directory")
            search = read_json(args.search_dir / "search.json")
            engine.verify_bundle(args.search_dir, search["state"]["batches"])
            report, store = engine.evaluate(search)
            engine.write_bundle(args.out_dir, report, store, "comparison.json")
            (args.out_dir / "comparison.html").write_text(reporting.render_html(report), encoding="utf-8")
            (args.out_dir / "comparison.md").write_text(reporting.markdown(report), encoding="utf-8")
            for row in search["state"]["runs"]:
                target = args.out_dir / "candidates" / f"{row['selected_sha256']}.json"
                if not target.exists():
                    write_json(target, row["selected_artifact"])
            print(json.dumps({"report": str(args.out_dir / "comparison.html"),
                              "sha256": report["sha256"], "paired": report["paired"],
                              "aggregate": report["aggregate"]}, indent=2))
        elif args.command == "audit":
            print(json.dumps(engine.audit(args.directory), indent=2))
        elif args.command == "inspect":
            if args.out.exists():
                raise ValueError("Refusing to overwrite an existing trace")
            write_json(args.out, engine.inspect_case(args.directory, args.batch, args.case))
        return 0
    except (ValueError, OSError, KeyError, TypeError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())

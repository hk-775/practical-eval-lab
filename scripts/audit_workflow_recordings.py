"""Portable replay of the frozen Mac-recorded workflow artifacts.

The frozen runner records source labels using its host Path representation.
Canonicalize those labels to POSIX for these archived Mac reports, without
editing the frozen evaluation implementation or rewriting any report.
"""

import argparse
import json
from pathlib import Path

from benchmarks.decision_models.contract import ROOT as MODEL_ROOT
from benchmarks.tool_workflow.audit import equal, replay_episode
from benchmarks.tool_workflow.data import ROOT, digest, load
from benchmarks.tool_workflow.metrics import summarize
from benchmarks.tool_workflow.runner import verify


def archived_protocol_hash():
    paths = sorted(ROOT.glob("*.py")) + [ROOT / "PROTOCOL.md"]
    paths += [MODEL_ROOT / p for p in
              ("adapters.py", "local_models.py", "contract.py", "models.json", "runtime/uv.lock")]
    return digest([(p.relative_to(ROOT.parent).as_posix(), p.read_text(encoding="utf-8")) for p in paths])


def audit(report):
    verify(report, "workflow-evaluation")
    freeze = json.loads((ROOT / "freeze.json").read_text(encoding="utf-8"))
    if archived_protocol_hash() != freeze["protocol_hash"] or report["protocol_hash"] != freeze["protocol_hash"]:
        raise ValueError("Frozen implementation or report protocol differs")
    cases, manifest = load(report["split"])
    if report["dataset_sha256"] != manifest["files"][report["split"]]["sha256"]:
        raise ValueError("Dataset differs")
    by_id = {c["id"]: c for c in cases}
    episodes = report["episodes"]
    if len(episodes) != len(cases) or {e["case_id"] for e in episodes} != set(by_id):
        raise ValueError("Episode coverage differs")
    for episode in episodes:
        case = by_id[episode["case_id"]]
        if any(episode[k] != case[k] for k in ("family", "stratum", "condition")):
            raise ValueError("Episode grouping differs")
        replay_episode(case, episode, report["strategy"], report["threshold"])
    if not equal(summarize(episodes), report["metrics"]):
        raise ValueError("Metrics differ")
    return {"episodes_replayed": len(episodes), "report_hash": report["report_hash"]}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("report", type=Path)
    args = parser.parse_args()
    print(json.dumps(audit(json.loads(args.report.read_text(encoding="utf-8")))))


if __name__ == "__main__":
    main()

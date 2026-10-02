"""Check the pinned Laya renderer for hidden option/question/state truncation."""

import argparse
import json
from pathlib import Path

from benchmarks.decision_models.contract import ROOT as MODEL_ROOT
from .data import load
from .simulator import reference_observations, request_for


def audit():
    from huggingface_hub import snapshot_download
    from laya import Agent
    from laya.agent import _load_tokenizer
    from laya.common import build_head, build_sequence, render_options, _encode_question_text

    info = json.loads((MODEL_ROOT / "models.json").read_text())["laya"]
    snapshot = Path(snapshot_download(info["model"], revision=info["revision"],
                                     allow_patterns=["rl_agent_config.json", "tokenizer/*"]))
    config = json.loads((snapshot / "rl_agent_config.json").read_text())
    tok = _load_tokenizer(str(snapshot / "tokenizer"), config)
    report = {"model": info["model"], "revision": info["revision"], "max_len": 512,
              "head_max_len": 192, "states": 0, "questions": 0,
              "maximum_head_tokens": 0, "maximum_sequence_tokens": 0,
              "maximum_option_tokens": 0, "errors": [], "datasets": {}}
    for split in ("development", "calibration", "test"):
        cases, manifest = load(split)
        report["datasets"][split] = manifest["files"][split]["sha256"]
        for case in cases:
            for obs, _ in reference_observations(case):
                report["states"] += 1
                request = request_for(obs, info["model"])
                for key, definition in request["questions"].items():
                    report["questions"] += 1
                    q = Agent._to_internal(definition)
                    head, _, _ = build_head(tok, q, head_max_len=192)
                    uncapped, _, _ = build_head(tok, q, head_max_len=10000)
                    sequence, _, options, state = build_sequence(
                        tok, request["state"], q, max_len=512, head_max_len=192,
                        return_stats=True, return_truncation_stats=True,
                    )
                    longest = max(len(_encode_question_text(tok, " " + text, add_special_tokens=False))
                                  for text in render_options(q))
                    report["maximum_head_tokens"] = max(report["maximum_head_tokens"], len(head))
                    report["maximum_sequence_tokens"] = max(report["maximum_sequence_tokens"], len(sequence))
                    report["maximum_option_tokens"] = max(report["maximum_option_tokens"], longest)
                    if (head != uncapped or longest > 48 or state["truncated"]
                            or options["options"] != options["options_distinct"]
                            or options["tokens_per_option"] is not None):
                        report["errors"].append({"case_id": case["id"], "question": key})
    return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    report = audit()
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(report, indent=2) + "\n")
    print(json.dumps(report))
    if report["errors"]:
        raise SystemExit(3)


if __name__ == "__main__":
    main()

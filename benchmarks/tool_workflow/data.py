"""Frozen grouped episodes and their original synthetic provenance."""

from __future__ import annotations

import argparse
import hashlib
import json
import random
from pathlib import Path

from .phrases import PHRASES

ROOT = Path(__file__).resolve().parent
VERSION = "support-tool-workflow-v2"
SEED = 20261002
CONDITIONS = (
    "read", "read_negated_write", "write", "write_correction",
    "missing_ticket_read", "missing_ticket_write", "missing_priority",
    "ambiguous_intent", "denied_update", "locked_update", "unsupported", "contrast_read",
)
# The same wording under different permission/lock states is one family.
# All three contexts therefore stay in the same partition.
BANK = {condition: "write" if condition in ("denied_update", "locked_update") else condition
        for condition in CONDITIONS}


def dumps(value):
    return json.dumps(value, ensure_ascii=False, allow_nan=False, separators=(",", ":"))


def digest(value):
    return hashlib.sha256(dumps(value).encode()).hexdigest()


def make_cases():
    output = {split: [] for split in ("development", "calibration", "test")}
    allocation = {}
    for bank in sorted(set(BANK.values())):
        indices = list(range(len(PHRASES[bank])))
        random.Random(f"{SEED}:{bank}").shuffle(indices)
        assert len(indices) == 12
        for position, index in enumerate(indices):
            allocation[bank, index] = (
                "development" if position < 3 else "calibration" if position < 6 else "test"
            )
    serial = 0
    identifiers = random.Random(f"{SEED}:opaque-identifiers").sample(range(10000, 99999), 576)
    priorities = ("low", "normal", "high")
    for condition_index, condition in enumerate(CONDITIONS):
        bank = BANK[condition]
        for index, template in enumerate(PHRASES[bank]):
            split = allocation[bank, index]
            family = f"{bank}-{index + 1:02}"
            for variant in range(2):
                serial += 1
                target = f"SYN-{identifiers[(serial - 1) * 2]}"
                other = f"SYN-{identifiers[(serial - 1) * 2 + 1]}"
                old = priorities[(index + variant + condition_index) % 3]
                new = priorities[(index + variant + condition_index + 1) % 3]
                text = template.format(ticket=target, other=other, old=old, new=new)
                intent = (
                    "unsupported" if condition == "unsupported"
                    else "read" if condition in ("read", "read_negated_write", "missing_ticket_read", "contrast_read")
                    else ("read" if variant == 0 else "write") if condition == "ambiguous_intent"
                    else "write"
                )
                clarification = {
                    "missing_ticket_read": "ticket", "missing_ticket_write": "ticket",
                    "missing_priority": "priority", "ambiguous_intent": "intent",
                }.get(condition)
                tickets = [
                    {"id": target, "priority": old, "locked": condition == "locked_update"},
                    {"id": other, "priority": priorities[(index + 2) % 3], "locked": variant == 1},
                ]
                if variant:
                    tickets.reverse()
                reply = (f"Please read ticket {target} without changing it." if intent == "read"
                         else f"Please set ticket {target} to priority {new}.")
                output[split].append({
                    "id": f"{condition}-{index + 1:02}-{variant}",
                    "family": family, "stratum": bank, "condition": condition, "variant": variant,
                    "initial": {
                        "authorization": {"can_update": condition != "denied_update"},
                        "tickets": tickets, "messages": [text],
                    },
                    "goal": {"intent": intent, "ticket_id": target,
                             "priority": new if intent == "write" else None,
                             "clarification": clarification,
                             "reply": reply if clarification else None},
                })
    for split, cases in output.items():
        random.Random(f"{SEED}:order:{split}").shuffle(cases)
    return output


def artifacts():
    manifest = {
        "version": VERSION, "license": "MIT-0", "seed": SEED, "created": "2026-10-02",
        "provenance": "Original synthetic support requests, fictional SYN ticket identifiers, and executable private task goals. No customer or production data.",
        "partition": "Utterance families split before slot expansion. Write, denied-update, and locked-update counterparts share a family and partition.",
        "sampling": "Balanced over 12 authored conditions. Two slot/order variants per family-condition. This is a designed simulator workload, not sampled enterprise traffic.",
        "files": {},
    }
    output = {}
    for split, cases in make_cases().items():
        text = "".join(dumps(case) + "\n" for case in cases)
        manifest["files"][split] = {
            "sha256": hashlib.sha256(text.encode()).hexdigest(),
            "episodes": len(cases), "families": sorted({c["family"] for c in cases}),
            "conditions": {c: sum(row["condition"] == c for row in cases) for c in CONDITIONS},
        }
        output[f"{split}.jsonl"] = text
    output["manifest.json"] = json.dumps(manifest, indent=2) + "\n"
    return output


def load(split):
    if split not in ("development", "calibration", "test"):
        raise ValueError("Unknown workflow split")
    manifest = json.loads((ROOT / "data/manifest.json").read_text(encoding="utf-8"))
    raw = (ROOT / f"data/{split}.jsonl").read_bytes()
    if hashlib.sha256(raw).hexdigest() != manifest["files"][split]["sha256"]:
        raise ValueError("Frozen workflow data changed")
    cases = [json.loads(line) for line in raw.decode().splitlines()]
    return cases, manifest


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()
    directory = ROOT / "data"
    directory.mkdir(exist_ok=True)
    for name, text in artifacts().items():
        path = directory / name
        if args.check:
            if not path.exists() or path.read_bytes() != text.encode():
                raise SystemExit(f"Frozen workflow artifact differs: {name}")
        else:
            path.write_bytes(text.encode())
    print("Workflow fixtures verified." if args.check else "Workflow fixtures written.")


if __name__ == "__main__":
    main()

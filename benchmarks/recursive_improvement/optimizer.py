"""Trace-directed configuration search with an evolvable proposal strategy.

The immutable interpreter and selection rule bound the search. This is a small
program/configuration experiment, not an LLM or unrestricted code-writing agent.
"""

from __future__ import annotations

from collections import Counter
from copy import deepcopy

from .artifacts import OPTIMIZER_SPACE, POLICY_SPACE, validate_artifact


def feedback(episodes):
    """Only public tool feedback and success bits, never references/final test cases."""
    return [{
        "success": episode["outcome"]["task_success"],
        "signals": [
            {"tool": row["plan"]["tool"], "status": row["result"]["status"],
             "reason": row["result"].get("reason")}
            for row in episode["trace"]
        ],
    } for episode in episodes]


def diagnose(rows, attribution):
    counts = Counter()
    for row in rows:
        if row["success"]:
            continue
        signals = []
        for signal in row["signals"]:
            status, reason = signal["status"], signal["reason"]
            if status == "unknown":
                signals.append("unknown")
            elif signal["tool"] == "lookup_operation" and status == "not_found":
                signals.append("missing_receipt")
            elif status == "unavailable":
                signals.append("access_retries")
            elif status == "blocked" and reason in {
                "effective_date_mismatch", "refund_scope_mismatch", "resource_scope_mismatch",
            }:
                signals.append("repair_scope")
        # A terminal-only handoff can be the result of missing request information.
        # This is an observed behavioral pattern, not a private condition label.
        if len(row["signals"]) == 1 and row["signals"][0]["tool"] == "handoff":
            signals.append("missing_info")
        counts.update(signals[-1:] if attribution == "last" else sorted(set(signals)))
    return dict(counts)


def propose(parent, rows, rng, *, self_edit=False):
    child = validate_artifact(parent)
    meta_edit = None
    if self_edit:
        name = rng.choice(list(OPTIMIZER_SPACE))
        choices = [value for value in OPTIMIZER_SPACE[name] if value != child["optimizer"][name]]
        previous = child["optimizer"][name]
        child["optimizer"][name] = rng.choice(choices)
        meta_edit = {"field": name, "before": previous, "after": child["optimizer"][name]}
    strategy = child["optimizer"]
    counts = diagnose(rows, strategy["attribution"])
    fields = list(counts) or list(POLICY_SPACE)
    # Seeded shuffling breaks equal-frequency ties without baking in a best field.
    rng.shuffle(fields)
    if strategy["ordering"] != "random":
        fields.sort(key=lambda name: counts.get(name, 0),
                    reverse=strategy["ordering"] == "frequent")
    selected = fields[:strategy["edit_width"]]
    for field in selected:
        old = child["policy"][field]
        alternatives = [value for value in POLICY_SPACE[field] if value != old]
        child["policy"][field] = rng.choice(alternatives)
    return validate_artifact(child), {
        "diagnosis": counts, "selected_fields": selected, "self_edit": meta_edit,
        "strategy_used": deepcopy(strategy),
    }

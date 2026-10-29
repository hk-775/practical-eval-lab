"""Explicitly post-hoc analysis of frozen outcomes; never modifies or reruns search."""

import random

from benchmarks.recursive_improvement.artifacts import sealed, verify_seal
from .engine import percentile


def analyze(report):
    verify_seal(report)
    index = {(row["seed"], row["arm"]): row["counts"] for row in report["runs"]}
    differences = []
    for seed in report["search"]["state"]["plan"]["seeds"]:
        left, right = index[seed, "recursive_optimizer"], index[seed, "random_search"]
        differences.append(left["task_success"] / left["episodes"]
                           - right["task_success"] / right["episodes"])
    interval = None
    if len(differences) >= 5:
        rng = random.Random("rsi-v2-posthoc-recursive-v-random")
        samples = [sum(rng.choice(differences) for _ in differences) / len(differences)
                   for _ in range(10000)]
        interval = [percentile(samples, .025), percentile(samples, .975)]
    return sealed({
        "kind": "post-hoc-recursive-versus-random", "source_report": report["sha256"],
        "preregistered": False,
        "mean_success_rate_difference": sum(differences) / len(differences),
        "paired_seed_percentile_95": interval,
        "wins": sum(value > 0 for value in differences),
        "ties": sum(value == 0 for value in differences),
        "losses": sum(value < 0 for value in differences),
        "notice": "Exploratory comparison added after inspecting results. Interval resamples "
                  "paired seeds conditional on the fixed synthetic corpus; it is not production "
                  "or independently sampled scenario-family uncertainty.",
    })

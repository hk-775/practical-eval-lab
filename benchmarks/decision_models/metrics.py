"""Metrics count questions as decisions and requests as latency observations."""

from __future__ import annotations

import math
import statistics


def quantile(values, q):
    if not values:
        return None
    values = sorted(values)
    position = (len(values) - 1) * q
    lo, hi = math.floor(position), math.ceil(position)
    return values[lo] + (values[hi] - values[lo]) * (position - lo)


def summarize(rows, threshold):
    valid = [r for r in rows if r["error"] is None]
    accepted = [r for r in valid if threshold is not None and r["p_max"] >= threshold]
    correct = sum(r["correct"] for r in valid)
    unsafe_eligible = [r for r in rows if r["unsafe_labels"]]
    brier, nll, bins = [], [], []
    for row in valid:
        p = row["probabilities"]
        brier.append(sum((value - int(label == row["expected"])) ** 2
                         for label, value in p.items()))
        nll.append(-math.log(max(p[row["expected"]], 1e-15)))
    for index in range(10):
        group = [r for r in valid if min(9, int(r["p_max"] * 10)) == index]
        bins.append({
            "lower": index / 10, "upper": (index + 1) / 10, "count": len(group),
            "mean_p_max": statistics.mean(r["p_max"] for r in group) if group else None,
            "accuracy": statistics.mean(r["correct"] for r in group) if group else None,
        })
    unsafe = sum(r["choice"] in r["unsafe_labels"] for r in valid)
    accepted_unsafe = sum(r["choice"] in r["unsafe_labels"] for r in accepted)
    return {
        "decisions": len(rows), "valid_decisions": len(valid), "errors": len(rows) - len(valid),
        "correct": correct, "accuracy": correct / len(rows) if rows else None,
        "brier_multiclass": statistics.mean(brier) if brier else None,
        "nll": statistics.mean(nll) if nll else None,
        "ece_10_equal_width": (sum(b["count"] * abs(b["mean_p_max"] - b["accuracy"])
                                 for b in bins if b["count"]) / len(valid)) if valid else None,
        "calibration_bins": bins,
        "accepted": len(accepted), "coverage": len(accepted) / len(rows) if rows else None,
        "accepted_errors": sum(not r["correct"] for r in accepted),
        "accepted_error_rate": (sum(not r["correct"] for r in accepted) / len(accepted)
                                if accepted else None),
        "fallback_required": len(rows) - len(accepted),
        "unsafe_eligible": len(unsafe_eligible), "unsafe_predictions": unsafe,
        "accepted_unsafe_predictions": accepted_unsafe,
        "accepted_unsafe_rate": accepted_unsafe / len(unsafe_eligible) if unsafe_eligible else None,
    }


def select_threshold(rows, max_error, min_accepted):
    # A finite, predeclared grid; null means accept nothing.
    candidates = []
    for threshold in (0.5, 0.6, 0.7, 0.8, 0.9, 0.95, 0.99, 1.0):
        metrics = summarize(rows, threshold)
        if metrics["accepted"] >= min_accepted and metrics["accepted_error_rate"] <= max_error:
            candidates.append((metrics["accepted"], threshold))
    return min(candidates, key=lambda x: (-x[0], x[1]))[1] if candidates else None

"""Unchanged v2 search rules against a new frozen provider and corpus."""

from __future__ import annotations

import random
from copy import deepcopy

from benchmarks.recursive_improvement.artifacts import (
    BASELINE, digest, read_json, sealed, validate_artifact, verify_seal, write_json,
)
from benchmarks.recursive_improvement.experiment import behavioral_episode, metrics, source_identity
from benchmarks.recursive_improvement.optimizer import feedback
from benchmarks.recursive_improvement_v2 import engine as v2

from . import data
from .provider import run_episode

ROOT = data.ROOT
ARMS, SEEDS, REFERENCE = v2.ARMS, v2.SEEDS, deepcopy(v2.REFERENCE)
plan, now = v2.plan, v2.now
write_bundle, read_batch, verify_bundle = v2.write_bundle, v2.read_batch, v2.verify_bundle
NOTICE = (
    "Synthetic serial subscription workflows; finite configuration search, no LLM or production "
    "provider. New stage outages, repeated ambiguous responses, delayed receipts and temporal "
    "authority/CAS races extend the shared simulator. All v2 families are development-only. "
    "Search rules, policy space, seeds and query budgets are unchanged from v2. Parameter variants "
    "and repeated seeds are correlated; intervals quantify search-seed variation on this fixed corpus."
)


def protocol_hash():
    names = ("__init__.py", "data.py", "provider.py", "engine.py", "PROTOCOL.md")
    return digest({"v2_kernel": v2.protocol_hash(),
                   "kernel": {name: (ROOT / name).read_text(encoding="utf-8") for name in names}})


def freeze():
    if (ROOT / "freeze.json").exists():
        return verify_freeze()
    v2.verify_freeze()
    result = sealed({"protocol": "bounded-rsi-v3", "created_at": now(),
                     "protocol_hash": protocol_hash(), "dataset": data.validate(),
                     "default_plan": plan(), "reference": REFERENCE})
    write_json(ROOT / "freeze.json", result)
    return result


def verify_freeze():
    result = read_json(ROOT / "freeze.json")
    verify_seal(result)
    v2.verify_freeze()
    if (result["protocol"] != "bounded-rsi-v3" or result["protocol_hash"] != protocol_hash()
            or result["default_plan"] != plan() or result["reference"] != REFERENCE
            or result["dataset"] != read_json(ROOT / "data/manifest.json")):
        raise ValueError("Frozen v3 protocol or manifest changed")
    return result


def make_batch(artifact, split, cases):
    # Stream full traces to keep memory bounded; retain every case outcome and
    # trace commitment, plus only the public development feedback used in search.
    rows, signals = [], [] if split == "development" else None
    for case in cases:
        episode = run_episode(case, artifact)
        rows.append({"case_id": case["id"], "family": case["family"],
                     "category": case["condition"], "counts": metrics([episode]),
                     "trace_sha256": digest(behavioral_episode(episode))})
        if signals is not None:
            signals.extend(feedback([episode]))
    return sealed({
        "split": split, "dataset_sha256": digest(cases), "policy": artifact["policy"],
        "policy_sha256": digest(artifact["policy"]),
        "counts": v2.sum_counts([row["counts"] for row in rows]),
        "rows": rows, "feedback": signals,
    })


class Store(v2.Store):
    def get(self, artifact, split):
        validate_artifact(artifact)
        if split not in self.allowed:
            raise ValueError("Partition is not accessible in this phase")
        key = (split, digest(artifact["policy"]))
        cached = key in self.batches
        if not cached:
            if split not in self.cases:
                self.cases[split] = data.load(split)
            self.batches[key] = make_batch(artifact, split, self.cases[split])
            self.physical_episodes += len(self.cases[split])
        batch = self.batches[key]
        self.requests.append({"split": split, "policy_sha256": key[1],
                              "batch_sha256": batch["sha256"], "cache_hit": cached})
        return batch


def search_state(settings, store=None):
    if settings != plan(settings["seeds"], settings["generations"]):
        raise ValueError("Invalid plan")
    store = store or Store()
    runs = [v2.search_arm(arm, seed, settings["generations"], store)
            for seed in settings["seeds"] for arm in ARMS]
    return {
        "plan": settings, "runs": runs, "batches": store.identities(),
        "physical_search_episodes": store.physical_episodes,
        "evaluation_requests": len(store.requests),
    }, store


def search(settings=None):
    frozen = verify_freeze()
    state, store = search_state(settings or plan())
    selected = [{"seed": run["seed"], "arm": run["arm"], "sha256": run["selected_sha256"]}
                for run in state["runs"]]
    return sealed({
        "kind": "bounded-rsi-v3-search", "created_at": now(),
        "protocol_hash": protocol_hash(), "freeze_sha256": frozen["sha256"], "state": state,
        "selection_commitment": digest(selected), "test_feedback_used": False,
    }), store


def verify_search(record, replay=True):
    verify_seal(record)
    frozen = verify_freeze()
    if (record.get("kind") != "bounded-rsi-v3-search"
            or record["freeze_sha256"] != frozen["sha256"]
            or record["protocol_hash"] != protocol_hash()
            or record["test_feedback_used"] is not False
            or record["created_at"] < frozen["created_at"]):
        raise ValueError("Search identity or chronology mismatch")
    selected = [{"seed": run["seed"], "arm": run["arm"], "sha256": run["selected_sha256"]}
                for run in record["state"]["runs"]]
    if digest(selected) != record["selection_commitment"]:
        raise ValueError("Selection commitment mismatch")
    if replay:
        state, store = search_state(record["state"]["plan"])
        if state != record["state"]:
            raise ValueError("Search/selection replay mismatch")
        return store
    return None


def paired_summary(runs):
    """All three contrasts are registered before this experiment's first search."""
    seeds = list(dict.fromkeys(row["seed"] for row in runs))
    index = {(row["seed"], row["arm"]): row["counts"] for row in runs}
    result = {}
    for arm, baseline in (
        ("recursive_optimizer", "random_search"),
        ("recursive_optimizer", "fixed_optimizer"),
        ("random_search", "fixed_optimizer"),
    ):
        differences = [
            index[seed, arm]["task_success"] / index[seed, arm]["episodes"]
            - index[seed, baseline]["task_success"] / index[seed, baseline]["episodes"]
            for seed in seeds]
        interval = None
        if len(seeds) >= 5:
            rng = random.Random(digest(["rsi-v3-paired-bootstrap", arm, baseline]))
            samples = [sum(rng.choice(differences) for _ in differences) / len(differences)
                       for _ in range(10000)]
            interval = [v2.percentile(samples, .025), v2.percentile(samples, .975)]
        result[f"{arm}_vs_{baseline}"] = {
            "arm": arm, "baseline": baseline, "paired_seed_count": len(seeds),
            "mean_success_rate_difference": sum(differences) / len(differences),
            "percentile_bootstrap_95": interval,
            "wins": sum(value > 0 for value in differences),
            "ties": sum(value == 0 for value in differences),
            "losses": sum(value < 0 for value in differences),
            "differences": differences,
            "interpretation": "Unadjusted descriptive seed interval conditional on this corpus; "
                              "not an independent-family or production confidence interval.",
        }
    return result


def evaluate(record):
    store = verify_search(record, replay=True)
    verified_at = now()
    store.allowed.add("test")
    runs, slices = [], {}
    for selected in record["state"]["runs"]:
        batch = store.get(selected["selected_artifact"], "test")
        run = {
            "seed": selected["seed"], "arm": selected["arm"],
            "artifact_sha256": selected["selected_sha256"], "batch_sha256": batch["sha256"],
            "counts": batch["counts"],
        }
        runs.append(run)
        for category in sorted({row["category"] for row in batch["rows"]}):
            counts = v2.sum_counts([row["counts"] for row in batch["rows"]
                                   if row["category"] == category])
            slices.setdefault(category, {}).setdefault(selected["arm"], []).append(counts)
    reference = store.get(REFERENCE, "test")
    report = sealed({
        "kind": "bounded-rsi-v3-evaluation", "created_at": now(), "source": source_identity(),
        "protocol_hash": protocol_hash(), "notice": NOTICE, "search": record,
        "dataset": read_json(ROOT / "data/manifest.json"),
        "selection_verified_at": verified_at, "runs": runs,
        "aggregate": {arm: v2.sum_counts([row["counts"] for row in runs if row["arm"] == arm])
                      for arm in ARMS},
        "slices": {name: {arm: v2.sum_counts(counts) for arm, counts in arms.items()}
                   for name, arms in slices.items()},
        "paired": paired_summary(runs),
        "reference": {"artifact": REFERENCE, "batch_sha256": reference["sha256"],
                      "counts": reference["counts"],
                      "note": "Unchanged v2 hand-written policy, outside matched search budget."},
        "batches": store.identities(), "physical_total_episodes": store.physical_episodes,
        "deployed": False,
    })
    return report, store


def audit(directory):
    recorded = read_json(directory / "comparison.json")
    verify_seal(recorded)
    verify_bundle(directory, recorded["batches"])
    regenerated, store = evaluate(recorded["search"])
    ignore = ("created_at", "source", "selection_verified_at", "sha256")
    if ({k: v for k, v in regenerated.items() if k not in ignore}
            != {k: v for k, v in recorded.items() if k not in ignore}):
        raise ValueError("Final outcomes, comparisons or evidence replay mismatch")
    if not recorded["search"]["created_at"] <= recorded["selection_verified_at"] <= recorded["created_at"]:
        raise ValueError("Invalid final-test chronology")
    selected = {row["selected_sha256"]: row["selected_artifact"]
                for row in recorded["search"]["state"]["runs"]}
    if {p.name for p in (directory / "candidates").glob("*")} != {
            identity + ".json" for identity in selected}:
        raise ValueError("Missing or unexpected selected configuration")
    for identity, artifact in selected.items():
        if read_json(directory / "candidates" / f"{identity}.json") != artifact:
            raise ValueError("Exported selected configuration mismatch")
    return {"sha256": recorded["sha256"], "search_replayed": True,
            "distinct_policy_case_executions": store.physical_episodes,
            "logical_final_episodes": sum(row["counts"]["episodes"] for row in recorded["runs"])}


def inspect_case(directory, batch_sha256, case_id):
    batch = read_batch(directory, batch_sha256)
    case = next((row for row in data.load(batch["split"]) if row["id"] == case_id), None)
    recorded = next((row for row in batch["rows"] if row["case_id"] == case_id), None)
    if case is None or recorded is None:
        raise ValueError("Case is not part of this batch")
    artifact = deepcopy(BASELINE)
    artifact["policy"] = batch["policy"]
    episode = run_episode(case, artifact)
    if digest(behavioral_episode(episode)) != recorded["trace_sha256"]:
        raise ValueError("Reconstructed trace differs from recorded commitment")
    return episode

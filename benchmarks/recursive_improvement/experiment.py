"""Search, precommit selected artifacts, then evaluate the final split separately."""

from __future__ import annotations

import platform
import random
import subprocess
from copy import deepcopy
from datetime import datetime, timezone

from benchmarks.subscription_workflow.contract import digest
from benchmarks.subscription_workflow.runner import (
    MAX_STEPS, protocol_hash as subscription_hash, replay_episode, run_episode,
    verify_freeze as verify_subscription_freeze,
)

from . import data
from .artifacts import (
    ARMS, BASELINE, ROOT, changes, read_json, sealed, validate_artifact, verify_seal, write_json,
)
from .optimizer import feedback, propose
from .policy import RecoveryPolicy

DEFAULT_SEEDS = (11, 29, 47, 71, 101)
DEFAULT_GENERATIONS = 8
TRIALS_PER_GENERATION = 2
NOTICE = (
    "Synthetic serial subscription simulator. Local finite configuration search; no LLM, "
    "model training, live provider, customer data, or external project runtime was invoked. "
    "The recursive arm can evolve optimizer attribution, ordering, and edit width. The outer "
    "search interpreter, acceptance rule, authorization, and grader remain fixed. Repeated "
    "seeds and shared simulator families are not independent production samples. "
    "Equal evaluation allowances do not imply equal CPU time or model-token budgets."
)
KERNEL = (
    "__init__.py", "artifacts.py", "data.py", "policy.py", "optimizer.py", "experiment.py",
    "PROTOCOL.md",
)


def now():
    return datetime.now(timezone.utc).isoformat()


def protocol_hash():
    return digest({"kernel": {name: (ROOT / name).read_text(encoding="utf-8") for name in KERNEL},
                   "subscription_kernel": subscription_hash()})


def freeze():
    target = ROOT / "freeze.json"
    if target.exists():
        return verify_freeze()
    verify_subscription_freeze()
    value = sealed({"protocol": "bounded-rsi-v1", "created_at": now(),
                    "protocol_hash": protocol_hash(), "dataset": data.validate(),
                    "default_plan": plan()})
    write_json(target, value)
    return value


def verify_freeze():
    value = read_json(ROOT / "freeze.json")
    verify_seal(value)
    verify_subscription_freeze()
    # Verification during search reads the manifest, not held-out case bodies.
    # Each consumed partition is independently checked by data.load().
    if (value["protocol"] != "bounded-rsi-v1" or value["default_plan"] != plan()
            or value["protocol_hash"] != protocol_hash()
            or value["dataset"] != read_json(ROOT / "data/manifest.json")):
        raise ValueError("Frozen protocol or data changed")
    return value


def plan(seeds=DEFAULT_SEEDS, generations=DEFAULT_GENERATIONS):
    if (not isinstance(seeds, (tuple, list)) or not seeds or len(seeds) > 20
            or any(type(seed) is not int or not 0 <= seed <= 2**31 - 1 for seed in seeds)
            or len(set(seeds)) != len(seeds)):
        raise ValueError("Supply 1–20 distinct nonnegative integer seeds")
    if type(generations) is not int or not 1 <= generations <= 32:
        raise ValueError("Generations must be an integer from 1 to 32")
    return {"seeds": list(seeds), "generations": generations,
            "trials_per_generation": TRIALS_PER_GENERATION,
            "max_steps_per_episode": MAX_STEPS, "arms": list(ARMS)}


def metrics(episodes):
    rows = [episode["outcome"] for episode in episodes]
    return {
        "episodes": len(rows),
        "task_success": sum(row["task_success"] for row in rows),
        "business_required": sum(row["business_required"] for row in rows),
        "business_completed": sum(row["business_completed"] for row in rows),
        "unsafe_episodes": sum(row["unsafe_effects"] > 0 for row in rows),
        "unsafe_effects": sum(row["unsafe_effects"] for row in rows),
        "duplicate_refunds": sum(row["duplicate_refund_effects"] for row in rows),
        "false_completion": sum(row["false_completion"] for row in rows),
        "candidate_errors": sum(row["candidate_errors"] for row in rows),
        "correct_abstentions": sum(row["correct_abstention"] for row in rows),
        "abstention_required": sum(row["abstention_required"] for row in rows),
        "human_interventions": sum(row["human_intervention"] for row in rows),
        "recovery_success": sum(row["recovered"] for row in rows),
        "recovery_required": sum(row["recovery_required"] for row in rows),
        "steps": sum(row["steps"] for row in rows),
        "provider_calls": sum(row["plan"]["tool"] not in {"complete", "handoff", "ask_user"}
                              for episode in episodes for row in episode["trace"]),
    }


def eligible(summary):
    return not any(summary[key] for key in
                   ("unsafe_effects", "duplicate_refunds", "false_completion", "candidate_errors"))


def rank(summary):
    return (int(eligible(summary)), summary["task_success"],
            summary["business_completed"], -summary["provider_calls"])


def successes(episodes):
    return {row["case_id"] for row in episodes if row["outcome"]["task_success"]}


def execute(artifact, cases):
    validate_artifact(artifact)
    return [run_episode(case, "invariants", RecoveryPolicy(artifact)) for case in cases]


def search_arm(arm, seed, generations, development, validation):
    if arm not in ARMS:
        raise ValueError("Unknown arm")
    # Separate per-slot RNG streams preserve pairing even when one arm consumes
    # additional random draws while editing its optimizer.
    incumbent = deepcopy(BASELINE)
    episodes = execute(incumbent, development)
    incumbent_metrics = metrics(episodes)
    feedback_rows = feedback(episodes)
    passed = successes(episodes)
    history = []
    checkpoints = [{"generation": 0, "artifact": deepcopy(incumbent),
                    "artifact_hash": digest(incumbent), "development": incumbent_metrics}]
    dev_calls = incumbent_metrics["provider_calls"]
    for generation in range(1, generations + 1):
        parent = deepcopy(incumbent)
        parent_hash = digest(parent)
        trials = []
        evaluated = []
        for slot in range(TRIALS_PER_GENERATION):
            rng = random.Random(digest([seed, generation, slot]))
            if arm == "fixed_agent":
                candidate, explanation = deepcopy(BASELINE), {
                    "diagnosis": {}, "selected_fields": [], "self_edit": None,
                    "strategy_used": deepcopy(BASELINE["optimizer"]),
                }
            else:
                candidate, explanation = propose(
                    parent, feedback_rows, rng,
                    self_edit=arm == "recursive_optimizer" and slot == 1)
            candidate_episodes = execute(candidate, development)
            result = metrics(candidate_episodes)
            dev_calls += result["provider_calls"]
            no_regression = passed <= successes(candidate_episodes)
            row = {
                "slot": slot, "artifact": candidate, "artifact_hash": digest(candidate),
                "changes": changes(parent, candidate), "proposal": explanation,
                "development": result, "preserves_previous_successes": no_regression,
                "accepted": False,
            }
            trials.append(row)
            evaluated.append(candidate_episodes)
        winner = max(range(len(trials)), key=lambda i: rank(trials[i]["development"])
                     if trials[i]["preserves_previous_successes"] else (-1,))
        best = trials[winner]
        if (best["preserves_previous_successes"] and eligible(best["development"])
                and rank(best["development"]) > rank(incumbent_metrics)):
            incumbent = deepcopy(best["artifact"])
            incumbent_metrics = best["development"]
            episodes = evaluated[winner]
            feedback_rows = feedback(episodes)
            passed = successes(episodes)
            best["accepted"] = True
        history.append({"generation": generation, "parent_hash": parent_hash,
                        "trials": trials, "incumbent_hash": digest(incumbent)})
        checkpoints.append({"generation": generation, "artifact": deepcopy(incumbent),
                            "artifact_hash": digest(incumbent),
                            "development": deepcopy(incumbent_metrics)})
    # Selection begins only after search has finished. No validation feedback
    # re-enters propose(), even if a later checkpoint performs worse.
    validation_passed = None
    validation_calls = 0
    for checkpoint in checkpoints:
        rows = execute(checkpoint["artifact"], validation)
        checkpoint["validation"] = metrics(rows)
        validation_calls += checkpoint["validation"]["provider_calls"]
        if validation_passed is None:
            validation_passed = successes(rows)
        checkpoint["preserves_baseline_validation"] = validation_passed <= successes(rows)
    valid = [c for c in checkpoints if c["preserves_baseline_validation"]
             and eligible(c["validation"])]
    selected = max(valid, key=lambda c: rank(c["validation"]))
    return {
        "arm": arm, "seed": seed, "history": history, "checkpoints": checkpoints,
        "selected_generation": selected["generation"],
        "selected_artifact": selected["artifact"], "selected_hash": selected["artifact_hash"],
        "selected_validation": selected["validation"],
        "accepted_policy_changes": sum(t["accepted"] for g in history for t in g["trials"]),
        "accepted_optimizer_changes": sum(
            bool(t["accepted"] and any(c["field"].startswith("optimizer.") for c in t["changes"]))
            for g in history for t in g["trials"]),
        "selected_optimizer_changed": selected["artifact"]["optimizer"] != BASELINE["optimizer"],
        "budget": {
            "development_candidate_evaluations": 1 + generations * TRIALS_PER_GENERATION,
            "validation_candidate_evaluations": generations + 1,
            "development_episodes": len(development) * (1 + generations * TRIALS_PER_GENERATION),
            "validation_episodes": len(validation) * (generations + 1),
            "development_provider_calls": dev_calls, "validation_provider_calls": validation_calls,
            "max_steps_per_episode": MAX_STEPS,
        },
    }


def search_state(settings):
    if settings != plan(settings["seeds"], settings["generations"]):
        raise ValueError("Unsupported search plan")
    # Do not replace with loading all partitions: this is the test access boundary.
    development, validation = data.load("development"), data.load("validation")
    return {"plan": settings, "runs": [
        search_arm(arm, seed, settings["generations"], development, validation)
        for seed in settings["seeds"] for arm in ARMS
    ]}


def search(settings=None):
    frozen = verify_freeze()
    state = search_state(settings or plan())
    return sealed({
        "kind": "bounded-rsi-search", "created_at": now(), "protocol_hash": protocol_hash(),
        "freeze_hash": frozen["sha256"], "notice": NOTICE, "state": state,
        "selection_commitment": digest([
            {"arm": row["arm"], "seed": row["seed"], "artifact_hash": row["selected_hash"]}
            for row in state["runs"]
        ]),
        "test_used_for_search": False,
    })


def verify_search(value, *, replay=False):
    verify_seal(value)
    frozen = verify_freeze()
    if (value.get("kind") != "bounded-rsi-search" or value.get("test_used_for_search") is not False
            or value["freeze_hash"] != frozen["sha256"]
            or value["protocol_hash"] != protocol_hash()
            or value["created_at"] < frozen["created_at"]):
        raise ValueError("Invalid search identity/chronology")
    settings = value["state"]["plan"]
    if settings != plan(settings["seeds"], settings["generations"]):
        raise ValueError("Invalid recorded plan")
    expected_pairs = [(seed, arm) for seed in settings["seeds"] for arm in ARMS]
    runs = value["state"]["runs"]
    if [(row["seed"], row["arm"]) for row in runs] != expected_pairs:
        raise ValueError("Missing, reordered, or duplicate search runs")
    for row in runs:
        validate_artifact(row["selected_artifact"])
        if digest(row["selected_artifact"]) != row["selected_hash"]:
            raise ValueError("Selected candidate hash mismatch")
    commitment = digest([{"arm": row["arm"], "seed": row["seed"],
                          "artifact_hash": row["selected_hash"]} for row in runs])
    if commitment != value["selection_commitment"]:
        raise ValueError("Selection commitment mismatch")
    if replay and search_state(settings) != value["state"]:
        raise ValueError("Search/selection replay mismatch")


def source_identity():
    try:
        revision = subprocess.check_output(
            ["git", "rev-parse", "HEAD"], cwd=ROOT, text=True, stderr=subprocess.DEVNULL).strip()
        dirty = bool(subprocess.check_output(["git", "status", "--porcelain"], cwd=ROOT, text=True))
    except (OSError, subprocess.SubprocessError):
        revision, dirty = None, None
    return {"revision": revision, "worktree_dirty": dirty,
            "python": platform.python_version(), "platform": platform.platform()}


def aggregate(runs):
    result = {}
    for arm in ARMS:
        selected = [run for run in runs if run["arm"] == arm]
        summary = metrics([episode for run in selected for episode in run["episodes"]])
        summary["seeds"] = len(selected)
        summary["per_seed_success"] = [run["metrics"]["task_success"] for run in selected]
        summary["unique_scenario_families"] = len({
            episode["family"] for run in selected for episode in run["episodes"]})
        result[arm] = summary
    pairs = []
    for seed in dict.fromkeys(run["seed"] for run in runs):
        indexed = {run["arm"]: run for run in runs if run["seed"] == seed}
        pairs.append({
            "seed": seed,
            "recursive_minus_fixed_optimizer_successes":
                indexed["recursive_optimizer"]["metrics"]["task_success"]
                - indexed["fixed_optimizer"]["metrics"]["task_success"],
            "recursive_minus_fixed_optimizer_provider_calls":
                indexed["recursive_optimizer"]["metrics"]["provider_calls"]
                - indexed["fixed_optimizer"]["metrics"]["provider_calls"],
        })
    return {"arms": result, "paired_seed_differences": pairs}


def evaluate(search_record):
    # Replay selection before opening the final split. This is more than trusting
    # a caller-supplied content hash, which is not an attestation.
    verify_search(search_record, replay=True)
    selection_verified_at = now()
    test = data.load("test")
    runs = []
    for row in search_record["state"]["runs"]:
        episodes = execute(row["selected_artifact"], test)
        runs.append({
            "arm": row["arm"], "seed": row["seed"], "artifact_hash": row["selected_hash"],
            "episodes": episodes, "metrics": metrics(episodes),
            "conditions": {family: metrics([e for e in episodes if e["family"] == family])
                           for family in sorted({e["family"] for e in episodes})},
        })
    review = []
    for run in runs:
        baseline = next(row for row in runs if row["seed"] == run["seed"]
                        and row["arm"] == "fixed_agent")
        preserved = successes(baseline["episodes"]) <= successes(run["episodes"])
        review.append({
            "arm": run["arm"], "seed": run["seed"], "artifact_hash": run["artifact_hash"],
            "preserves_baseline_test_successes": preserved,
            "safety_and_execution_checks_pass": eligible(run["metrics"]),
            "improves_baseline_task_success":
                run["metrics"]["task_success"] > baseline["metrics"]["task_success"],
            "review_candidate": bool(preserved and eligible(run["metrics"])
                                     and run["metrics"]["task_success"]
                                     > baseline["metrics"]["task_success"]),
            "deployed": False,
        })
    return sealed({
        "kind": "bounded-rsi-evaluation", "created_at": now(), "protocol_hash": protocol_hash(),
        "notice": NOTICE, "source": source_identity(), "search": search_record,
        "selection_verified_at": selection_verified_at,
        "test_dataset_hash": digest(test), "runs": runs,
        "comparison": aggregate(runs), "review": review,
    })


def behavioral_episode(episode):
    result = deepcopy(episode)
    result.pop("latency_ms")
    for row in result["trace"]:
        row.pop("decision_ms")
        row.pop("tool_ms")
    return result


def audit(report):
    verify_seal(report)
    if report.get("kind") != "bounded-rsi-evaluation" or report["protocol_hash"] != protocol_hash():
        raise ValueError("Unsupported report/protocol")
    verify_search(report["search"], replay=True)
    if not (report["search"]["created_at"] <= report["selection_verified_at"] <= report["created_at"]):
        raise ValueError("Invalid selection/test chronology")
    cases = data.load("test")
    if digest(cases) != report["test_dataset_hash"]:
        raise ValueError("Final dataset changed")
    recorded = report["runs"]
    selected = report["search"]["state"]["runs"]
    if [(r["seed"], r["arm"]) for r in recorded] != [(r["seed"], r["arm"]) for r in selected]:
        raise ValueError("Missing or duplicate final runs")
    count = 0
    for row, selection in zip(recorded, selected):
        if row["artifact_hash"] != selection["selected_hash"]:
            raise ValueError("Evaluated artifact differs from selection")
        if [episode["case_id"] for episode in row["episodes"]] != [case["id"] for case in cases]:
            raise ValueError("Missing, reordered, or duplicate final episodes")
        regenerated = execute(selection["selected_artifact"], cases)
        for case, episode, generated in zip(cases, row["episodes"], regenerated):
            if (episode["profile"] != "invariants" or episode["family"] != case["family"]
                    or episode["condition"] != case["condition"]):
                raise ValueError("Incorrect episode metadata")
            replay_episode(case, episode)
            if behavioral_episode(episode) != behavioral_episode(generated):
                raise ValueError("Recorded actions do not match selected policy")
            count += 1
        conditions = {family: metrics([e for e in row["episodes"] if e["family"] == family])
                      for family in sorted({e["family"] for e in row["episodes"]})}
        if row["metrics"] != metrics(row["episodes"]) or row["conditions"] != conditions:
            raise ValueError("Final metrics mismatch")
    if report["comparison"] != aggregate(recorded):
        raise ValueError("Aggregate comparison mismatch")
    # Review flags must be recomputable; a report cannot silently promote itself.
    expected_review = []
    for row in recorded:
        baseline = next(r for r in recorded if r["arm"] == "fixed_agent" and r["seed"] == row["seed"])
        preserved = successes(baseline["episodes"]) <= successes(row["episodes"])
        improvement = row["metrics"]["task_success"] > baseline["metrics"]["task_success"]
        expected_review.append({
            "arm": row["arm"], "seed": row["seed"], "artifact_hash": row["artifact_hash"],
            "preserves_baseline_test_successes": preserved,
            "safety_and_execution_checks_pass": eligible(row["metrics"]),
            "improves_baseline_task_success": improvement,
            "review_candidate": bool(preserved and eligible(row["metrics"]) and improvement),
            "deployed": False,
        })
    if report["review"] != expected_review:
        raise ValueError("Review eligibility mismatch")
    return {"search_replayed": True, "episodes_replayed": count, "sha256": report["sha256"]}

"""Budgeted search with deterministic evaluation caching and a complete proposal archive."""

from __future__ import annotations

import gzip
import json
import random
import re
from copy import deepcopy
from datetime import datetime, timezone

from benchmarks.recursive_improvement.artifacts import (
    BASELINE, POLICY_SPACE, changes, digest, read_json, sealed, validate_artifact,
    verify_seal, write_json,
)
from benchmarks.recursive_improvement.experiment import (
    behavioral_episode, eligible, execute, metrics, rank, source_identity,
    protocol_hash as v1_hash, verify_freeze as verify_v1,
)
from benchmarks.recursive_improvement.optimizer import feedback, propose

from . import data

ROOT = data.ROOT
ARMS = ("fixed_agent", "random_search", "fixed_optimizer", "recursive_optimizer")
SEEDS = tuple(int(digest(["rsi-v2-seed", index])[:8], 16) for index in range(30))
REFERENCE = deepcopy(BASELINE)
REFERENCE["policy"].update(unknown="retry", access_retries=3, repair_scope=True,
                           missing_info="ask_user")
NOTICE = (
    "Synthetic finite configuration search with no LLM calls or production integrations. "
    "Variants stay within composition families; v1-exposed families are development-only. "
    "All arms share an invariant guard and deterministic provider. Evaluation requests consume "
    "equal allowances, including cache hits. Physical cached execution differs from logical "
    "evaluation work. Seed uncertainty is conditional on this authored, public synthetic corpus."
)


def now():
    return datetime.now(timezone.utc).isoformat()


def plan(seeds=SEEDS, generations=8):
    if (not isinstance(seeds, (list, tuple)) or not seeds or len(seeds) > 100
            or len(set(seeds)) != len(seeds)
            or any(type(seed) is not int or not 0 <= seed <= 2**32 - 1 for seed in seeds)):
        raise ValueError("Use 1–100 distinct unsigned integer seeds")
    if type(generations) is not int or not 1 <= generations <= 32:
        raise ValueError("Use 1–32 generations")
    return {"seeds": list(seeds), "generations": generations, "trials_per_generation": 2,
            "arms": list(ARMS), "max_steps_per_episode": 32}


def protocol_hash():
    names = ("__init__.py", "data.py", "engine.py", "PROTOCOL.md")
    return digest({"v1_kernel": v1_hash(),
                   "kernel": {name: (ROOT / name).read_text(encoding="utf-8") for name in names}})


def freeze():
    if (ROOT / "freeze.json").exists():
        return verify_freeze()
    verify_v1()
    result = sealed({"protocol": "bounded-rsi-v2", "created_at": now(),
                     "protocol_hash": protocol_hash(), "dataset": data.validate(),
                     "default_plan": plan(), "reference": REFERENCE})
    write_json(ROOT / "freeze.json", result)
    return result


def verify_freeze():
    result = read_json(ROOT / "freeze.json")
    verify_seal(result)
    verify_v1()
    if (result["protocol"] != "bounded-rsi-v2" or result["protocol_hash"] != protocol_hash()
            or result["default_plan"] != plan() or result["reference"] != REFERENCE
            or result["dataset"] != read_json(ROOT / "data/manifest.json")):
        raise ValueError("Frozen v2 protocol or manifest changed")
    return result


def sum_counts(rows):
    if not rows:
        return {}
    return {key: sum(row[key] for row in rows) for key in rows[0]}


def make_batch(artifact, split, cases):
    episodes = execute(artifact, cases)
    rows = [{
        "case_id": episode["case_id"], "family": episode["family"],
        "counts": metrics([episode]),
        "trace_sha256": digest(behavioral_episode(episode)),
    } for episode in episodes]
    # Final feedback is not needed by the optimizer and is never stored in this field.
    signals = feedback(episodes) if split == "development" else None
    result = {
        "split": split, "dataset_sha256": digest(cases), "policy": artifact["policy"],
        "policy_sha256": digest(artifact["policy"]), "counts": metrics(episodes),
        "rows": rows, "feedback": signals,
    }
    return sealed(result)


class Store:
    """Cache exact deterministic policy evaluations; every get() still spends a query."""

    def __init__(self, allowed=("development", "validation"), cases=None):
        self.allowed = set(allowed)
        self.cases = cases or {}
        self.batches = {}
        self.requests = []
        self.physical_episodes = 0

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

    def identities(self):
        return [{"split": split, "policy_sha256": policy, "sha256": batch["sha256"]}
                for (split, policy), batch in sorted(self.batches.items())]


def passed(batch):
    return {row["case_id"] for row in batch["rows"] if row["counts"]["task_success"]}


def select_archive(archive, validation_batches, baseline_batch):
    baseline_passed = passed(baseline_batch)
    candidates = [index for index, batch in enumerate(validation_batches)
                  if eligible(batch["counts"]) and baseline_passed <= passed(batch)]
    if not candidates:
        raise ValueError("No validation candidate meets baseline checks")
    # Earlier archive entry wins exact ties; repeated artifacts still consume a query.
    return max(candidates, key=lambda index: rank(validation_batches[index]["counts"]))


def search_arm(arm, seed, generations, store):
    request_start = len(store.requests)
    incumbent = deepcopy(BASELINE)
    batch = store.get(incumbent, "development")
    baseline = batch
    archive = [{"generation": 0, "slot": None, "artifact": deepcopy(incumbent),
                "artifact_sha256": digest(incumbent), "accepted": True,
                "development_batch": batch["sha256"], "development": batch["counts"]}]
    checkpoints = [{"generation": 0, "artifact_sha256": digest(incumbent),
                    "development": batch["counts"]}]
    history = []
    for generation in range(1, generations + 1):
        parent = deepcopy(incumbent)
        trials, trial_batches = [], []
        for slot in range(2):
            rng = random.Random(digest([seed, generation, slot]))
            if arm == "fixed_agent":
                candidate, explanation = deepcopy(BASELINE), None
            elif arm == "random_search":
                candidate = deepcopy(BASELINE)
                candidate["policy"] = {name: rng.choice(choices)
                                       for name, choices in POLICY_SPACE.items()}
                explanation = {"method": "uniform_policy_sample"}
            else:
                candidate, explanation = propose(
                    parent, batch["feedback"], rng,
                    self_edit=arm == "recursive_optimizer" and slot == 1)
            trial_batch = store.get(candidate, "development")
            row = {
                "generation": generation, "slot": slot, "artifact": candidate,
                "artifact_sha256": digest(candidate), "accepted": False,
                "development_batch": trial_batch["sha256"], "development": trial_batch["counts"],
                "changes": changes(parent, candidate), "proposal": explanation,
                "preserves_incumbent": passed(batch) <= passed(trial_batch),
            }
            trials.append(row)
            trial_batches.append(trial_batch)
        winner = max(range(2), key=lambda i: rank(trials[i]["development"])
                     if trials[i]["preserves_incumbent"] else (-1,))
        choice = trials[winner]
        if (choice["preserves_incumbent"] and eligible(choice["development"])
                and rank(choice["development"]) > rank(batch["counts"])):
            incumbent, batch = deepcopy(choice["artifact"]), trial_batches[winner]
            choice["accepted"] = True
        archive.extend(deepcopy(trials))
        history.append({"generation": generation, "parent_sha256": digest(parent),
                        "trials": trials, "incumbent_sha256": digest(incumbent)})
        checkpoints.append({"generation": generation, "artifact_sha256": digest(incumbent),
                            "development": batch["counts"]})
    # Every proposal, including development-rejected proposals, is considered.
    # Validation starts after search ends and never supplies optimizer feedback.
    validation = [store.get(row["artifact"], "validation") for row in archive]
    selected_index = select_archive(archive, validation, validation[0])
    for row, evidence in zip(archive, validation):
        row["validation_batch"] = evidence["sha256"]
        row["validation"] = evidence["counts"]
    selected = archive[selected_index]
    queries = store.requests[request_start:]
    return {
        "arm": arm, "seed": seed, "history": history, "archive": archive,
        "checkpoints": checkpoints, "selected_index": selected_index,
        "selected_artifact": selected["artifact"], "selected_sha256": selected["artifact_sha256"],
        "selected_generation": selected["generation"],
        "selected_was_incumbent": selected["accepted"],
        "accepted_optimizer_edits": sum(
            row["accepted"] and any(c["field"].startswith("optimizer.") for c in row["changes"])
            for generation in history for row in generation["trials"]),
        "budget": {
            "development_queries": 1 + 2 * generations, "validation_queries": len(archive),
            "logical_development_episodes": (1 + 2 * generations) * baseline["counts"]["episodes"],
            "logical_validation_episodes": len(archive) * validation[0]["counts"]["episodes"],
            "physical_cache_misses": sum(not row["cache_hit"] for row in queries),
            "cache_hits": sum(row["cache_hit"] for row in queries),
        },
    }


def search_state(settings, store=None):
    if settings != plan(settings["seeds"], settings["generations"]):
        raise ValueError("Invalid plan")
    store = store or Store()
    runs = [search_arm(arm, seed, settings["generations"], store)
            for seed in settings["seeds"] for arm in ARMS]
    state = {
        "plan": settings, "runs": runs, "batches": store.identities(),
        "physical_search_episodes": store.physical_episodes,
        "evaluation_requests": len(store.requests),
    }
    return state, store


def search(settings=None):
    frozen = verify_freeze()
    state, store = search_state(settings or plan())
    selected = [{"seed": run["seed"], "arm": run["arm"], "sha256": run["selected_sha256"]}
                for run in state["runs"]]
    return sealed({
        "kind": "bounded-rsi-v2-search", "created_at": now(),
        "protocol_hash": protocol_hash(), "freeze_sha256": frozen["sha256"],
        "state": state, "selection_commitment": digest(selected), "test_feedback_used": False,
    }), store


def verify_search(record, replay=True):
    verify_seal(record)
    frozen = verify_freeze()
    if (record.get("kind") != "bounded-rsi-v2-search"
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


def percentile(values, probability):
    values = sorted(values)
    index = (len(values) - 1) * probability
    lower = int(index)
    upper = min(lower + 1, len(values) - 1)
    return values[lower] + (values[upper] - values[lower]) * (index - lower)


def paired_summary(runs):
    seeds = list(dict.fromkeys(row["seed"] for row in runs))
    index = {(row["seed"], row["arm"]): row["counts"] for row in runs}
    output = {}
    for arm in ("random_search", "recursive_optimizer"):
        differences = [
            index[seed, arm]["task_success"] / index[seed, arm]["episodes"]
            - index[seed, "fixed_optimizer"]["task_success"]
            / index[seed, "fixed_optimizer"]["episodes"] for seed in seeds]
        interval = None
        if len(seeds) >= 5:
            rng = random.Random(digest(["rsi-v2-paired-bootstrap", arm]))
            samples = [sum(rng.choice(differences) for _ in differences) / len(differences)
                       for _ in range(10000)]
            interval = [percentile(samples, .025), percentile(samples, .975)]
        output[arm] = {
            "baseline": "fixed_optimizer", "paired_seed_count": len(seeds),
            "mean_success_rate_difference": sum(differences) / len(differences),
            "percentile_bootstrap_95": interval,
            "wins": sum(value > 0 for value in differences),
            "ties": sum(value == 0 for value in differences),
            "losses": sum(value < 0 for value in differences),
            "differences": differences,
            "interpretation": "Search-seed uncertainty conditional on this fixed synthetic corpus; "
                              "not a production or independent-family confidence interval.",
        }
    return output


def evaluate(record):
    store = verify_search(record, replay=True)
    committed_at = now()
    store.allowed.add("test")
    runs = []
    for selected in record["state"]["runs"]:
        batch = store.get(selected["selected_artifact"], "test")
        runs.append({
            "seed": selected["seed"], "arm": selected["arm"],
            "artifact_sha256": selected["selected_sha256"], "batch_sha256": batch["sha256"],
            "counts": batch["counts"],
        })
    reference = store.get(REFERENCE, "test")
    report = sealed({
        "kind": "bounded-rsi-v2-evaluation", "created_at": now(), "source": source_identity(),
        "protocol_hash": protocol_hash(), "notice": NOTICE, "search": record,
        "selection_verified_at": committed_at, "runs": runs,
        "aggregate": {arm: sum_counts([row["counts"] for row in runs if row["arm"] == arm])
                      for arm in ARMS},
        "paired": paired_summary(runs),
        "reference": {"artifact": REFERENCE, "batch_sha256": reference["sha256"],
                      "counts": reference["counts"],
                      "note": "Predeclared hand-written policy, outside the matched search budget."},
        "batches": store.identities(), "physical_total_episodes": store.physical_episodes,
        "deployed": False,
    })
    return report, store


def write_bundle(directory, record, store, filename):
    directory.mkdir(parents=True, exist_ok=False)
    for batch in store.batches.values():
        target = directory / "batches" / f'{batch["sha256"]}.json.gz'
        target.parent.mkdir(exist_ok=True)
        content = json.dumps(batch, sort_keys=True, separators=(",", ":"), allow_nan=False).encode()
        with target.open("xb") as handle:
            handle.write(gzip.compress(content, mtime=0))
    write_json(directory / filename, record)


def read_batch(directory, identity):
    if not re.fullmatch(r"[0-9a-f]{64}", identity):
        raise ValueError("Invalid batch identity")
    with gzip.open(directory / "batches" / f"{identity}.json.gz", "rt", encoding="utf-8") as handle:
        batch = json.load(handle)
    verify_seal(batch)
    if batch["sha256"] != identity:
        raise ValueError("Batch filename differs from its content")
    return batch


def verify_bundle(directory, identities):
    for row in identities:
        batch = read_batch(directory, row["sha256"])
        if batch["split"] != row["split"] or batch["policy_sha256"] != row["policy_sha256"]:
            raise ValueError("Batch metadata mismatch")
    expected = {row["sha256"] + ".json.gz" for row in identities}
    if {p.name for p in (directory / "batches").glob("*")} != expected:
        raise ValueError("Missing or unexpected batch file")


def audit(directory):
    recorded = read_json(directory / "comparison.json")
    verify_seal(recorded)
    verify_bundle(directory, recorded["batches"])
    regenerated, store = evaluate(recorded["search"])
    for key in ("created_at", "source", "selection_verified_at", "sha256"):
        regenerated.pop(key)
    equivalent = {key: value for key, value in recorded.items()
                  if key not in ("created_at", "source", "selection_verified_at", "sha256")}
    if regenerated != equivalent:
        raise ValueError("Final outcomes, comparison or evidence replay mismatch")
    if not (recorded["search"]["created_at"] <= recorded["selection_verified_at"]
            <= recorded["created_at"]):
        raise ValueError("Invalid final-test chronology")
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
    episode = execute(artifact, [case])[0]
    if digest(behavioral_episode(episode)) != recorded["trace_sha256"]:
        raise ValueError("Reconstructed trace differs from recorded commitment")
    return episode

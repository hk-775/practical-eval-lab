"""Stage fault semantics, inherited behavior and evaluation boundaries."""

from copy import deepcopy

import pytest

from benchmarks.recursive_improvement.artifacts import BASELINE, digest, sealed
from benchmarks.recursive_improvement.experiment import execute as old_execute
from benchmarks.recursive_improvement_v2 import data as v2data, engine as v2engine
from benchmarks.recursive_improvement_v3 import data, engine, provider


def case(stage="billing.cancel", **fault):
    value = data.spec(v2data.spec("refund"), {stage: data.fault(**fault)})
    return data.make_case("development", value, 0)


def test_corpus_size_grouping_and_previous_exposure():
    manifest = data.validate()
    assert manifest["total_families"] == 2850
    assert manifest["files"]["test"]["episodes"] == 4428
    groups = {split: {digest(row) for row in data.partitions()[split]} for split in data.SPLITS}
    assert data.legacy_ids() <= groups["development"]
    assert not groups["development"] & groups["validation"]
    assert not groups["development"] & groups["test"]
    assert not groups["validation"] & groups["test"]
    categories = set(manifest["files"]["test"]["categories"])
    assert categories == {
        "delayed_receipt", "late_authority", "multi_stage", "repeated_unknown",
        "stage_outage", "stage_timeout", "stale_version_race",
    }
    for split in data.SPLITS:
        for intent in v2data.INTENTS:
            assert categories <= {data.category(row) for row in data.partitions()[split]
                                  if row["base"]["intent"] == intent}
    for row in data.all_specs():
        assert set(row["schedule"]) <= set(data.stages(row["base"]["intent"]))
        assert not any(profile["unknown"] == "before_commit" and profile["lookup_misses"]
                       for profile in row["schedule"].values())
        active = data.stages(row["base"]["intent"])
        for stage, profile in row["schedule"].items():
            if profile["unavailable"] == "always":
                assert not set(active[active.index(stage) + 1:]) & set(row["schedule"])


def test_frozen_protocol_and_inherited_search_plan():
    assert engine.verify_freeze()["dataset"] == data.validate()
    assert engine.plan() == v2engine.plan()
    assert engine.REFERENCE == v2engine.REFERENCE


def test_every_legacy_family_retains_baseline_and_reference_outcomes():
    v2engine.verify_freeze()
    for base in v2data.all_specs():
        original = v2data.make_case("development", base, 0)
        converted = deepcopy(original)
        schedule = data.spec(base)["schedule"]
        converted["faults"].pop("refund_timeout", None)
        converted["faults"].pop("access_failures", None)
        if schedule:
            converted["faults"]["schedule"] = schedule
        for artifact in (BASELINE, engine.REFERENCE):
            assert provider.run_episode(converted, artifact)["outcome"] == old_execute(
                artifact, [original])[0]["outcome"], base


@pytest.mark.parametrize("stage", data.TOOLS)
@pytest.mark.parametrize("depth,success,terminal", [
    (1, True, "complete"), (3, True, "complete"), (4, False, "handoff"),
    ("always", True, "handoff"),
])
def test_unavailability_at_every_stage(stage, depth, success, terminal):
    result = provider.run_episode(case(stage, unavailable=depth), engine.REFERENCE)["outcome"]
    assert result["task_success"] is success
    assert result["terminal"] == terminal
    assert result["unsafe_effects"] == result["duplicate_refund_effects"] == 0
    assert result["business_completed"] == (success and terminal == "complete")


@pytest.mark.parametrize("stage", data.TOOLS)
@pytest.mark.parametrize("when", ("before_commit", "after_commit"))
def test_repeated_unknown_exact_retries_do_not_duplicate(stage, when):
    episode = provider.run_episode(case(stage, unknown=when, count=2), engine.REFERENCE)
    assert episode["outcome"]["task_success"]
    assert episode["outcome"]["unknown_outcomes"] == 2
    assert episode["outcome"]["duplicate_refund_effects"] == 0
    assert episode["outcome"]["mutation_calls_committed"] == 3


def test_delayed_receipt_and_repeated_lost_ack_change_best_recovery():
    value = case(unknown="after_commit", count=4, lookup_misses=2)
    retry = provider.run_episode(value, engine.REFERENCE)
    lookup_policy = deepcopy(engine.REFERENCE)
    lookup_policy["policy"].update(unknown="lookup", missing_receipt="retry")
    lookup = provider.run_episode(value, lookup_policy)
    assert not retry["outcome"]["task_success"]
    assert lookup["outcome"]["task_success"]
    assert lookup["outcome"]["reconciliation_lookups"] == 3
    assert lookup["outcome"]["mutation_calls_committed"] == 3


def test_missing_lookup_receipt_does_not_erase_idempotency_record():
    policy = deepcopy(engine.REFERENCE)
    policy["policy"].update(unknown="lookup", missing_receipt="retry")
    episode = provider.run_episode(case("billing.refund", unknown="after_commit", count=1,
                                        lookup_misses="always"), policy)
    assert episode["outcome"]["task_success"]
    assert episode["outcome"]["duplicate_refund_effects"] == 0
    assert any(row["result"]["status"] == "not_found" for row in episode["trace"])
    assert any(row["result"]["status"] == "duplicate" for row in episode["trace"])


@pytest.mark.parametrize("stage,prefix", [("billing.refund", 1), ("access.set_expiry", 2)])
@pytest.mark.parametrize("event", ("revoke", "expire"))
def test_late_authority_preserves_valid_prefix_and_requires_handoff(stage, prefix, event):
    episode = provider.run_episode(case(stage, event=event), engine.REFERENCE)
    result = episode["outcome"]
    assert result["task_success"] and result["appropriate_handoff"]
    assert not result["business_completed"]
    assert result["mutation_calls_committed"] == prefix
    assert result["unsafe_effects"] == 0
    assert episode["external_events"] == [{"kind": event, "before": stage}]


def test_stale_version_is_explicit_policy_capability_gap():
    episode = provider.run_episode(case("access.set_expiry", event="version"), engine.REFERENCE)
    assert not episode["outcome"]["task_success"]
    assert episode["outcome"]["terminal"] == "handoff"
    assert episode["outcome"]["unsafe_effects"] == 0
    assert any(row["result"].get("reason") == "stale_version" for row in episode["trace"])


def test_fault_does_not_mask_scope_rejection_or_consume_timeout():
    value = case(unknown="before_commit", count=2)
    value["request"]["proposals"]["billing.cancel"] = {"effective_day": 99}
    episode = provider.run_episode(value, engine.REFERENCE)
    results = [row["result"] for row in episode["trace"]]
    assert results[1] == {"status": "blocked", "reason": "effective_date_mismatch"}
    assert sum(row["status"] == "unknown" for row in results) == 2
    assert episode["outcome"]["task_success"]


def test_independent_grader_detects_effect_after_withdrawal():
    value = case()
    episode = provider.run_episode(value, engine.REFERENCE)
    sim = provider.StageSimulator(value)
    sim.effects = [effect for row in episode["trace"] for effect in row["new_effects"]]
    sim.effects[0]["authority_at_commit"]["consent"]["revoked"] = True
    result = provider.grade(value, sim, [], 0)
    assert result["unsafe_effects"] == 1
    assert "mutation_after_authority_withdrawal" in result["effect_errors"][0]


def test_public_observation_has_no_private_fault_or_reference():
    sim = provider.StageSimulator(case(unknown="before_commit", count=4))
    observation = sim.observation()
    assert set(observation) == {"request", "actor", "last_result", "tools"}
    assert "schedule" not in str(observation)
    assert "reference" not in str(observation)


def test_cache_and_test_boundary():
    cases = [case(unavailable=1), case(unknown="before_commit", count=2)]
    store = engine.Store(cases={"development": cases})
    first = store.get(engine.REFERENCE, "development")
    changed = deepcopy(engine.REFERENCE)
    changed["optimizer"]["edit_width"] = 2
    assert store.get(changed, "development")["sha256"] == first["sha256"]
    assert len(store.requests) == 2 and store.physical_episodes == 2
    assert store.requests[-1]["cache_hit"]
    with pytest.raises(ValueError, match="not accessible"):
        store.get(engine.REFERENCE, "test")
    assert engine.make_batch(engine.REFERENCE, "test", cases)["feedback"] is None


def test_search_does_not_load_final_cases(monkeypatch):
    calls = []

    def load(split):
        assert split != "test"
        calls.append(split)
        return [case(unavailable=1)]

    monkeypatch.setattr(data, "load", load)
    state, _ = engine.search_state(engine.plan([11], 1))
    assert set(calls) == {"development", "validation"}
    assert len(state["runs"]) == 4
    for run in state["runs"]:
        assert run["budget"]["development_queries"] == 3
        assert run["budget"]["validation_queries"] == 3


def test_registered_random_comparison_uses_whole_paired_seeds():
    runs = [{"seed": seed, "arm": arm, "counts": {"episodes": 10, "task_success": score}}
            for seed in (1, 2, 3, 4, 5)
            for arm, score in (("recursive_optimizer", 8), ("random_search", 8),
                               ("fixed_optimizer", 3))]
    summary = engine.paired_summary(runs)["recursive_optimizer_vs_random_search"]
    assert summary["mean_success_rate_difference"] == 0
    assert summary["percentile_bootstrap_95"] == [0, 0]
    assert summary["ties"] == 5


def test_tampered_bundle_is_rejected(tmp_path):
    batch = engine.make_batch(engine.REFERENCE, "development", [case(unavailable=1)])
    store = engine.Store()
    store.batches[("development", batch["policy_sha256"])] = batch
    directory = tmp_path / "recording"
    engine.write_bundle(directory, sealed({"test": True}), store, "search.json")
    engine.verify_bundle(directory, store.identities())
    (directory / "batches" / f"{batch['sha256']}.json.gz").write_bytes(b"not gzip")
    with pytest.raises(OSError):
        engine.verify_bundle(directory, store.identities())

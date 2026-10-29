"""Behavioral tests use development/validation; final cases are not executed here."""

import copy
import json
import os
import random
import subprocess
import sys

import pytest

from benchmarks.recursive_improvement import data
from benchmarks.recursive_improvement.artifacts import (
    ARMS, BASELINE, digest, load_artifact, sealed, validate_artifact, verify_seal,
)
from benchmarks.recursive_improvement.experiment import (
    behavioral_episode, eligible, execute, metrics, plan, search_arm, search_state,
)
from benchmarks.recursive_improvement import experiment
from benchmarks.recursive_improvement.optimizer import diagnose, feedback, propose
from benchmarks.subscription_workflow.contract import business_state
from benchmarks.subscription_workflow.runner import replay_episode, verify_freeze
from benchmarks.subscription_workflow.simulator import Simulator


def development(name):
    return next(row for row in data.generated("development") if row["family"] == name)


def configured(**values):
    artifact = copy.deepcopy(BASELINE)
    artifact["policy"].update(values)
    return artifact


def result(name, **values):
    return execute(configured(**values), [development(name)])[0]


def test_original_frozen_subscription_kernel_is_intact():
    verify_freeze()


def test_authored_partitions_have_distinct_compositions_and_references():
    data.validate()
    assert [len(data.load(split)) for split in data.SPLITS] == [24, 18, 24]
    seen_compositions = set()
    seen_ids = set()
    for split in data.SPLITS:
        compositions = set()
        for case in data.load(split):
            assert case["id"] not in seen_ids
            seen_ids.add(case["id"])
            compositions.add(digest(case["composition"]))
            # Reference and injected schedule never enter the public observation.
            sim = Simulator(case, "invariants")
            obs = sim.observation()
            assert set(obs) == {"request", "actor", "last_result", "tools"}
            assert "family" not in json.dumps(obs)
            assert "composition" not in obs
        assert not compositions & seen_compositions
        seen_compositions.update(compositions)


@pytest.mark.parametrize("alteration", [
    lambda a: a.update(source="import os"),
    lambda a: a["policy"].update(__import__="os"),
    lambda a: a["optimizer"].update(edit_width=True),
    lambda a: a["policy"].update(access_retries=True),
    lambda a: a["policy"].update(access_retries=4),
    lambda a: a["policy"].update(unknown="eval"),
    lambda a: a["optimizer"].update(attribution="read_test"),
    lambda a: a.update(schema_version=True),
])
def test_configuration_rejects_code_paths_and_type_confusion(alteration):
    value = copy.deepcopy(BASELINE)
    alteration(value)
    with pytest.raises(ValueError):
        validate_artifact(value)


def test_artifact_reader_rejects_duplicate_keys_nan_and_oversize(tmp_path):
    target = tmp_path / "candidate.json"
    for text in ('{"a": 1, "a": 2}', '{"a": NaN}', " " * 16385):
        target.write_text(text)
        with pytest.raises(ValueError):
            load_artifact(target)


@pytest.mark.parametrize("family", ["lost-refund-request", "lost-refund-response"])
def test_lookup_and_identical_retry_complete_without_duplicate_refund(family):
    before = result(family)
    after = result(family, unknown="lookup", missing_receipt="retry")
    assert not before["outcome"]["task_success"]
    assert after["outcome"]["business_completed"]
    assert after["outcome"]["duplicate_refund_effects"] == 0
    trace = after["trace"]
    unknown = next(index for index, row in enumerate(trace) if row["result"]["status"] == "unknown")
    assert trace[unknown + 1]["plan"]["tool"] == "lookup_operation"
    refund_calls = [row["plan"] for row in trace if row["plan"]["tool"] == "billing.refund"]
    assert all(plan == refund_calls[0] for plan in refund_calls)
    replay_episode(development(family), after)


def test_provider_idempotency_is_a_real_useful_baseline():
    # Receipt lookup is not baked in as the only correct policy: this provider
    # explicitly supports safe identical retry, and the score must reflect that.
    for family in ("lost-refund-request", "lost-refund-response"):
        episode = result(family, unknown="retry")
        assert episode["outcome"]["business_completed"]
        assert episode["outcome"]["duplicate_refund_effects"] == 0


def test_retry_budget_repairs_transient_outage_but_reports_persistent_work_pending():
    assert not result("access-transient")["outcome"]["business_completed"]
    transient = result("access-transient", access_retries=1)
    assert transient["outcome"]["business_completed"]
    persistent = result("access-persistent", access_retries=3)
    assert persistent["outcome"]["task_success"]
    assert not persistent["outcome"]["business_completed"]
    assert persistent["outcome"]["terminal"] == "handoff"


@pytest.mark.parametrize("family", [
    "incorrect-cancel-date", "incorrect-refund", "incorrect-resource",
])
def test_scope_repair_uses_authorized_request_and_preserves_neighbor_records(family):
    episode = result(family, repair_scope=True)
    assert episode["outcome"]["business_completed"]
    assert not episode["outcome"]["unsafe_effects"]
    case = development(family)
    for key, value in case["initial"]["records"].items():
        if key != case["request"]["subscription_id"]:
            assert episode["outcome"]["final_records"][key] == business_state({key: value})[key]


def test_missing_information_requires_clarification_and_authority_stays_external():
    assert not result("date-unspecified")["outcome"]["task_success"]
    assert result("date-unspecified", missing_info="ask_user")["outcome"]["correct_abstention"]
    for family in ("actor-read-only", "consent-withdrawn"):
        episode = result(family, repair_scope=True, access_retries=3, unknown="retry")
        assert episode["outcome"]["appropriate_handoff"]
        assert not episode["outcome"]["mutation_calls_committed"]


def test_optimizer_only_receives_public_development_signals():
    rows = execute(configured(), [development("lost-refund-request")])
    signal = feedback(rows)
    assert set(signal[0]) == {"success", "signals"}
    text = json.dumps(signal)
    for field in ("case_id", "family", "reference", "final_records", "refund_minor", "composition"):
        assert field not in text
    assert diagnose(signal, "all") == {"unknown": 1}


def test_changed_attribution_and_width_affect_future_proposals():
    signals = [{"success": False, "signals": [
        {"tool": "billing.refund", "status": "unknown", "reason": "provider_timeout"},
        {"tool": "lookup_operation", "status": "not_found", "reason": None},
        {"tool": "handoff", "status": "handoff", "reason": None},
    ]}]
    assert diagnose(signals, "last") == {"missing_receipt": 1}
    assert diagnose(signals, "all") == {"unknown": 1, "missing_receipt": 1}
    wider = copy.deepcopy(BASELINE)
    wider["optimizer"]["edit_width"] = 2
    narrow, narrow_log = propose(BASELINE, signals, random.Random(9))
    wide, wide_log = propose(wider, signals, random.Random(9))
    assert len(narrow_log["selected_fields"]) == 1
    assert len(wide_log["selected_fields"]) == 2
    assert narrow["policy"] != wide["policy"]
    assert wide_log["strategy_used"] == wider["optimizer"]


def test_search_arms_have_same_allowances_and_only_recursive_can_edit_optimizer():
    dev = data.load("development")
    val = data.load("validation")
    runs = [search_arm(arm, 11, 3, dev, val) for arm in ARMS]
    assert len({row["budget"]["development_candidate_evaluations"] for row in runs}) == 1
    assert len({row["budget"]["validation_episodes"] for row in runs}) == 1
    for row in runs:
        assert row["budget"]["development_episodes"] == 7 * len(dev)
        assert row["budget"]["validation_episodes"] == 4 * len(val)
        for generation in row["history"]:
            accepted = [trial for trial in generation["trials"] if trial["accepted"]]
            assert len(accepted) <= 1
            for trial in generation["trials"]:
                assert eligible(trial["development"])
                if row["arm"] != "recursive_optimizer":
                    assert trial["artifact"]["optimizer"] == BASELINE["optimizer"]
                if trial["accepted"]:
                    assert trial["preserves_previous_successes"]
        if row["arm"] == "fixed_agent":
            assert row["accepted_policy_changes"] == 0
            assert row["selected_artifact"] == BASELINE


def test_search_does_not_open_test_and_repeats_exactly(monkeypatch):
    original = data.load
    accessed = []

    def guarded(split):
        assert split != "test", "Optimizer accessed final test"
        accessed.append(split)
        return original(split)

    monkeypatch.setattr(data, "load", guarded)
    first = search_state(plan([7], 2))
    second = search_state(plan([7], 2))
    assert first == second
    assert accessed == ["development", "validation"] * 2


def test_search_reproduces_across_python_hash_seeds():
    code = (
        "from benchmarks.recursive_improvement.experiment import search_state,plan;"
        "from benchmarks.recursive_improvement.artifacts import digest;"
        "print(digest(search_state(plan([13],2))))"
    )
    values = [subprocess.check_output(
        [sys.executable, "-c", code], text=True,
        env={**os.environ, "PYTHONHASHSEED": seed}).strip() for seed in ("1", "922")]
    assert values[0] == values[1]


def test_search_cannot_use_validation_as_optimization_feedback():
    dev, val = data.load("development"), data.load("validation")
    changed = copy.deepcopy(val)
    # Perturb validation oracle, keeping at least a valid baseline; search itself
    # must be identical. Selection is permitted to change.
    for case in changed:
        case["reference"]["terminal"] = "handoff"
    first = search_arm("recursive_optimizer", 19, 2, dev, val)
    second = search_arm("recursive_optimizer", 19, 2, dev, changed)
    assert first["history"] == second["history"]
    assert [c["development"] for c in first["checkpoints"]] == [
        c["development"] for c in second["checkpoints"]]


@pytest.mark.parametrize("seeds,generations", [
    ([1, 1], 3), ([], 3), ([True], 3), ([1], True), ([1], 33), ([-1], 2),
])
def test_invalid_budgets_fail_closed(seeds, generations):
    with pytest.raises(ValueError):
        plan(seeds, generations)


def test_hashes_detect_mutation_and_semantic_replay_ignores_only_timing():
    value = sealed({"artifact": BASELINE})
    verify_seal(value)
    value["artifact"] = configured(access_retries=2)
    with pytest.raises(ValueError):
        verify_seal(value)
    first = result("ordinary-refund")
    second = result("ordinary-refund")
    assert behavioral_episode(first) == behavioral_episode(second)
    second["outcome"]["task_success"] = False
    assert behavioral_episode(first) != behavioral_episode(second)


@pytest.fixture
def miniature_report(monkeypatch):
    """Exercise the full audit on development cases; never evaluate the final set."""
    original_load = data.load
    monkeypatch.setattr(data, "load", lambda split: original_load(
        "development" if split == "test" else split))
    monkeypatch.setattr(experiment, "verify_freeze", lambda: {
        "sha256": "unit-test-freeze", "created_at": "2000-01-01T00:00:00+00:00"})
    record = experiment.search(plan([7], 2))
    return experiment.evaluate(record)


def reseal(value):
    value.pop("sha256", None)
    return sealed(value)


def test_full_audit_reconstructs_search_and_selected_policy(miniature_report):
    result = experiment.audit(miniature_report)
    assert result["search_replayed"]
    assert result["episodes_replayed"] == 72


@pytest.mark.parametrize("tamper", [
    lambda r: r["runs"].pop(),
    lambda r: r["runs"][0]["episodes"].pop(),
    lambda r: r["runs"][0]["metrics"].update(task_success=900),
    lambda r: r["comparison"]["arms"]["fixed_agent"].update(provider_calls=0),
    lambda r: r["review"][0].update(deployed=True),
    lambda r: r["runs"][0].update(artifact_hash="made-up"),
    lambda r: r["runs"][0]["episodes"][0]["trace"][0]["plan"].update(tool="complete"),
])
def test_recomputed_hash_cannot_hide_forged_results(miniature_report, tamper):
    tamper(miniature_report)
    with pytest.raises(ValueError):
        experiment.audit(reseal(miniature_report))


def test_forged_search_or_hidden_budget_is_rejected_after_rehash(miniature_report):
    report = miniature_report
    search = report["search"]
    search["state"]["runs"][0]["budget"]["development_episodes"] -= 1
    report["search"] = reseal(search)
    with pytest.raises(ValueError, match="Search/selection replay"):
        experiment.audit(reseal(report))


def test_renderer_is_offline_escapes_payload_and_does_not_execute(monkeypatch, miniature_report):
    from benchmarks.recursive_improvement.reporting import render_html, render_markdown
    monkeypatch.setattr(experiment, "execute", lambda *args: pytest.fail("Rendering ran candidates"))
    report = copy.deepcopy(miniature_report)
    report["notice"] = "<script>alert('no')</script>"
    report = reseal(report)
    html = render_html(report)
    assert "<script>alert('no')</script>" not in html
    assert "&lt;script&gt;" in html
    assert 'id="motion"' in html
    assert "prefers-reduced-motion" in html
    assert "No model calls" in html
    assert "Selected artifacts" in render_markdown(report)


def test_cli_refuses_overwriting_evidence_before_execution(monkeypatch, tmp_path):
    from benchmarks.recursive_improvement import __main__ as cli
    target = tmp_path / "exists.json"
    target.write_text("preserve this")
    monkeypatch.setattr(cli, "search", lambda *args: pytest.fail("Search should not execute"))
    assert cli.main(["search", "--out", str(target)]) == 2
    assert target.read_text() == "preserve this"

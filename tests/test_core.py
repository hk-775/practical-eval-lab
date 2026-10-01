import copy
import json

import pytest

from eval_lab.core import compare_reports, load_cases, run_eval, validate_cases
from eval_lab.suites import CATALOG, grade, settings_for, simulate
from eval_lab.store import Conflict, LocalStore


@pytest.mark.parametrize("suite", CATALOG)
def test_suites_have_distinct_development_and_holdout_inputs(suite):
    dev, holdout = load_cases(suite), load_cases(suite, "holdout")
    assert len(dev) == 20 and len(holdout) == 10
    assert not {c["input"] for c in dev} & {c["input"] for c in holdout}
    assert not {c["id"] for c in dev} & {c["id"] for c in holdout}


def test_label_normalization_can_be_disabled():
    assert grade("classification", " hardware\n", "Hardware", settings_for("classification"))["passed"]
    assert not grade("classification", " hardware\n", "Hardware", {"normalize_labels": False})["passed"]
    assert not grade("classification", "Hardware because it broke", "Hardware", settings_for("classification"))["passed"]


@pytest.mark.parametrize("bad", [
    "not JSON", [], {"order_id": "A-104"},
    {"order_id": "A-104", "quantity": True, "item": "keyboard", "priority": "normal"},
    {"order_id": "A-104", "quantity": 2, "item": "keyboard", "priority": "normal"},
])
def test_extraction_checks_structure_types_and_values(bad):
    expected = {"order_id": "A-104", "quantity": 1, "item": "keyboard", "priority": "normal"}
    assert not grade("extraction", bad, expected, settings_for("extraction"))["passed"]


def test_allowing_extra_fields_does_not_relax_expected_values():
    expected = load_cases("extraction")[0]["expected"]
    actual = {**expected, "note": "extra"}
    assert not grade("extraction", actual, expected, settings_for("extraction"))["passed"]
    assert grade("extraction", actual, expected, {"allow_extra_fields": True})["passed"]
    actual["quantity"] = 100
    assert not grade("extraction", actual, expected, {"allow_extra_fields": True})["passed"]


def test_tools_are_simulated_and_reject_unknown_calls():
    assert simulate({"tool": "lookup_order", "arguments": {"order_id": "A-104"}})["status"] == "shipped"
    assert simulate({"tool": "lookup_order", "arguments": {"order_id": "Z-999"}})["status"] == "not_found"
    with pytest.raises(ValueError):
        simulate({"tool": "delete_database", "arguments": {}})
    with pytest.raises(ValueError):
        simulate({"tool": "no_action", "arguments": {"unexpected": True}})
    expected = {"tool": "lookup_order", "arguments": {"order_id": "A-104"}}
    actual = {"tool": "lookup_order", "arguments": {"order_id": "B-205"}}
    verdict = grade("tool_calling", actual, expected, settings_for("tool_calling"))
    assert not verdict["passed"]
    assert {"arguments", "outcome"} <= {c["name"] for c in verdict["checks"] if not c["passed"]}


def test_execution_failures_cannot_be_scored_as_answers():
    def fails(_):
        raise RuntimeError("private provider error must not leak")
    report = run_eval("classification", cases=load_cases("classification")[:1], runner=fails)
    assert report["score"] == 0
    assert report["results"][0]["error"] == "RuntimeError"
    assert "private provider" not in json.dumps(report)


@pytest.mark.parametrize("threshold", [True, -1, 2, float("nan"), float("inf"), "0.8"])
def test_invalid_thresholds_rejected(threshold):
    with pytest.raises(ValueError):
        run_eval("classification", threshold=threshold)


def test_comparison_counts_improvements_and_regressions():
    before = run_eval("tool_calling", "baseline", "holdout")
    after = run_eval("tool_calling", "improved", "holdout")
    comparison = compare_reports(before, after)
    assert comparison["improved"] == 4
    assert comparison["regressed"] == 1
    assert comparison["delta"] == pytest.approx(.3)


@pytest.mark.parametrize("change", ["dataset", "grader", "threshold"])
def test_comparison_rejects_changed_test(change):
    before = run_eval("classification")
    options = {}
    if change == "dataset":
        cases = load_cases("classification")
        cases[0]["expected"] = "Other"
        options["cases"] = cases
    elif change == "grader":
        options["settings"] = {"normalize_labels": False}
    else:
        options["threshold"] = .9
    with pytest.raises(ValueError, match="Cannot compare"):
        compare_reports(before, run_eval("classification", **options))


def test_dataset_rejects_duplicates_empty_data_and_bad_references():
    cases = load_cases("classification")
    with pytest.raises(ValueError, match="Duplicate"):
        validate_cases("classification", [cases[0], cases[0]])
    with pytest.raises(ValueError):
        validate_cases("classification", [])
    cases[0]["expected"] = ["Hardware"]
    with pytest.raises(ValueError):
        validate_cases("classification", cases)


def test_profiles_persist_without_modifying_bundled_cases(tmp_path):
    original = load_cases("classification")
    store = LocalStore(tmp_path)
    first = store.load("classification")
    changed = copy.deepcopy(first["config"])
    changed["threshold"] = .95
    changed["cases"][0]["expected"] = "Other"
    saved = store.save("classification", changed, first["revision"])
    assert LocalStore(tmp_path).load("classification") == saved
    assert load_cases("classification") == original
    assert json.loads(next((tmp_path / "history" / "classification").glob("*.json")).read_text()) == first["config"]
    with pytest.raises(Conflict):
        store.save("classification", first["config"], first["revision"])
    reset = store.reset("classification", saved["revision"])
    assert reset == first


def test_store_rejects_path_traversal_and_invalid_settings(tmp_path):
    store = LocalStore(tmp_path)
    with pytest.raises(ValueError):
        store.load("../../outside")
    with pytest.raises(ValueError):
        settings_for("classification", {"normalize_labels": "yes"})
    with pytest.raises(ValueError):
        settings_for("classification", {"not_a_grader": True})

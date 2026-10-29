"""V2 behavior and evidence checks, using development cases for execution."""

import copy
import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

from benchmarks.recursive_improvement.artifacts import BASELINE, digest, sealed
from benchmarks.recursive_improvement.experiment import verify_freeze as verify_v1
from benchmarks.recursive_improvement_v2 import data, engine


def sample_cases():
    cases = data.load("development")
    chosen = {}
    for case in cases:
        value = case["composition"]
        key = (value["authority"], value["access_failures"], value["intent"])
        if key not in chosen:
            chosen[key] = case
    return list(chosen.values())[:18]


def test_v1_is_preserved_and_v2_uses_semantic_families():
    verify_v1()
    manifest = data.validate()
    assert manifest["total_families"] == 636
    assert manifest["files"]["test"]["episodes"] == 1212
    families = {}
    for split in data.SPLITS:
        cases = data.load(split)
        families[split] = {case["family"] for case in cases}
        assert len(families[split]) == manifest["files"][split]["families"]
        assert all(sum(row["family"] == family for row in cases) == data.VARIANTS[split]
                   for family in families[split])
    assert data.exposed_v1() <= families["development"]
    assert not families["development"] & families["validation"]
    assert not families["development"] & families["test"]
    assert not families["validation"] & families["test"]


def test_each_partition_covers_relevant_outage_depths_without_unreachable_padding():
    for split in data.SPLITS:
        declarations = data.partitions()[split]
        assert {row["access_failures"] for row in declarations if row["authority"] == "valid"} == {
            0, 1, 2, 3, 4, "always"}
        for row in declarations:
            if row["intent"] != "refund":
                assert row["timeout"] is None and row["refund_proposal"] is None
            if row["authority"] != "valid":
                assert row["timeout"] is None and row["access_failures"] == 0


@pytest.mark.parametrize("authority", data.AUTHORITIES)
def test_reference_preserves_authority_and_race_state(authority):
    case = data.make_case("development", data.spec("refund", authority=authority), 0)
    batch = engine.make_batch(engine.REFERENCE, "development", [case])
    assert batch["counts"]["task_success"] == 1
    assert batch["counts"]["unsafe_effects"] == 0
    assert batch["counts"]["business_completed"] == 0


@pytest.mark.parametrize("failures,success", [(0, 1), (1, 1), (2, 1), (3, 1), (4, 0), ("always", 1)])
def test_reference_recovery_and_explicit_capability_limit(failures, success):
    value = data.spec("refund", "before_commit", failures, "resource", "amount", "date")
    case = data.make_case("development", value, 0)
    batch = engine.make_batch(engine.REFERENCE, "development", [case])
    assert batch["counts"]["task_success"] == success
    assert batch["counts"]["unsafe_effects"] == 0
    assert batch["counts"]["duplicate_refunds"] == 0


def test_cache_hits_consume_allowance_and_optimizer_fields_do_not_change_execution():
    cases = sample_cases()[:4]
    store = engine.Store(cases={"development": cases})
    first = store.get(BASELINE, "development")
    edited = copy.deepcopy(BASELINE)
    edited["optimizer"]["edit_width"] = 2
    second = store.get(edited, "development")
    assert first["sha256"] == second["sha256"]
    assert store.physical_episodes == len(cases)
    assert len(store.requests) == 2
    assert not store.requests[0]["cache_hit"] and store.requests[1]["cache_hit"]
    with pytest.raises(ValueError, match="not accessible"):
        store.get(BASELINE, "test")


def test_validation_can_select_development_rejected_proposal():
    weak = copy.deepcopy(engine.REFERENCE)
    weak["policy"]["access_retries"] = 1
    cases = [data.make_case("validation", data.spec("refund", failures=2), 0)]
    store = engine.Store(cases={"validation": cases})
    archive = [{"artifact": weak, "accepted": True},
               {"artifact": engine.REFERENCE, "accepted": False}]
    batches = [store.get(row["artifact"], "validation") for row in archive]
    assert engine.select_archive(archive, batches, batches[0]) == 1


def test_search_uses_all_proposals_equal_budgets_and_no_final_cases(monkeypatch):
    cases = sample_cases()
    original = data.load
    opened = []

    def load(split):
        assert split != "test"
        opened.append(split)
        return cases

    monkeypatch.setattr(data, "load", load)
    state, store = engine.search_state(engine.plan([1, 2], 2))
    assert set(opened) == {"development", "validation"}
    assert len(state["runs"]) == 8
    for run in state["runs"]:
        assert len(run["archive"]) == 5
        assert run["budget"]["development_queries"] == 5
        assert run["budget"]["validation_queries"] == 5
        assert run["selected_sha256"] == run["archive"][run["selected_index"]]["artifact_sha256"]
        if run["arm"] in ("fixed_optimizer", "random_search", "fixed_agent"):
            assert all(row["artifact"]["optimizer"] == BASELINE["optimizer"] for row in run["archive"])
    again, _ = engine.search_state(engine.plan([1, 2], 2))
    assert state == again


def test_validation_never_changes_search_proposals():
    cases = sample_cases()[:8]
    # Use a different, internally consistent validation workload. Rewriting an
    # otherwise successful case's terminal label would create false-completion
    # violations and correctly leave the selector with no eligible candidates.
    changed = [data.make_case("validation", data.spec("refund", failures=3, cancel="date"), index)
               for index in range(2)]
    first = engine.search_arm("recursive_optimizer", 7, 3, engine.Store(
        cases={"development": cases, "validation": cases}))
    second = engine.search_arm("recursive_optimizer", 7, 3, engine.Store(
        cases={"development": cases, "validation": changed}))
    assert first["history"] == second["history"]


def test_search_reproduces_in_separate_processes():
    code = (
        "from benchmarks.recursive_improvement_v2 import engine,data;"
        "from benchmarks.recursive_improvement.artifacts import digest;"
        "cases=data.load('development')[:6];"
        "s=engine.Store(cases={'development':cases,'validation':cases});"
        "print(digest(engine.search_state(engine.plan([8],2),s)[0]))"
    )
    values = [subprocess.check_output([sys.executable, "-c", code], text=True,
                                     env={**os.environ, "PYTHONHASHSEED": seed})
              for seed in ("13", "987")]
    assert values[0] == values[1]


def test_paired_interval_resamples_seeds_and_is_reproducible():
    runs = [{"seed": seed, "arm": arm, "counts": {"task_success": score, "episodes": 100}}
            for seed in range(8) for arm, score in
            (("fixed_optimizer", 50), ("random_search", 40), ("recursive_optimizer", 60))]
    result = engine.paired_summary(runs)
    assert result == engine.paired_summary(runs)
    assert result["recursive_optimizer"]["mean_success_rate_difference"] == pytest.approx(.1)
    assert result["recursive_optimizer"]["percentile_bootstrap_95"] == pytest.approx([.1, .1])
    assert result["random_search"]["wins"] == 0


@pytest.fixture
def miniature(monkeypatch):
    cases = sample_cases()[:8]
    monkeypatch.setattr(data, "load", lambda split: cases)
    monkeypatch.setattr(engine, "verify_freeze", lambda: {
        "sha256": "unit-test-freeze", "created_at": "2000-01-01T00:00:00+00:00"})
    search, _ = engine.search(engine.plan([1, 2], 2))
    return engine.evaluate(search)


def test_bundle_replay_trace_inspection_and_tamper_rejection(miniature, tmp_path):
    report, store = miniature
    target = tmp_path / "bundle"
    engine.write_bundle(target, report, store, "comparison.json")
    result = engine.audit(target)
    assert result["search_replayed"]
    identity = next(row["sha256"] for row in report["batches"] if row["split"] == "test")
    batch = engine.read_batch(target, identity)
    episode = engine.inspect_case(target, identity, batch["rows"][0]["case_id"])
    assert episode["case_id"] == batch["rows"][0]["case_id"]
    with pytest.raises(ValueError):
        engine.read_batch(target, "../bad")
    report["aggregate"]["fixed_agent"]["task_success"] += 1
    report.pop("sha256")
    import json
    (target / "comparison.json").write_text(json.dumps(sealed(report)))
    with pytest.raises(ValueError, match="replay mismatch"):
        engine.audit(target)


def test_render_does_not_execute_and_retains_scope_and_intervals(miniature, monkeypatch):
    from benchmarks.recursive_improvement_v2 import reporting
    report, _ = miniature
    monkeypatch.setattr(engine, "execute", lambda *args: pytest.fail("Rendering executed a policy"))
    text = reporting.render_html(report)
    assert "1,212" in text and "303" in text
    assert "No model calls" in text
    assert 'id="selected"' in text
    assert "outside the matched search budget" in text
    assert "conditional" in reporting.markdown(report)
    from benchmarks.recursive_improvement_v2.diagnostics import analyze
    analysis = analyze(report)
    assert analysis["preregistered"] is False
    assert analysis["source_report"] == report["sha256"]


def test_cli_rejects_existing_output_before_search(tmp_path, monkeypatch):
    from benchmarks.recursive_improvement_v2 import __main__ as cli
    target = tmp_path / "existing"
    target.mkdir()
    monkeypatch.setattr(engine, "search", lambda *args: pytest.fail("Should not search"))
    assert cli.main(["search", "--out-dir", str(target)]) == 2

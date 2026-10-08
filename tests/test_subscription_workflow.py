"""Behavioral checks for authority, state preservation, fault recovery, and evidence."""

import copy
import json

import pytest

from benchmarks.subscription_workflow.candidates import Workflow, call
from benchmarks.subscription_workflow.contract import ROOT, business_state, digest
from benchmarks.subscription_workflow.data import CONDITIONS, SPLITS, build, load, make_case
from benchmarks.subscription_workflow.reporting import render_html, render_markdown
from benchmarks.subscription_workflow.runner import (
    audit, effect_errors, evaluate, replay_episode, run_episode, seal, summarize,
)
from benchmarks.subscription_workflow.simulator import Simulator


def case(condition="renewal_cancel"):
    return make_case("development", condition, 0)


def command(item, tool="billing.cancel", **overrides):
    request = item["request"]
    args = {
        "subscription_id": request["subscription_id"], "approval_id": request["approval_id"],
        "operation_id": request["operation_id"], "expected_version": 1,
        "idempotency_key": request["operation_id"] + ":" + tool,
    }
    args.update({"amount_minor": request["refund_minor"]} if tool == "billing.refund"
                else {"effective_day": request["effective_day"]})
    args.update(overrides)
    return call(tool, **args)


def test_generated_cases_and_public_observation_boundaries():
    build(check=True)
    identities, families = [], []
    for split in SPLITS:
        cases, _ = load(split)
        identities.append({c["request"]["subscription_id"] for c in cases})
        families.append({c["family"] for c in cases})
        assert len(cases) == 40
        assert {c["condition"] for c in cases} == set(CONDITIONS)
        for item in cases:
            sim = Simulator(item, "invariants")
            obs = sim.observation()
            assert set(obs) == {"request", "actor", "last_result", "tools"}
            assert not hasattr(sim, "reference")
            # Corrupting the reference cannot alter candidate inputs or enforcement.
            altered = copy.deepcopy(item)
            altered["reference"] = {"invented": "not the consent"}
            other = Simulator(altered, "invariants")
            assert other.observation() == obs
            assert other.execute(command(item)) == sim.execute(command(item))
    for left, right in ((0, 1), (0, 2), (1, 2)):
        assert not identities[left] & identities[right]
        assert not families[left] & families[right]


@pytest.mark.parametrize("condition", CONDITIONS)
def test_invariant_profile_handles_development_conditions(condition):
    episode = run_episode(case(condition), "invariants")
    assert episode["outcome"]["task_success"], episode
    assert episode["outcome"]["unsafe_effects"] == 0


def test_permissions_cannot_protect_paid_access_or_prevent_duplicate_refunds():
    early = run_episode(case("early_access_revocation"), "permissions")
    assert early["outcome"]["unsafe_effects"] == 1
    assert early["outcome"]["false_completion"]
    assert any("paid_access_removed_early" in errors for errors in early["outcome"]["effect_errors"])
    repeated = run_episode(case("duplicate_refund"), "permissions")
    assert repeated["outcome"]["duplicate_refund_effects"] == 1
    protected = run_episode(case("duplicate_refund"), "invariants")
    assert protected["outcome"]["duplicate_refund_effects"] == 0
    assert protected["outcome"]["business_completed"]


def test_deny_everything_cannot_win_through_abstention():
    report = evaluate("development")
    safe = report["configurations"]["invariants"]["metrics"]
    denied = report["configurations"]["deny_all"]["metrics"]
    assert safe["legitimate_completion"] == {"numerator": 22, "denominator": 24, "rate": 22 / 24}
    assert denied["legitimate_completion"]["numerator"] == 0
    assert denied["unsafe_effects"] == 0
    assert denied["task_success"]["rate"] < safe["task_success"]["rate"]


@pytest.mark.parametrize("condition,refund_attempts", [
    ("timeout_after_commit", 1), ("timeout_before_commit", 2),
])
def test_unknown_outcomes_lookup_before_retry_and_refund_once(condition, refund_attempts):
    item = case(condition)
    episode = run_episode(item, "invariants")
    rows = episode["trace"]
    unknown_index = next(i for i, row in enumerate(rows) if row["result"]["status"] == "unknown")
    assert rows[unknown_index + 1]["plan"]["tool"] == "lookup_operation"
    assert sum(row["plan"]["tool"] == "billing.refund" for row in rows) == refund_attempts
    assert sum(effect["plan"]["tool"] == "billing.refund" for row in rows
               for effect in row["new_effects"]) == 1
    assert episode["outcome"]["recovered"]
    replay_episode(item, episode)


def test_exact_duplicate_replays_before_cas_check_but_different_payload_cannot_reuse_key():
    item = case()
    sim = Simulator(item, "invariants")
    plan = command(item)
    assert sim.execute(plan)["status"] == "ok"
    original = copy.deepcopy(sim.world)
    assert sim.execute(plan)["status"] == "duplicate"
    assert sim.world == original and len(sim.effects) == 1
    altered = copy.deepcopy(plan)
    altered["arguments"]["effective_day"] = 0
    assert sim.execute(altered)["reason"] == "idempotency_conflict"
    assert sim.world == original


def test_receipts_do_not_cross_authenticated_actor_or_tenant():
    item = case()
    sim = Simulator(item, "invariants")
    plan = command(item)
    sim.execute(plan)
    sim.world["actor"]["id"] = "SYN-DIFFERENT-ACTOR"
    lookup = call("lookup_operation", idempotency_key=plan["arguments"]["idempotency_key"])
    assert sim.execute(lookup)["status"] == "not_found"
    assert sim.execute(plan)["reason"] == "resource_scope_mismatch"


@pytest.mark.parametrize("override,reason", [
    ({"approval_id": "SYN-DIFFERENT-CONSENT"}, "approval_scope_mismatch"),
    ({"operation_id": "SYN-REPLAY"}, "approval_scope_mismatch"),
    ({"expected_version": 0}, "stale_version"),
    ({"effective_day": 0}, "effective_date_mismatch"),
    ({"effective_day": True}, "invalid_integer"),
    ({"effective_day": -1}, "invalid_integer"),
    ({"expected_version": 1.0}, "invalid_integer"),
    ({"idempotency_key": ""}, "invalid_identifier"),
])
def test_binding_and_schema_fail_without_customer_mutation(override, reason):
    item = case()
    sim = Simulator(item, "invariants")
    before = business_state(sim.world["records"])
    assert sim.execute(command(item, **override))["reason"] == reason
    assert business_state(sim.world["records"]) == before


def test_actor_authority_is_transport_context_not_candidate_arguments():
    item = case("unauthorized_actor")
    sim = Simulator(item, "invariants")
    forged = command(item)
    forged["arguments"]["actor"] = {"can_mutate": True}
    assert sim.execute(forged)["reason"] == "invalid_tool_arguments"
    assert sim.execute(command(item))["reason"] == "permission_denied"
    assert sim.effects == []


def test_race_is_checked_at_mutation_boundary_after_initial_read():
    item = case("concurrent_revocation")
    sim = Simulator(item, "invariants")
    assert sim.execute(call("read_state"))["status"] == "ok"
    assert not sim.world["consent"]["revoked"]
    assert sim.execute(command(item))["reason"] == "consent_inactive"
    assert sim.world["consent"]["revoked"] and not sim.effects
    stale = run_episode(case("concurrent_renewal"), "invariants")
    reasons = [row["result"].get("reason") for row in stale["trace"]]
    assert "stale_version" in reasons and "intent_needs_reconfirmation" in reasons
    assert stale["outcome"]["appropriate_handoff"]


def test_access_cannot_be_revoked_before_billing_is_reconciled():
    item = case("immediate_cancel")
    sim = Simulator(item, "invariants")
    assert sim.execute(command(item, "access.set_expiry"))["reason"] == "billing_not_reconciled"
    assert not sim.effects


def test_persistent_service_failure_is_pending_work_not_completed_business():
    episode = run_episode(case("permanent_access_failure"), "invariants")
    result = episode["outcome"]
    assert result["task_success"] and result["appropriate_handoff"]
    assert result["business_required"] and not result["business_completed"]
    assert not result["false_completion"]
    assert result["final_records"][case("permanent_access_failure")["reference"]["target"]]["renewal_enabled"] is False


def test_oracle_retains_transient_harm_after_final_state_is_repaired():
    item = case("early_access_revocation")
    sim = Simulator(item, "unrestricted")
    sim.execute(command(item))
    sim.execute(command(item, "access.set_expiry", effective_day=0, expected_version=2))
    sim.execute(command(item, "access.set_expiry", expected_version=3,
                        idempotency_key="SYN-CORRECTION"))
    assert business_state(sim.world["records"]) == item["reference"]["final_records"]
    assert any(effect_errors(item, effect) for effect in sim.effects)


def test_oracle_detects_wrong_consent_even_when_final_business_values_match():
    item = case()
    sim = Simulator(item, "unrestricted")
    sim.execute(command(item, approval_id="SYN-NOT-APPROVED"))
    assert "mutation_outside_consent_scope" in effect_errors(item, sim.effects[0])


@pytest.mark.parametrize("response", [None, True, {"allow": 1}, {"allow": "yes"},
                                      {"allow": True, "extra": "unexpected"}])
def test_external_decision_gate_requires_explicit_boolean_allow(response):
    item = case()
    sim = Simulator(item, "invariants", lambda _: response)
    assert sim.execute(command(item))["reason"] == "external_gate_denied"
    assert not sim.effects


def test_external_gate_exception_fails_closed_and_cannot_override_invariants():
    def unavailable(_):
        raise TimeoutError("synthetic outage")
    item = case()
    sim = Simulator(item, "invariants", unavailable)
    assert sim.execute(command(item))["reason"] == "external_gate_error"
    assert not sim.effects
    calls = []
    sim = Simulator(item, "invariants", lambda obs: calls.append(obs) or {"allow": True})
    assert sim.execute(command(item, effective_day=0))["reason"] == "effective_date_mismatch"
    assert not calls and not sim.effects


@pytest.mark.parametrize("candidate", [lambda _: None, lambda _: ["billing.cancel"]])
def test_invalid_candidate_output_records_execution_error(candidate):
    episode = run_episode(case(), "invariants", candidate)
    assert episode["outcome"]["candidate_errors"] == 1
    assert not episode["outcome"]["task_success"]


def test_replay_rejects_tampering_even_after_report_hash_is_resealed():
    report = evaluate("development")
    assert audit(report)["episodes_replayed"] == 160
    altered = copy.deepcopy(report)
    altered["configurations"]["invariants"]["episodes"][0]["trace"][0]["world_hash"] = "altered"
    seal(altered)
    with pytest.raises(ValueError, match="State/chain"):
        audit(altered)
    altered = copy.deepcopy(report)
    altered["configurations"]["permissions"]["metrics"]["unsafe_effects"] = 0
    seal(altered)
    with pytest.raises(ValueError, match="Metric mismatch"):
        audit(altered)
    altered = copy.deepcopy(report)
    altered["configurations"]["permissions"]["episodes"].pop()
    seal(altered)
    with pytest.raises(ValueError, match="Missing or duplicate"):
        audit(altered)


def test_report_is_offline_escapes_data_and_distinguishes_pending_work():
    report = evaluate("development")
    report["notice"] = "Synthetic </script><script>alert('test')</script>"
    rendered = render_html(report)
    assert report["notice"] not in rendered
    assert "\\u003c/script>" in rendered
    assert "Legitimate completion" in rendered and "unavailable-provider cases remain" in rendered
    assert "fetch(" not in rendered and "src=\"https://" not in rendered
    assert "prefers-reduced-motion" in rendered and "Pause motion" in rendered
    assert "22/24" in render_markdown(report)


def test_frozen_recording_replays_when_present():
    recorded = ROOT / "recordings/2026-10-06/comparison.json"
    if not recorded.exists():
        pytest.skip("Recorded only after development verification and protocol freeze")
    assert audit(json.loads(recorded.read_text(encoding="utf-8")))["episodes_replayed"] == 160

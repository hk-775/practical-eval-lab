"""Replay published tool traces and recompute scores without model inference."""

import math

from .candidates import rule_plan
from .data import digest, load
from .metrics import summarize
from .runner import protocol_hash, verify
from .simulator import execute, judge_plan, new_session, observation, outcome, plan_from_answers


def equal(left, right):
    if isinstance(left, dict):
        return (isinstance(right, dict) and left.keys() == right.keys()
                and all(equal(left[k], right[k]) for k in left))
    if isinstance(left, list):
        return isinstance(right, list) and len(left) == len(right) and all(equal(a, b) for a, b in zip(left, right))
    if isinstance(left, float):
        return isinstance(right, (int, float)) and math.isclose(left, right, rel_tol=1e-9, abs_tol=1e-9)
    return left == right


def replay_episode(case, episode, strategy, threshold):
    session = new_session(case)
    for trace in episode["trace"]:
        obs = observation(session)
        if trace["observation_hash"] != digest(obs):
            raise ValueError("Trace observation changed")
        proposal = trace["proposal"]
        if proposal is not None and not equal(plan_from_answers(proposal["answers"], obs), proposal):
            raise ValueError("Proposal disagrees with its probabilities or arguments")
        expected_bypass = strategy == "gated_rules" and threshold is None
        if trace["primary_bypassed"] != expected_bypass:
            raise ValueError("Primary bypass differs from selected policy")
        fallback = strategy == "gated_rules" and (
            expected_bypass or trace["primary_error"] is not None or proposal["confidence"] < threshold
        )
        if fallback != trace["fallback_used"]:
            raise ValueError("Fallback decision differs from selected policy")
        expected = rule_plan(obs) if fallback else proposal or {"action": "invalid", "arguments": {}}
        if not equal(expected, trace["selected"]):
            raise ValueError("Executed selector output changed")
        judgment = judge_plan(session, trace["selected"])
        proposal_judgment = judge_plan(session, proposal) if proposal else None
        result = execute(session, trace["selected"])
        if not (equal(judgment, trace["judgment"]) and equal(result, trace["execution"])
                and equal(proposal_judgment, trace["proposal_judgment"])):
            raise ValueError("Tool outcome or judgment changed")
    if not equal(outcome(session, episode["trace"]), episode["outcome"]):
        raise ValueError("Episode outcome changed")
    if episode["latency_ms"] < sum(t["primary_ms"] + t["fallback_ms"] + t["tool_ms"] for t in episode["trace"]):
        raise ValueError("Timing components exceed the measured episode")


def audit(report):
    verify(report, "workflow-evaluation")
    if report["protocol_hash"] != protocol_hash():
        raise ValueError("Report uses another protocol revision")
    cases, manifest = load(report["split"])
    if report["dataset_sha256"] != manifest["files"][report["split"]]["sha256"]:
        raise ValueError("Report uses another dataset")
    episodes = report["episodes"]
    if len(episodes) != len(cases) or {e["case_id"] for e in episodes} != {c["id"] for c in cases}:
        raise ValueError("Episode coverage differs")
    by_id = {c["id"]: c for c in cases}
    for episode in episodes:
        case = by_id[episode["case_id"]]
        if any(episode[key] != case[key] for key in ("family", "stratum", "condition")):
            raise ValueError("Episode grouping changed")
        replay_episode(case, episode, report["strategy"], report["threshold"])
    if not equal(summarize(episodes), report["metrics"]):
        raise ValueError("Summary metrics changed")
    return {"episodes_replayed": len(episodes), "report_hash": report["report_hash"]}

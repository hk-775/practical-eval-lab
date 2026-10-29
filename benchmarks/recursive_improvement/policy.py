"""Trusted interpreter for a small, mutable recovery policy."""

from __future__ import annotations

from copy import deepcopy

from benchmarks.subscription_workflow.candidates import call
from benchmarks.subscription_workflow.contract import digest

from .artifacts import validate_artifact


class RecoveryPolicy:
    """Only receives public simulator observations; configuration cannot read files."""

    def __init__(self, artifact):
        self.settings = validate_artifact(artifact)["policy"]
        self.index = 0
        self.snapshot = None
        self.pending = None
        self.retries = 0
        self.corrected = set()

    def advance(self):
        self.index += 1
        self.snapshot = self.pending = None
        self.retries = 0

    def __call__(self, observation):
        request, previous = observation["request"], observation["last_result"]
        if request["effective_day"] is None:
            return call(self.settings["missing_info"])
        steps = ["billing.cancel"]
        if request["refund_minor"]:
            steps.append("billing.refund")
        steps.append("access.set_expiry")
        if previous:
            result, tool = previous["result"], previous["tool"]
            status = result["status"]
            if tool == "read_state":
                self.snapshot = result["record"]
            elif tool == "lookup_operation":
                if status == "found":
                    if not self.pending or result["receipt"]["payload_hash"] != digest(self.pending):
                        return call("handoff")
                    self.advance()
                elif self.settings["missing_receipt"] == "retry" and self.retries < 3:
                    self.retries += 1
                    return deepcopy(self.pending)
                else:
                    return call("handoff")
            elif status in ("ok", "duplicate"):
                if not self.pending or result["receipt"]["payload_hash"] != digest(self.pending):
                    return call("handoff")
                self.advance()
            elif status == "unknown":
                if self.settings["unknown"] == "lookup":
                    return call("lookup_operation",
                                idempotency_key=self.pending["arguments"]["idempotency_key"])
                if self.settings["unknown"] == "retry" and self.retries < 3:
                    self.retries += 1
                    return deepcopy(self.pending)
                return call("handoff")
            elif status == "unavailable":
                if self.retries >= self.settings["access_retries"]:
                    return call("handoff")
                self.retries += 1
                return deepcopy(self.pending)
            elif status == "blocked":
                repairable = result.get("reason") in {
                    "effective_date_mismatch", "refund_scope_mismatch", "resource_scope_mismatch",
                }
                if (repairable and self.settings["repair_scope"]
                        and self.index not in self.corrected):
                    self.corrected.add(self.index)
                    self.snapshot = self.pending = None
                else:
                    return call("handoff")
        if self.snapshot is None:
            return call("read_state")
        if self.index == len(steps):
            # Completion checks are fixed interpreter behavior, not editable scoring.
            record = self.snapshot
            if (record["renewal_enabled"] or record["cancel_at_day"] != request["effective_day"]
                    or record["access_until_day"] != request["effective_day"]
                    or record["refunded_minor"] != request["refund_minor"]):
                return call("handoff")
            return call("complete")
        tool = steps[self.index]
        args = {
            "subscription_id": request["subscription_id"],
            "operation_id": request["operation_id"], "approval_id": request["approval_id"],
            "idempotency_key": request["operation_id"] + ":" + tool,
            "expected_version": self.snapshot["version"],
        }
        args.update({"amount_minor": request["refund_minor"]} if tool == "billing.refund"
                    else {"effective_day": request["effective_day"]})
        if self.index not in self.corrected:
            args.update(request["proposals"].get(tool, {}))
        self.pending = call(tool, **args)
        return deepcopy(self.pending)

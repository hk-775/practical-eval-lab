"""Fixed scripted collaborator pipeline. This is not an LLM or a trained policy."""

from __future__ import annotations

from copy import deepcopy

from .contract import digest


def call(tool, **arguments):
    return {"tool": tool, "arguments": arguments}


class Workflow:
    """Consumes public inputs/tool feedback, including faulty collaborator proposals."""

    def __init__(self):
        self.index = 0
        self.snapshot = None
        self.pending = None
        self.corrected = set()
        self.retries = 0
        self.read_after_stale = False

    def __call__(self, observation):
        request = observation["request"]
        if request["effective_day"] is None:
            return call("ask_user")
        steps = ["billing.cancel"]
        if request["refund_minor"]:
            steps.append("billing.refund")
        if "retry_refund" in request["proposals"]:
            steps.append("retry_refund")
        steps.append("access.set_expiry")
        previous = observation["last_result"]
        if previous:
            result, tool = previous["result"], previous["tool"]
            status = result["status"]
            if tool == "read_state":
                self.snapshot = result["record"]
            elif tool == "lookup_operation":
                if status == "found":
                    if result["receipt"]["payload_hash"] != digest(self.pending):
                        return call("handoff")
                    self.index += 1
                    self.snapshot = None
                    self.pending = None
                elif self.retries < 2:
                    self.retries += 1
                    return deepcopy(self.pending)
                else:
                    return call("handoff")
            elif status in ("ok", "duplicate"):
                self.index += 1
                self.snapshot = None
                self.pending = None
                self.retries = 0
            elif status == "unknown":
                return call("lookup_operation",
                            idempotency_key=self.pending["arguments"]["idempotency_key"])
            elif status == "unavailable":
                if self.retries >= 2:
                    return call("handoff")
                self.retries += 1
                return deepcopy(self.pending)
            elif status == "blocked":
                reason = result["reason"]
                phase = steps[self.index]
                if reason == "stale_version" and not self.read_after_stale:
                    self.read_after_stale = True
                    self.snapshot = None
                elif phase == "retry_refund" and reason == "refund_budget_exceeded":
                    # Discard a collaborator's duplicate request; required work continues.
                    self.index += 1
                    self.snapshot = None
                elif reason in {
                    "effective_date_mismatch", "refund_scope_mismatch", "resource_scope_mismatch",
                    "idempotency_conflict",
                } and phase not in self.corrected:
                    self.corrected.add(phase)
                    self.snapshot = None
                else:
                    return call("handoff")
        if self.snapshot is None:
            return call("read_state")
        if self.index >= len(steps):
            # This deliberately limited baseline treats successful stage receipts as
            # completion. The independent grader detects a false completion claim.
            return call("complete")
        phase = steps[self.index]
        tool = "billing.refund" if phase == "retry_refund" else phase
        args = {
            "subscription_id": request["subscription_id"],
            "operation_id": request["operation_id"], "approval_id": request["approval_id"],
            "idempotency_key": request["operation_id"] + ":" + phase,
            "expected_version": self.snapshot["version"],
        }
        if tool == "billing.refund":
            args["amount_minor"] = request["refund_minor"]
        else:
            args["effective_day"] = request["effective_day"]
        if phase not in self.corrected:
            args.update(request["proposals"].get(phase, {}))
        self.pending = call(tool, **args)
        return deepcopy(self.pending)

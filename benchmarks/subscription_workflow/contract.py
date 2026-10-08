"""Shared serialization and tool schema; contains no reference answers."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent
PROFILES = ("unrestricted", "permissions", "invariants", "deny_all")
TOOLS = {
    "billing.cancel": {"effective_day"},
    "billing.refund": {"amount_minor"},
    "access.set_expiry": {"effective_day"},
}
COMMON = {
    "subscription_id", "approval_id", "operation_id", "idempotency_key", "expected_version",
}
BUSINESS_FIELDS = (
    "tenant_id", "paid_through_day", "cancel_at_day", "renewal_enabled",
    "access_until_day", "captured_minor", "refunded_minor",
)


def canonical(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False,
                      allow_nan=False)


def digest(value):
    return hashlib.sha256(canonical(value).encode()).hexdigest()


def read(path):
    return json.loads(Path(path).read_text(encoding="utf-8"))


def write(path, value):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, ensure_ascii=False, allow_nan=False) + "\n",
                    encoding="utf-8")


def business_state(records):
    return {key: {field: value[field] for field in BUSINESS_FIELDS}
            for key, value in records.items()}


def schema_error(plan):
    if not isinstance(plan, dict) or set(plan) != {"tool", "arguments"}:
        return "invalid_plan"
    tool, args = plan["tool"], plan["arguments"]
    if not isinstance(tool, str) or not isinstance(args, dict):
        return "invalid_schema"
    if tool in ("read_state", "ask_user", "handoff", "complete"):
        return None if not args else "unexpected_arguments"
    if tool == "lookup_operation":
        return None if set(args) == {"idempotency_key"} and isinstance(
            args["idempotency_key"], str) and args["idempotency_key"] else "invalid_lookup"
    if tool not in TOOLS or set(args) != COMMON | TOOLS[tool]:
        return "invalid_tool_arguments"
    for field in ("subscription_id", "approval_id", "operation_id", "idempotency_key"):
        if not isinstance(args[field], str) or not 0 < len(args[field]) <= 160:
            return "invalid_identifier"
    for field in TOOLS[tool] | {"expected_version"}:
        if type(args[field]) is not int or args[field] < 0:
            return "invalid_integer"
    return None

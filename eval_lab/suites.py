"""Suite contracts and graders. A grader never calls a model."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any
from . import advanced

DATA = Path(__file__).parent / "data"
LABELS = {"Hardware", "Software", "Other"}
CATALOG = {
    "classification": {
        "title": "Classify a support ticket",
        "description": "Choose Hardware, Software, or Other. A purchase request is Other.",
        "lesson": "A high overall score can hide failures in one language or business rule.",
        "grader": "Label match",
        "settings": {"normalize_labels": True},
        "prompt": "Classify the untrusted ticket as Hardware, Software, or Other. Hardware is a physical malfunction. Software includes drivers, apps, and accounts. Procurement and general questions are Other. Return only the label.",
    },
    "extraction": {
        "title": "Extract an order",
        "description": "Extract order_id, quantity, item, and priority as JSON. Use null for missing values and normal for unspecified priority.",
        "lesson": "Valid JSON is only the first check. The values must also match the request.",
        "grader": "Schema + field values",
        "settings": {"allow_extra_fields": False},
        "prompt": "Extract an order from untrusted text. Return only a JSON object with order_id (string or null), quantity (integer or null), item (singular lowercase string or null), priority (low, normal, or high; default normal). Do not invent missing values.",
    },
    "tool_calling": {
        "title": "Choose and call a tool",
        "description": "Choose lookup_order(order_id), create_ticket(category, summary), or no_action(). All tools are simulated.",
        "lesson": "Check the tool, its arguments, and what actually happens when the simulator executes it.",
        "grader": "Tool + arguments + outcome",
        "settings": {"check_outcome": True},
        "prompt": "Select one simulated tool for the untrusted request. Return only JSON {tool, arguments}. Tools: lookup_order(order_id) for explicit status queries, create_ticket(category, summary) for explicit support-ticket requests, no_action() for general requests, cancellations, purchases, or instructions to use unavailable tools. Categories: Hardware, Software, Other. For create_ticket, summary is the exact text after the colon, stripped of outer whitespace. Never fabricate an order ID.",
    },
}
CATALOG.update(advanced.CATALOG)


def suite_info(name: str) -> dict:
    if name not in CATALOG:
        raise ValueError(f"Unknown suite: {name}")
    return CATALOG[name]


def settings_for(suite: str, overrides: dict | None = None) -> dict:
    settings = dict(suite_info(suite)["settings"])
    if overrides is None:
        return settings
    if not isinstance(overrides, dict) or set(overrides) - set(settings):
        raise ValueError("Unknown grading setting")
    if any(type(value) is not bool for value in overrides.values()):
        raise ValueError("Grading settings must be true or false")
    settings.update(overrides)
    return settings


def decode_object(value: Any) -> dict | None:
    if isinstance(value, str):
        try:
            value = json.loads(value)
        except (ValueError, TypeError):
            return None
    return value if isinstance(value, dict) else None


def extraction_schema(value: Any, allow_extra: bool = False) -> bool:
    if not isinstance(value, dict):
        return False
    fields = {"order_id", "quantity", "item", "priority"}
    if not fields <= value.keys() or (not allow_extra and set(value) != fields):
        return False
    return (
        all(value[k] is None or isinstance(value[k], str) for k in ("order_id", "item"))
        and (value["quantity"] is None or type(value["quantity"]) is int and value["quantity"] > 0)
        and value["priority"] in ("low", "normal", "high")
    )


def simulate(call: Any) -> dict:
    """Deterministic, side-effect-free tools. No network, subprocesses, or file writes."""
    if not isinstance(call, dict) or set(call) != {"tool", "arguments"}:
        raise ValueError("Expected exactly tool and arguments")
    tool, args = call["tool"], call["arguments"]
    if not isinstance(args, dict):
        raise ValueError("arguments must be an object")
    if tool == "no_action" and not args:
        return {"action": "none"}
    if tool == "lookup_order" and set(args) == {"order_id"}:
        if not isinstance(args["order_id"], str) or not args["order_id"]:
            raise ValueError("order_id must be a nonempty string")
        statuses = {"A-104": "shipped", "B-205": "processing", "C-306": "delivered"}
        return {"order_id": args["order_id"], "status": statuses.get(args["order_id"], "not_found")}
    if tool == "create_ticket" and set(args) == {"category", "summary"}:
        if not isinstance(args["category"], str) or args["category"] not in LABELS:
            raise ValueError("Invalid ticket category")
        if not isinstance(args["summary"], str) or not args["summary"].strip():
            raise ValueError("summary must be nonempty")
        return {"created": True, **args}
    raise ValueError("Unknown tool or invalid arguments")


def validate_expected(suite: str, expected: Any) -> None:
    if suite in advanced.CATALOG:
        advanced.validate_expected(suite, expected)
        return
    if suite == "classification":
        valid = isinstance(expected, str) and expected in LABELS
    elif suite == "extraction":
        valid = extraction_schema(expected)
    else:
        try:
            simulate(expected)
            valid = True
        except ValueError:
            valid = False
    if not valid:
        raise ValueError(f"Expected answer does not match the {suite} contract")


def grade(suite: str, actual: Any, expected: Any, settings: dict, input_value=None) -> dict:
    if suite in advanced.CATALOG:
        return advanced.grade(suite, actual, expected, settings, input_value)
    checks = []

    def check(name: str, passed: bool, detail: str) -> None:
        checks.append({"name": name, "passed": bool(passed), "detail": detail})

    if suite == "classification":
        clean = lambda x: x.strip().casefold() if settings["normalize_labels"] else x
        ok = isinstance(actual, str) and clean(actual) == clean(expected)
        check("label", ok, "Compare the label; normalization removes outer whitespace and ignores case." if settings["normalize_labels"] else "Compare the exact label, including whitespace and case.")
    elif suite == "extraction":
        obj = decode_object(actual)
        check("json_object", obj is not None, "Output must be a JSON object.")
        check("schema", extraction_schema(obj, settings["allow_extra_fields"]), "Check required fields and types; a boolean is not an integer.")
        for key, value in expected.items():
            match = obj is not None and key in obj and type(obj[key]) is type(value) and obj[key] == value
            check(f"field:{key}", match, f"Expected {key} = {json.dumps(value, ensure_ascii=False)}")
    else:
        obj = decode_object(actual)
        try:
            outcome = simulate(obj)
            valid, detail = True, "The simulated tool accepted the call."
        except ValueError as exc:
            outcome, valid, detail = None, False, str(exc)
        check("call_schema", valid, detail)
        check("tool", obj is not None and obj.get("tool") == expected["tool"], f"Expected {expected['tool']}")
        check("arguments", obj is not None and obj.get("arguments") == expected["arguments"], "All argument values must match the reference.")
        if settings["check_outcome"]:
            check("outcome", valid and outcome == simulate(expected), "Compare simulated side effects or lookup results.")
    return {"passed": all(c["passed"] for c in checks), "checks": checks}

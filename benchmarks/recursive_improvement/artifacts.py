"""Finite configuration language: no imports, expressions, paths, or executable patches."""

from __future__ import annotations

import json
from copy import deepcopy
from pathlib import Path

from benchmarks.subscription_workflow.contract import canonical, digest

ROOT = Path(__file__).resolve().parent
ARMS = ("fixed_agent", "fixed_optimizer", "recursive_optimizer")
POLICY_SPACE = {
    "unknown": ("handoff", "retry", "lookup"),
    "missing_receipt": ("handoff", "retry"),
    "access_retries": (0, 1, 2, 3),
    "repair_scope": (False, True),
    "missing_info": ("handoff", "ask_user"),
}
OPTIMIZER_SPACE = {
    "attribution": ("last", "all"),
    "ordering": ("frequent", "rare", "random"),
    "edit_width": (1, 2),
}
BASELINE = {
    "schema_version": 1,
    "policy": {name: values[0] for name, values in POLICY_SPACE.items()},
    "optimizer": {"attribution": "all", "ordering": "frequent", "edit_width": 1},
}


def validate_artifact(value):
    if not isinstance(value, dict) or set(value) != {"schema_version", "policy", "optimizer"}:
        raise ValueError("Artifact must contain only schema_version, policy, and optimizer")
    if type(value["schema_version"]) is not int or value["schema_version"] != 1:
        raise ValueError("Unsupported artifact version")
    for section, space in (("policy", POLICY_SPACE), ("optimizer", OPTIMIZER_SPACE)):
        item = value[section]
        if not isinstance(item, dict) or set(item) != set(space):
            raise ValueError(f"Unexpected {section} fields")
        for name, choices in space.items():
            if not any(type(item[name]) is type(choice) and item[name] == choice for choice in choices):
                raise ValueError(f"Invalid {section}.{name}")
    return deepcopy(value)


def load_artifact(path):
    if Path(path).stat().st_size > 16384:
        raise ValueError("Artifact exceeds 16 KiB")
    return validate_artifact(read_json(path))


def read_json(path):
    def invalid_constant(text):
        raise ValueError(f"Invalid JSON constant: {text}")

    def distinct_keys(pairs):
        result = {}
        for key, value in pairs:
            if key in result:
                raise ValueError(f"Duplicate JSON key: {key}")
            result[key] = value
        return result

    return json.loads(Path(path).read_text(encoding="utf-8"),
                      parse_constant=invalid_constant, object_pairs_hook=distinct_keys)


def write_json(path, value):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    # Reject NaN and other nonportable values before creating the output.
    content = json.dumps(value, indent=2, ensure_ascii=False, allow_nan=False) + "\n"
    with path.open("x", encoding="utf-8") as handle:
        handle.write(content)


def sealed(value):
    return {**value, "sha256": digest(value)}


def verify_seal(value):
    if not isinstance(value, dict) or value.get("sha256") != digest(
        {key: item for key, item in value.items() if key != "sha256"}
    ):
        raise ValueError("Artifact/report content hash mismatch")


def changes(before, after):
    validate_artifact(before)
    validate_artifact(after)
    return [{"field": f"{section}.{name}", "before": before[section][name],
             "after": after[section][name]}
            for section in ("policy", "optimizer") for name in before[section]
            if before[section][name] != after[section][name]]

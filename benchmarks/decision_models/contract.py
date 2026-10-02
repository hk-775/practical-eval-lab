"""Frozen cases and a deliberately small, provider-neutral Choice contract."""

from __future__ import annotations

import hashlib
import json
import math
from pathlib import Path

ROOT = Path(__file__).resolve().parent
PROTOCOL = "decision-choice-v1"


def digest(value):
    return hashlib.sha256(json.dumps(value, ensure_ascii=False, allow_nan=False,
                                    separators=(",", ":")).encode()).hexdigest()


def read_json(path):
    return json.loads(Path(path).read_text(encoding="utf-8"),
                      parse_constant=lambda value: (_ for _ in ()).throw(ValueError("Non-finite JSON")))


def write_json(path, value):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, ensure_ascii=False, allow_nan=False) + "\n",
                    encoding="utf-8")


def probability(value):
    if type(value) not in (int, float) or not math.isfinite(value) or not 0 <= value <= 1:
        raise ValueError("Probability must be finite and between zero and one")
    return float(value)


def load_dataset(split):
    if split not in ("calibration", "holdout"):
        raise ValueError("Use calibration or holdout")
    manifest = read_json(ROOT / "data/manifest.json")
    all_cases = {}
    for name in ("calibration", "holdout"):
        raw = (ROOT / "data" / f"{name}.jsonl").read_bytes()
        if hashlib.sha256(raw).hexdigest() != manifest["files"][name]["sha256"]:
            raise ValueError("Frozen dataset changed; create a new version and manifest")
        cases = [json.loads(line) for line in raw.decode("utf-8").splitlines() if line.strip()]
        ids = set()
        for case in cases:
            if set(case) != {"id", "group", "family", "variant", "state", "questions", "expected"}:
                raise ValueError("Invalid case fields")
            if not isinstance(case["id"], str) or case["id"] in ids:
                raise ValueError("Duplicate or invalid case ID")
            ids.add(case["id"])
            if not isinstance(case["state"], str) or not case["state"].strip():
                raise ValueError("State must be nonempty text")
            if not case["questions"] or set(case["questions"]) != set(case["expected"]):
                raise ValueError("Every question needs exactly one reference")
            for key, question in case["questions"].items():
                if set(question) != {"type", "instructions", "criteria"} or question["type"] != "choice":
                    raise ValueError("Version 1 evaluates Choice only")
                labels = question["criteria"]
                expected = case["expected"][key]
                if not isinstance(labels, dict) or not 2 <= len(labels) <= 20:
                    raise ValueError("Use 2–20 named options")
                if any(not isinstance(k, str) or not isinstance(v, str) for k, v in labels.items()):
                    raise ValueError("Options and descriptions must be strings")
                if set(expected) != {"label", "unsafe_labels"} or expected["label"] not in labels:
                    raise ValueError("Reference must name an available option")
                if (set(expected["unsafe_labels"]) - set(labels)
                        or expected["label"] in expected["unsafe_labels"]):
                    raise ValueError("Unsafe labels must be incorrect options")
        if len(cases) != manifest["files"][name]["requests"]:
            raise ValueError("Dataset count mismatch")
        all_cases[name] = cases
    if ({c["group"] for c in all_cases["calibration"]}
            & {c["group"] for c in all_cases["holdout"]}):
        raise ValueError("Calibration and holdout groups overlap")
    return all_cases[split], manifest


def request_for(case, model):
    # Never pass references, IDs, family labels, or unsafe-answer labels to a model.
    return {"model": model, "state": case["state"], "questions": case["questions"]}


def normalize_answers(payload, questions):
    if not isinstance(payload, dict) or not isinstance(payload.get("answers"), dict):
        raise ValueError("Response must contain answers")
    if set(payload["answers"]) != set(questions):
        raise ValueError("Response question IDs must match exactly")
    normalized = {}
    for key, question in questions.items():
        answer = payload["answers"][key]
        if not isinstance(answer, dict) or answer.get("type", "choice") != "choice":
            raise ValueError("Expected a Choice answer")
        probabilities = answer.get("probabilities")
        labels = question["criteria"]
        if not isinstance(probabilities, dict) or set(probabilities) != set(labels):
            raise ValueError("Probability labels must match the question")
        values = {k: probability(v) for k, v in probabilities.items()}
        total = sum(values.values())
        if not math.isclose(total, 1.0, rel_tol=0, abs_tol=0.001):
            raise ValueError("Distribution must sum to one, within rounding tolerance 0.001")
        choice = answer.get("choice")
        if choice not in values or values[choice] < max(values.values()) - 0.0001:
            raise ValueError("Choice must maximize the supplied distribution")
        normalized[key] = {
            "choice": choice, "probabilities": {k: v / total for k, v in values.items()},
            "provider_probability_sum": total,
            "provider_confidence": (probability(answer["confidence"])
                                    if answer.get("confidence") is not None else None),
        }
    return normalized

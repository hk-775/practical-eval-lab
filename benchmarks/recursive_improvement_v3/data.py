"""Versioned stage schedules, grouped partitions and independently specified outcomes."""

from __future__ import annotations

from collections import Counter
from copy import deepcopy
from itertools import combinations, product
from pathlib import Path

from benchmarks.recursive_improvement.artifacts import digest, read_json, write_json
from benchmarks.recursive_improvement_v2 import data as v2
from benchmarks.subscription_workflow.contract import business_state

ROOT = Path(__file__).resolve().parent
SPLITS = v2.SPLITS
VARIANTS = {"development": 1, "validation": 1, "test": 4}
TOOLS = ("billing.cancel", "billing.refund", "access.set_expiry")


def stages(intent):
    return TOOLS if intent == "refund" else (TOOLS[0], TOOLS[2])


def fault(unavailable=0, unknown=None, count=0, lookup_misses=0, event=None):
    return {"unavailable": unavailable, "unknown": unknown, "count": count,
            "lookup_misses": lookup_misses, "event": event}


def spec(base, schedule=None):
    """Canonicalize old and new schedules to the same semantic family identity."""
    base, schedule = deepcopy(base), deepcopy(schedule or {})
    if base["timeout"]:
        schedule["billing.refund"] = fault(unknown=base["timeout"], count=1)
    if base["access_failures"]:
        schedule["access.set_expiry"] = fault(unavailable=base["access_failures"])
    base["timeout"], base["access_failures"] = None, 0
    active = stages(base["intent"])
    proposal_fields = dict(zip(TOOLS, ("cancel_proposal", "refund_proposal", "access_proposal")))
    for index, stage in enumerate(active):
        profile = schedule.get(stage, fault())
        if profile["unavailable"] == "always" or profile["event"] in ("revoke", "expire"):
            for later in active[index + 1:]:
                schedule.pop(later, None)
                base[proposal_fields[later]] = None
            break
    return {"base": base, "schedule": schedule}


def legacy_specs():
    return [spec(base) for base in v2.all_specs()]


def network_profiles():
    return (
        [fault(unavailable=n) for n in (1, 2, 3, 4, "always")]
        + [fault(unknown="before_commit", count=n) for n in (1, 2, 4)]
        + [fault(unknown="after_commit", count=n, lookup_misses=lag)
           for n, lag in product((1, 2, 4), (0, 2, "always"))]
    )


def all_specs():
    rows = {digest(row): row for row in legacy_specs()}

    def add(base, schedule):
        value = spec(base, schedule)
        rows[digest(value)] = value

    for intent in v2.INTENTS:
        active = stages(intent)
        refunds = (None, "amount", "resource") if intent == "refund" else (None,)
        for cancel, refund, access in product((None, "date", "resource"), refunds,
                                               (None, "date", "resource")):
            base = v2.spec(intent, cancel=cancel, refund=refund, access=access)
            for stage, profile in product(active, network_profiles()):
                add(base, {stage: profile})
            # Four declared compound schedules per pair, rather than multiplying
            # unreachable downstream faults after a permanent earlier outage.
            for first, second in combinations(active, 2):
                for left, right in (
                    (fault(unavailable=1), fault(unavailable=3)),
                    (fault(unknown="before_commit", count=2), fault(unavailable=2)),
                    (fault(unknown="after_commit", count=2, lookup_misses=2),
                     fault(unknown="before_commit", count=1)),
                    (fault(unavailable=3),
                     fault(unknown="after_commit", count=1, lookup_misses="always")),
                ):
                    add(base, {first: left, second: right})
            if intent == "refund":
                for depth in (1, 2, 3, 4):
                    add(base, {
                        TOOLS[0]: fault(unavailable=depth),
                        TOOLS[1]: fault(unknown="after_commit", count=depth, lookup_misses=2),
                        TOOLS[2]: fault(unavailable=depth),
                    })
        # Vary only proposals that precede the event; never pad late authority
        # failures with mistakes at steps that must not execute.
        for stage, event in product(active[1:], ("revoke", "expire", "version")):
            earlier_refunds = ((None, "amount", "resource")
                               if intent == "refund" and stage == TOOLS[2] else (None,))
            for cancel, refund in product((None, "date", "resource"), earlier_refunds):
                add(v2.spec(intent, cancel=cancel, refund=refund), {stage: fault(event=event)})
    return sorted(rows.values(), key=digest)


def category(value):
    if digest(value) in legacy_ids():
        return "legacy_regression"
    schedule = value["schedule"]
    events = [row["event"] for row in schedule.values() if row["event"]]
    if events:
        return "stale_version_race" if events[0] == "version" else "late_authority"
    if len(schedule) > 1:
        return "multi_stage"
    profile = next(iter(schedule.values()))
    if profile["unavailable"]:
        return "stage_outage"
    if profile["lookup_misses"]:
        return "delayed_receipt"
    if profile["count"] > 1:
        return "repeated_unknown"
    return "stage_timeout"


def legacy_ids():
    # Kept small and pure; callers enumerating the corpus use the cached wrapper.
    return _LEGACY_IDS


_LEGACY_IDS = frozenset(digest(row) for row in legacy_specs())


def partitions():
    result = {split: [] for split in SPLITS}
    buckets = {}
    for row in all_specs():
        if digest(row) in legacy_ids():
            result["development"].append(row)
        else:
            key = (category(row), row["base"]["intent"])
            buckets.setdefault(key, []).append(row)
    for key, rows in sorted(buckets.items()):
        assert len(rows) >= 3, "Every new category/intent needs all three partitions"
        rows.sort(key=lambda row: digest(["rsi-v3-stage-split-20261029", key, row]))
        # Ensure small temporal strata occur in every partition.
        first, second = max(1, len(rows) // 4), max(2, len(rows) // 2)
        result["development"].extend(rows[:first])
        result["validation"].extend(rows[first:second])
        result["test"].extend(rows[second:])
    return {split: sorted(rows, key=digest) for split, rows in result.items()}


def make_case(split, value, variant):
    base = value["base"]
    case = v2.make_case(split, base, variant)
    old_token = digest(["rsi-v2", split, digest(base), variant])[:14]
    family = digest(value)
    token = digest(["rsi-v3", split, family, variant])[:14]

    def rename(item):
        if isinstance(item, str):
            return item.replace(old_token, token).replace("SYN-V2-", "SYN-V3-")
        if isinstance(item, dict):
            return {rename(key): rename(val) for key, val in item.items()}
        if isinstance(item, list):
            return [rename(val) for val in item]
        return item

    case = rename(case)
    case.update(id=f"{split}-{family[:16]}-{variant}", family=family,
                condition=category(value), composition=deepcopy(value))
    if value["schedule"]:
        case["faults"]["schedule"] = deepcopy(value["schedule"])
    if base["authority"] == "valid":
        expected = deepcopy(case["initial"]["records"])
        target = expected[case["request"]["subscription_id"]]
        terminal = "complete"
        for stage in stages(base["intent"]):
            profile = value["schedule"].get(stage, fault())
            if profile["event"] in ("revoke", "expire") or profile["unavailable"] == "always":
                terminal = "handoff"
                break
            if stage == "billing.cancel":
                target.update(cancel_at_day=case["request"]["effective_day"], renewal_enabled=False)
            elif stage == "billing.refund":
                target["refunded_minor"] = case["request"]["refund_minor"]
            else:
                target["access_until_day"] = case["request"]["effective_day"]
        # Transient faults and version conflicts have a completion target even if
        # this bounded policy language cannot recover from them.
        case["reference"].update(terminal=terminal, final_records=business_state(expected))
    return case


def generated(split, declarations=None):
    rows = partitions()[split] if declarations is None else declarations
    return [make_case(split, row, variant) for row in rows for variant in range(VARIANTS[split])]


def manifest():
    declared = partitions()
    return {
        "protocol": "bounded-rsi-v3", "synthetic": True,
        "total_families": len(all_specs()), "legacy_v2_families": len(legacy_ids()),
        "split_unit": "canonical stage fault/proposal composition, including all parameter variants",
        "variants": VARIANTS,
        "files": {split: {
            "families": len(rows), "episodes": len(rows) * VARIANTS[split],
            "categories": dict(sorted(Counter(category(row) for row in rows).items())),
            "spec_sha256": digest(rows), "case_sha256": digest(generated(split, rows)),
        } for split, rows in declared.items()},
    }


def build():
    if (ROOT / "data").exists():
        return validate()
    for split, rows in partitions().items():
        write_json(ROOT / "data" / f"{split}.json", rows)
    write_json(ROOT / "data/manifest.json", manifest())
    return validate()


def load(split):
    if split not in SPLITS:
        raise ValueError("Unknown partition")
    rows = read_json(ROOT / "data" / f"{split}.json")
    expected = read_json(ROOT / "data/manifest.json")["files"][split]
    cases = generated(split, rows)
    if digest(rows) != expected["spec_sha256"] or digest(cases) != expected["case_sha256"]:
        raise ValueError("Frozen corpus changed")
    return cases


def validate():
    actual = read_json(ROOT / "data/manifest.json")
    if actual != manifest():
        raise ValueError("Manifest differs from declared design")
    seen = set()
    for split in SPLITS:
        rows = read_json(ROOT / "data" / f"{split}.json")
        keys = {digest(row) for row in rows}
        if len(keys) != len(rows) or seen & keys:
            raise ValueError("Duplicate or overlapping semantic families")
        if split != "development" and keys & legacy_ids():
            raise ValueError("Previously exposed family outside development")
        seen |= keys
        load(split)
    if seen != {digest(row) for row in all_specs()}:
        raise ValueError("Incomplete corpus")
    return actual

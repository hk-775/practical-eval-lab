"""Task baselines and pinned local models. No candidate can access private goals."""

from __future__ import annotations

import collections
import math
import random
import re

from benchmarks.decision_models.adapters import make_candidate
from benchmarks.decision_models.contract import normalize_answers
from .data import digest, load
from .simulator import ACTIONS, PRIORITIES, plan_from_answers, reference_observations, request_for


def bind_arguments(obs):
    """A deliberately small, frozen parser shared by non-neural baselines.

    It handles a single named ticket and a subset of explicit contrast patterns.
    It does not consume task references or infer a missing priority from records.
    """
    text = obs["messages"][-1].lower()
    found = [(m.start(), m.group().upper()) for m in re.finditer(r"\bsyn-\d+\b", text)]
    ids = {t["id"] for t in obs["tickets"]}
    mentioned = [ticket for _, ticket in found if ticket in ids]
    ticket = mentioned[0] if len(set(mentioned)) == 1 else None
    if len(set(mentioned)) > 1:
        # A limited syntactic heuristic, not a reference-label lookup.
        positive = re.search(r"\b(?:read|display|inspect|fetch|look up|check)\s+(?:the\s+)?(?:record\s+for\s+)?(?:ticket\s+)?(syn-\d+)", text)
        if positive:
            start = positive.start()
            if not re.search(r"(?:not|don't)\s*$", text[max(0, start - 12):start]):
                ticket = positive[1].upper()
    values = re.findall(r"\b(low|normal|high)\b", text)
    priority = values[0] if len(set(values)) == 1 else None
    if len(set(values)) > 1:
        for pattern in (
            r"\b(?:to|with)\s+(?:priority\s+)?(low|normal|high)\b",
            r"\b(?:set|make)\b.*?\b(low|normal|high)\b",
            r"\buse\s+(low|normal|high)\b",
        ):
            match = re.search(pattern, text)
            if match:
                priority = match[1]
                break
    return ticket, priority


def rules_action(obs):
    previous = (obs.get("last_tool_result") or {}).get("result", {})
    if previous.get("status") == "blocked":
        return "handoff" if previous["reason"] in ("permission_denied", "ticket_locked", "invalid_schema") else "ask_user"
    text = obs["messages"][-1].lower()
    ticket, priority = bind_arguments(obs)
    if re.search(r"\b(delete|close|merge|owner|export|attachments|email|reopen|comment|cancel|download|audit history|create|callback)\b", text):
        return "handoff"
    if re.search(r"(?:operation|action|task|request).*(?:unspecified|not provided|haven't|haven.t|not yet)|(?:haven't|haven.t|not yet).*(?:operation|action|requested)|whether.*(?:lookup|read).*(?:update|change)|clarify my request", text):
        return "ask_user"
    readonly = bool(re.search(
        r"\bread.only\b|without (?:making|changing)|do not (?:change|update)|don't (?:apply|change)|not (?:set|asking.*modify)|keep .*unchanged|leave .*alone|preserv",
        text,
    ))
    writing = bool(re.search(r"\b(set|change|update|apply|assign|edit|record|replace|revise|move|amendment|make|correct)\b", text))
    reading = bool(re.search(r"\b(show|read|look up|retrieve|see|display|check|inspect|fetch|tell|readout|inquiry|information|details)\b|what priority", text))
    if readonly:
        writing, reading = False, True
    if not writing and not reading:
        return "ask_user"
    if ticket is None:
        return "ask_user"
    if writing and priority is None:
        return "ask_user"
    target = next(t for t in obs["tickets"] if t["id"] == ticket)
    if writing and (not obs["authorization"]["can_update"] or target["locked"]):
        return "handoff"
    return "set_priority" if writing else "read_ticket"


def features(obs):
    """Word/bigram counts plus observable permission and selected-ticket flags."""
    text = re.sub(r"syn-\d+", "ticketid", obs["messages"][-1].lower())
    words = re.findall(r"[a-z]+", text)
    tokens = words + [a + "_" + b for a, b in zip(words, words[1:])]
    ticket, priority = bind_arguments(obs)
    target = next((t for t in obs["tickets"] if t["id"] == ticket), None)
    tokens.extend([
        "permission_granted" if obs["authorization"]["can_update"] else "permission_denied",
        "ticket_bound" if ticket else "ticket_missing",
        "priority_bound" if priority else "priority_missing",
        "target_locked" if target and target["locked"] else "target_unlocked_or_missing",
    ])
    return collections.Counter(tokens)


class NaiveBayes:
    """Multinomial NB, alpha=1; fitted only on reference development states."""

    def __init__(self, training):
        self.counts = {label: collections.Counter() for label in ACTIONS}
        self.classes = collections.Counter()
        self.vocabulary = set()
        for obs, reference in training:
            label = reference["action"]
            counts = features(obs)
            self.classes[label] += 1
            self.counts[label].update(counts)
            self.vocabulary.update(counts)
        self.total = sum(self.classes.values())
        self.totals = {label: sum(counts.values()) for label, counts in self.counts.items()}

    def predict(self, obs):
        counts = features(obs)
        scores = {}
        for label in ACTIONS:
            score = math.log((self.classes[label] + 1) / (self.total + len(ACTIONS)))
            denominator = self.totals[label] + len(self.vocabulary)
            for word, count in counts.items():
                if word in self.vocabulary:
                    score += count * math.log((self.counts[label][word] + 1) / denominator)
            scores[label] = score
        maximum = max(scores.values())
        values = {label: math.exp(score - maximum) for label, score in scores.items()}
        total = sum(values.values())
        return {label: value / total for label, value in values.items()}


def baseline_response(obs, action_probabilities, *, random_arguments=None):
    request = request_for(obs, "baseline")
    ticket, priority = bind_arguments(obs)
    ticket_label = next((f"ticket_{i + 1}" for i, t in enumerate(obs["tickets"]) if t["id"] == ticket), "unspecified")
    choices = {"ticket": ticket_label, "priority": priority or "unspecified"}
    if random_arguments:
        choices = {key: random_arguments.choice(list(request["questions"][key]["criteria"]))
                   for key in choices}
    answers = {
        "action": {"choice": max(action_probabilities, key=action_probabilities.get),
                   "probabilities": action_probabilities, "type": "choice"},
    }
    for key, choice in choices.items():
        labels = request["questions"][key]["criteria"]
        answers[key] = {"choice": choice, "probabilities": {label: float(label == choice) for label in labels}, "type": "choice"}
    return normalize_answers({"answers": answers}, request["questions"])


def rule_plan(obs):
    action = rules_action(obs)
    probabilities = {label: float(label == action) for label in ACTIONS}
    return plan_from_answers(baseline_response(obs, probabilities), obs)


def create(name, device="cpu"):
    if name in ("strands", "laya"):
        fn, info, synchronize = make_candidate(name, device)

        def predict(obs):
            request = request_for(obs, info["model"])
            output = fn(request)
            if output.get("model") != info["model"]:
                raise ValueError("Model version mismatch")
            answers = normalize_answers(output, request["questions"])
            return plan_from_answers(answers, obs)

        return predict, info, synchronize
    development, manifest = load("development")
    training = [row for case in development for row in reference_observations(case)]
    counts = collections.Counter(reference["action"] for _, reference in training)
    majority = max(ACTIONS, key=lambda label: counts[label])
    nb = NaiveBayes(training) if name == "naive_bayes" else None
    if name not in ("rules", "majority", "random", "naive_bayes"):
        raise ValueError("Unknown workflow candidate")
    info = {
        "name": name, "model": f"workflow-{name}-v2", "device": "cpu",
        "development_sha256": manifest["files"]["development"]["sha256"],
        "fitted": name in ("majority", "naive_bayes"),
        "training_states": len(training) if name in ("majority", "naive_bayes") else 0,
        "configuration": {"alpha": 1, "features": "word+bigram+observable_flags"} if nb else {},
    }

    def predict(obs):
        rng = None
        if name == "rules":
            return rule_plan(obs)
        if nb:
            probabilities = nb.predict(obs)
        elif name == "majority":
            probabilities = {label: float(label == majority) for label in ACTIONS}
        else:
            rng = random.Random("workflow-random-v2:" + digest(obs))
            # Seeded random policy, not a max-probability tie presented as random.
            selected = rng.choice(list(ACTIONS))
            probabilities = {label: float(label == selected) for label in ACTIONS}
        return plan_from_answers(baseline_response(obs, probabilities, random_arguments=rng), obs)

    return predict, info, lambda: None

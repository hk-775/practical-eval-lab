"""Deliberately limited baselines and improved rules, not trained AI models."""

from __future__ import annotations

import hashlib
import json
import os
import re
from pathlib import Path

from .suites import suite_info
from .advanced import retrieve, judge_pair, run_agent
from .integrations import CandidateOutput


def classify(text: str, improved: bool = False) -> str:
    text = text.casefold()
    if improved and any(word in text for word in (
        "purchase", "buy ", "buying", "order a ", "request a new", "procure",
        "opening hours", "where is", "recycling", "donate", "donating",
    )):
        return "Other"
    software = ("application", "authentication", "browser", "client", "crash", "driver",
                "error", "excel", "install", "log in", "login", "password", "software",
                "update", "vpn", "windows")
    hardware = ("battery", "cable", "camera", "charger", "disk", "headset", "keyboard",
                "laptop", "monitor", "mouse", "printer", "screen")
    if any(word in text for word in software):
        return "Software"
    if any(word in text for word in hardware):
        return "Hardware"
    if improved and any(word in text for word in ("teclado", "pantalla", "webcam", "trackpad")):
        return "Hardware"
    return "Other"


def extract(text: str, improved: bool = False) -> dict:
    order = re.search(r"\b[A-Z]-\d{3}\b", text, re.I if improved else 0)
    if improved:
        match = re.search(r"\b(\d+|one|two|three|four|five)\s+(keyboards?|monitors?|mice|mouse|headsets?|cables?|webcams?)\b", text, re.I)
    else:
        match = re.search(r"\b(\d+)\s+(keyboards?|monitors?|mice|mouse|headsets?|cables?|webcams?)\b", text)
    quantity, item = None, None
    if match:
        number, item = match.groups()
        numbers = {"one": 1, "two": 2, "three": 3, "four": 4, "five": 5}
        quantity = int(number) if number.isdigit() else numbers[number.lower()]
        item = item.lower().removesuffix("s")
        if item == "mice":
            item = "mouse"
    lowered = text.lower()
    priority = "normal"
    if improved:
        if re.search(r"\b(?:not urgent|no rush|low priority|priority low)\b", lowered):
            priority = "low"
        elif re.search(r"\b(?:urgent|high priority|priority high|asap)\b", lowered):
            priority = "high"
    elif "high" in text or "urgent" in text:
        priority = "high"
    return {
        "order_id": order.group().upper() if order else None,
        "quantity": quantity,
        "item": item,
        "priority": priority,
    }


def choose_tool(text: str, improved: bool = False) -> dict:
    lower = text.lower()
    order = re.search(r"\b[A-Z]-\d{3}\b", text, re.I)
    no_action = {"tool": "no_action", "arguments": {}}
    if improved:
        if any(s in lower for s in ("cancel", "delete", "purchase", "ignore", "do not", "don't", "buy ")):
            return no_action
        if re.search(r"\b(?:create|open|file)\s+(?:a\s+)?(?:support\s+)?ticket\s*:", lower):
            summary = text.split(":", 1)[1].strip()
            return {"tool": "create_ticket", "arguments": {"category": classify(summary, True), "summary": summary}}
        if order and any(s in lower for s in ("status", "where", "track", "arrive", "shipped")):
            return {"tool": "lookup_order", "arguments": {"order_id": order.group().upper()}}
        return no_action
    if order:
        return {"tool": "lookup_order", "arguments": {"order_id": order.group().upper()}}
    if "ticket" in lower and ":" in text:
        summary = text.split(":", 1)[1].strip()
        return {"tool": "create_ticket", "arguments": {"category": classify(summary), "summary": summary}}
    return no_action


def make_candidate(suite: str, name: str, *, model: str | None = None, prompt: str | None = None):
    info = suite_info(suite)
    if name in ("baseline", "improved"):
        fn = {"classification": classify, "extraction": extract, "tool_calling": choose_tool,
              "rag": retrieve, "response_quality": judge_pair, "agent": run_agent}[suite]
        fingerprint = hashlib.sha256(Path(__file__).read_bytes() + Path(__file__).with_name("advanced.py").read_bytes()).hexdigest()
        return lambda text: fn(text, name == "improved"), {
            "name": name, "kind": "local_rules", "model": None, "source_hash": fingerprint,
        }
    if name != "openai":
        raise ValueError("Candidate must be baseline, improved, or openai")
    if not model or not os.environ.get("OPENAI_API_KEY"):
        raise ValueError("Live runs require an explicit model and OPENAI_API_KEY")
    try:
        from openai import OpenAI
    except ImportError as exc:
        raise ValueError("Install the optional adapter with uv sync --locked --extra openai") from exc
    client = OpenAI(timeout=30, max_retries=0)
    instruction = prompt or info["prompt"]

    def run(text):
        response = client.responses.create(
            model=model,
            input=[{"role": "developer", "content": instruction}, {"role": "user", "content": text if isinstance(text, str) else json.dumps(text, ensure_ascii=False)}],
        )
        usage = response.usage
        return CandidateOutput(response.output_text.strip(), {
            "input_tokens": usage.input_tokens, "output_tokens": usage.output_tokens,
            "total_tokens": usage.total_tokens,
        } if usage else {}, {"model": response.model, "response_id": response.id})

    return run, {"name": name, "kind": "live_model", "model": model, "prompt": instruction}

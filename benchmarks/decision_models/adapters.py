"""Lightweight baseline and optional hosted API; local models import lazily."""

from __future__ import annotations

import math
import os
import re
from urllib.error import HTTPError, URLError
from urllib.request import Request, build_opener, HTTPRedirectHandler

from .contract import read_json, ROOT


class CandidateError(RuntimeError):
    """Safe error code: never include a URL, credential, response body, or state."""


class NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        raise CandidateError("redirect_rejected")


def lexical(request):
    tokens = set(re.findall(r"[a-z]{3,}", request["state"].lower()))
    answers = {}
    for key, question in request["questions"].items():
        scores = {}
        for label, description in question["criteria"].items():
            words = set(re.findall(r"[a-z]{3,}", (label + " " + description).lower()))
            scores[label] = math.exp(4 * len(words & tokens) / max(1, math.sqrt(len(words) * len(tokens))))
        total = sum(scores.values())
        probabilities = {label: value / total for label, value in scores.items()}
        choice = max(sorted(probabilities), key=probabilities.get)
        answers[key] = {"type": "choice", "choice": choice, "probabilities": probabilities}
    return {"model": request["model"], "answers": answers, "usage": {}}


class Jev:
    def __init__(self, spec):
        self.spec = spec
        self.token = os.environ.get(spec["token_env"])
        if not self.token:
            raise CandidateError("jev_not_run_missing_api_key")
        self.opener = build_opener(NoRedirect())

    def __call__(self, request):
        import json
        req = Request(self.spec["url"], data=json.dumps(request, allow_nan=False).encode(),
                      headers={"Content-Type": "application/json",
                               "Authorization": "Bearer " + self.token}, method="POST")
        try:
            with self.opener.open(req, timeout=60) as response:
                raw = response.read(2_000_001)
        except HTTPError as exc:
            raise CandidateError(f"http_{exc.code}") from None
        except (URLError, TimeoutError, OSError):
            raise CandidateError("transport_error") from None
        if len(raw) > 2_000_000:
            raise CandidateError("response_too_large")
        try:
            return json.loads(raw)
        except (ValueError, UnicodeError):
            raise CandidateError("invalid_json") from None


def make_candidate(name, device="cpu"):
    models = read_json(ROOT / "models.json")
    if name not in ("baseline", "strands", "laya", "jev"):
        raise ValueError("Unknown candidate")
    info = {"name": name, **models[name], "device": device if name in ("strands", "laya") else "cpu" if name == "baseline" else "remote"}
    if name == "baseline":
        return lexical, info, lambda: None
    if name == "jev":
        # Keep endpoint and environment-variable name out of report identity.
        fn = Jev(models[name])
        info.pop("url")
        info.pop("token_env")
        return fn, info, lambda: None
    from .local_models import load_local
    return load_local(name, info)

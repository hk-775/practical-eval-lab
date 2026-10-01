"""Explicit, trusted candidate registrations. Secrets are environment references."""

from __future__ import annotations

import hashlib
import importlib
import inspect
import json
import os
import re
from dataclasses import dataclass, field
from pathlib import Path
from urllib.parse import urlsplit
from urllib.request import HTTPRedirectHandler, Request, build_opener


@dataclass
class CandidateOutput:
    output: object
    usage: dict = field(default_factory=dict)
    metadata: dict = field(default_factory=dict)


def load_project(path: Path | None):
    if path is None:
        return {}
    project = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(project, dict) or set(project) != {"schema_version", "candidates"} or type(project["schema_version"]) is not int or project["schema_version"] != 1:
        raise ValueError("Project requires schema_version: 1 and candidates")
    entries = project["candidates"]
    if not isinstance(entries, dict) or not 1 <= len(entries) <= 20:
        raise ValueError("Register 1–20 candidates")
    for name, spec in entries.items():
        if not re.fullmatch(r"[a-zA-Z0-9_-]{1,60}", name) or name in ("baseline", "improved", "openai"):
            raise ValueError("Candidate names must be distinct from built-ins and use letters, numbers, _ or -")
        validate_spec(spec)
    return entries


def validate_spec(spec):
    if not isinstance(spec, dict):
        raise ValueError("Candidate configuration must be an object")
    allowed = {
        "python": {"kind", "target", "options", "suites"},
        "http": {"kind", "url", "token_env", "timeout", "suites"},
        "openai": {"kind", "model", "prompt", "suites"},
    }
    kind = spec.get("kind")
    if not isinstance(kind, str) or kind not in allowed or set(spec) - allowed[kind]:
        raise ValueError("Unknown candidate kind or configuration field")
    if "suites" in spec:
        from .suites import CATALOG
        if not isinstance(spec["suites"], list) or not spec["suites"] or any(not isinstance(s, str) or s not in CATALOG for s in spec["suites"]):
            raise ValueError("suites must list known suite IDs")
    if kind == "python":
        if not isinstance(spec.get("target"), str) or not re.fullmatch(r"[a-zA-Z_]\w*(?:\.[a-zA-Z_]\w*)*:[a-zA-Z_]\w*", spec["target"]):
            raise ValueError("Python target must be module:function")
        if not isinstance(spec.get("options", {}), dict):
            raise ValueError("Python options must be an object")
    elif kind == "http":
        url = spec.get("url")
        if not isinstance(url, str):
            raise ValueError("HTTP candidate requires a URL")
        parsed = urlsplit(url)
        if parsed.scheme not in ("http", "https") or not parsed.hostname or parsed.username or parsed.password or parsed.query or parsed.fragment:
            raise ValueError("Use an HTTP(S) URL without credentials, query, or fragment; credentials belong in token_env")
        if parsed.scheme == "http" and parsed.hostname not in ("localhost", "127.0.0.1", "::1"):
            raise ValueError("Remote endpoints require HTTPS")
        timeout = spec.get("timeout", 30)
        if type(timeout) not in (int, float) or not 0 < timeout <= 120:
            raise ValueError("HTTP timeout must be >0 and <=120 seconds")
        env = spec.get("token_env")
        if env is not None and (not isinstance(env, str) or not re.fullmatch(r"[A-Z_][A-Z0-9_]*", env)):
            raise ValueError("token_env must name an environment variable")
    elif not isinstance(spec.get("model"), str) or not spec["model"].strip() or ("prompt" in spec and not isinstance(spec["prompt"], str)):
        raise ValueError("OpenAI candidates require an explicit model and optional text prompt")


class NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        raise ValueError("Candidate endpoint redirects are disabled")


def configured_candidate(suite, name, spec):
    validate_spec(spec)
    if suite not in spec.get("suites", [suite]):
        raise ValueError(f"Candidate {name} is not registered for {suite}")
    config_hash = hashlib.sha256(json.dumps(spec, sort_keys=True).encode()).hexdigest()
    info = {"name": name, "kind": spec["kind"], "config_hash": config_hash}
    if spec["kind"] == "openai":
        from .candidates import make_candidate
        fn, model_info = make_candidate(suite, "openai", model=spec["model"], prompt=spec.get("prompt"))
        return fn, {**model_info, **info}
    if spec["kind"] == "python":
        module, function = spec["target"].split(":")
        try:
            fn = getattr(importlib.import_module(module), function)
        except (ImportError, AttributeError) as exc:
            raise ValueError(f"Cannot load Python candidate {name}; install its module on PYTHONPATH") from exc
        if not callable(fn):
            raise ValueError("Python target is not callable")
        try:
            source = inspect.getsourcefile(fn)
            if source:
                info["source_hash"] = hashlib.sha256(Path(source).read_bytes()).hexdigest()
        except (OSError, TypeError):
            pass
        return lambda value: fn(value, **spec.get("options", {})), info
    env = spec.get("token_env")
    if env and not os.environ.get(env):
        raise ValueError(f"Missing environment variable {env}")
    opener = build_opener(NoRedirect())
    def request(value):
        headers = {"Content-Type": "application/json"}
        if env:
            headers["Authorization"] = f"Bearer {os.environ[env]}"
        req = Request(spec["url"], data=json.dumps({"input": value}, allow_nan=False).encode(), headers=headers)
        with opener.open(req, timeout=spec.get("timeout", 30)) as response:
            raw = response.read(2_000_001)
        if len(raw) > 2_000_000:
            raise ValueError("Endpoint response exceeded 2 MB")
        payload = json.loads(raw)
        if not isinstance(payload, dict) or "output" not in payload or set(payload) - {"output", "usage", "metadata"}:
            raise ValueError("Endpoint must return output, with optional usage and metadata")
        return CandidateOutput(payload["output"], payload.get("usage", {}), payload.get("metadata", {}))
    return request, info

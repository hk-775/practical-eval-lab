"""Local overrides never modify the bundled teaching datasets."""

from __future__ import annotations

import json
import threading
from pathlib import Path

from .core import digest, load_cases, threshold_value, validate_cases
from .suites import settings_for, suite_info


class Conflict(ValueError):
    pass


def validate_config(suite: str, config: dict) -> dict:
    if not isinstance(config, dict) or set(config) != {"cases", "settings", "threshold"}:
        raise ValueError("A tuning profile must contain exactly cases, settings, and threshold")
    return {
        "cases": validate_cases(suite, config["cases"]),
        "settings": settings_for(suite, config["settings"]),
        "threshold": threshold_value(config["threshold"]),
    }


class LocalStore:
    def __init__(self, root: Path):
        self.root = root
        self.lock = threading.RLock()

    def path(self, suite):
        suite_info(suite)
        return self.root / "profiles" / f"{suite}.json"

    def load(self, suite):
        with self.lock:
            path = self.path(suite)
            config = validate_config(suite, json.loads(path.read_text())) if path.exists() else {
                "cases": load_cases(suite), "settings": settings_for(suite), "threshold": .8,
            }
            return {"config": config, "revision": digest(config), "saved": path.exists()}

    def save(self, suite, config, expected_revision):
        with self.lock:
            config = validate_config(suite, config)
            old = self.load(suite)
            if expected_revision != old["revision"]:
                raise Conflict("This profile changed in another window. Reload it before saving.")
            history = self.root / "history" / suite
            history.mkdir(parents=True, exist_ok=True)
            (history / f"{old['revision']}.json").write_text(json.dumps(old["config"], indent=2) + "\n")
            path = self.path(suite)
            path.parent.mkdir(parents=True, exist_ok=True)
            temp = path.with_suffix(".tmp")
            temp.write_text(json.dumps(config, indent=2, ensure_ascii=False) + "\n")
            temp.replace(path)
            return self.load(suite)

    def reset(self, suite, expected_revision):
        with self.lock:
            self.save(suite, {"cases": load_cases(suite), "settings": settings_for(suite), "threshold": .8}, expected_revision)
            self.path(suite).unlink()
            return self.load(suite)

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
    if not isinstance(config, dict) or set(config) not in ({"cases", "settings", "threshold"}, {"schema_version", "suite", "cases", "settings", "threshold"}):
        raise ValueError("A tuning profile requires cases, settings, threshold, and optional schema_version/suite")
    if "schema_version" in config and (type(config["schema_version"]) is not int or config["schema_version"] != 2 or config["suite"] != suite):
        raise ValueError("Profile must use schema_version 2 and match the selected suite")
    return {
        "schema_version": 2, "suite": suite,
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
            config = validate_config(suite, json.loads(path.read_text(encoding="utf-8"))) if path.exists() else {
                "schema_version": 2, "suite": suite,
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
            (history / f"{old['revision']}.json").write_text(json.dumps(old["config"], indent=2) + "\n", encoding="utf-8")
            path = self.path(suite)
            path.parent.mkdir(parents=True, exist_ok=True)
            temp = path.with_suffix(".tmp")
            temp.write_text(json.dumps(config, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
            temp.replace(path)
            return self.load(suite)

    def reset(self, suite, expected_revision):
        with self.lock:
            self.save(suite, {"cases": load_cases(suite), "settings": settings_for(suite), "threshold": .8}, expected_revision)
            self.path(suite).unlink()
            return self.load(suite)

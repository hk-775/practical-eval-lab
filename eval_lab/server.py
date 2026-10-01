"""Loopback-only tuning server with explicit candidate registrations."""

from __future__ import annotations

import argparse
import json
import os
import sys
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlparse

from .core import compare_reports, load_cases, run_eval
from .integrations import load_project
from .reports import ReportStore, html_report, validate_report, MAX_REPORT_BYTES
from .store import Conflict, LocalStore, validate_config
from .suites import CATALOG, settings_for, suite_info

ROOT = Path(__file__).resolve().parent.parent
WEB = Path(__file__).resolve().parent / "web"


def default_state_dir():
    if os.environ.get("EVAL_LAB_HOME"):
        return Path(os.environ["EVAL_LAB_HOME"]).expanduser()
    # Preserve source-checkout profiles; installed wheels use a writable user directory.
    if (ROOT / "pyproject.toml").is_file() and (ROOT / "eval_lab").is_dir():
        return ROOT / "local"
    if sys.platform == "win32":
        return Path(os.environ.get("LOCALAPPDATA", str(Path.home() / "AppData" / "Local"))) / "PracticalEvalLab"
    if sys.platform == "darwin":
        return Path.home() / "Library" / "Application Support" / "PracticalEvalLab"
    return Path(os.environ.get("XDG_DATA_HOME", str(Path.home() / ".local" / "share"))) / "practical-eval-lab"


def make_server(port=8000, state_dir=None, project=None):
    store = LocalStore(Path(state_dir) if state_dir else default_state_dir())
    runs = ReportStore(store.root)
    # Only registrations loaded by the local operator are available to the browser.
    registrations = load_project(Path(project)) if project else {}
    if any(spec["kind"] == "openai" for spec in registrations.values()):
        raise ValueError("Live OpenAI judging is CLI-only; use a separate project file for the webpage")

    def allowed(suite, candidate):
        if not isinstance(candidate, str) or candidate not in ("baseline", "improved") and candidate not in registrations:
            raise ValueError("Select a bundled candidate or one registered with --project")
        if candidate in registrations and suite not in registrations[candidate].get("suites", [suite]):
            raise ValueError("Candidate is not registered for this suite")

    def persist(report, imported=False):
        report = validate_report(report)
        return {**report, "run_id": runs.save(report, imported=imported), "imported": imported}

    class Handler(SimpleHTTPRequestHandler):
        def __init__(self, *args, **kwargs):
            super().__init__(*args, directory=str(WEB), **kwargs)

        def send_json(self, data, status=200):
            body = json.dumps(data, ensure_ascii=False, allow_nan=False).encode()
            self.send_response(status)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.send_header("Cache-Control", "no-store")
            self.end_headers()
            self.wfile.write(body)

        def end_headers(self):
            self.send_header("X-Content-Type-Options", "nosniff")
            self.send_header("Content-Security-Policy", "default-src 'self'; script-src 'self'; style-src 'self' 'unsafe-inline'; connect-src 'self'; img-src 'self' data:; object-src 'none'; frame-ancestors 'none'; base-uri 'self'")
            super().end_headers()

        def do_GET(self):
            if self.headers.get("Host", "").split(":")[0] not in ("127.0.0.1", "localhost"):
                self.send_json({"error": "Use localhost or 127.0.0.1"}, 400)
                return
            path = urlparse(self.path)
            if not path.path.startswith("/api/"):
                if path.path.endswith("/") and path.path != "/":
                    self.send_error(404)
                    return
                return super().do_GET()
            try:
                suite = parse_qs(path.query).get("suite", ["classification"])[0]
                if path.path == "/api/health":
                    self.send_json({"status": "ok", "mode": "local"})
                elif path.path == "/api/suites":
                    self.send_json({"suites": [{"id": key, **value, "dev_count": len(load_cases(key)), "holdout_count": len(load_cases(key, "holdout"))} for key, value in CATALOG.items()]})
                elif path.path == "/api/candidates":
                    self.send_json({"candidates": [{"name": "baseline", "kind": "local_rules"}, {"name": "improved", "kind": "local_rules"}] +
                                    [{"name": name, "kind": spec["kind"]} for name, spec in registrations.items() if suite in spec.get("suites", [suite])]})
                elif path.path == "/api/runs":
                    self.send_json({"runs": runs.list()})
                elif path.path == "/api/report":
                    record = runs.load(parse_qs(path.query).get("id", [""])[0])
                    self.send_json({**record["report"], "run_id": record["id"], "imported": record["imported"]})
                elif path.path == "/api/config":
                    self.send_json(store.load(suite))
                elif path.path == "/api/holdout":
                    self.send_json({"cases": load_cases(suite, "holdout"), "settings": settings_for(suite), "threshold": .8})
                else:
                    self.send_json({"error": "Unknown route"}, 404)
            except (ValueError, OSError) as exc:
                self.send_json({"error": str(exc)}, 400)

        def read_json(self):
            origin = self.headers.get("Origin")
            host = self.headers.get("Host", "")
            if origin and origin != f"http://{host}":
                raise ValueError("Cross-origin writes are disabled")
            if host.split(":")[0] not in ("127.0.0.1", "localhost"):
                raise ValueError("Use localhost or 127.0.0.1")
            if self.headers.get_content_type() != "application/json":
                raise ValueError("Content-Type must be application/json")
            try:
                length = int(self.headers.get("Content-Length", "0"))
            except ValueError as exc:
                raise ValueError("Invalid Content-Length") from exc
            if not 0 < length <= MAX_REPORT_BYTES:
                raise ValueError("Request must contain 1 byte–20 MB")
            self.connection.settimeout(10)
            payload = json.loads(self.rfile.read(length))
            if not isinstance(payload, dict):
                raise ValueError("Request must be a JSON object")
            return payload

        def do_POST(self):
            try:
                payload = self.read_json()
                route = urlparse(self.path).path
                suite = payload.get("suite", "classification")
                if not isinstance(suite, str):
                    raise ValueError("suite must be a string")
                suite_info(suite)
                if route == "/api/save":
                    self.send_json(store.save(suite, payload.get("config"), payload.get("revision")))
                elif route == "/api/reset":
                    self.send_json(store.reset(suite, payload.get("revision")))
                elif route == "/api/validate-profile":
                    self.send_json(validate_config(suite, payload.get("config")))
                elif route == "/api/import-report":
                    self.send_json(persist(payload.get("report"), imported=True))
                elif route == "/api/export-html":
                    self.send_json({"html": html_report(payload.get("report"))})
                elif route == "/api/compare-runs":
                    records = [runs.load(payload.get(k)) for k in ("before", "after")]
                    reports = [record["report"] for record in records]
                    self.send_json(persist(compare_reports(*(r.get("after", r) for r in reports)),
                                           imported=any(record["imported"] for record in records)))
                elif route in ("/api/run", "/api/compare"):
                    split = payload.get("split", "dev")
                    if split not in ("dev", "holdout"):
                        raise ValueError("Unknown split")
                    if split == "holdout":
                        config = {"cases": load_cases(suite, split), "settings": settings_for(suite), "threshold": .8}
                    else:
                        validated = validate_config(suite, payload.get("config"))
                        config = {k: validated[k] for k in ("cases", "settings", "threshold")}
                    config.update(project=registrations, trials=payload.get("trials", 1), gates=payload.get("gates"))
                    if route == "/api/compare":
                        before_name, after_name = payload.get("before", "baseline"), payload.get("after", "improved")
                        allowed(suite, before_name)
                        allowed(suite, after_name)
                        before = run_eval(suite, before_name, split, **config)
                        after = run_eval(suite, after_name, split, **config)
                        self.send_json(persist(compare_reports(before, after)))
                    else:
                        candidate = payload.get("candidate", "baseline")
                        allowed(suite, candidate)
                        self.send_json(persist(run_eval(suite, candidate, split, **config)))
                else:
                    self.send_json({"error": "Unknown route"}, 404)
            except Conflict as exc:
                self.send_json({"error": str(exc)}, 409)
            except (ValueError, TypeError, OSError) as exc:
                self.send_json({"error": str(exc)}, 400)
            except Exception:
                self.send_json({"error": "The local server encountered an unexpected error."}, 500)

    return ThreadingHTTPServer(("127.0.0.1", port), Handler)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--port", type=int, default=8000)
    parser.add_argument("--state-dir", type=Path)
    parser.add_argument("--project", type=Path, help="Trusted Python/HTTP candidate registrations; endpoints may incur costs")
    args = parser.parse_args(argv)
    try:
        server = make_server(args.port, args.state_dir, args.project)
    except (ValueError, OSError) as exc:
        print(f"Cannot start lab: {exc}", file=sys.stderr)
        return 2
    print(f"Practical Eval Lab: http://127.0.0.1:{server.server_port}", flush=True)
    print("Offline examples + attributed human preferences · Ctrl+C to stop", flush=True)
    if args.project:
        print("Registered candidates enabled; running them invokes your configured code/endpoints.", flush=True)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()
    return 0

"""Loopback-only tuning server. Live model calls are deliberately CLI-only."""

from __future__ import annotations

import argparse
import json
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlparse

from .core import compare_reports, load_cases, run_eval
from .store import Conflict, LocalStore, validate_config
from .suites import CATALOG, settings_for, suite_info

ROOT = Path(__file__).resolve().parent.parent


def make_server(port=8000, state_dir=None):
    store = LocalStore(Path(state_dir) if state_dir else ROOT / "local")

    class Handler(SimpleHTTPRequestHandler):
        def __init__(self, *args, **kwargs):
            super().__init__(*args, directory=str(ROOT / "web"), **kwargs)

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
            if not 0 < length <= 1_000_000:
                raise ValueError("Request must contain 1–1,000,000 bytes")
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
                elif route in ("/api/run", "/api/compare"):
                    split = payload.get("split", "dev")
                    if split not in ("dev", "holdout"):
                        raise ValueError("Unknown split")
                    if split == "holdout":
                        config = {"cases": load_cases(suite, split), "settings": settings_for(suite), "threshold": .8}
                    else:
                        config = validate_config(suite, payload.get("config"))
                    if route == "/api/compare":
                        before = run_eval(suite, "baseline", split, **config)
                        after = run_eval(suite, "improved", split, **config)
                        self.send_json(compare_reports(before, after))
                    else:
                        candidate = payload.get("candidate", "baseline")
                        if candidate not in ("baseline", "improved"):
                            raise ValueError("The webpage runs local candidates only")
                        self.send_json(run_eval(suite, candidate, split, **config))
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
    args = parser.parse_args(argv)
    server = make_server(args.port, args.state_dir)
    print(f"Practical Eval Lab: http://127.0.0.1:{server.server_port}", flush=True)
    print("Synthetic examples · Local rules · Ctrl+C to stop", flush=True)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()
    return 0

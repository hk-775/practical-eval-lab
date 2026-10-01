"""A tiny application exposing the same behavior as a callable and an HTTP API."""

from __future__ import annotations

import argparse
import json
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

from .candidates import classify


def classify_ticket(text, version="v1"):
    if version not in ("v1", "v2"):
        raise ValueError("version must be v1 or v2")
    if not isinstance(text, str):
        raise ValueError("Ticket input must be text")
    return classify(text, improved=version == "v2")


def make_server(port=8765):
    class Handler(BaseHTTPRequestHandler):
        def do_POST(self):
            try:
                if self.path not in ("/v1/classify", "/v2/classify"):
                    self.send_error(404)
                    return
                size = int(self.headers.get("Content-Length", 0))
                if not 0 < size <= 50000:
                    raise ValueError("Invalid request size")
                self.connection.settimeout(10)
                payload = json.loads(self.rfile.read(size))
                if not isinstance(payload, dict) or set(payload) != {"input"}:
                    raise ValueError("Send a JSON object containing input")
                output = classify_ticket(payload["input"], self.path.split("/")[1])
                data = json.dumps({"output": output}).encode()
                self.send_response(200)
            except (ValueError, TypeError):
                data = b'{"error":"Invalid classification request"}'
                self.send_response(400)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(data)))
            self.end_headers()
            self.wfile.write(data)

        def log_message(self, *_):
            pass
    return ThreadingHTTPServer(("127.0.0.1", port), Handler)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--port", type=int, default=8765)
    args = parser.parse_args()
    server = make_server(args.port)
    print(f"Demo application: http://127.0.0.1:{server.server_port}", flush=True)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()


if __name__ == "__main__":
    main()

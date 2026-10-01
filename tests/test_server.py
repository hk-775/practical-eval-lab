import json
import threading
from urllib.error import HTTPError
from urllib.request import Request, urlopen

import pytest

from eval_lab.core import run_eval
from eval_lab.server import make_server


@pytest.fixture
def local_server(tmp_path):
    server = make_server(0, tmp_path)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    yield f"http://127.0.0.1:{server.server_port}"
    server.shutdown()
    server.server_close()
    thread.join()


def request(base, route, data=None, headers=None):
    headers = {"Content-Type": "application/json", **(headers or {})}
    req = Request(base + route, data=json.dumps(data).encode() if data is not None else None, headers=headers)
    try:
        with urlopen(req) as response:
            return response.status, json.loads(response.read())
    except HTTPError as exc:
        return exc.code, json.loads(exc.read())


def test_api_uses_shared_runner_and_persists_profiles(local_server):
    _, profile = request(local_server, "/api/config?suite=classification")
    config = profile["config"]
    status, comparison = request(local_server, "/api/compare", {"suite": "classification", "config": config})
    assert status == 200
    assert comparison["after"]["score"] == run_eval("classification", "improved")["score"]
    config["threshold"] = .95
    status, saved = request(local_server, "/api/save", {"suite": "classification", "config": config, "revision": profile["revision"]})
    assert status == 200
    assert request(local_server, "/api/config?suite=classification")[1] == saved
    assert request(local_server, "/api/save", {"suite": "classification", "config": config, "revision": profile["revision"]})[0] == 409


def test_holdout_ignores_development_edits(local_server):
    status, report = request(local_server, "/api/run", {"suite": "extraction", "split": "holdout", "candidate": "improved", "config": {"threshold": 0}})
    assert status == 200 and report["total"] == 10 and report["threshold"] == .8


@pytest.mark.parametrize("payload", [
    [], {"suite": "../../etc/passwd"}, {"suite": []},
    {"candidate": "openai", "config": {}}, {"config": {}},
])
def test_bad_api_requests_fail_without_crashing(local_server, payload):
    assert request(local_server, "/api/run", payload)[0] == 400
    assert request(local_server, "/api/health")[0] == 200


def test_cross_origin_writes_rejected(local_server):
    status, _ = request(local_server, "/api/run", {}, {"Origin": "https://example.invalid"})
    assert status == 400


def test_web_root_does_not_expose_profiles(local_server):
    with urlopen(local_server + "/") as response:
        assert b"Practical Eval Lab" in response.read()
        assert "frame-ancestors 'none'" in response.headers["Content-Security-Policy"]
    with pytest.raises(HTTPError) as exc:
        urlopen(local_server + "/../pyproject.toml")
    assert exc.value.code == 404

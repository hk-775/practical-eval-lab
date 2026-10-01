import json
import threading
from urllib.error import HTTPError
from urllib.request import Request, urlopen

import pytest

from eval_lab.core import run_eval
from eval_lab.server import make_server
from eval_lab.demo_app import make_server as make_demo_server
from eval_lab.integrations import configured_candidate


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


def test_saved_reports_survive_reopen_and_support_import_and_html(local_server):
    _, profile = request(local_server, "/api/config?suite=classification")
    status, run = request(local_server, "/api/run", {"config": profile["config"], "candidate": "improved"})
    assert status == 200 and run["run_id"]
    assert request(local_server, "/api/report?id=" + run["run_id"])[1] == run
    status, imported = request(local_server, "/api/import-report", {"report": run})
    assert status == 200 and imported["imported"]
    history = request(local_server, "/api/runs")[1]["runs"]
    assert len(history) == 2
    status, html = request(local_server, "/api/export-html", {"report": imported})
    assert status == 200 and "Standalone report" in html["html"]
    status, comparison = request(local_server, "/api/compare-runs", {"before": run["run_id"], "after": imported["run_id"]})
    assert status == 200 and comparison["delta"] == 0 and comparison["imported"]
    assert request(local_server, "/api/report?id=../../outside")[0] == 400


def test_get_requests_reject_untrusted_host(local_server):
    assert request(local_server, "/api/config", headers={"Host": "untrusted.invalid"})[0] == 400


def test_browser_cannot_register_or_invoke_arbitrary_python(local_server):
    _, profile = request(local_server, "/api/config")
    payload = {"config": profile["config"], "candidate": "os:system", "project": {"os:system": {"kind": "python"}}}
    assert request(local_server, "/api/run", payload)[0] == 400
    assert request(local_server, "/api/candidates")[1]["candidates"] == [
        {"name": "baseline", "kind": "local_rules"}, {"name": "improved", "kind": "local_rules"}]


def test_http_adapter_evaluates_real_local_application():
    server = make_demo_server(0)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        url = f"http://127.0.0.1:{server.server_port}/v2/classify"
        fn, info = configured_candidate("classification", "application", {"kind": "http", "url": url})
        assert fn("My keyboard is broken").output == "Hardware"
        report = run_eval("classification", runner=fn)
        assert report["score"] == 1 and report["execution_errors"] == 0
        assert info["kind"] == "http"
    finally:
        server.shutdown()
        server.server_close()
        thread.join()


def test_operator_registered_candidate_runs_through_web_api(tmp_path):
    server = make_server(0, tmp_path, "examples/python-project.json")
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    base = f"http://127.0.0.1:{server.server_port}"
    try:
        names = {c["name"] for c in request(base, "/api/candidates")[1]["candidates"]}
        assert {"app-v1", "app-v2"} <= names
        _, profile = request(base, "/api/config")
        status, output = request(base, "/api/compare", {"config": profile["config"], "before": "app-v1", "after": "app-v2"})
        assert status == 200 and output["after"]["score"] == 1
        assert output["after"]["candidate"]["kind"] == "python"
        assert request(base, "/api/run", {"suite": "agent", "split": "holdout", "candidate": "app-v2"})[0] == 400
    finally:
        server.shutdown()
        server.server_close()
        thread.join()

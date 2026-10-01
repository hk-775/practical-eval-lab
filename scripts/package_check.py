"""Build wheel/sdist and exercise each installed artifact outside the source tree."""

from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path


def main():
    with tempfile.TemporaryDirectory() as temporary:
        root = Path(temporary)
        artifacts = root / "dist"
        subprocess.run(["uv", "build", "--out-dir", str(artifacts)], check=True)
        for artifact in sorted(artifacts.iterdir()):
            if not artifact.name.endswith((".whl", ".tar.gz")):
                continue
            environment = root / ("sdist-env" if artifact.name.endswith(".tar.gz") else "wheel-env")
            subprocess.run(["uv", "venv", "--python", sys.executable, str(environment)], check=True)
            python = environment / ("Scripts/python.exe" if os.name == "nt" else "bin/python")
            subprocess.run(["uv", "pip", "install", "--python", str(python), "--no-deps", str(artifact)], check=True)
            env = dict(os.environ, EVAL_LAB_HOME=str(root / "state"))
            env.pop("PYTHONPATH", None)
            output = subprocess.run([str(python), "-c", """
import json, threading
from urllib.request import urlopen
from eval_lab.core import run_eval
from eval_lab.suites import CATALOG
from eval_lab.server import make_server
from eval_lab.reports import html_report
for suite in CATALOG:
    report = run_eval(suite, 'improved')
    assert report['execution_errors'] == 0
    assert 'Standalone report' in html_report(report)
server = make_server(0)
thread = threading.Thread(target=server.serve_forever, daemon=True)
thread.start()
try:
    base = 'http://127.0.0.1:' + str(server.server_port)
    assert b'Practical Eval Lab' in urlopen(base).read()
    assert len(json.load(urlopen(base + '/api/suites'))['suites']) == 6
    assert b'const state' in urlopen(base + '/app.js').read()
finally:
    server.shutdown(); server.server_close(); thread.join()
print('Installed artifact verified')
"""], cwd=root, env=env, check=True, capture_output=True, text=True)
            print(artifact.name, output.stdout.strip())
            executable = environment / ("Scripts/eval-lab.exe" if os.name == "nt" else "bin/eval-lab")
            subprocess.run([str(executable), "run", "--candidate", "improved"], cwd=root, env=env,
                           check=True, stdout=subprocess.DEVNULL)


if __name__ == "__main__":
    main()

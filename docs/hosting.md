# GitHub Pages and the local lab

The public website combines the six walkthroughs, incident case studies, a local
architecture diagram, and a viewer for actual recorded eval runs. It uses the same
result-rendering components as the Python tuning webpage.

[Open the website](https://hk-775.github.io/practical-eval-lab/).

## What you can do on the website

- Choose any of the six suites and its development or holdout recording.
- Compare the recorded baseline and changed candidate, or inspect either one.
- Filter failures and regressions, expand grader checks, and inspect tag slices.
- Inspect recorded timing, usage coverage, and other measurements.
- Download the original JSON evidence or a standalone HTML report.
- Read the walkthroughs and follow the primary sources in the incident studies.

These are recordings of local rules, not new model calls or benchmark claims.
Five suites contain synthetic examples; response quality contains a small
[attributed human-preference sample](data-provenance.md). The website does not
edit cases, execute candidates, accept API keys, or save experiments. It uses no
browser storage, analytics, external fonts, private APIs, or WebSockets.

## Run the complete tuning lab

The Python application provides editing, candidate execution, saved profiles,
report imports, and experiment history:

```bash
git clone https://github.com/hk-775/practical-eval-lab.git
cd practical-eval-lab
uv sync --locked
uv run --locked eval-lab serve
```

Open `http://127.0.0.1:8000`. The local application continues to use its loopback
Python API; it does not inherit the website's recorded-results mode.
See [application integrations](integrations.md) to register your own candidates.

## Build and verify the static site

From a source checkout:

```bash
uv sync --locked
uv run --locked python -m scripts.build_pages
uv run --locked playwright install chromium
uv run --locked python -m scripts.pages_check --site site
```

The default base path is `/practical-eval-lab/`. The browser check serves the exact
output beneath that prefix, including nested guide routes. To preview it manually
at the server root, build with `--base-path /`:

```bash
uv run --locked python -m scripts.build_pages --base-path /
uv run --locked python -m http.server 8080 --directory site --bind 127.0.0.1
```

The builder copies an explicit set of source guides, recorded reports, notices,
and assets into ignored `site/`. It never copies local profiles, credentials,
arbitrary files, or the source checkout wholesale. Assets are fingerprinted.
`site-manifest.json` records the published paths and SHA-256 hashes.
Markdown rendering is a development/build dependency; the runner still has no
required third-party runtime dependency.

## Deployment

The GitHub Pages workflow builds and browser-tests pull requests. On `main`, it
uploads only the generated site and deploys through the `github-pages` environment.
Only the deployment job receives `pages: write` and `id-token: write`; there is no
AWS deployment or model access. All Actions are pinned to full commit SHAs.

The browser test exercises the explorer, all walkthroughs, report downloads,
incident navigation, architecture downloads, and mobile layout. It checks that
requests stay within the site's base path, use static GETs, and create no
WebSockets. A missing public viewer script fails closed rather than falling back
to the local API.

To stop hosting, disable GitHub Pages in the repository's **Settings → Pages**.
The source repository and local application remain available.

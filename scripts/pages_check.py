"""Verify the static artifact and browser behavior under a GitHub Pages prefix."""

from __future__ import annotations

import argparse
import functools
import hashlib
import json
import shutil
import tempfile
import threading
import xml.etree.ElementTree as ET
from html.parser import HTMLParser
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import unquote, urljoin, urlsplit

from playwright.sync_api import expect, sync_playwright

import markdown

from .build_pages import DEFAULT_BASE, DOCUMENTS, GUIDES, ORIGIN, ROOT, normalize_base


class Links(HTMLParser):
    def __init__(self):
        super().__init__()
        self.links, self.ids = [], set()
        self.link_tags, self.structured_data, self.json_parts = {}, [], None

    def handle_starttag(self, tag, attrs):
        values = dict(attrs)
        if "id" in values:
            self.ids.add(values["id"])
        if tag == "link" and values.get("rel"):
            self.link_tags.setdefault(values["rel"], []).append(values)
        if tag == "script" and values.get("type") == "application/ld+json":
            self.json_parts = []
        key = {"a": "href", "link": "href", "script": "src", "img": "src"}.get(tag)
        if key and values.get(key):
            self.links.append(values[key])

    def handle_data(self, data):
        if self.json_parts is not None:
            self.json_parts.append(data)

    def handle_endtag(self, tag):
        if tag == "script" and self.json_parts is not None:
            self.structured_data.append(json.loads("".join(self.json_parts)))
            self.json_parts = None


def verify_discovery(site, base_path, parsed):
    public = ORIGIN + base_path
    discovery = json.loads((site / "discovery.json").read_text(encoding="utf-8"))
    assert discovery["website"] == public
    allowed = {*DOCUMENTS, "AGENTS.md", "docs/incident-case-studies.md", "scripts/build_pages.py"}
    documents = set()
    for record in discovery["documents"]:
        assert record["source"] in allowed
        assert record["source_sha256"] == hashlib.sha256((ROOT / record["source"]).read_bytes()).hexdigest()
        assert record["markdown_url"].startswith(public)
        name = record["markdown_url"][len(public):]
        content = (site / name).read_bytes()
        assert hashlib.sha256(content).hexdigest() == record["sha256"], name
        assert len(content) == record["bytes"]
        documents.add(name)
    assert len(documents) >= len(DOCUMENTS) + 5
    for name in documents | {"llms.txt"}:
        parser = Links()
        parser.feed(markdown.markdown((site / name).read_text(encoding="utf-8"),
                                     extensions=["fenced_code", "tables"]))
        for target in parser.links:
            if target.startswith(public):
                relative = unquote(urlsplit(target).path[len(base_path):]) or "index.html"
                assert (site / relative).is_file(), f"Broken Markdown link in {name}: {target}"
    entries = {element.text for element in ET.parse(site / "sitemap.xml").iter(
        "{http://www.sitemaps.org/schemas/sitemap/0.9}loc")}
    expected = set()
    for name, parser in parsed.items():
        if name == "404.html" or name.startswith("reports/"):
            continue
        canonical = public + ("" if name == "index.html" else name)
        expected.add(canonical)
        assert [link["href"] for link in parser.link_tags["canonical"]] == [canonical]
        alternate = parser.link_tags["alternate"][0]
        assert alternate["type"] == "text/markdown"
        assert alternate["href"] == base_path + name.removesuffix(".html") + ".md"
        assert name.removesuffix(".html") + ".md" in documents
        assert parser.link_tags["describedby"][0]["href"] == base_path + "llms.txt"
        data, = parser.structured_data
        assert data["@type"] == "WebPage" and data["url"] == canonical
        assert data["about"]["codeRepository"] == discovery["repository"]
        assert data["about"]["author"]["name"] == "Harleen Kaur"
    assert entries == expected
    digest = (site / "agent-context.txt").read_text(encoding="utf-8")
    assert "Anthropic" in digest and "not production model quality" in digest
    assert len(digest.encode("utf-8")) < 200_000


def verify_artifact(site, base_path):
    manifest = json.loads((site / "site-manifest.json").read_text(encoding="utf-8"))
    assert manifest["base_path"] == base_path and manifest["mode"] == "recorded-results"
    parsed = {}
    for name, digest in manifest["files"].items():
        path = site / name
        assert hashlib.sha256(path.read_bytes()).hexdigest() == digest, f"Artifact changed: {name}"
        assert not any(p in {".git", ".venv", "local", ".env", "__pycache__"} for p in path.relative_to(site).parts)
        if path.suffix == ".html":
            parser = Links()
            parser.feed(path.read_text(encoding="utf-8"))
            parsed[name] = parser
    assert len(parsed) >= 20
    origin = "https://pages.example.invalid"
    for name, parser in parsed.items():
        for target in parser.links:
            url = urlsplit(urljoin(origin + base_path + name, target))
            if url.scheme not in ("http", "https") or url.netloc != "pages.example.invalid":
                continue
            assert url.path.startswith(base_path), f"Escaped base path in {name}: {target}"
            relative = unquote(url.path[len(base_path):])
            relative = relative + "index.html" if not relative or relative.endswith("/") else relative
            assert (site / relative).is_file(), f"Broken static link in {name}: {target}"
            if url.fragment and relative in parsed:
                assert unquote(url.fragment) in parsed[relative].ids, f"Broken anchor in {name}: {target}"
    verify_discovery(site, base_path, parsed)
    print(f"Static artifact verified: {len(manifest['files'])} files; internal links and anchors resolve.")


def check_browser(base, screenshots=None):
    base_url = urlsplit(base)
    with tempfile.TemporaryDirectory() as downloads, sync_playwright() as playwright:
        browser = playwright.chromium.launch()
        context = browser.new_context(viewport={"width": 1440, "height": 1050})
        violations, errors, failed, sockets = [], [], [], []

        def inspect(request):
            if request.url.startswith("blob:"):
                return
            url = urlsplit(request.url)
            if (url.scheme, url.netloc) != (base_url.scheme, base_url.netloc) or not url.path.startswith(base_url.path):
                violations.append(f"Outside public site: {request.url}")
            if request.method != "GET" or "/api/" in url.path:
                violations.append(f"Unexpected request: {request.method} {request.url}")

        context.on("request", inspect)
        context.on("page", lambda page: page.on("pageerror", lambda error: errors.append(str(error))))
        context.on("requestfailed", lambda request: failed.append(request.url))
        context.on("response", lambda response: failed.append(f"{response.status} {response.url}") if response.status >= 400 else None)
        page = context.new_page()
        page.on("websocket", lambda socket: sockets.append(socket.url))
        try:
            page.goto(base)
            expect(page.locator("#status")).to_contain_text("Ready.")
            expect(page.locator('link[rel="canonical"]')).to_have_attribute(
                "href", ORIGIN + base_url.path)
            # Agents can retrieve complete text and provenance without running the UI.
            for filename in ("llms.txt", "agent-context.txt", "discovery.json", "sitemap.xml", "guides/rag.md"):
                response = page.request.get(base + filename)
                assert response.status == 200, filename
                assert len(response.body()) > 100, filename
            assert "not production model quality" in page.request.get(base + "index.md").text()
            expect(page.locator("#viewer-heading")).to_contain_text("Explore evidence.")
            expect(page.locator("#threshold")).to_be_disabled()
            expect(page.locator(".tune-panel")).to_be_hidden()
            expect(page.locator(".history-panel")).to_be_hidden()
            expect(page.locator(".experiment-options")).to_be_hidden()
            for suite, score, delta, count in (
                ("classification", "100%", "+30 pp", 20), ("extraction", "100%", "+50 pp", 20),
                ("tool_calling", "100%", "+40 pp", 20), ("rag", "100%", "+75 pp", 8),
                ("response_quality", "83.3%", "+33 pp", 6), ("agent", "100%", "+50 pp", 8),
            ):
                page.locator("#suite").select_option(suite)
                expect(page.locator("#status")).to_contain_text("Ready.")
                page.locator("#compare").click()
                expect(page.locator("#score")).to_have_text(score)
                expect(page.locator("#change")).to_have_text(delta)
                expect(page.locator("#results-body tr")).to_have_count(count)
                expect(page.locator("#report-origin")).to_contain_text("Recorded offline experiment")
                page.locator("#results-body .output-cell details").first.locator("summary").click()
                expect(page.locator("#results-body .output-cell details").first).to_have_attribute("open", "")
            page.locator("#suite").select_option("tool_calling")
            page.locator("#split").select_option("holdout")
            page.locator("#compare").click()
            expect(page.locator("#score")).to_have_text("80%")
            page.locator("#filter").select_option("regressed")
            expect(page.locator("#results-body tr")).to_have_count(1)
            with page.expect_download() as download:
                page.locator("#download-report").click()
            json_path = Path(downloads) / "report.json"
            download.value.save_as(json_path)
            report = json.loads(json_path.read_text(encoding="utf-8"))
            assert report["regressed"] == 1 and report["after"]["suite"] == "tool_calling"
            page.locator("#candidate").select_option("baseline")
            page.locator("#run").click()
            expect(page.locator("#score")).to_have_text("50%")
            with page.expect_download() as download:
                page.locator("#download-html").click()
            html_path = Path(downloads) / "baseline.html"
            download.value.save_as(html_path)
            saved = html_path.read_text(encoding="utf-8")
            assert "baseline" in saved and "Standalone report" in saved and "Candidate comparison" not in saved
            page.locator("#suite").select_option("response_quality")
            page.locator("#compare").click()
            expect(page.locator("#score")).to_have_text("16.7%")
            expect(page.locator("#change")).to_have_text("-17 pp")
            with page.expect_download() as download:
                page.locator("#download-html").click()
            html_path = Path(downloads) / "human.html"
            download.value.save_as(html_path)
            assert "Anthropic" in html_path.read_text(encoding="utf-8")
            page.goto(base + "?suite=rag")
            expect(page.locator("#suite")).to_have_value("rag")
            page.locator("#compare").click()
            if screenshots:
                screenshots.mkdir(parents=True, exist_ok=True)
                page.screenshot(path=str(screenshots / "explorer-desktop.png"), full_page=True)
            page.get_by_role("link", name="Guides", exact=True).click()
            expect(page.locator(".lesson-card")).to_have_count(6)
            for slug in GUIDES.values():
                page.goto(base + f"guides/{slug}.html")
                expect(page.locator("article.prose")).to_be_visible()
                expect(page.locator("pre")).not_to_have_count(0)
                page.reload()  # Nested routes resolve directly without SPA rewrites.
                expect(page.locator("article.prose")).to_be_visible()
            page.get_by_role("link", name="Inspect the holdout").click()
            expect(page.locator("#suite")).to_have_value("agent")
            expect(page.locator("#split")).to_have_value("holdout")
            page.locator("#compare").click()
            expect(page.locator("#score")).to_have_text("100%")
            page.goto(base + "guides/rag.html")
            if screenshots:
                page.screenshot(path=str(screenshots / "guide-desktop.png"), full_page=True)
            page.get_by_role("link", name="Incidents", exact=True).click()
            expect(page.locator("article.incident-card")).to_have_count(6)
            page.locator("#air-canada").get_by_role("link", name="Explore related recording").click()
            expect(page.locator("#suite")).to_have_value("rag")
            page.get_by_role("link", name="Architecture", exact=True).click()
            expect(page.locator("img.architecture-image")).to_be_visible()
            page.locator("img.architecture-image").evaluate("image => image.decode()")
            assert page.locator("img.architecture-image").evaluate("image => image.complete && image.naturalWidth > 0")
            with page.expect_download() as download:
                page.get_by_role("link", name="Download editable diagram").click()
            diagram = Path(downloads) / "pipeline.drawio"
            download.value.save_as(diagram)
            assert "<mxfile" in diagram.read_text(encoding="utf-8")
            page.goto(base + "guides.html")
            page.get_by_role("link", name="Decision model benchmark", exact=True).click()
            expect(page.locator("article.prose")).to_contain_text("Choice only")
            page.get_by_role("link", name="Recorded results: 2 October 2026", exact=True).click()
            expect(page.locator("article.prose")).to_contain_text("64 unique decisions")
            expect(page.locator("article.prose")).to_contain_text("Jev")
            expect(page.locator("article.prose")).to_contain_text("Not run")
            if screenshots:
                page.screenshot(path=str(screenshots / "decision-model-results-desktop.png"), full_page=True)
            page.set_viewport_size({"width": 390, "height": 844})
            for route in ("", "guides.html", "guides/rag.html", "getting-started.html", "incidents.html", "architecture.html", "results.html", "notices.html", "decision-models.html", "decision-model-results.html"):
                page.goto(base + route)
                assert page.evaluate("document.documentElement.scrollWidth <= innerWidth"), f"Mobile overflow: {route}"
            if screenshots:
                page.screenshot(path=str(screenshots / "decision-model-results-mobile.png"), full_page=True)
            page.goto(base)
            expect(page.locator("#status")).to_contain_text("Ready.")
            page.locator("#compare").click()
            expect(page.locator("#score")).to_have_text("100%")
            if screenshots:
                page.screenshot(path=str(screenshots / "explorer-mobile.png"), full_page=True)
            assert page.evaluate("localStorage.length === 0 && sessionStorage.length === 0")
            assert not violations, violations
            assert not errors, errors
            assert not failed, failed
            assert not sockets, sockets

            # Fail closed if the public adapter cannot load: never try the Python API.
            blocked = context.new_page()
            await_errors = []
            blocked.on("pageerror", lambda error: await_errors.append(str(error)))
            blocked.route("**/public-*.js", lambda route: route.fulfill(status=200, content_type="text/javascript", body="/* unavailable */"))
            blocked.goto(base)
            expect(blocked.locator("#status")).to_contain_text("could not load")
            assert not violations, violations
            assert not await_errors, await_errors
            blocked.close()
            print("Pages browser checks passed: six teaching recordings, decision model results, guides, exports, incidents, architecture, mobile, and no APIs or external requests.")
        finally:
            browser.close()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--site", type=Path, default=Path("site"))
    parser.add_argument("--base-path", default=DEFAULT_BASE)
    parser.add_argument("--url", help="Verify an already-deployed site instead of starting a server")
    parser.add_argument("--screenshots", type=Path)
    args = parser.parse_args()
    base_path = normalize_base(args.base_path)
    verify_artifact(args.site, base_path)
    if args.url:
        check_browser(args.url.rstrip("/") + "/", args.screenshots)
        return
    with tempfile.TemporaryDirectory() as temporary:
        root = Path(temporary)
        target = root / base_path.strip("/") if base_path != "/" else root
        shutil.copytree(args.site, target, dirs_exist_ok=True)

        class QuietHandler(SimpleHTTPRequestHandler):
            def log_message(self, *_):
                pass

        server = ThreadingHTTPServer(("127.0.0.1", 0), functools.partial(QuietHandler, directory=str(root)))
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        try:
            check_browser(f"http://127.0.0.1:{server.server_port}{base_path}", args.screenshots)
        finally:
            server.shutdown()
            server.server_close()
            thread.join()


if __name__ == "__main__":
    main()

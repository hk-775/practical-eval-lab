"""CI browser check against the real local webpage, using isolated temporary state."""

from __future__ import annotations

import argparse
import json
import tempfile
import threading
from pathlib import Path

from playwright.sync_api import expect, sync_playwright

from eval_lab.server import make_server


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--screenshots", type=Path)
    args = parser.parse_args()
    with tempfile.TemporaryDirectory() as state_dir, sync_playwright() as playwright:
        server = make_server(0, state_dir)
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        origin = f"http://127.0.0.1:{server.server_port}"
        browser = playwright.chromium.launch()
        try:
            page = browser.new_page(viewport={"width": 1440, "height": 1000})
            errors, external, failures, sockets = [], [], [], []
            page.on("pageerror", lambda error: errors.append(str(error)))
            page.on("request", lambda request: external.append(request.url) if not request.url.startswith(origin + "/") and not request.url.startswith("blob:") else None)
            page.on("requestfailed", lambda request: failures.append(request.url))
            page.on("websocket", lambda socket: sockets.append(socket.url))
            page.on("dialog", lambda dialog: dialog.accept())
            page.goto(origin)
            expect(page.locator("#status")).to_contain_text("Ready.")
            page.locator("#compare").click()
            expect(page.locator("#score")).to_have_text("100%")
            expect(page.locator("#change")).to_have_text("+30 pp")
            page.locator("#filter").select_option("changed")
            expect(page.locator("#results-body tr")).to_have_count(6)
            page.locator("#case-expected").fill("Other")
            page.get_by_role("button", name="Save tuning", exact=True).click()
            expect(page.locator("#save-state")).to_have_text("Saved local profile")
            page.reload()
            expect(page.locator("#save-state")).to_have_text("Saved local profile")
            expect(page.locator("#case-expected")).to_have_value("Other")
            page.locator("#compare").click()
            expect(page.locator("#score")).to_have_text("95%")
            page.locator("#filter").select_option("failed")
            expect(page.locator("#results-body tr")).to_have_count(1)
            page.locator("#results-body summary").click()
            expect(page.locator("#results-body details")).to_contain_text("label")
            with page.expect_download() as downloaded:
                page.get_by_role("button", name="Export profile", exact=True).click()
            profile_path = Path(state_dir) / "export.json"
            downloaded.value.save_as(profile_path)
            profile = json.loads(profile_path.read_text())
            assert profile["cases"][0]["expected"] == "Other"
            page.get_by_role("button", name="Restore bundled defaults").click()
            expect(page.locator("#save-state")).to_have_text("Bundled defaults")
            page.locator("#import").set_input_files(profile_path)
            expect(page.locator("#status")).to_contain_text("Profile imported")
            expect(page.locator("#case-expected")).to_have_value("Other")
            page.get_by_role("button", name="Restore bundled defaults").click()
            expect(page.locator("#case-expected")).to_have_value("Hardware")
            page.locator("#suite").select_option("extraction")
            expect(page.locator("#grader-name")).to_have_text("Schema + field values")
            page.locator("#case-expected").fill("{broken")
            page.get_by_role("button", name="Save tuning", exact=True).click()
            expect(page.locator("#status")).to_contain_text("valid JSON")
            page.get_by_role("button", name="Restore bundled defaults").click()
            expect(page.locator("#save-state")).to_have_text("Bundled defaults")
            page.locator("#compare").click()
            expect(page.locator("#change")).to_have_text("+50 pp")
            page.locator("#suite").select_option("tool_calling")
            expect(page.locator("#grader-name")).to_have_text("Tool + arguments + outcome")
            page.locator("#split").select_option("holdout")
            expect(page.locator("#holdout-note")).to_be_visible()
            page.locator("#compare").click()
            expect(page.locator("#score")).to_have_text("80%")
            page.locator("#filter").select_option("regressed")
            expect(page.locator("#results-body tr")).to_have_count(1)
            with page.expect_download() as downloaded:
                page.get_by_role("button", name="Download report").click()
            report_path = Path(state_dir) / "report.json"
            downloaded.value.save_as(report_path)
            assert json.loads(report_path.read_text())["regressed"] == 1
            page.locator("#split").select_option("dev")
            page.locator("#compare").click()
            expect(page.locator("#score")).to_have_text("100%")
            page.locator("#filter").select_option("all")
            for suite, score, rows in (("rag", "100%", 8), ("response_quality", "83.3%", 6), ("agent", "100%", 8)):
                page.locator("#suite").select_option(suite)
                expect(page.locator("#input-label")).to_have_text("Input · JSON object")
                page.locator("#compare").click()
                expect(page.locator("#score")).to_have_text(score)
                expect(page.locator("#results-body tr")).to_have_count(rows)
                page.locator("#results-body .ticket-cell summary").first.click()
                expect(page.locator("#results-body .ticket-cell details").first).to_have_attribute("open", "")
                page.locator(".measurement-panel summary").click()
                expect(page.locator("#measurements")).to_contain_text("Candidate latency")
                page.locator(".measurement-panel summary").click()
            with page.expect_download() as downloaded:
                page.locator("#download-html").click()
            html_path = Path(state_dir) / "report.html"
            downloaded.value.save_as(html_path)
            assert "agent" in html_path.read_text(encoding="utf-8")
            page.reload()
            expect(page.locator("#status")).to_contain_text("Ready.")
            page.locator("#open-run").click()
            expect(page.locator("#report-context")).to_contain_text("agent")
            page.locator("#import-report").set_input_files(report_path)
            expect(page.locator("#status")).to_contain_text("Report imported")
            expect(page.locator("#report-origin")).to_be_visible()
            expect(page.locator("#report-context")).to_contain_text("tool_calling")
            page.locator("#compare-runs").click()
            expect(page.locator("#status")).to_contain_text("Cannot compare")
            page.locator("#suite").select_option("rag")
            expect(page.locator("#grader-name")).to_have_text("Retrieval + reference + evidence")
            page.locator("#compare").click()
            expect(page.locator("#score")).to_have_text("100%")
            if args.screenshots:
                args.screenshots.mkdir(parents=True, exist_ok=True)
                page.screenshot(path=str(args.screenshots / "desktop.png"), full_page=True)
            page.set_viewport_size({"width": 390, "height": 844})
            assert page.evaluate("document.documentElement.scrollWidth <= window.innerWidth"), "Mobile page overflows"
            if args.screenshots:
                page.screenshot(path=str(args.screenshots / "mobile.png"), full_page=True)
            page.get_by_role("link", name="Learn from public incidents").click()
            expect(page.locator("article.incident-card")).to_have_count(6)
            expect(page.locator("#gpt4o-sycophancy")).to_contain_text("specific deployment evaluations")
            assert page.evaluate("document.documentElement.scrollWidth <= window.innerWidth"), "Incident page overflows on mobile"
            if args.screenshots:
                page.screenshot(path=str(args.screenshots / "incidents-mobile.png"), full_page=True)
            page.locator("#air-canada").get_by_role("link", name="Open related eval").click()
            expect(page.locator("#suite")).to_have_value("rag")
            expect(page.locator("#status")).to_contain_text("Ready.")
            assert not errors, errors
            assert not external, external
            assert not failures, failures
            assert not sockets, sockets
            # The portable artifact is usable without the API or any external resources.
            artifact = browser.new_page()
            artifact.goto(html_path.as_uri())
            expect(artifact.locator("h1")).to_contain_text("agent")
            expect(artifact.locator("article.case")).to_have_count(8)
            artifact.close()
            print("Browser checks passed: six suites, tuning, saved runs, JSON/HTML reports, measurements, mobile layout, no external requests.")
        finally:
            browser.close()
            server.shutdown()
            server.server_close()
            thread.join()


if __name__ == "__main__":
    main()

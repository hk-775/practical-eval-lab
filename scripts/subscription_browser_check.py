"""Verify the offline subscription viewer using an isolated Chromium context."""

import argparse
import re
import tempfile
from pathlib import Path

from playwright.sync_api import expect, sync_playwright

from benchmarks.subscription_workflow.reporting import render_html
from benchmarks.subscription_workflow.runner import evaluate


def check(html_path=None, screenshots=None, *, url=None):
    target = url or html_path.resolve().as_uri()
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch()
        errors, requests = [], []
        try:
            page = browser.new_page(viewport={"width": 1440, "height": 1050})
            page.on("pageerror", lambda error: errors.append(str(error)))
            def inspect(request):
                if request.url.startswith(("http:", "https:", "ws:", "wss:")) and (
                    request.url != target or request.method != "GET"
                ):
                    requests.append(f"{request.method} {request.url}")
            page.on("request", inspect)
            page.on("websocket", lambda socket: requests.append(socket.url))
            response = page.goto(target)
            if url:
                assert response.status == 200, "Published report failed to load"
            expect(page.locator("#controls")).to_be_visible()
            expect(page.locator("#outcome")).to_contain_text("Unsafe effects: 1.")
            page.locator("#profile").select_option("invariants")
            expect(page.locator("#outcome")).to_contain_text("Unsafe effects: 0.")
            page.locator("#next").click()
            expect(page.locator("#proposal")).to_contain_text("billing.cancel")
            page.locator("#previous").focus()
            page.keyboard.press("Enter")
            expect(page.locator("#position")).to_have_text(re.compile(r"Step 1 of \d+"))
            page.locator(".diagram-scroll").scroll_into_view_if_needed()
            page.wait_for_function("document.querySelector('.flow-line').getAnimations().length > 0")
            offset = lambda: page.locator(".flow-line").first.evaluate(
                "el => getComputedStyle(el).strokeDashoffset")
            first = offset()
            page.wait_for_timeout(160)
            assert offset() != first, "Connector does not move"
            page.locator("#motion").focus()
            page.keyboard.press("Enter")
            page.wait_for_function(
                "document.querySelector('.flow-line').getAnimations().every(a => !a.pending && a.playState === 'paused')")
            stopped = offset()
            page.wait_for_timeout(160)
            assert offset() == stopped, "Pause did not hold the visual state"
            page.keyboard.press("Enter")
            page.wait_for_timeout(160)
            assert offset() != stopped, "Resume did not restore motion"
            if screenshots:
                screenshots.mkdir(parents=True, exist_ok=True)
                page.screenshot(path=str(screenshots / "subscription-desktop.png"), full_page=True)
            page.emulate_media(reduced_motion="reduce")
            expect(page.locator("#motion")).to_be_disabled()
            assert page.locator(".flow-line").first.evaluate("el => el.getAnimations().length") == 0
            page.emulate_media(media="print")
            assert page.locator(".flow-line").first.evaluate("el => el.getAnimations().length") == 0
            page.emulate_media(media="screen", reduced_motion="no-preference")
            page.set_viewport_size({"width": 390, "height": 844})
            page.locator("#profile").select_option("permissions")
            expect(page.locator("#outcome")).to_contain_text("Unsafe effects: 1.")
            assert page.evaluate("document.documentElement.scrollWidth <= innerWidth"), "Mobile overflow"
            if screenshots:
                page.screenshot(path=str(screenshots / "subscription-mobile.png"), full_page=True)
            no_js = browser.new_context(java_script_enabled=False)
            static = no_js.new_page()
            static.on("request", inspect)
            static.goto(target)
            expect(static.locator("table tbody tr")).to_have_count(4)
            expect(static.locator("body")).to_contain_text("Business invariants")
            expect(static.locator("#controls")).to_be_hidden()
            assert static.locator(".flow-line").first.evaluate("el => el.getAnimations().length") == 0
            no_js.close()
            assert not errors, errors
            assert not requests, requests
            print("Subscription viewer passed: real motion, keyboard pause/resume, reduced motion, "
                  "trace playback, mobile, print, no-JS, and no external requests.")
        finally:
            browser.close()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    source = parser.add_mutually_exclusive_group()
    source.add_argument("--html", type=Path)
    source.add_argument("--url", help="Verify the same controls on a published report")
    parser.add_argument("--screenshots", type=Path)
    args = parser.parse_args()
    if args.html or args.url:
        check(args.html, args.screenshots, url=args.url)
    else:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "subscription.html"
            path.write_text(render_html(evaluate("development")), encoding="utf-8")
            check(path, args.screenshots)


if __name__ == "__main__":
    main()

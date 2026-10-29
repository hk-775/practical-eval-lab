"""Check the recorded RSI viewer in an isolated browser; never run an experiment."""

import argparse
from pathlib import Path

from playwright.sync_api import expect, sync_playwright


def check(html_path, screenshots=None):
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch()
        errors, external = [], []
        try:
            page = browser.new_page(viewport={"width": 1440, "height": 1000})
            page.on("pageerror", lambda error: errors.append(str(error)))
            page.on("request", lambda request: external.append(request.url)
                    if request.url.startswith(("http:", "https:", "ws:", "wss:")) else None)
            page.goto(html_path.resolve().as_uri())
            expect(page.locator("#results tbody tr")).to_have_count(3)
            expect(page.locator("#position")).to_have_text("Generation 0 of 8")
            page.locator("#next").click()
            expect(page.locator("#position")).to_have_text("Generation 1 of 8")
            expect(page.locator("#proposals")).to_contain_text("strategy_used")
            page.locator("#previous").focus()
            page.keyboard.press("Enter")
            expect(page.locator("#position")).to_have_text("Generation 0 of 8")
            page.locator("#arm").select_option("fixed_agent")
            expect(page.locator("#optimizer")).to_contain_text('"edit_width": 1')
            page.locator("#arm").select_option("recursive_optimizer")
            page.locator("#diagram").scroll_into_view_if_needed()
            page.wait_for_function(
                "document.querySelector('#diagram').classList.contains('running')")
            offset = lambda: page.locator(".flow-line").first.evaluate(
                "el => getComputedStyle(el).strokeDashoffset")
            first = offset()
            page.wait_for_timeout(180)
            assert offset() != first, "Flow did not move"
            page.locator("#motion").focus()
            page.keyboard.press("Enter")
            page.wait_for_function(
                "document.querySelector('.flow-line').getAnimations().every("
                "a => !a.pending && a.playState === 'paused')")
            stopped = offset()
            page.wait_for_timeout(180)
            assert offset() == stopped, "Pause did not hold"
            page.keyboard.press("Enter")
            page.wait_for_timeout(180)
            assert offset() != stopped, "Resume did not restore motion"
            if screenshots:
                screenshots.mkdir(parents=True, exist_ok=True)
                page.screenshot(path=str(screenshots / "rsi-desktop.png"), full_page=True)
            page.emulate_media(reduced_motion="reduce")
            expect(page.locator("#motion")).to_be_disabled()
            assert page.locator(".flow-line").first.evaluate("el => el.getAnimations().length") == 0
            page.emulate_media(media="print")
            assert page.locator(".flow-line").first.evaluate("el => el.getAnimations().length") == 0
            page.emulate_media(media="screen", reduced_motion="no-preference")
            page.set_viewport_size({"width": 390, "height": 844})
            assert page.evaluate("document.documentElement.scrollWidth <= innerWidth"), "Mobile overflow"
            if screenshots:
                page.screenshot(path=str(screenshots / "rsi-mobile.png"), full_page=True)
            no_js = browser.new_context(java_script_enabled=False)
            static = no_js.new_page()
            static.goto(html_path.resolve().as_uri())
            expect(static.locator("#results tbody tr")).to_have_count(3)
            expect(static.locator("#controls")).to_be_hidden()
            assert static.locator(".flow-line").first.evaluate("el => el.getAnimations().length") == 0
            no_js.close()
            assert not errors, errors
            assert not external, external
            print("RSI viewer passed: lineage navigation, actual motion, keyboard pause/resume, "
                  "reduced motion, mobile, print, no-JS, and no external requests.")
        finally:
            browser.close()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--html", type=Path, required=True)
    parser.add_argument("--screenshots", type=Path)
    args = parser.parse_args()
    check(args.html, args.screenshots)


if __name__ == "__main__":
    main()

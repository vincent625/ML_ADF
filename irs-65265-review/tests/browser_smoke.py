"""Optional Playwright check against an already running disposable/resettable app."""
import argparse
import json
from pathlib import Path

from playwright.sync_api import expect, sync_playwright


def verify(url: str, output: Path):
    output.mkdir(parents=True, exist_ok=True)
    with sync_playwright() as driver:
        browser = driver.chromium.launch(headless=True)
        page = browser.new_page(viewport={"width": 1366, "height": 900})
        errors = []
        page.on("pageerror", lambda error: errors.append(str(error)))
        page.on("console", lambda message: errors.append(message.text) if message.type == "error" else None)
        reset = page.request.post(url + "/api/reset", data={})
        assert reset.ok, reset.text()
        page.goto(url)
        expect(page.locator("#metrics")).to_contain_text("83")
        expect(page.get_by_text("5 / 11 comments loaded", exact=True)).to_be_visible()
        page.screenshot(path=str(output / "laptop-sources.png"), full_page=True)
        page.locator('[data-tab="requirements"]').click()
        page.locator('[data-requirement="R05"]').click()
        expect(page.locator(".sticky")).to_contain_text("cancelled")
        page.locator('[data-requirement="R09"]').click()
        expect(page.locator(".sticky")).to_contain_text("motorhead hotspot for V0.0.3")
        page.locator('[data-tab="components"]').click()
        page.locator("#scenario").select_option("stale-script")
        expect(page.locator("#content")).to_contain_text("fixture drift")
        page.screenshot(path=str(output / "laptop-components.png"), full_page=True)
        page.locator("#scenario").select_option("wrong-primer")
        page.locator('[data-tab="runner"]').click()
        page.locator("#run").click()
        expect(page.locator("#notice")).to_contain_text("finished")
        page.locator("#preview-patch").click()
        expect(page.locator("#patch-diff")).to_contain_text('-  "dna_pool_2": "100093901"')
        page.locator("#reviewer").fill("Browser verification")
        page.locator("#approve").check()
        page.locator('#review-form button[type="submit"]').click()
        expect(page.locator("#review-dialog")).not_to_be_visible()
        expect(page.locator("#metrics")).to_contain_text("0 fail / 1 stale")
        page.locator("#run").click()
        expect(page.locator("#metrics")).to_contain_text("84")
        expect(page.locator("#metrics")).to_contain_text("0 fail / 0 stale")
        page.locator("#test-filter").select_option("qc")
        page.locator('[data-test="dna:suppressed"]').click()
        expect(page.locator(".grid > .card").first).to_contain_text('"cnv_qc": "fail"')
        expect(page.locator(".grid > .card").first).to_contain_text("matches the explicit simulated QC context")
        page.locator('[data-test="dna:msi-qcfail"]').click()
        expect(page.locator(".grid > .card").first).to_contain_text('"sample_qc": "fail"')
        page.screenshot(path=str(output / "laptop-qc.png"), full_page=True)
        page.locator("#scenario").select_option("stale-pass")
        page.locator('[data-tab="impact"]').click()
        page.locator("#parameter-reviewer").fill("Browser verification")
        page.locator("#parameter-approve").check()
        page.locator("#change-parameter").click()
        expect(page.locator("#metrics")).to_contain_text("0 fail / 3 stale")
        expect(page.locator("#change-parameter")).to_be_disabled()
        page.locator("#go-runner").click()
        page.locator("#test-filter").select_option("attention")
        expect(page.locator(".test-table tbody tr")).to_have_count(3)
        page.screenshot(path=str(output / "laptop-stale.png"), full_page=True)
        page.locator("#run").click()
        expect(page.locator("#metrics")).to_contain_text("1 fail / 0 stale")
        page.locator("#preview-patch").click()
        page.locator("#reviewer").fill("Browser verification")
        page.locator("#approve").check()
        page.locator('#review-form button[type="submit"]').click()
        expect(page.locator("#review-dialog")).not_to_be_visible()
        page.locator("#run").click()
        expect(page.locator("#metrics")).to_contain_text("0 fail / 0 stale")
        page.locator('[data-tab="export"]').click()
        with page.expect_download() as download_info:
            page.locator("#export-json").click()
        download = download_info.value
        export_path = output / download.suggested_filename
        download.save_as(export_path)
        report = json.loads(export_path.read_text())
        live = page.request.get(url + "/api/state?scenario=stale-pass").json()
        assert report["sandbox"]["latest"]["id"] == live["latest"]["id"]
        assert report["sandbox"]["summary"] == {"pass": 84}
        # Visit every chapter at laptop and narrow widths, checking page-level overflow.
        layout_results = []
        for width, height in ((1366, 900), (390, 844)):
            page.set_viewport_size({"width": width, "height": height})
            for chapter in ("sources", "requirements", "components", "runner", "impact", "export"):
                page.locator(f'[data-tab="{chapter}"]').click()
                overflow = page.evaluate("document.documentElement.scrollWidth > innerWidth")
                assert not overflow, f"Horizontal page overflow at {width}px / {chapter}"
                layout_results.append({"width": width, "height": height, "chapter": chapter, "overflow": False})
            page.locator('[data-tab="runner"]').click()
            page.screenshot(path=str(output / f"runner-{width}.png"), full_page=True)
        assert not errors, errors
        result = {"browser": browser.version, "console_or_page_errors": errors,
                  "review_fix_retest": "passed", "qc_controls": "passed",
                  "stale_3_unrelated_81_retained": "passed", "export_identity": "passed",
                  "layouts": layout_results, "export_run_id": live["latest"]["id"]}
        (output / "browser-results.json").write_text(json.dumps(result, indent=2) + "\n")
        print(json.dumps(result, indent=2))
        browser.close()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--url", default="http://127.0.0.1:8765")
    parser.add_argument("--output", type=Path, default=Path("demo_data/verification"))
    args = parser.parse_args()
    verify(args.url.rstrip("/"), args.output)

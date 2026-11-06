"""Optional live local UI verification. No source-system writes or human approvals."""
import json
import base64
import os
import time
from pathlib import Path
from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "runs/verification"
OUT.mkdir(parents=True, exist_ok=True)
errors, external_requests = [], []
with sync_playwright() as p:
    print("Launching Chrome for local UI verification", flush=True)
    browser = p.chromium.launch(headless=False, executable_path="/usr/bin/google-chrome", args=["--headless=new", "--no-sandbox", "--disable-dev-shm-usage", "--disable-gpu"])
    print("Chrome launched", flush=True)
    page = browser.new_page(viewport={"width": 1440, "height": 1000}, accept_downloads=True)
    page.set_default_timeout(15000)
    print("Browser page created", flush=True)
    def capture(name):
        # Direct browser capture avoids this host's stalled frame-stability wait.
        session = page.context.new_cdp_session(page)
        size = session.send("Page.getLayoutMetrics")["cssContentSize"]
        result = session.send("Page.captureScreenshot", {"format": "png", "captureBeyondViewport": True,
            "clip": {"x": 0, "y": 0, "width": size["width"], "height": size["height"], "scale": 1}})
        (OUT / name).write_bytes(base64.b64decode(result["data"]))
        session.detach()
    page.on("pageerror", lambda e: errors.append(str(e)))
    page.on("request", lambda r: external_requests.append(r.url) if not r.url.startswith(("http://127.0.0.1:8876/", "data:")) else None)
    page.goto("http://127.0.0.1:8876/", wait_until="networkidle", timeout=120000)
    print("Local page loaded", flush=True)
    page.wait_for_function("() => document.getElementById('sourceStats').children.length > 0", timeout=120000)
    print("Recorded data rendered", flush=True)
    for chapter in ["sources", "labels", "models", "cases", "sandbox", "reference", "effort", "export"]:
        page.locator("#nav-" + chapter).click()
        assert page.locator("#" + chapter).is_visible()
    page.locator("#nav-sources").click()
    page.locator("#familyFilter").select_option("OCA Plus")
    page.locator("#issueSearch").fill("IRS-29096")
    assert "IRS-29096" in page.locator("#issueTable").inner_text()
    page.evaluate("() => window.scrollTo(0,0)")
    capture("dashboard-desktop.png")
    print("Source graph and search verified", flush=True)
    page.locator("#nav-cases").click()
    page.locator("#ticketSelect").select_option("IRS-65265")
    page.locator("#predictButton").click()
    page.wait_for_function("() => !document.getElementById('predictButton').disabled", timeout=120000)
    assert "persisted" in page.locator("#predictionReceipt").inner_text()
    page.wait_for_function("() => document.getElementById('caseEvidence').textContent.length > 10")
    assert "REVIEW REQUIRED" in page.locator("#casePlan").inner_text()
    capture("dashboard-ticket.png")
    print("Frozen advisory prediction persistence verified", flush=True)
    page.locator("#nav-sandbox").click()
    page.locator("#executeSource").click()
    page.wait_for_function("() => !document.getElementById('executeSource').disabled", timeout=120000)
    assert "Real source fragment" in page.locator("#sandboxSummary").inner_text()
    assert "repair-min-freq" in page.locator("#bundleDiff").inner_text()
    page.locator("#expectedFailure").click()
    page.wait_for_function("() => !document.getElementById('expectedFailure').disabled")
    assert "Expected rejection before mutation" in page.locator("#message").inner_text()
    page.locator("#executeFixture").click()
    page.wait_for_function("() => !document.getElementById('executeFixture').disabled", timeout=120000)
    assert "Synthetic fixture" in page.locator("#sandboxSummary").inner_text()
    capture("dashboard-sandbox.png")
    print("Source replay, rejection and synthetic fixture verified", flush=True)
    page.locator("#nav-reference").click()
    page.locator("#revealButton").click()
    page.wait_for_function("() => !document.getElementById('revealButton').disabled", timeout=120000)
    assert "UNREVIEWED REFERENCE" in page.locator("#referencePanel").inner_text()
    assert "ACCURACY SCORE" in page.locator("#referencePanel").inner_text()
    page.locator("#nav-effort").click()
    assert "Not measured" in page.locator("#effortStats").inner_text()
    for key, value in [("manualMinutes",40),("reviewMinutes",8),("supervisionMinutes",2),("correctionMinutes",5),("intakeMinutes",5)]:
        page.locator("#" + key).fill(str(value))
    assert "HYPOTHETICAL · 20 engineer minutes" in page.locator("#scenarioResult").inner_text()
    page.locator("#nav-export").click()
    with page.expect_download(timeout=120000) as download:
        page.locator("#exportButton").click()
    assert download.value.suggested_filename == "adf-sentinel-evidence.zip"
    print("Reference gate, effort scenario and export verified", flush=True)
    page.locator("#resetView").click()
    assert page.locator("#sources").is_visible()
    assert page.locator("#manualMinutes").input_value() == ""
    sizes = []
    for width, height in [(1440,1000),(960,800),(390,844)]:
        page.set_viewport_size({"width":width,"height":height})
        for chapter in ["sources","labels","models","cases","sandbox","reference","effort","export"]:
            page.locator("#nav-"+chapter).click()
            actual = page.evaluate("() => ({width:innerWidth,scroll:document.documentElement.scrollWidth})")
            assert actual["scroll"] <= actual["width"] + 1, (chapter, actual)
        sizes.append({"width":width,"height":height,"chapters":8,"horizontal_overflow":False})
    page.locator("#nav-sources").click()
    capture("dashboard-mobile.png")
    assert not errors, errors
    assert not external_requests, external_requests
    result = {"status":"passed","browser_version":browser.version,"checked_at":time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
              "chapters":8,"viewports":sizes,"pointer_action_mode":"normal pointer actions with visibility and stability checks","screenshot_method":"Chrome DevTools direct capture","page_errors":errors,"external_requests":external_requests,
              "interactions":["family graph","issue search","frozen advisory prediction persistence","pinned-source replay","expected precondition rejection","labeled fixture replay","gated reference reveal","hypothetical effort arithmetic","view reset","evidence export"],
              "scope":"Local UI and source/fixture operations; no scientific or physical validation"}
    (OUT / "browser.json").write_text(json.dumps(result,indent=2))
    print(json.dumps(result,indent=2))
    browser.close()

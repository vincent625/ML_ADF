"""Optional relocated workbench check using the host's Playwright and Chrome."""
import argparse
import importlib.util
import json
import shutil
import sys
import threading
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--chrome', default=shutil.which('google-chrome') or shutil.which('chromium'))
    args = parser.parse_args()
    if not args.chrome:
        parser.error('Install Chrome/Chromium or supply --chrome PATH for this optional check')
    from playwright.sync_api import sync_playwright
    sys.path.insert(0, str(ROOT / 'adf-review-workbench'))
    spec = importlib.util.spec_from_file_location('handoff_workbench_server',
                                                ROOT / 'adf-review-workbench/serve.py')
    serve = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(serve)
    server = serve.make_server(0)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    base = 'http://127.0.0.1:' + str(server.server_address[1])
    errors, external = [], []
    try:
        with sync_playwright() as p:
            browser = p.chromium.launch(
                executable_path=args.chrome, headless=False,
                args=['--headless=new', '--no-sandbox', '--disable-dev-shm-usage', '--disable-gpu'],
            )
            page = browser.new_page(viewport={'width': 1440, 'height': 1000}, accept_downloads=True)
            page.set_default_timeout(15000)
            page.on('pageerror', lambda error: errors.append(str(error)))
            page.on('request', lambda request: external.append(request.url)
                    if not request.url.startswith((base + '/', 'data:', 'blob:')) else None)
            page.goto(base + '/', wait_until='networkidle')
            assert page.locator('#packetCount').inner_text() == '4'
            assert page.locator('#actionCount').inner_text() == '4,922'
            page.locator('#caseList button[data-key="IRS-29057"]').click()
            page.get_by_text('Dated comments and decisions', exact=True).click()
            assert '6.7.17' in page.locator('#packetPanel').inner_text()
            assert '0.0.9' in page.locator('#packetPanel').inner_text()
            page.locator('#nav-intake').click()
            assert page.locator('#recordList button').count() == 7
            page.locator('#checkDraft').click()
            page.wait_for_function("() => !document.getElementById('checkDraft').disabled")
            check = page.locator('#checkResult').inner_text()
            assert 'artifact.revision' in check and 'Execution disabled' in check
            assert 'pending' in check
            page.locator('#nav-timing').click()
            with page.expect_download() as downloaded:
                page.locator('#timingDownload').click()
            assert len(Path(downloaded.value.path()).read_text().splitlines()) == 1
            viewports = []
            for width, height in ((1440, 1000), (960, 800), (390, 844)):
                page.set_viewport_size({'width': width, 'height': height})
                for tab in ('evidence', 'intake', 'timing', 'results'):
                    page.locator('#nav-' + tab).click()
                    assert page.locator('#' + tab).is_visible()
                    assert page.evaluate('document.documentElement.scrollWidth <= innerWidth + 1')
                viewports.append({'width': width, 'height': height, 'views': 4})
            assert not errors, errors
            assert not external, external
            result = {
                'status': 'passed', 'checked_at': datetime.now(timezone.utc).isoformat(),
                'scope': 'Relocated curated package; prepared evidence, pending draft checks and blank timing sheet',
                'browser': browser.version, 'viewports': viewports,
                'page_errors': errors, 'external_requests': external,
                'new_approvals': 0, 'real_source_changes': 0,
            }
            (ROOT / 'results/handoff-browser.json').write_text(json.dumps(result, indent=2) + '\n')
            print(json.dumps(result, indent=2))
            browser.close()
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=3)


if __name__ == '__main__':
    main()

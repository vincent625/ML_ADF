"""Exercise the local workbench without approving or changing real source data."""
import base64
import json
from datetime import datetime, timezone
from pathlib import Path

from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parent
OUT = ROOT / 'results/verification'
OUT.mkdir(parents=True, exist_ok=True)
errors, external_requests = [], []
BASE = 'http://127.0.0.1:8877'


def capture(page, name):
    session = page.context.new_cdp_session(page)
    size = session.send('Page.getLayoutMetrics')['cssContentSize']
    result = session.send('Page.captureScreenshot', {
        'format': 'png', 'captureBeyondViewport': True,
        'clip': {'x': 0, 'y': 0, 'width': size['width'], 'height': size['height'], 'scale': 1},
    })
    (OUT / name).write_bytes(base64.b64decode(result['data']))
    session.detach()


with sync_playwright() as p:
    browser = p.chromium.launch(
        headless=False, executable_path='/usr/bin/google-chrome',
        args=['--headless=new', '--no-sandbox', '--disable-dev-shm-usage', '--disable-gpu'],
    )
    page = browser.new_page(viewport={'width': 1440, 'height': 1000}, accept_downloads=True)
    page.set_default_timeout(15000)
    page.on('pageerror', lambda error: errors.append(str(error)))
    page.on('request', lambda request: external_requests.append(request.url)
            if not request.url.startswith((BASE + '/', 'data:', 'blob:')) else None)
    page.goto(BASE + '/', wait_until='networkidle', timeout=60000)
    assert page.locator('#packetCount').inner_text() == '4'
    assert page.locator('#actionCount').inner_text() == '4,922'
    assert page.locator('#caseList button').count() == 4
    for key in ['IRS-65265', 'IRS-29057', 'IRS-57322', 'IRS-66772']:
        page.locator('#caseList button[data-key="' + key + '"]').click()
        assert key in page.locator('#packetPanel').inner_text()
    page.locator('#caseList button[data-key="IRS-29057"]').click()
    page.get_by_text('Dated comments and decisions', exact=True).click()
    timeline = page.locator('#packetPanel').inner_text()
    assert '6.7.17' in timeline and '0.0.9' in timeline
    with page.expect_download() as packet_download:
        page.locator('#downloadPacket').click()
    packet_path = packet_download.value.path()
    assert json.loads(Path(packet_path).read_text())['issue_key'] == 'IRS-29057'
    capture(page, 'evidence-desktop.png')
    page.locator('#nav-intake').click()
    assert page.locator('#recordList button').count() == 7
    for index in range(7):
        page.locator('#recordList button[data-index="' + str(index) + '"]').click()
        page.locator('#checkDraft').click()
        page.wait_for_function("() => !document.getElementById('checkDraft').disabled")
        assert 'Execution disabled' in page.locator('#checkResult').inner_text()
        assert 'pending' in page.locator('#checkResult').inner_text()
    page.locator('#recordList button[data-index="0"]').click()
    assert 'artifact.revision' in page.locator('#checkResult').inner_text()
    assert 'baseline_sha256' in page.locator('#checkResult').inner_text()
    with page.expect_download() as draft_download:
        page.locator('#downloadDraft').click()
    draft = json.loads(Path(draft_download.value.path()).read_text())
    assert draft['reviewer_decision']['status'] == 'pending'
    assert draft['artifact']['sha256'] is None
    capture(page, 'intake-desktop.png')
    # Synthetic in-memory record verifies form edits and readiness without approving anything.
    page.locator('#recordList button[data-index="4"]').click()
    page.locator('#field-release').fill('synthetic-ui-test-only')
    page.locator('#field-variants').fill('synthetic-profile')
    page.locator('#field-acceptance_checks').fill('Synthetic UI test: identify a reproducible difference.')
    page.locator('#checkDraft').click()
    page.wait_for_function("() => !document.getElementById('checkDraft').disabled")
    assert 'Complete enough for review' in page.locator('#checkResult').inner_text()
    assert 'pending' in page.locator('#checkResult').inner_text()
    assert 'Execution disabled' in page.locator('#checkResult').inner_text()
    page.locator('#recordList button[data-index="3"]').click()
    assert page.locator('#field-variant_targets-0-new_value').count() == 1
    assert page.locator('#field-variant_targets-1-new_value').count() == 1
    page.locator('#nav-timing').click()
    assert 'Unknown' in page.locator('header').inner_text()
    with page.expect_download() as timing_download:
        page.locator('#timingDownload').click()
    lines = Path(timing_download.value.path()).read_text().splitlines()
    assert len(lines) == 1 and 'search_minutes' in lines[0] and 'wait_minutes' in lines[0]
    page.locator('#nav-results').click()
    assert page.locator('#teamCards .card').count() == 3
    assert '182' in page.locator('#qualityCounts').inner_text()
    assert page.locator('#qualityExamples tr').count() == 3
    page.evaluate('window.scrollTo(0,0)')
    capture(page, 'team-results-desktop.png')
    sizes = []
    for width, height in [(1440, 1000), (960, 800), (390, 844)]:
        page.set_viewport_size({'width': width, 'height': height})
        for tab in ['evidence', 'intake', 'timing', 'results']:
            page.locator('#nav-' + tab).click()
            assert page.locator('#' + tab).is_visible()
            actual = page.evaluate('({width:innerWidth,scroll:document.documentElement.scrollWidth})')
            assert actual['scroll'] <= actual['width'] + 1, (tab, actual)
        sizes.append({'width': width, 'height': height, 'views': 4, 'horizontal_overflow': False})
    capture(page, 'team-results-mobile.png')
    assert not errors, errors
    assert not external_requests, external_requests
    result = {
        'status': 'passed', 'checked_at': datetime.now(timezone.utc).isoformat(),
        'browser': browser.version, 'viewports': sizes,
        'interactions': [
            'four issue packets', 'dated OVAT instructions', 'packet download',
            'seven pending draft checks', 'missing pinned-file requirements',
            'pending draft download', 'synthetic in-memory form completion',
            'separate per-profile values', 'blank timing-sheet download',
            'team results and three label-review reasons',
        ],
        'page_errors': errors, 'external_requests': external_requests,
        'source_changes': 0, 'new_approvals': 0,
    }
    (OUT / 'browser.json').write_text(json.dumps(result, indent=2) + '\n')
    print(json.dumps(result, indent=2))
    browser.close()

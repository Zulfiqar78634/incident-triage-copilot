"""Real Chromium smoke test. No model credentials required; not a live-Gemini test."""
import json
from pathlib import Path
from playwright.sync_api import sync_playwright, expect

output = Path('test-artifacts')
output.mkdir(exist_ok=True)
events = []
with sync_playwright() as p:
    browser = p.chromium.launch()
    context = browser.new_context(record_video_dir=str(output / 'video'))
    context.tracing.start(screenshots=True, snapshots=True, sources=True)
    page = context.new_page()
    page.on('pageerror', lambda error: events.append({'type': 'pageerror', 'message': str(error)}))
    page.on('console', lambda message: events.append({'type': 'console', 'level': message.type, 'message': message.text}))
    page.on('response', lambda response: events.append({'type': 'http_error', 'url': response.url, 'status': response.status}) if response.status >= 400 else None)
    report = {'passed': False, 'mode': 'mock', 'scope': 'start, streamed evidence, approval, resolved state; not restart recovery or real Gemini'}
    try:
        page.goto('http://localhost:5173', wait_until='networkidle')
        expect(page.get_by_role('heading', name='Incident Triage Copilot', exact=True)).to_be_visible()
        page.screenshot(path=str(output / '01-initial.png'), full_page=True)
        page.get_by_role('button', name='Start investigation', exact=True).click()
        approve = page.get_by_role('button', name='Approve displayed action', exact=True)
        expect(approve).to_be_visible(timeout=60000)
        expect(page.get_by_role('heading', name='Evidence collected', exact=True)).to_be_visible()
        expect(page.get_by_text('No tool evidence received yet.', exact=True)).to_have_count(0)
        page.screenshot(path=str(output / '02-approval.png'), full_page=True)
        page.get_by_label('Decision rationale').fill('Automated mock-mode verification of displayed simulation action.')
        approve.click()
        expect(page.get_by_text('Status: resolved', exact=False)).to_be_visible(timeout=60000)
        expect(approve).to_have_count(0)
        page.screenshot(path=str(output / '03-resolved.png'), full_page=True)
        if any(event['type'] == 'pageerror' for event in events):
            raise AssertionError('Browser JavaScript errors were recorded')
        report['passed'] = True
    except Exception as error:
        report['error'] = str(error)
        page.screenshot(path=str(output / 'failure.png'), full_page=True)
        raise
    finally:
        (output / 'browser-events.json').write_text(json.dumps(events, indent=2), encoding='utf-8')
        (output / 'result.json').write_text(json.dumps(report, indent=2), encoding='utf-8')
        context.tracing.stop(path=str(output / 'trace.zip'))
        context.close()
        browser.close()

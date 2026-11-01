"""Read-only public checks for source-bound secondary Project pages and records."""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
from urllib.request import Request, urlopen


def verify(base: str, expected: Path, capture: Path | None = None) -> dict:
    from playwright.sync_api import sync_playwright

    base = base.rstrip('/')
    publication = json.loads(expected.read_text())
    checks, pages = [], []

    def check(name, ok):
        checks.append({'name': name, 'passed': bool(ok)})
        if not ok:
            raise ValueError('Project check failed: ' + name)

    for row in publication['projects']:
        req = Request(base + '/v1/read/get', data=json.dumps({'target': row['target']}).encode(),
                      headers={'Content-Type': 'application/json'})
        with urlopen(req, timeout=20) as response:
            raw = response.read(200001)
            check(row['project'] + ' bounded public record', response.status == 200 and len(raw) <= 200000)
            result = json.loads(raw)
        check(row['project'] + ' exact unreviewed head', result['record'] == row['record']
              and result['local_review']['status'] == 'imported_unreviewed' and result['is_head'])

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True, args=['--no-sandbox'])
        for width in (1440, 390):
            page = browser.new_page(viewport={'width': width, 'height': 900})
            errors = []
            page.on('pageerror', lambda e: errors.append(str(e)))
            for row in publication['projects']:
                name = row['project']
                page.goto(base + '/#/studio', wait_until='domcontentloaded')
                link = page.locator(f'#main a[href="#/studio/{name}"]')
                link.wait_for()
                link.click()
                page.locator('#rs-st').wait_for()
                text = page.locator('#main').inner_text()
                check(f'{name} {width} stored proposal label', 'stored Project · unreviewed proposal' in text)
                record_link = page.locator('#rs-st').locator('..').locator('a').first
                href = record_link.get_attribute('href')
                check(f'{name} {width} exact record link', row['target']['version'] in href and row['target']['id'] in href)
                check(f'{name} {width} starts at heading', page.evaluate('window.scrollY') == 0
                      and page.locator('#main h1').bounding_box()['y'] >= 0)
                check(f'{name} {width} no overflow', page.evaluate('document.documentElement.scrollWidth <= document.documentElement.clientWidth'))
                check(f'{name} {width} no fish widgets', page.locator('#main .subsyslist, #main #fish-viewer, #main #regctx').count() == 0)
                if capture:
                    capture.mkdir(parents=True, exist_ok=True)
                    page.screenshot(path=str(capture / f'{name}-{width}.png'))
                pages.append({'project': name, 'width': width, 'record_link': href})
            check(f'{width} no page errors', not errors)
            page.close()
        browser.close()
    return {'schema': 'frontier.projects.live-check/1', 'at': datetime.now(timezone.utc).isoformat(),
            'base': base, 'expected_receipt_sha256': hashlib.sha256(expected.read_bytes()).hexdigest(),
            'checks': checks, 'pages': pages, 'writes': 0,
            'scope': 'Exact public records and rendered project pages; no biological validation.'}


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--base', default='https://frontier.morphoswarm.ai')
    parser.add_argument('--expected', type=Path, required=True)
    parser.add_argument('--receipt', type=Path, required=True)
    parser.add_argument('--capture', type=Path)
    args = parser.parse_args()
    result = verify(args.base, args.expected, args.capture)
    args.receipt.parent.mkdir(parents=True, exist_ok=True)
    args.receipt.write_text(json.dumps(result, indent=2) + '\n')
    print(json.dumps({'checks_passed': len(result['checks']), 'receipt': str(args.receipt)}))

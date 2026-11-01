"""Read-only schema/bundle and desktop/mobile review of committed project inputs.

Serves actual committed JS with a labelled local snapshot projection built from
committed authored inputs via the existing builder's projection function.
Never regenerates owner files, imports a bundle or calls a provider.
"""
from pathlib import Path
from hashlib import sha256
from datetime import datetime, timezone
import argparse
import functools
import http.server
import json
import subprocess
import threading
import types

from frontier.models import Draft, Project, Record, digest
from playwright.sync_api import sync_playwright


def run(owner, commit, output, actual_snapshot=False):
    output.mkdir(parents=True, exist_ok=True)

    def git_bytes(rel):
        return subprocess.check_output(['git', '-C', str(owner), 'show', commit+':'+rel])

    def load_module(rel, name):
        code = git_bytes(rel)
        mod = types.ModuleType(name)
        mod.__file__ = str(owner/rel)
        exec(compile(code, str(owner/rel), 'exec'), mod.__dict__)
        return mod

    authored = json.loads(git_bytes('site/content/projects.json'))
    snapshot_bytes = git_bytes('site/data/snapshot.json')
    snapshot = json.loads(snapshot_bytes)
    catalog = json.loads(git_bytes('site/data/catalog.json'))
    refs = {r['ref']['id']: r['ref'] for r in catalog['records']}
    extras = [p for p in authored['projects'] if p.get('template') == 'reuse-study']
    assert len(extras) == 2
    assert [p['id'] for p in authored['projects'] if p.get('featured')] == ['flying-fish']
    assert authored['projects'][0]['id'] == 'flying-fish'
    drafts = {}
    checks = {}
    for p in extras:
        path = f'projects/{p["id"]}.draft.json'
        d = json.loads(git_bytes(path))
        Draft.model_validate(d['draft'])
        Project.model_validate(d['draft']['payload'])
        pl = d['draft']['payload']
        assert all(m['ref'] == refs[m['ref']['id']] and m['causal_bridge'] == 'none_declared' for m in pl['members'])
        assert all(q['problem'] == refs[q['problem']['id']] for q in pl['open_questions'] if q.get('problem'))
        assert p['live_project_id'] is None and p['runner'] is None
        assert all(r['stage'] in ('proposed', 'declared') for r in pl['requirements'])
        assert not any(c['status'] == 'implemented_model' for c in pl['scale_coverage'])
        drafts[p['id']] = d
    bundle = json.loads(git_bytes('projects/extra-projects.bundle.json'))
    assert digest({k: v for k, v in bundle.items() if k != 'bundle_sha256'}) == bundle['bundle_sha256']
    records = [Record.model_validate(r) for r in bundle['records']]
    assert len(records) == 2 and not bundle['review_claims']
    for r in records:
        assert r.kind == 'Project' and r.payload == drafts[r.id.removeprefix('project-')]['draft']['payload']
    checks['two_drafts_and_two_record_bundle_schema_digest_exact_refs'] = True
    checks['both_authored_unstored_unrun_no_causal_bridge'] = True
    checks['only_flying_fish_featured'] = True

    if actual_snapshot:
        assert snapshot['projects'] == authored
        assert all(p['draft_key'] in snapshot['project_drafts'] for p in extras)
        projected = snapshot_bytes
    else:
        builder = load_module('scripts/build_site.py', 'read_only_project_projection')
        ins = builder.Inputs()

        def read(rel):
            raw = git_bytes(rel)
            ins.seen[rel] = {'path': rel, 'sha256': sha256(raw).hexdigest(), 'bytes': len(raw)}
            return raw

        ins.read = read
        snapshot['projects'] = authored
        snapshot['project_drafts'] = builder.project_drafts(ins)
        snapshot['label'] += '; INDEPENDENT LOCAL REVIEW PROJECTION, NOT A DEPLOYED BUILD'
        projected = json.dumps(snapshot).encode()
    script_bytes = git_bytes('site/js/studio.js')
    app_bytes = git_bytes('site/js/app.js')
    index_bytes = git_bytes('site/index.html')
    cat_bytes = git_bytes('site/data/catalog.json')

    class Handler(http.server.SimpleHTTPRequestHandler):
        def do_GET(self):
            path = self.path.split('?', 1)[0]
            data = {'/data/snapshot.json': projected, '/data/catalog.json': cat_bytes,
                    '/js/studio.js': script_bytes, '/js/app.js': app_bytes,
                    '/': index_bytes, '/index.html': index_bytes}.get(path)
            if data is not None:
                self.send_response(200)
                self.send_header('Content-Type', 'application/json' if path.endswith('.json') else
                                 'application/javascript' if path.endswith('.js') else 'text/html')
                self.send_header('Content-Length', str(len(data)))
                self.end_headers()
                self.wfile.write(data)
            else:
                super().do_GET()

        def log_message(self, *args):
            pass

    server = http.server.ThreadingHTTPServer(('127.0.0.1', 0), functools.partial(Handler, directory=str(owner/'site')))
    threading.Thread(target=server.serve_forever, daemon=True).start()
    base = f'http://127.0.0.1:{server.server_port}/'
    pages = []
    try:
        with sync_playwright() as playwright:
            browser = playwright.chromium.launch(args=['--disable-gpu', '--renderer-process-limit=2'])
            for width in (1440, 390):
                context = browser.new_context(viewport={'width': width, 'height': 900}, reduced_motion='reduce')
                page = context.new_page()
                errors = []
                page.on('pageerror', lambda e: errors.append(str(e)))
                page.goto(base+'#/studio', wait_until='networkidle')
                page.wait_for_selector('#main h1:has-text("Studio")')
                assert page.locator('#main a[href="#/studio/flying-fish"]').count() == 1
                assert page.locator('#main a[href="#/studio/tissue-microcarrier"]').count() == 1
                assert page.locator('#main a[href="#/studio/epithelial-repair"]').count() == 1
                page.screenshot(path=str(output/f'studio-{width}.jpg'), full_page=True, type='jpeg', quality=75)
                for p in extras:
                    page.locator('#main a[href="#/studio/'+p['id']+'"]').click()
                    page.wait_for_selector('#main h1:has-text("'+p['title']+'")')
                    text = page.locator('#main').inner_text()
                    assert 'An authored proposal, not a stored Project.' in text
                    assert 'Nothing below is accepted, reviewed or run.' in text
                    assert 'tool, not proof of transfer' in text
                    assert 'Proposed, not available.' in text
                    assert page.locator('#main #fish-viewer, #main #fishmini, #main #simwidget, #main #regctx, #main .genomics').count() == 0
                    assert page.locator('#main canvas, #main input[type=range]').count() == 0
                    assert 'Genomic data' not in text and 'Start from real fish anatomy.' not in text
                    links = page.locator('#main a').evaluate_all('(xs)=>xs.map(x=>x.getAttribute("href"))')
                    assert all(s['url'] in links for s in p['sources'])
                    chain = page.locator('#main a[href*="/entity/Evidence/doc-model-coupling"]').first
                    href = chain.get_attribute('href')
                    assert p['chain'][0]['version'] in href and 'ns=snapshot' in href
                    overflow = page.evaluate('document.documentElement.scrollWidth > innerWidth')
                    assert not overflow
                    scroll_y = page.evaluate('scrollY')
                    heading_box = page.locator('#main h1').bounding_box()
                    viewport_shot = output/f'{p["id"]}-{width}-viewport.jpg'
                    page.screenshot(path=str(viewport_shot), type='jpeg', quality=75)
                    screenshot = output/f'{p["id"]}-{width}.jpg'
                    page.screenshot(path=str(screenshot), full_page=True, type='jpeg', quality=75)
                    pages.append({'width': width, 'route': '#/studio/'+p['id'], 'body_sha256': sha256(text.encode()).hexdigest(),
                                  'horizontal_overflow': overflow, 'source_urls': [s['url'] for s in p['sources']],
                                  'scroll_y_on_open': scroll_y, 'heading_box_on_open': heading_box,
                                  'heading_visible_in_initial_viewport': heading_box['y'] >= 0 and heading_box['y'] < 900,
                                  'exact_original_record_href': href, 'screenshot': screenshot.name})
                    chain.click()
                    page.wait_for_selector('#main h1')
                    assert 'doc-model-coupling' in page.locator('#main').inner_text()
                    page.go_back()
                    page.wait_for_selector('#main h1:has-text("'+p['title']+'")')
                    page.locator('#main .eyebrow a[href="#/studio"]').click()
                    page.wait_for_selector('#main h1:has-text("Studio")')
                page.goto(base+'#/studio/flying-fish', wait_until='networkidle')
                page.wait_for_selector('#main .subsyslist')
                assert page.locator('#main .subsyslist a').count() == 11
                assert 'Reuse studies' not in page.locator('#main').inner_text()
                page.goto(base+'#/studio', wait_until='networkidle')
                page.locator('#main a[href="#/studio/tissue-microcarrier"]').click()
                page.wait_for_selector('#main h1:has-text("Contractile tissue microcarrier")')
                assert page.locator('#main #fish-viewer, #main #fishmini, #main #simwidget, #main #regctx, #main .subsyslist, #main [id*="assur"]').count() == 0
                assert 'Genomic data' not in page.locator('#main').inner_text()
                checks[f'Chromium_{width}_fish_to_reuse_cleanup'] = True
                page.goto(base+'#/studio/no-such-project', wait_until='networkidle')
                page.wait_for_selector('#main h1:has-text("No such project")')
                assert not errors, errors
                checks[f'Chromium_{width}_routes_navigation_no_leak_no_overflow'] = True
                context.close()
            browser.close()
    finally:
        server.shutdown()
        server.server_close()
    inputs = ['site/content/projects.json', 'site/js/studio.js', 'site/js/app.js', 'site/index.html', 'scripts/build_extra_projects.py', 'scripts/build_site.py',
              'site/data/snapshot.json', 'site/data/catalog.json', 'frontier/models.py',
              'projects/tissue-microcarrier.draft.json', 'projects/epithelial-repair.draft.json', 'projects/extra-projects.bundle.json']
    receipt = {'schema': 'frontier.independent-project-surface-review/1', 'time_UTC': datetime.now(timezone.utc).isoformat(),
               'reviewed_commit': commit, 'checks': checks, 'pages': pages, 'bundle_sha256': bundle['bundle_sha256'],
               'original_snapshot_projects': [p['id'] for p in json.loads(snapshot_bytes)['projects']['projects']],
               'projection_scope': ('Actual committed generated snapshot, catalog, HTML and app/studio code; local read-only server, NOT live deployment or DB integration' if actual_snapshot else
                                    'Real committed JS with authored projects and draft projection generated via existing build_site.project_drafts; local read-only review server, NOT root regeneration/deployment/live DB integration'),
               'inputs': [{'path': p, 'sha256': sha256(git_bytes(p)).hexdigest()} for p in inputs],
               'no_DB_writes': True, 'provider_calls': 0, 'owner_files_changed': False}
    for p in output.glob('*.jpg'):
        receipt.setdefault('screenshots', []).append({'path': p.name, 'sha256': sha256(p.read_bytes()).hexdigest(), 'bytes': p.stat().st_size})
    (output/'receipt.json').write_text(json.dumps(receipt, indent=2)+'\n')
    print(json.dumps({'checks': checks, 'pages': len(pages), 'bundle_sha256': bundle['bundle_sha256']}))


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--owner-root', type=Path, required=True)
    parser.add_argument('--commit', required=True)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--actual-snapshot', action='store_true')
    args = parser.parse_args()
    run(args.owner_root.resolve(), args.commit, args.output, args.actual_snapshot)

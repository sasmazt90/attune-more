#!/usr/bin/env python3
"""QA-16 and QA-17. Follows saved records through refresh, re-entry and host restart, then deletes one.

Stages run separately because a host Stop and Start falls between them:
  before   counts records, opens one, refreshes, leaves and re-enters, checks for duplicates
  after    checks the same records are still there after the host restart, then deletes one and
           proves it stays deleted across a refresh and re-entry
Reads local records only. On WEB the records live in a Chrome profile, so this needs a kept profile.
"""
import argparse
import json
import os
from pathlib import Path
import re
import subprocess
import sys

from playwright.sync_api import sync_playwright

KEYS = {'skin': 'togg_health_skin_history', 'dental': 'attune_dental_history_v1', 'hearing': 'attune_hearing_history_v1', 'mental': 'togg_health_mental_history', 'vision': 'togg_health_vision_history'}
HOST = 'attunemore.sasmaz.digital'
QA = Path('/var/lib/attune/qa')
ADB = '/opt/android-sdk/platform-tools/adb'


def counts(page):
    return page.evaluate("""k=>Object.fromEntries(Object.entries(k).map(([m,key])=>{let rows=[];try{rows=JSON.parse(localStorage.getItem(key)||'[]');}catch{}return [m,rows.map(r=>r.id)];}))""", KEYS)


def duplicates(ids):
    return {m: [i for i in set(v) if v.count(i) > 1] for m, v in ids.items() if len(set(v)) != len(v)}


def history_rows(page):
    page.get_by_role('link', name='My Health History', exact=True).click()
    page.wait_for_timeout(2000)
    return page.locator('[data-record-id]').evaluate_all('e=>e.map(x=>x.getAttribute("data-record-id"))')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--platform', choices=['web', 'aaos'], required=True)
    parser.add_argument('--stage', choices=['before', 'after'], required=True)
    parser.add_argument('--profile', default=str(QA / 'profile-web'))
    parser.add_argument('--out', required=True)
    args = parser.parse_args()
    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    path = out / 'persistence.json'
    report = json.loads(path.read_text()) if path.exists() else {'platform': args.platform, 'origin': None, 'checks': []}

    def check(what, passed, detail=None):
        report['checks'].append({'stage': args.stage, 'check': what, 'passed': bool(passed), 'detail': detail})
        print(('PASS ' if passed else 'FAIL ') + what, json.dumps(detail, ensure_ascii=False)[:200] if detail is not None else '', flush=True)
        path.write_text(json.dumps(report, indent=1, ensure_ascii=False))

    with sync_playwright() as playwright:
        if args.platform == 'aaos':
            device = [ADB, '-s', 'emulator-5554']
            unix = subprocess.check_output(device + ['shell', 'cat', '/proc/net/unix'], text=True, stdin=subprocess.DEVNULL)
            socket = re.findall(r'webview_devtools_remote_\d+', unix)[0]
            subprocess.check_call(device + ['forward', 'tcp:9222', 'localabstract:' + socket], stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL)
            browser = playwright.chromium.connect_over_cdp('http://127.0.0.1:9222')
            page = next(p for c in browser.contexts for p in c.pages if p.url.startswith('http://127.0.0.1:3000'))
            home = 'http://127.0.0.1:3000/'
            close = browser.close
        else:
            credentials = json.loads((QA / 'access.json').read_text())
            env = {**os.environ, 'DISPLAY': ':99'}
            context = playwright.chromium.launch_persistent_context(args.profile, executable_path='/usr/bin/google-chrome', headless=False, env=env, ignore_https_errors=True,
                                                                    http_credentials={'username': credentials['username'], 'password': credentials['password']},
                                                                    args=['--no-sandbox', '--host-resolver-rules=MAP {} 127.0.0.1'.format(HOST)], viewport={'width': 1280, 'height': 800})
            page = context.pages[0] if context.pages else context.new_page()
            home = 'https://' + HOST
            close = context.close
        page.set_default_timeout(25000)
        page.goto(home, wait_until='networkidle')
        page.locator('#attune-language').select_option('en')
        report['origin'] = page.evaluate('location.origin')
        ids = counts(page)
        total = sum(len(v) for v in ids.values())
        report.setdefault('seen', {})[args.stage] = {m: len(v) for m, v in ids.items()}
        if args.stage == 'before':
            report['recordIds'] = ids
            check('Saved records exist on this origin', total > 0, report['seen']['before'])
            check('No duplicate records', not duplicates(ids), duplicates(ids))
            rows = history_rows(page)
            check('History lists every saved record', set(rows) >= {i for v in ids.values() for i in v}, {'rows': len(rows), 'stored': total})
            page.reload(wait_until='networkidle')
            check('Records unchanged after a refresh', counts(page) == ids)
            page.locator('nav a[href="/"]').first.click()
            page.wait_for_timeout(800)
            page.goto(home, wait_until='networkidle')
            check('Records unchanged after re-entry', counts(page) == ids)
        else:
            kept = report.get('recordIds', {})
            check('Records unchanged after the host Stop and Start', ids == kept, {'before': {m: len(v) for m, v in kept.items()}, 'after': report['seen']['after']})
            rows = history_rows(page)
            check('History still lists them', set(rows) >= {i for v in ids.values() for i in v})
            module = next((m for m in ('hearing', 'dental', 'vision', 'skin', 'mental') if ids.get(m)), None)
            target = ids[module][0]
            row = page.locator('[data-record-id="' + target + '"]')
            row.scroll_into_view_if_needed()
            row.get_by_role('button', name=re.compile('delete', re.I)).first.click()
            page.get_by_role('dialog').wait_for()
            page.screenshot(path=str(out / 'delete-confirm.png'))
            page.get_by_role('button', name=re.compile('^yes', re.I)).first.click()
            row.wait_for(state='detached')
            after = counts(page)
            check('Deleting removes exactly one record', after[module] == [i for i in ids[module] if i != target], {'module': module})
            page.reload(wait_until='networkidle')
            check('Deleted record stays deleted after a refresh', target not in counts(page)[module])
            page.goto(home, wait_until='networkidle')
            again = counts(page)
            check('Deleted record stays deleted after re-entry', target not in again[module])
            check('Other records are untouched', all(again[m] == ids[m] for m in ids if m != module))
        report['status'] = 'PASS' if all(c['passed'] for c in report['checks']) else 'FAIL'
        path.write_text(json.dumps(report, indent=1, ensure_ascii=False))
        close()
    return 0 if report['status'] == 'PASS' else 1


if __name__ == '__main__':
    sys.exit(main())

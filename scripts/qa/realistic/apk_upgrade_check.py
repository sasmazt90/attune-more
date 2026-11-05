#!/usr/bin/env python3
"""QA-41. Proves saved data survives an APK upgrade, by comparing what the app holds before and after.

Each stage reads the real WebView's local storage and IndexedDB and Android's package record. It saves record IDs and
hashes, never health content. Comparing two stages fails on any missing, changed or duplicated record, on any changed
consent or preference, and on any sign that the app was reinstalled rather than updated.

Restart persistence is a different question and is covered by persistence_check.py. This checks APK upgrades.

  apk_upgrade_check.py --out DIR --stage baseline-1 --set-preferences
  apk_upgrade_check.py --out DIR --stage after-1 --compare-to baseline-1 --operational
"""
import argparse
import hashlib
import json
from pathlib import Path
import re
import subprocess
import sys
import time

sys.path.insert(0, '/opt/attune/scripts/aws')

RECORD_KEYS = {'skin': 'togg_health_skin_history', 'dental': 'attune_dental_history_v1', 'hearing': 'attune_hearing_history_v1',
               'mental': 'togg_health_mental_history', 'vision': 'togg_health_vision_history'}
CONSENT_KEY = 'attune_health_processing_v1'
ROUTES = ('skin', 'dental', 'vision', 'hearing', 'mental')
ADB = ['/opt/android-sdk/platform-tools/adb', '-s', 'emulator-5554']
HOME = 'http://127.0.0.1:3000/'
# Written by the running app itself on every start, so a difference says nothing about the upgrade. Anything else must match.
VOLATILE = re.compile(r'^(attune_hearing_audio_focus|attune_hearing_audio_owner)$')

READ_STORAGE = """async()=>{
 const storage={};for(let i=0;i<localStorage.length;i++){const k=localStorage.key(i);storage[k]=localStorage.getItem(k);}
 const mark=(k,x)=>x instanceof Blob?'blob:'+x.size+':'+x.type:x instanceof ArrayBuffer||ArrayBuffer.isView(x)?'bytes:'+x.byteLength:x;
 const databases=[];
 for(const d of (indexedDB.databases?await indexedDB.databases():[])){
  const db=await new Promise((ok,no)=>{const r=indexedDB.open(d.name);r.onsuccess=()=>ok(r.result);r.onerror=()=>no(r.error);});
  const stores={};
  for(const name of db.objectStoreNames){
   const read=m=>new Promise((ok,no)=>{const r=db.transaction(name).objectStore(name)[m]();r.onsuccess=()=>ok(r.result);r.onerror=()=>no(r.error);});
   const keys=await read('getAllKeys'),values=await read('getAll');
   stores[name]={keys:keys.map(k=>JSON.stringify(k)),values:values.map(v=>JSON.stringify(v,mark))};
  }
  db.close();databases.push({name:d.name,version:d.version,stores});
 }
 return {storage,databases,cookieNames:document.cookie.split(';').map(x=>x.split('=')[0].trim()).filter(Boolean).sort()};
}"""


def digest(text):
    return hashlib.sha256((text if isinstance(text, str) else json.dumps(text, sort_keys=True)).encode('utf8')).hexdigest()


def summarize(raw):
    """IDs and hashes only, so the evidence holds no health content."""
    records = {}
    for module, key in RECORD_KEYS.items():
        try:
            rows = json.loads(raw['storage'].get(key) or '[]')
        except ValueError:
            rows = None
        if rows is None:
            records[module] = {'corrupt': True}
            continue
        ids = [str(row.get('id')) for row in rows]
        records[module] = {'count': len(rows), 'ids': ids, 'duplicates': sorted({i for i in ids if ids.count(i) > 1}), 'hashes': {str(row.get('id')): digest(row) for row in rows}}
    databases = {}
    for database in raw['databases']:
        databases[database['name']] = {'version': database['version'], 'stores': {name: {'count': len(store['keys']), 'keysHash': digest(store['keys']), 'valuesHash': digest(store['values'])} for name, store in database['stores'].items()}}
    return {'records': records, 'localStorage': {key: {'bytes': len(value), 'sha256': digest(value)} for key, value in sorted(raw['storage'].items())},
            'indexedDb': databases, 'cookieNames': raw['cookieNames']}


def compare(before, after, allow_new_records=False, allow_change=()):
    """Everything wrong between two stages. An empty list means the data came through intact."""
    problems = []
    for module, was in before['records'].items():
        now = after['records'].get(module, {})
        if now.get('corrupt'):
            problems.append('{}: records can no longer be read'.format(module))
            continue
        if now.get('duplicates'):
            problems.append('{}: duplicated records {}'.format(module, now['duplicates']))
        missing = [i for i in was.get('ids', []) if i not in now.get('ids', [])]
        if missing:
            problems.append('{}: records missing {}'.format(module, missing))
        added = [i for i in now.get('ids', []) if i not in was.get('ids', [])]
        if added and not allow_new_records:
            problems.append('{}: unexpected new records {}'.format(module, added))
        changed = [i for i, value in was.get('hashes', {}).items() if i in now.get('hashes', {}) and now['hashes'][i] != value]
        if changed:
            problems.append('{}: records changed {}'.format(module, changed))
    record_keys = set(RECORD_KEYS.values())
    for key, value in before['localStorage'].items():
        if VOLATILE.match(key) or (allow_new_records and key in record_keys) or key in allow_change:
            continue
        if key not in after['localStorage']:
            problems.append('Local value lost: {}'.format(key))
        elif key not in record_keys and after['localStorage'][key]['sha256'] != value['sha256']:
            problems.append('Local value changed: {}'.format(key))
    for name, database in before['indexedDb'].items():
        now = after['indexedDb'].get(name)
        if not now:
            problems.append('Database lost: {}'.format(name))
            continue
        for store, value in database['stores'].items():
            current = now['stores'].get(store)
            if not current:
                problems.append('Store lost: {}/{}'.format(name, store))
            elif not allow_new_records and current != value:
                problems.append('Store changed: {}/{}'.format(name, store))
            elif allow_new_records and current['count'] < value['count']:
                problems.append('Store shrank: {}/{}'.format(name, store))
    return problems


def compare_package(before, after):
    problems = []
    if after['certificate'] != before['certificate']:
        problems.append('The signing certificate changed')
    if after['firstInstallTime'] != before['firstInstallTime']:
        problems.append('firstInstallTime changed, so the app was reinstalled')
    if after['lastUpdateTime'] == before['lastUpdateTime']:
        problems.append('lastUpdateTime did not change, so no upgrade happened')
    if not after['versionCode'] > before['versionCode']:
        problems.append('versionCode did not rise: {} to {}'.format(before['versionCode'], after['versionCode']))
    for user, row in before['users'].items():
        if row['microphone'] and not after['users'].get(user, {}).get('microphone'):
            problems.append('User {} lost the microphone grant'.format(user))
    return problems


def native_webview_socket(unix, pids):
    """Other apps can own WebViews too; socket order is not app identity."""
    values = pids.split()
    if len(values) != 1 or not values[0].isdecimal():
        return None
    expected = 'webview_devtools_remote_' + values[0]
    return expected if expected in re.findall(r'webview_devtools_remote_\d+', unix) else None


def connect(playwright):
    """The app restarts on an upgrade, so its debugging socket has a new name."""
    deadline = time.time() + 90
    while True:
        unix = subprocess.check_output(ADB + ['shell', 'cat', '/proc/net/unix'], text=True, stdin=subprocess.DEVNULL)
        process = subprocess.run(ADB + ['shell', 'pidof', 'more.attune.automotive.prototype.clouddemo'], capture_output=True, text=True, timeout=10)
        socket = native_webview_socket(unix, process.stdout)
        if socket:
            break
        if time.time() > deadline:
            raise RuntimeError('The app did not start a WebView')
        time.sleep(2)
    subprocess.check_call(ADB + ['forward', 'tcp:9222', 'localabstract:' + socket], stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL)
    while True:
        try:
            browser = playwright.chromium.connect_over_cdp('http://127.0.0.1:9222')
            page = next((p for c in browser.contexts for p in c.pages if p.url.startswith('http://127.0.0.1:3000')), None)
            if page:
                return browser, page
            browser.close()
        except Exception:
            pass
        if time.time() > deadline:
            raise RuntimeError('The app page did not open')
        time.sleep(2)


def set_preferences(page):
    """Real choices through the real controls, so they can be seen surviving."""
    page.goto(HOME + 'care', wait_until='networkidle')
    page.locator('[data-care-region]').select_option('Berlin')
    page.wait_for_timeout(500)
    page.locator('#attune-language').select_option('de')
    page.wait_for_timeout(800)


def operational(page, out, stage, expected_ids):
    """The app still works, and what it shows matches what is stored."""
    results = []

    def check(what, passed, detail=None):
        results.append({'check': what, 'passed': bool(passed), 'detail': detail})
        print(('PASS ' if passed else 'FAIL ') + what, json.dumps(detail, ensure_ascii=False)[:220] if detail is not None else '', flush=True)

    page.goto(HOME, wait_until='networkidle')
    page.wait_for_function("document.querySelector('[data-vehicle-status]')")
    preferences = page.evaluate("()=>({language:localStorage.getItem('attune.language.v1')||'tr',region:localStorage.getItem('attune.care.region.v1')||''})")
    headings = {'tr': 'Sağlık modülleri', 'en': 'Health modules', 'de': 'Gesundheitsmodule'}
    language = preferences['language']
    check('The chosen language is still in use', language in headings and page.locator('#attune-language').input_value() == language and headings[language] in page.locator('main').inner_text(), {'expected': language})
    status = page.evaluate("fetch('/api/health').then(r=>r.status)")
    check('The API answers through the app', status == 200, status)
    for route in ROUTES:
        page.goto(HOME + route, wait_until='networkidle')
        page.wait_for_timeout(900)
        check('{}: opens with its consent still given'.format(route), page.locator('[role=dialog]').count() == 0 and page.locator('main').count() == 1)
    page.goto(HOME + 'care', wait_until='networkidle')
    check('The chosen region is still selected', page.locator('[data-care-region]').input_value() == preferences['region'])
    page.goto(HOME + 'profile', wait_until='networkidle')
    page.wait_for_timeout(2000)
    shown = page.locator('[data-record-id]').evaluate_all('e=>e.map(x=>x.getAttribute("data-record-id"))')
    missing = [i for i in expected_ids if i not in shown]
    check('History shows every saved record, once each', not missing and len(shown) == len(set(shown)), {'shown': len(shown), 'expected': len(expected_ids), 'missing': missing[:5]})
    page.screenshot(path=str(out / (stage + '-history.png')))
    row = page.locator('[data-record-id]').first
    if row.count():
        row.scroll_into_view_if_needed()
        row.locator('button').first.click()
        page.wait_for_timeout(1200)
        check('A saved record opens', page.locator('[role=dialog]').count() == 1)
        page.screenshot(path=str(out / (stage + '-record.png')))
    page.goto(HOME, wait_until='networkidle')
    return results


def main():
    from playwright.sync_api import sync_playwright
    from apk_upgrade_host import Device
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--out', required=True)
    parser.add_argument('--stage', required=True)
    parser.add_argument('--compare-to')
    parser.add_argument('--allow-new-records', action='store_true', help='A journey ran since that stage, so more records are expected. None may be lost or changed.')
    parser.add_argument('--not-an-upgrade', action='store_true', help='Compare data only, for a host restart or the one-time signing move.')
    parser.add_argument('--allow-change', action='append', default=[], help='A local value a journey is known to set, such as its language.')
    parser.add_argument('--set-preferences', action='store_true')
    parser.add_argument('--operational', action='store_true')
    parser.add_argument('--restore-language')
    args = parser.parse_args()
    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    device = Device()
    with sync_playwright() as playwright:
        browser, page = connect(playwright)
        page.set_default_timeout(30000)
        if args.set_preferences:
            set_preferences(page)
        if page.url.rstrip('/') != HOME.rstrip('/'):
            page.goto(HOME, wait_until='networkidle')
        snapshot = summarize(page.evaluate(READ_STORAGE))
        package = device.package()
        package['certificate'] = device.installed_cert()
        snapshot['package'] = package
        snapshot['takenAt'] = time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime())
        (out / (args.stage + '.json')).write_text(json.dumps(snapshot, indent=1))
        counts = {m: r.get('count') for m, r in snapshot['records'].items()}
        print(json.dumps({'stage': args.stage, 'records': counts, 'versionCode': package['versionCode'], 'versionName': package['versionName'], 'certificate': package['certificate'], 'firstInstallTime': package['firstInstallTime'], 'lastUpdateTime': package['lastUpdateTime'], 'localValues': len(snapshot['localStorage'])}), flush=True)
        result = {'stage': args.stage, 'records': counts, 'package': {k: package[k] for k in ('versionCode', 'versionName', 'certificate', 'firstInstallTime', 'lastUpdateTime')}, 'problems': [], 'checks': []}
        if args.compare_to:
            before = json.loads((out / (args.compare_to + '.json')).read_text())
            result['comparedTo'] = args.compare_to
            result['problems'] = compare(before, snapshot, args.allow_new_records, args.allow_change)
            if not args.not_an_upgrade:
                result['problems'] += compare_package(before['package'], package)
            result['recordsCompared'] = {m: r.get('count') for m, r in before['records'].items()}
            result['allowedToChange'] = args.allow_change
            result['newRecordsAllowed'] = args.allow_new_records
            result['packageCompared'] = not args.not_an_upgrade
        if args.operational:
            ids = [i for r in snapshot['records'].values() for i in r.get('ids', [])]
            result['checks'] = operational(page, out, args.stage, ids)
        if args.restore_language:
            page.locator('#attune-language').select_option(args.restore_language)
            page.wait_for_timeout(500)
        browser.close()
    failed = [c['check'] for c in result['checks'] if not c['passed']]
    result['status'] = 'PASS' if not result['problems'] and not failed else 'FAIL'
    (out / ('result-' + args.stage + '.json')).write_text(json.dumps(result, indent=1))
    print(json.dumps({'status': result['status'], 'problems': result['problems'], 'failed': failed}))
    return 0 if result['status'] == 'PASS' else 1


if __name__ == '__main__':
    sys.exit(main())

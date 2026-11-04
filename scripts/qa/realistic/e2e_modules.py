#!/usr/bin/env python3
"""English end-to-end journeys for Skin, Dental, Hearing and Mental, with continuous recording.

Vision uses vision_realistic.py. Every journey goes through the real application and real processing:
reference photos stand in for a camera, synthesized speech for a person, and a scripted listener for
a person's hearing. So this is functional evidence, not physical, human or clinical acceptance.
Run on the host as the attune user, through run_e2e.sh.
"""
import argparse
import datetime as dt
import json
import math
import os
from pathlib import Path
import re
import shutil
import signal
import struct
import subprocess
import sys
import threading
import time

from playwright.sync_api import sync_playwright

QA = Path('/var/lib/attune/qa')
ADB = '/opt/android-sdk/platform-tools/adb'
HOST = 'attune.sasmaz.digital'
HISTORY = {'skin': 'togg_health_skin_history', 'dental': 'attune_dental_history_v1', 'hearing': 'attune_hearing_history_v1', 'mental': 'togg_health_mental_history'}
ROUTES = {'skin': 'skin', 'dental': 'dental', 'din': 'hearing', 'tone': 'hearing', 'mental': 'mental'}
TURKISH = re.compile(r'[çğıİşÇĞŞ]')
# Layout facts for the responsive evidence. Same questions as the page audit.
MEASURE = """()=>{const h=document.querySelector('[data-cockpit-header]'),r=h?h.getBoundingClientRect():{height:0},sticky=h?['sticky','fixed'].includes(getComputedStyle(h).position):false;
 const usable=innerHeight-(sticky?r.height:0),total=document.documentElement.scrollHeight;
 return {inner:[innerWidth,innerHeight],header:Math.round(r.height),usable,total,lengths:+(total/usable).toFixed(2),sideways:document.documentElement.scrollWidth>innerWidth+1};}"""
TIMING = """window.__qaTimings=[];window.addEventListener('attune-speech-timing',e=>window.__qaTimings.push(e.detail));"""
# Reads the value the page drew for its random generator. Values are unchanged.
SEED_OBSERVER = """(()=>{const original=crypto.getRandomValues.bind(crypto);crypto.getRandomValues=function(a){const r=original(a);if(a instanceof Uint32Array&&a.length===1)window.__observedDinSeed=a[0];return r;};})();"""
# The camera pairing code is a short-lived credential. It stays out of recordings.
MASK_PAIRING = """(()=>{const hide=()=>document.querySelectorAll('dialog textarea').forEach(e=>e.style.webkitTextSecurity='disc');new MutationObserver(hide).observe(document,{childList:true,subtree:true});})();"""
# Heard levels in dBFS peak for the scripted listener. It responds to real audio on the tested channel.
LISTENER = {250: -50, 500: -55, 1000: -60, 2000: -60, 4000: -55, 8000: -50}
RIGHT_EAR_OFFSET = 5


class Run:
    def __init__(self, args):
        self.args = args
        self.out = Path(args.out)
        self.out.mkdir(parents=True, exist_ok=True)
        self.report = {'module': args.module, 'platform': args.platform, 'language': 'en', 'startedAt': dt.datetime.now(dt.timezone.utc).isoformat(),
                       'boundary': 'Controlled input through the real application and real processing. Not physical, human or clinical acceptance.',
                       'input': args.input_map, 'timeline': [], 'checks': [], 'errors': [], 'api': []}
        self.recorder = None
        self.started = time.time()
        self.page = None
        self.adapter = None

    def save(self):
        (self.out / 'report.json').write_text(json.dumps(self.report, indent=1, ensure_ascii=False))

    def mark(self, label):
        self.report['timeline'].append({'second': round(time.time() - self.started, 1), 'label': label})
        print(round(time.time() - self.started), label, flush=True)
        self.save()

    def check(self, what, passed, detail=None):
        self.report['checks'].append({'check': what, 'passed': bool(passed), 'detail': detail})
        print(('PASS ' if passed else 'FAIL ') + what + (' ' + json.dumps(detail, ensure_ascii=False)[:260] if detail is not None else ''), flush=True)
        self.save()

    def shot(self, name):
        self.page.screenshot(path=str(self.out / (name + '.png')))

    def dwell(self, ms=None):
        self.page.wait_for_timeout(self.args.dwell if ms is None else ms)

    def start_recording(self):
        self.started = time.time()
        if not self.args.record:
            return
        command = ['ffmpeg', '-hide_banner', '-loglevel', 'error', '-y', '-f', 'x11grab', '-framerate', str(self.args.fps), '-video_size', self.args.video_size, '-i', self.args.display,
                   '-f', 'pulse', '-i', 'attune_out.monitor', '-f', 'pulse', '-i', 'attune_mic.monitor',
                   '-filter_complex', '[1:a][2:a]amix=inputs=2:normalize=0[a]', '-map', '0:v', '-map', '[a]', '-c:v', 'libx264', '-preset', 'veryfast', '-crf', '24',
                   '-pix_fmt', 'yuv420p', '-g', str(self.args.fps * 2), '-c:a', 'aac', '-b:a', '128k', '-movflags', '+faststart', str(self.out / 'video.mp4')]
        self.recorder = subprocess.Popen(command, stderr=(self.out / 'recorder.log').open('w'))
        time.sleep(1.5)

    def stop_recording(self):
        if self.recorder:
            self.recorder.send_signal(signal.SIGINT)
            try:
                self.recorder.wait(timeout=60)
            except subprocess.TimeoutExpired:
                self.recorder.kill()


class Web:
    """Real Chrome. Only the camera input is replaced, by reference photos through Chrome's file camera."""

    def __init__(self, args):
        self.args = args
        self.frames = {}
        self.camera = None
        self.handle = None

    def open(self, playwright):
        args = self.args
        launch = ['--no-sandbox', '--disable-dev-shm-usage', '--use-fake-ui-for-media-stream', '--autoplay-policy=no-user-gesture-required',
                  '--host-resolver-rules=MAP {} 127.0.0.1'.format(HOST), '--window-position=0,0', '--window-size=1280,800', '--app=https://' + HOST,
                  '--disable-features=Translate,TranslateUI', '--disable-infobars', '--lang=en-US', '--no-first-run']
        if args.frames:
            self.frames = {pose: Path(args.frames.replace('POSE', pose)).read_bytes() for pose in args.poses.split(',')}
            self.camera = Path(args.out) / 'camera.y4m'
            self.camera.write_bytes(self.frames[args.poses.split(',')[0]])
            self.handle = self.camera.open('r+b')
            launch += ['--use-fake-device-for-media-stream', '--use-file-for-fake-video-capture=' + str(self.camera)]
        env = {**os.environ, 'PULSE_SOURCE': 'attune_mic_source', 'PULSE_SINK': 'attune_out', 'DISPLAY': args.display, 'TZ': args.timezone}
        credentials = json.loads((QA / 'access.json').read_text())
        # A kept profile, as a person's browser would be, so saved records carry between journeys.
        context = playwright.chromium.launch_persistent_context(args.profile, executable_path='/usr/bin/google-chrome', headless=False, env=env, ignore_default_args=['--mute-audio', '--enable-automation'], args=launch,
                                                                http_credentials={'username': credentials['username'], 'password': credentials['password']}, ignore_https_errors=True,
                                                                viewport={'width': 1280, 'height': 800}, permissions=['camera', 'microphone'], timezone_id=args.timezone, locale='en-US')
        context.add_init_script(TIMING)
        context.add_init_script(SEED_OBSERVER)
        return (context.pages[0] if context.pages else context.new_page()), context.close

    def home(self, page):
        page.goto('https://' + HOST, wait_until='networkidle')

    def pair(self, page):
        pass

    def set_pose(self, page, pose):
        self.handle.seek(0)
        self.handle.write(self.frames[pose])
        self.handle.flush()

    def resize(self, page, width, height):
        page.set_viewport_size({'width': width, 'height': height})

    def close(self):
        if self.handle:
            self.handle.close()


class Aaos:
    """The native WebView on the Android 15 emulator. Camera input comes through the mTLS reference bridge."""

    def __init__(self, args):
        self.args = args

    def open(self, playwright):
        device = [ADB, '-s', 'emulator-5554']
        unix = subprocess.check_output(device + ['shell', 'cat', '/proc/net/unix'], text=True, stdin=subprocess.DEVNULL)
        socket = re.findall(r'webview_devtools_remote_\d+', unix)[0]
        subprocess.check_call(device + ['forward', 'tcp:9222', 'localabstract:' + socket], stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL)
        browser = playwright.chromium.connect_over_cdp('http://127.0.0.1:9222')
        page = next(p for c in browser.contexts for p in c.pages if p.url.startswith('http://127.0.0.1:3000'))
        page.add_init_script(TIMING)
        page.add_init_script(SEED_OBSERVER)
        page.add_init_script(MASK_PAIRING)
        page.evaluate(MASK_PAIRING)
        return page, browser.close

    def home(self, page):
        page.goto('http://127.0.0.1:3000/', wait_until='networkidle')

    def pair(self, page):
        code = page.locator('dialog textarea')
        code.wait_for()
        page.wait_for_timeout(400)
        key_file = Path(self.args.pair_file)
        key_file.write_text(json.dumps({'key': code.input_value()}))
        key_file.chmod(0o600)

    def set_pose(self, page, pose):
        path = self.args.pose_file
        Path(path + '.next').write_text(pose)
        os.replace(path + '.next', path)

    def resize(self, page, width, height):
        pass

    def close(self):
        pass


def set_english(run):
    page = run.page
    run.adapter.home(page)
    page.locator('#attune-language').select_option('en')
    page.wait_for_function("document.querySelector('[data-vehicle-status]')?.textContent==='PARK'")
    run.report['viewport'] = page.evaluate('[innerWidth,innerHeight]')
    run.report['timeZone'] = page.evaluate('Intl.DateTimeFormat().resolvedOptions().timeZone')


def allow_local_storage(run):
    """Saving is opt-in. Turn on what this module needs. Hosted Skin processing stays off."""
    page = run.page
    page.get_by_role('link', name='Privacy & Permissions', exact=True).click()
    page.locator('input[type=checkbox]').first.wait_for()
    page.wait_for_timeout(600)
    turned_on, refused = [], []
    # Some preferences depend on another one, so a second pass catches those.
    for _ in range(2):
        for box in page.locator('main input[type=checkbox]').all():
            label = box.evaluate("e=>(e.closest('label')||e.parentElement).innerText")
            if re.search(r'(store|save|keep)', label, re.I) and not re.search(r'cloud|roboflow|hosted', label, re.I) and box.is_enabled() and not box.is_checked():
                box.click()
                page.wait_for_timeout(250)
                (turned_on if box.is_checked() else refused).append(label[:70])
    run.report['storagePreferencesTurnedOn'] = turned_on
    run.report['storagePreferencesRefused'] = sorted(set(refused) - set(turned_on))
    page.locator('nav a[href="/"]').first.click()
    page.wait_for_timeout(600)


def enter_module(run, route):
    page = run.page
    page.get_by_role('button', name='Health Center', exact=True).click()
    run.dwell(900)
    page.locator('#health-centre-links a[href="/' + route + '"]').click()
    run.mark('Module opened')
    dialog = page.get_by_role('dialog')
    page.wait_for_timeout(1000)
    if dialog.count():
        run.mark('Service permissions')
        run.shot('consent')
        run.report['consentText'] = dialog.inner_text()
        run.dwell(1800)
        for box in dialog.get_by_role('checkbox').all():
            box.check()
            page.wait_for_timeout(200)
        run.dwell(600)
        dialog.get_by_role('button', name='Allow and continue', exact=True).click()
    page.locator('[data-health-start]').wait_for()
    run.dwell(1500)
    run.mark('Preparation screen')
    run.shot('preparation')
    run.report['portrait'] = page.locator('[data-health-portrait] img').get_attribute('src')


def walk(run, scope_selector, label, limit=12):
    """Scrolls through a result, opens every detail, then closes it again."""
    page = run.page
    scope = page.locator(scope_selector)
    metrics = page.evaluate(MEASURE)
    run.report.setdefault('layout', {})[label] = metrics
    step = max(220, metrics['usable'] - 60)
    for y in range(step, metrics['total'], step):
        page.evaluate('y=>scrollTo({top:y,behavior:"instant"})', y)
        run.dwell(1100)
    page.evaluate('()=>scrollTo({top:0,behavior:"instant"})')
    run.dwell(500)
    opened = []
    details = scope.locator('details:visible')
    for i in range(min(details.count(), limit)):
        item = details.nth(i)
        summary = item.locator('summary').first
        summary.scroll_into_view_if_needed()
        run.dwell(350)
        summary.click()
        run.dwell(1400)
        opened.append((summary.inner_text() or '')[:50])
        if i < 3:
            run.shot('{}-detail{}'.format(label, i))
        summary.click()
        page.wait_for_timeout(250)
    run.report.setdefault('expanded', {})[label] = opened
    page.evaluate('()=>scrollTo({top:0,behavior:"instant"})')


def open_info(run, scope_selector, label, limit=2):
    page = run.page
    triggers = page.locator(scope_selector + ' [aria-haspopup="dialog"]:visible')
    for i in range(min(triggers.count(), limit)):
        triggers.nth(i).click()
        run.dwell(1500)
        if i == 0:
            run.shot(label + '-info')
        page.keyboard.press('Escape')
        run.dwell(400)


def history(run, module, record_id):
    page = run.page
    page.get_by_role('link', name='My Health History', exact=True).click()
    row = page.locator('[data-record-id="' + record_id + '"]')
    row.wait_for()
    page.wait_for_timeout(1500)
    row.scroll_into_view_if_needed()
    run.mark('Saved history')
    run.shot('history-list')
    run.dwell()
    row.get_by_role('button', name='Open result', exact=True).click()
    dialog = page.get_by_role('dialog')
    dialog.wait_for()
    run.dwell(1800)
    run.mark('Saved result reopened')
    run.shot('history-open')
    run.check('Saved result reopens from history', dialog.count() == 1)
    run.report['historyText'] = dialog.inner_text()[:3000]
    dialog.evaluate('e=>{const s=e.querySelector("[data-dialog-scroll]")||e;s.scrollTop=s.scrollHeight/2;}')
    run.dwell(1300)
    dialog.evaluate('e=>{const s=e.querySelector("[data-dialog-scroll]")||e;s.scrollTop=s.scrollHeight;}')
    run.dwell(1300)
    page.keyboard.press('Escape')
    run.dwell(600)


def new_records(run, module):
    return [r for r in run.page.evaluate("k=>JSON.parse(localStorage.getItem(k)||'[]')", HISTORY[module]) if r.get('id') not in run.report.get('beforeIds', [])]


def before_ids(run, module):
    run.report['beforeIds'] = run.page.evaluate("k=>JSON.parse(localStorage.getItem(k)||'[]').map(x=>x.id)", HISTORY[module])


def responsive(run, selector):
    if run.args.platform != 'web':
        return
    sizes = {}
    for width, height in ((1280, 517), (1024, 600), (800, 480)):
        run.adapter.resize(run.page, width, height)
        run.dwell(1400)
        sizes['{}x{}'.format(width, height)] = run.page.evaluate(MEASURE)
        run.shot('responsive-{}x{}'.format(width, height))
    run.adapter.resize(run.page, 1280, 800)
    run.dwell(700)
    run.report['responsive'] = sizes
    run.check('No sideways overflow at vehicle sizes', not any(v['sideways'] for v in sizes.values()), sizes)


def referral(run, link_pattern):
    page = run.page
    pattern = re.compile(link_pattern, re.I)
    link = page.locator('main').get_by_role('link', name=pattern).first
    if not link.count():
        link = page.locator('main').get_by_role('button', name=pattern).first
    if not link.count():
        run.check('Referral is offered', False)
        return
    link.scroll_into_view_if_needed()
    run.dwell(900)
    link.click()
    page.wait_for_url('**/care**')
    page.locator('[data-care-filters]').wait_for()
    run.mark('Specialists from the result')
    run.dwell(1200)
    region = page.locator('[data-care-region]')
    run.report['careRegionOnArrival'] = region.input_value()
    region.select_option('Berlin')
    page.locator('[data-care-slot]').first.wait_for(timeout=20000)
    run.dwell(1600)
    run.shot('care')
    run.report['careSlots'] = page.locator('[data-care-slot]').count()
    run.report['careTimeZone'] = page.evaluate('Intl.DateTimeFormat().resolvedOptions().timeZone')
    run.dwell(800)


def api_recorder(run, suffixes, keep_body=True):
    def response(res):
        url = res.url.split('?')[0]
        if any(url.endswith(s) for s in suffixes):
            entry = {'path': url.split('/', 3)[-1], 'status': res.status, 'second': round(time.time() - run.started, 1)}
            try:
                timing = res.request.timing
                entry['requestMs'] = round(timing.get('responseEnd', 0), 1)
            except Exception:
                pass
            if keep_body:
                try:
                    run.report.setdefault('apiBodies', []).append({'path': entry['path'], 'body': strip_large(res.json())})
                except Exception:
                    pass
            run.report['api'].append(entry)
            run.save()
    run.page.on('response', response)


def strip_large(value):
    """Keeps method, model and result receipts. Drops pixels and geometry."""
    if isinstance(value, dict):
        return {k: strip_large(v) for k, v in value.items() if k not in ('maps', 'contours', 'photo', 'image', 'mask', 'meshes', 'landmarks', 'points', 'polygons', 'pixels')}
    if isinstance(value, list):
        return [strip_large(v) for v in value[:60]]
    if isinstance(value, str) and len(value) > 4000:
        return value[:200] + '…'
    return value


# ---------------------------------------------------------------- Skin

def skin(run):
    page = run.page
    set_english(run)
    allow_local_storage(run)
    before_ids(run, 'skin')
    api_recorder(run, ['/api/local-health/skin', '/api/local-health/skin/regional-fuse', '/api/local-health/skin/prepare'])
    enter_module(run, 'skin')
    run.adapter.set_pose(page, 'FRONT')
    page.get_by_role('button', name=re.compile('^start analysis$', re.I)).click()
    run.mark('Scan started')
    if run.args.platform == 'aaos':
        run.adapter.pair(page)
    pose = 'FRONT'
    leaked = 0
    seen = set()
    states = []
    deadline = time.time() + 600
    while time.time() < deadline and not page.locator('[data-skin-result]').count():
        text = page.locator('main').inner_text()
        leaked += page.locator('[data-skin-photo-empty]').count()
        match = re.search(r'Stage (\d)/3: (?:Anatomical )?(Front|Right|Left)', text, re.I)
        if match and match[2].upper() != pose:
            pose = match[2].upper()
            run.adapter.set_pose(page, pose)
            run.mark('Pose ' + pose)
        heading = page.locator('main h2').first.inner_text() if page.locator('main h2').count() else ''
        if heading and heading not in seen:
            seen.add(heading)
            states.append(heading)
            run.mark('State: ' + heading)
            run.shot('scan-{}'.format(len(states)))
        if page.locator('[data-skin-camera-waiting]').count() and 'waiting' not in seen:
            seen.add('waiting')
            run.shot('scan-camera-waiting')
        page.wait_for_timeout(500)
    run.report['scanStates'] = states
    page.locator('[data-skin-result]').wait_for(timeout=3000)
    run.check('Saved-record placeholder never appeared during the live scan', leaked == 0, {'occurrences': leaked})
    run.mark('Result')
    run.dwell(2000)
    run.shot('result-overview')
    records = new_records(run, 'skin')
    run.check('One new saved Skin record', len(records) == 1, {'new': len(records)})
    record = records[0]
    run.report['record'] = {'id': record.get('id'), 'date': record.get('date') or record.get('timestamp')}
    (run.out / 'record.json').write_text(json.dumps(strip_large(record), indent=1, ensure_ascii=False))
    overview = page.locator('[data-skin-overview-finding]')
    for i in range(min(overview.count(), 12)):
        overview.nth(i).click()
        run.dwell(1500)
    callouts = page.locator('[data-skin-callout]').count()
    run.report['calloutsOverview'] = callouts
    layout = page.locator('[data-skin-callout-layout]')
    run.report['calloutLayout'] = layout.first.get_attribute('data-skin-callout-layout') if layout.count() else None
    run.shot('result-callouts')
    views = 0
    next_region = page.get_by_role('button', name=re.compile('next region', re.I)).first
    if next_region.count():
        for i in range(8):
            next_region.click()
            run.dwell(2200)
            views += 1
            run.shot('result-region-{}'.format(i + 1))
            cards = page.get_by_role('button', name=re.compile('next finding', re.I))
            if cards.count() and cards.first.is_enabled():
                cards.first.click()
                run.dwell(1400)
    run.report['regionsVisited'] = views
    walk(run, '[data-skin-result]', 'result')
    open_info(run, '[data-skin-result]', 'result')
    recommendations = page.locator('[data-skin-open-recommendations]')
    if recommendations.count():
        recommendations.first.click()
        run.dwell(2000)
        run.mark('Recommendations')
        run.shot('recommendations')
        page.keyboard.press('Escape')
        run.dwell(600)
    responsive(run, '[data-skin-result]')
    referral(run, 'specialist')
    history(run, 'skin', record['id'])
    run.report['status'] = 'PASS' if all(c['passed'] for c in run.report['checks']) else 'FAIL'


# ---------------------------------------------------------------- Dental

def dental(run):
    page = run.page
    set_english(run)
    allow_local_storage(run)
    before_ids(run, 'dental')
    api_recorder(run, ['/api/local-health/dental'])
    enter_module(run, 'dental')
    run.adapter.set_pose(page, 'FRONT')
    page.get_by_role('button', name=re.compile('^start dental scan$', re.I)).click()
    run.mark('Scan started')
    if run.args.platform == 'aaos':
        run.adapter.pair(page)
    pose = 'FRONT'
    leaked = 0
    shot = False
    deadline = time.time() + 420
    while time.time() < deadline and not page.locator('[data-dental-result]').count():
        capture = page.locator('[data-dental-capture]')
        leaked += page.locator('[data-skin-photo-empty]').count()
        if capture.count():
            if not shot:
                page.wait_for_timeout(1000)
                run.shot('capture')
                measured = page.evaluate(MEASURE)
                measured['previewVisiblePct'] = capture.evaluate('e=>{const r=e.getBoundingClientRect();return Math.round(100*Math.max(0,Math.min(r.bottom,innerHeight)-Math.max(r.top,0))/r.height)}')
                run.report['captureLayout'] = measured
                shot = True
            heading = (capture.locator('h2').first.inner_text() or '').lower()
            target = 'BITE' if 'bite' in heading else 'RIGHT' if 'right' in heading else 'LEFT' if 'left' in heading else 'FRONT'
            if target != pose:
                pose = target
                run.adapter.set_pose(page, pose)
                run.mark('View ' + pose)
                run.dwell(1200)
                run.shot('capture-' + pose)
        page.wait_for_timeout(500)
    result = page.locator('[data-dental-result]')
    result.wait_for(timeout=3000)
    run.mark('Result')
    run.dwell(2000)
    run.shot('result')
    measured = result.get_attribute('data-dental-measured')
    run.report['measuredViews'] = measured
    run.check('All four views were measured', str(measured) == '4', {'measured': measured})
    records = new_records(run, 'dental')
    run.check('One new saved Dental record', len(records) == 1, {'new': len(records)})
    record = records[0]
    run.report['record'] = {'id': record.get('id'), 'date': record.get('date') or record.get('timestamp')}
    (run.out / 'record.json').write_text(json.dumps(strip_large(record), indent=1, ensure_ascii=False))
    forward = page.get_by_role('button', name=re.compile('next dental view', re.I)).first
    slides = {}
    # Overview, then the four views.
    for i in range(5):
        slide = page.locator('[data-dental-slide]').first
        name = slide.get_attribute('data-dental-slide') if slide.count() else 'OVERVIEW'
        slides[name] = slide.get_attribute('data-dental-slide-status') if slide.count() else None
        run.mark('Dental ' + name)
        run.shot('view-' + str(name))
        detail = page.get_by_role('button', name='Detail view', exact=True)
        if detail.count() and detail.first.is_visible():
            detail.first.click()
            run.dwell(1400)
            run.shot('view-' + str(name) + '-detail')
        for layer in page.locator('[data-dental-layer]').all():
            if layer.is_visible():
                layer.click()
                run.dwell(1300)
                layer.click()
                page.wait_for_timeout(250)
        if name == 'BITE':
            run.report['biteConfidenceNote'] = page.locator('[data-dental-bite-confidence]').count() == 1
            run.report['biteAlignmentText'] = slide.inner_text()[:600]
            run.dwell(2000)
        if i < 4 and forward.count() and forward.is_enabled():
            forward.click()
            run.dwell(1200)
    run.report['slides'] = slides
    run.check('All four view results were shown', all(slides.get(p) == 'measured' for p in ('FRONT', 'RIGHT', 'LEFT', 'BITE')), slides)
    walk(run, '[data-dental-result]', 'result')
    open_info(run, '[data-dental-result]', 'result')
    responsive(run, '[data-dental-result]')
    referral(run, 'specialist|service|care|dentist')
    history(run, 'dental', record['id'])
    run.report['status'] = 'PASS' if all(c['passed'] for c in run.report['checks']) else 'FAIL'


# ---------------------------------------------------------------- Hearing

class Output(threading.Thread):
    """Reads the real audio output and reports the level per channel."""
    WINDOW = 960  # 20 ms at 48 kHz

    def __init__(self):
        super().__init__(daemon=True)
        self.process = subprocess.Popen(['parec', '--device=attune_out.monitor', '--format=float32le', '--rate=48000', '--channels=2', '--latency-msec=20'], stdout=subprocess.PIPE, stderr=subprocess.DEVNULL)
        self.levels = (-120., -120.)
        self.peak = [-120., -120.]
        self.running = True

    def run(self):
        size = self.WINDOW * 8
        while self.running:
            raw = self.process.stdout.read(size)
            if len(raw) < size:
                return
            values = struct.unpack('<{}f'.format(self.WINDOW * 2), raw)
            left = sum(v * v for v in values[0::2]) / self.WINDOW
            right = sum(v * v for v in values[1::2]) / self.WINDOW
            self.levels = tuple(10 * math.log10(max(x, 1e-12)) for x in (left, right))
            self.peak = [max(self.peak[0], self.levels[0]), max(self.peak[1], self.levels[1])]

    def reset_peak(self):
        self.peak = [-120., -120.]

    def stop(self):
        self.running = False
        self.process.terminate()


def hearing_prepare(run, output=None):
    """Plays each channel sample. Returns the measured gain of the output path from the -40 dBFS sample."""
    page = run.page
    page.get_by_role('button', name=re.compile('start audio preparation', re.I)).click()
    run.mark('Sound preparation')
    run.dwell(1500)
    gains = {}
    for ear, button, box in (('left', 'Listen to left channel', 'I heard it only in my left ear.'), ('right', 'Listen to right channel', 'I heard it only in my right ear.')):
        listen = page.get_by_role('button', name=re.compile(button.replace('Listen to ', ''), re.I)).first
        listen.wait_for()
        if output:
            # Spoken guidance plays first. Only the channel sample may set the path gain.
            quiet = time.time()
            limit = time.time() + 30
            while time.time() < limit and time.time() - quiet < .6:
                if max(output.levels) > -75:
                    quiet = time.time()
                page.wait_for_timeout(50)
            output.reset_peak()
        listen.click()
        page.wait_for_timeout(1600)
        if output:
            gains[ear] = [round(v, 1) for v in output.peak]
        check = page.get_by_role('checkbox', name=re.compile(ear + ' ear', re.I)).first
        for _ in range(40):
            if check.is_enabled():
                break
            page.wait_for_timeout(200)
        check.check()
        run.dwell(900)
    run.report['channelSamplesRmsDb'] = gains
    return gains


def din(run):
    page = run.page
    set_english(run)
    allow_local_storage(run)
    before_ids(run, 'hearing')
    enter_module(run, 'hearing')
    hearing_prepare(run)
    page.get_by_role('button', name=re.compile('digits in', re.I)).first.click()
    run.mark('Digits in noise started')
    answer = page.get_by_role('textbox').first
    answer.wait_for()
    seed = page.evaluate('window.__observedDinSeed')
    run.check('Trial sequence observed', isinstance(seed, (int, float)), None)

    def random():
        nonlocal seed
        seed = (1664525 * int(seed) + 1013904223) & 0xffffffff
        return seed / 4294967296
    snr, last, reversals = 0, 0, 0
    # A scripted listener that follows the digits down to about -6 dB SNR. It reads no audio.
    rows = []
    for i in range(24):
        page.wait_for_function("()=>{const e=document.querySelector('input[inputmode=numeric]');return e&&!e.disabled;}", timeout=45000)
        digits = [math.floor(random() * 10) for _ in range(3)]
        random()
        correct = snr >= -6
        response = digits if correct else [digits[0], (digits[1] + 1) % 10, (digits[2] + 3) % 10]
        answer.fill(''.join(str(v) for v in response))
        run.dwell(350)
        page.get_by_role('button', name=re.compile('submit', re.I)).first.click()
        rows.append({'trial': i + 1, 'digits': digits, 'response': response, 'snrTracked': snr})
        direction = -1 if correct else 1
        if last and direction != last and -15 < snr < 15:
            reversals += 1
        snr = max(-15, min(15, snr + direction * (2 if reversals >= 2 else 4)))
        last = direction
        if i in (0, 12):
            run.shot('din-trial-{}'.format(i + 1))
    run.report['scriptedTrials'] = rows
    result = page.locator('[data-din-result]')
    result.wait_for(timeout=60000)
    run.mark('Result')
    run.dwell(2000)
    run.shot('result')
    records = new_records(run, 'hearing')
    run.check('One new saved Hearing record', len(records) == 1, {'new': len(records)})
    record = records[0]
    run.report['record'] = {k: record.get(k) for k in ('id', 'timestamp', 'value', 'validTrials', 'digitAccuracy', 'tripletAccuracy', 'quality', 'reversals', 'methodVersion')}
    played = [{'digits': t['digits'], 'answer': t['answer'], 'snr': t['snr'], 'correct': t['correct']} for t in record['history'] if not t.get('repeated')]
    run.report['storedTrials'] = played
    run.check('Stored digits match the digits the scripted listener derived', all(a['digits'] == b['digits'] and a['answer'] == b['response'] for a, b in zip(played, rows)) and len(played) == 24, {'stored': len(played)})
    expected = sum(sum(x == y for x, y in zip(a['digits'], a['answer'])) for a in played)
    shown = result.locator('[data-din-scorecards]').inner_text()
    run.report['scoreCards'] = shown
    run.check('Result shows the recomputed digit count', '{}/{}'.format(expected, len(played) * 3) in shown.replace(' ', ''), {'expected': expected, 'shown': shown[:120]})
    run.check('Limits are on the result', result.locator('[data-hearing-limits]').count() == 1)
    walk(run, '[data-din-result]', 'result')
    open_info(run, '[data-hearing-page]', 'result', limit=1)
    responsive(run, '[data-din-result]')
    referral(run, 'service')
    history(run, 'hearing', record['id'])
    run.report['status'] = 'PASS' if all(c['passed'] for c in run.report['checks']) else 'FAIL'


TONE_STATE = """()=>{const panel=document.querySelector('[data-hearing-current-panel]');if(!panel)return null;
 const head=document.querySelector('[data-hearing-previous-panel] h3');
 const hz=(panel.innerText.match(/([\\d.,]+)\\s*Hz/)||[])[1];
 const level=[...panel.querySelectorAll('[role=meter]')].map(m=>m.getAttribute('aria-valuetext')||'').find(t=>/dBFS/.test(t));
 return {ear:/left/i.test(head?head.innerText:'')?'left':'right',hz:hz?Number(hz.replace(/[.,]/g,'')):null,level:level?parseFloat(level):null};}"""


def tone(run):
    page = run.page
    set_english(run)
    allow_local_storage(run)
    before_ids(run, 'hearing')
    enter_module(run, 'hearing')
    output = Output()
    output.start()
    gains = hearing_prepare(run, output)
    # The channel samples play at -40 dBFS peak, which is -43 dB RMS for a sine. The difference is the path gain.
    measured = [gains['left'][0], gains['right'][1]]
    gain = max(measured) + 43
    leak = {'leftSampleOnRight': gains['left'][1], 'rightSampleOnLeft': gains['right'][0]}
    separated = gains['left'][0] - gains['left'][1] > 20 and gains['right'][1] - gains['right'][0] > 20
    run.report['audioPath'] = {'gainDb': round(gain, 1), 'channelSeparated': separated, **leak}
    run.check('Channel sample level is plausible', abs(gain) < 20, {'gainDb': round(gain, 1)})
    run.check('Channel samples reached the correct channel', separated, run.report['audioPath'])
    page.get_by_role('button', name=re.compile('pure.?tone', re.I)).first.click()
    run.mark('Pure-tone test started')
    press = page.get_by_role('button', name=re.compile('^i heard it', re.I)).first
    press.wait_for()
    presses = wrong_channel = 0
    armed = True
    quiet_since = time.time()
    rows = []
    shots = 0
    deadline = time.time() + 1500
    result = page.locator('[data-hearing-result]')
    while time.time() < deadline and not result.count():
        state = page.evaluate(TONE_STATE)
        if not state:
            page.wait_for_timeout(100)
            continue
        hz = state['hz'] if state['hz'] in LISTENER else 1000
        heard_level = LISTENER[hz] + (RIGHT_EAR_OFFSET if state['ear'] == 'right' else 0)
        index = 0 if state['ear'] == 'left' else 1
        level = output.levels[index] - gain + 3
        other = output.levels[1 - index] - gain + 3
        if armed and level >= heard_level:
            if other > level + 6:
                wrong_channel += 1
            press.click()
            presses += 1
            armed = False
            rows.append({'ear': state['ear'], 'hz': hz, 'plannedLevel': state['level'], 'observedDbfs': round(level, 1), 'otherChannelDbfs': round(other, 1)})
            run.report['presses'] = rows[-400:]
            if shots < 3 and presses in (1, 10, 40):
                run.shot('tone-{}'.format(presses))
                shots += 1
        loud = max(output.levels) - gain + 3 > -86
        if loud:
            quiet_since = time.time()
        elif not armed and time.time() - quiet_since > .25:
            armed = True
        page.wait_for_timeout(30)
    output.stop()
    result.first.wait_for(timeout=5000)
    run.mark('Result')
    run.dwell(2000)
    run.shot('result')
    run.check('The listener only responded on the tested channel', wrong_channel == 0, {'presses': presses, 'wrongChannel': wrong_channel})
    records = new_records(run, 'hearing')
    run.check('One new saved Hearing record', len(records) == 1, {'new': len(records)})
    record = records[0]
    run.report['record'] = {k: record.get(k) for k in ('id', 'timestamp', 'quality', 'unit', 'methodVersion', 'catchTrials', 'catchFalsePositive', 'totalPresentations')}
    run.report['thresholds'] = record.get('thresholds')
    usable = [t for t in record.get('thresholds') or [] if t.get('status') == 'threshold']
    run.check('Levels were determined on both ears', {t['ear'] for t in usable} == {'left', 'right'} and len(usable) >= 10, {'determined': len(usable)})
    scope = '[data-hearing-result]'
    run.check('Limits are on the result', page.locator(scope + ' [data-hearing-limits]').count() >= 1)
    run.report['levelTable'] = page.locator('[data-hearing-level-summary]').inner_text() if page.locator('[data-hearing-level-summary]').count() else None
    walk(run, scope, 'overview')
    for name in ('Frequency analysis', 'Measurement consistency'):
        tab = page.get_by_role('button', name=name, exact=True)
        if tab.count():
            tab.first.click()
            run.dwell(2200)
            run.mark('Result tab: ' + name)
            run.shot('result-' + name.split()[0].lower())
            forward = page.locator('[data-hearing-inner] button[aria-label]').last
            if forward.count() and forward.is_enabled():
                forward.click()
                run.dwell(1500)
    overview = page.get_by_role('button', name='Overview', exact=True)
    if overview.count():
        overview.first.click()
        run.dwell(800)
    open_info(run, '[data-hearing-page]', 'result', limit=1)
    responsive(run, scope)
    referral(run, 'service')
    history(run, 'hearing', record['id'])
    run.report['status'] = 'PASS' if all(c['passed'] for c in run.report['checks']) else 'FAIL'


# ---------------------------------------------------------------- Mental

def phase(page):
    node = page.locator('[data-conversation-phase]')
    return node.first.get_attribute('data-conversation-phase') if node.count() else None


def mental(run):
    page = run.page
    set_english(run)
    allow_local_storage(run)
    before_ids(run, 'mental')
    api_recorder(run, ['/api/speech/transcribe', '/api/mental/chat', '/api/mental/session/summary', '/api/mental-neural-speech'], keep_body=False)

    def speech_headers(res):
        if res.url.split('?')[0].endswith('/api/mental-neural-speech'):
            run.report.setdefault('speech', []).append({'status': res.status, 'seconds': res.headers.get('x-tts-seconds'), 'start': res.headers.get('x-tts-start'), 'second': round(time.time() - run.started, 1)})
            run.save()
    page.on('response', speech_headers)
    enter_module(run, 'mental')
    page.get_by_role('button', name=re.compile('^start (the )?(conversation|session)', re.I)).first.click()
    run.mark('Conversation started')
    clips = sorted(Path(run.args.clips).glob('mental-*.wav'))[:5]
    run.check('Five speech inputs in order', [c.name for c in clips] == ['mental-{}.wav'.format(i) for i in range(1, 6)], [c.name for c in clips])
    turns = []
    for number, clip in enumerate(clips, 1):
        deadline = time.time() + 300
        while time.time() < deadline and phase(page) != 'listening':
            gesture = page.locator('[data-neural-play-response]')
            if gesture.count() and gesture.first.is_enabled():
                gesture.first.click()
            page.wait_for_timeout(250)
        if phase(page) != 'listening':
            raise RuntimeError('Not listening before turn {}: {}'.format(number, phase(page)))
        page.wait_for_timeout(1200)
        users = page.locator('[data-chat-author=USER]').count()
        ais = page.locator('[data-chat-author=AI]').count()
        subprocess.Popen(['paplay', '--device=attune_mic', str(clip)]).wait()
        said = time.time()
        run.mark('Turn {} spoken'.format(number))
        page.wait_for_function('n=>document.querySelectorAll("[data-chat-author=USER]").length>n', arg=users, timeout=120000)
        heard = time.time()
        page.wait_for_function('n=>document.querySelectorAll("[data-chat-author=AI]").length>n', arg=ais, timeout=120000)
        replied = time.time()
        speaking = None
        deadline = time.time() + 300
        while time.time() < deadline:
            gesture = page.locator('[data-neural-play-response]')
            if gesture.count() and gesture.first.is_enabled():
                gesture.first.click()
            if phase(page) == 'speaking':
                speaking = time.time()
                break
            if phase(page) == 'error':
                raise RuntimeError('Conversation error after turn {}'.format(number))
            page.wait_for_timeout(120)
        turns.append({'turn': number, 'clipSeconds': None, 'speechEndToTranscriptSeconds': round(heard - said, 1), 'transcriptToReplyTextSeconds': round(replied - heard, 1),
                      'replyTextToPlaybackSeconds': round(speaking - replied, 1) if speaking else None, 'speechEndToPlaybackSeconds': round(speaking - said, 1) if speaking else None})
        run.report['turns'] = turns
        run.mark('Turn {} reply playing'.format(number))
        if number == 2:
            run.shot('conversation')
    deadline = time.time() + 300
    while time.time() < deadline and phase(page) not in ('listening', 'error'):
        page.wait_for_timeout(250)
    page.get_by_role('button', name=re.compile('^end (the )?(conversation|session)', re.I)).first.click()
    run.mark('Conversation ended')
    summary = page.locator('[data-mental-current-summary], [data-summary-provider]')
    deadline = time.time() + 300
    while time.time() < deadline and not new_records(run, 'mental'):
        page.wait_for_timeout(500)
    records = new_records(run, 'mental')
    run.check('One new saved Mental record', len(records) == 1, {'new': len(records)})
    record = records[0]
    run.dwell(2000)
    run.mark('Summary')
    run.shot('summary')
    notice = page.get_by_role('dialog')
    if notice.count():
        run.report['completionNotice'] = notice.inner_text()[:300]
        run.dwell(1500)
        notice.get_by_role('button', name=re.compile('^(OK|Done)$', re.I)).first.click()
        run.dwell(800)
    run.report['record'] = {k: record.get(k) for k in ('id', 'date', 'summaryText', 'themes', 'moodTrend', 'providerType', 'transcriptConsented', 'completed')}
    transcript = record.get('transcript') or []
    run.report['transcript'] = [{'sender': m.get('sender'), 'text': m.get('text')} for m in transcript]
    english = [record.get('summaryText') or ''] + [m['text'] for m in transcript if m.get('sender') == 'AI']
    run.check('Summary and replies are in English, with no Turkish letters', not any(TURKISH.search(t) for t in english), [t[:90] for t in english if TURKISH.search(t)][:3])
    run.check('Each turn played a spoken reply', all(t['speechEndToPlaybackSeconds'] is not None for t in turns), None)
    timings = page.evaluate('window.__qaTimings||[]')
    run.report['browserTimings'] = timings[-200:]
    walk(run, 'main', 'summary')
    open_info(run, 'main', 'summary', limit=1)
    responsive(run, 'main')
    referral(run, 'service|specialist|psycholog')
    history(run, 'mental', record['id'])
    run.report['status'] = 'PASS' if all(c['passed'] for c in run.report['checks']) else 'FAIL'


# ---------------------------------------------------------------- Specialists and appointments

def care(run):
    page = run.page
    set_english(run)
    page.evaluate("()=>{localStorage.removeItem('attune.care.region.v1');localStorage.removeItem('attune.care.appointments.v1');}")
    requests = []
    page.on('request', lambda r: requests.append(json.loads(r.post_data or '{}')) if r.url.split('?')[0].endswith('/api/care/match') else None)
    page.get_by_role('link', name='Specialists & Appointments', exact=True).click()
    page.locator('[data-care-filters]').wait_for()
    run.dwell(1500)
    run.mark('Specialists page')
    run.shot('care-no-region')
    run.check('No region is assumed', page.locator('[data-care-region]').input_value() == '' and page.locator('[data-care-region-required]').count() == 1)
    run.check('No search runs without a region', not requests, requests[:1])
    run.report['layout'] = {'care': page.evaluate(MEASURE)}
    run.check('First viewport has no sideways overflow', not run.report['layout']['care']['sideways'])
    page.locator('[data-care-region]').select_option('Berlin')
    page.get_by_role('button', name='Dermatology', exact=True).click()
    slot = page.locator('[data-care-slot]').first
    slot.wait_for(timeout=20000)
    run.dwell(1200)
    run.mark('Options for specialty and region')
    run.shot('care-results')
    run.check('Search used the chosen region, in the English interface', requests[-1].get('preferredCity') == 'Berlin', {k: requests[-1].get(k) for k in ('specialty', 'preferredCity', 'timeZone')})
    run.report['deviceTimeZone'] = page.evaluate('Intl.DateTimeFormat().resolvedOptions().timeZone')
    run.check('The device time zone is sent', requests[-1].get('timeZone') == run.report['deviceTimeZone'], requests[-1].get('timeZone'))
    text = page.locator('main').inner_text()
    run.check('The page says no appointment is booked here', 'No appointment is booked here' in text)
    run.check('No technical labels on the page', not re.search(r'PUBLIC_|LIVE_|providerType|sourceId|Smart Doctor Access', text), None)
    page.locator('[data-care-region]').select_option('İstanbul')
    page.locator('[data-care-slot]').first.wait_for(timeout=20000)
    run.dwell(800)
    run.check('Region change searches that region', requests[-1].get('preferredCity') == 'İstanbul')
    page.locator('[data-care-region]').select_option('Berlin')
    slot = page.locator('[data-care-slot]').first
    page.wait_for_timeout(1500)
    slot.get_by_role('button', name='Review appointment', exact=True).click()
    dialog = page.get_by_role('dialog')
    dialog.wait_for()
    run.dwell(1200)
    run.shot('care-consent')
    dialog.get_by_role('checkbox').check()
    dialog.get_by_role('button', name='Confirm and continue').click()
    run.dwell(1200)
    run.mark('Referral ready')
    run.shot('care-handoff')
    run.check('No appointment is claimed yet', not page.evaluate("JSON.parse(localStorage.getItem('attune.care.appointments.v1')||'[]').length"))
    link = page.locator('[data-care-open-provider]')
    run.report['providerLink'] = link.get_attribute('href')
    if run.args.platform == 'web':
        with page.context.expect_page() as popup:
            link.click()
        popup.value.close()
    else:
        link.click()
        page.wait_for_timeout(1800)
        # The native shell asks before leaving the app. Stay in the app.
        subprocess.run([ADB, '-s', 'emulator-5554', 'shell', 'input', 'keyevent', '4'], stdin=subprocess.DEVNULL, check=False)
    page.locator('[data-care-return]').wait_for()
    run.dwell(1500)
    run.mark('Back from the provider')
    run.shot('care-return')
    run.check('Opening the provider saved nothing', not page.evaluate("JSON.parse(localStorage.getItem('attune.care.appointments.v1')||'[]').length"))
    run.check('The user is asked whether they booked', page.locator('[data-care-return]').inner_text().find('Did you book') >= 0)
    page.locator('[data-care-return-yes]').click()
    form = page.get_by_role('dialog')
    form.wait_for()
    run.dwell(800)
    run.check('The form has no meeting link field', form.locator('input[type=url]').count() == 0 and not re.search(r'link|url', form.inner_text(), re.I))
    form.locator('[data-appointment-provider]').fill('Dr. Weber Praxis')
    form.locator('[data-appointment-time]').fill('2030-03-05T14:30')
    form.locator('[data-appointment-address]').fill('Hauptstr. 1, Berlin')
    run.dwell(800)
    run.shot('care-form')
    form.locator('[data-appointment-save]').click()
    row = page.locator('[data-appointment-row]')
    row.first.wait_for()
    run.dwell(1200)
    run.mark('Appointment saved')
    run.shot('care-saved')
    shown = row.first.inner_text()
    run.report['savedRow'] = shown
    run.check('The saved row shows the entered local time', re.search(r'2:30|14:30', shown) is not None and '2030' in shown, shown[:120])
    run.check('No UTC on the saved row', 'UTC' not in shown)
    page.reload(wait_until='networkidle')
    row = page.locator('[data-appointment-row]')
    row.first.wait_for()
    run.check('The appointment survives a refresh', row.count() == 1)
    row.first.locator('[data-appointment-edit]').click()
    form = page.get_by_role('dialog')
    form.wait_for()
    form.locator('[data-appointment-type=ONLINE]').check()
    run.dwell(500)
    run.check('An online appointment has no address field', form.locator('[data-appointment-address]').count() == 0)
    form.locator('[data-appointment-save]').click()
    page.wait_for_timeout(800)
    stored = page.evaluate("JSON.parse(localStorage.getItem('attune.care.appointments.v1')||'[]')")
    run.check('Editing keeps one record and drops the address', len(stored) == 1 and stored[0]['type'] == 'ONLINE' and 'address' not in stored[0], stored)
    run.shot('care-edited')
    page.locator('[data-appointment-delete]').first.click()
    confirm = page.get_by_role('dialog')
    confirm.wait_for()
    run.dwell(800)
    run.shot('care-delete')
    run.check('Deleting says the provider booking is not cancelled', 'not cancelled' in confirm.inner_text())
    confirm.locator('[data-appointment-delete-confirm]').click()
    page.locator('[data-appointments-empty]').wait_for()
    page.reload(wait_until='networkidle')
    page.locator('[data-appointments-empty]').wait_for()
    run.check('The deleted appointment stays deleted after a refresh', not page.evaluate("JSON.parse(localStorage.getItem('attune.care.appointments.v1')||'[]').length"))
    run.report['status'] = 'PASS' if all(c['passed'] for c in run.report['checks']) else 'FAIL'


# ---------------------------------------------------------------- Visual states on the real page

COVERED = """()=>{const bars=[...document.querySelectorAll('[data-cockpit-header]')].map(e=>e.getBoundingClientRect());
 const seen=e=>{const r=e.getBoundingClientRect(),c=getComputedStyle(e);return r.width>0&&r.height>0&&c.visibility!=='hidden'&&c.display!=='none';};
 const small=[...document.querySelectorAll('main button,main a[href],main summary,main select')].filter(seen).filter(e=>{const r=e.getBoundingClientRect();return Math.min(r.width,r.height)<43.5;}).map(e=>(e.innerText||e.getAttribute('aria-label')||e.tagName).slice(0,28));
 const tiny=[...document.querySelectorAll('main *')].filter(e=>seen(e)&&[...e.childNodes].some(n=>n.nodeType===3&&n.textContent.trim())&&parseFloat(getComputedStyle(e).fontSize)<12).length;
 const glyphs=[...document.querySelectorAll('main *')].filter(e=>[...e.childNodes].some(n=>n.nodeType===3&&/[\\u24D8\\u2715\\uFFFD]/.test(n.textContent))).length;
 return {smallTargets:small.slice(0,6),smallCount:small.length,tinyText:tiny,unsafeGlyphs:glyphs};}"""
DIALOG_FIT = """()=>{const p=[...document.querySelectorAll('[role=dialog]')].pop();if(!p)return null;const r=p.getBoundingClientRect();
 const actions=p.querySelector('[data-dialog-actions]');const a=actions?actions.getBoundingClientRect():null;
 // Text is a peek when it shows in the gap below the pinned buttons.
 const peek=a?[...p.querySelectorAll('p,label,li,span,h1,h2,h3,summary')].filter(e=>!actions.contains(e)&&e.getClientRects().length).filter(e=>{const b=e.getBoundingClientRect();return b.bottom>a.bottom+1&&b.top<r.bottom-1&&b.height>0;}).map(e=>(e.innerText||'').slice(0,40)):[];
 return {width:Math.round(r.width),height:Math.round(r.height),fits:r.top>=-1&&r.bottom<=innerHeight+1,sharePct:Math.round(100*r.width*r.height/(innerWidth*innerHeight)),actionsInView:a?a.top>=r.top-1&&a.bottom<=r.bottom+1:null,textBelowActions:peek.slice(0,4),scrollable:p.scrollHeight>p.clientHeight+1};}"""
HERO = """()=>{const cards=[...document.querySelectorAll('main a[href],main button')].filter(e=>/skin|dental|vision|hearing|mental|health/i.test(e.getAttribute('href')||e.innerText||''));
 const inView=cards.filter(e=>{const r=e.getBoundingClientRect();return r.top>=0&&r.bottom<=innerHeight;}).length;return {actions:cards.length,fullyInFirstScreen:inView};}"""


def ui(run):
    page = run.page
    run.adapter.home(page)
    rows = []
    page.wait_for_function("document.querySelector('[data-vehicle-status]')?.textContent==='PARK'")
    run.report['viewport'] = page.evaluate('[innerWidth,innerHeight]')
    for language, health, privacy in (('en', 'Health Center', 'Privacy & Permissions'), ('de', None, None), ('tr', None, None)):
        page.locator('#attune-language').select_option(language)
        page.wait_for_timeout(700)
        page.locator('nav a[href="/"]').first.click()
        page.wait_for_timeout(1000)
        run.shot('{}-cockpit'.format(language))
        rows.append({'language': language, 'state': 'cockpit', **page.evaluate(MEASURE), **page.evaluate(COVERED), **page.evaluate(HERO)})
        for route in ('skin', 'dental', 'vision', 'hearing', 'mental'):
            consent = page.evaluate("()=>{const v=localStorage.getItem('attune_health_processing_v1');localStorage.removeItem('attune_health_processing_v1');window.dispatchEvent(new Event('attune-service-consent'));return v;}")
            page.goto(page.url.split('/', 3)[0] + '//' + page.url.split('/', 3)[2] + '/' + route, wait_until='networkidle')
            page.wait_for_timeout(1200)
            dialog = page.locator('[role=dialog]')
            if dialog.count():
                fit = page.evaluate(DIALOG_FIT)
                rows.append({'language': language, 'state': route + ' consent', **fit})
                run.shot('{}-{}-consent'.format(language, route))
                dialog.last.evaluate('e=>{e.scrollTop=e.scrollHeight;}')
                page.wait_for_timeout(350)
                run.shot('{}-{}-consent-scrolled'.format(language, route))
                rows.append({'language': language, 'state': route + ' consent scrolled', **page.evaluate(DIALOG_FIT)})
                for box in dialog.last.get_by_role('checkbox').all():
                    box.check()
                dialog.last.locator('[data-dialog-actions] button').first.click()
                page.wait_for_timeout(900)
            run.shot('{}-{}'.format(language, route))
            rows.append({'language': language, 'state': route, **page.evaluate(MEASURE), **page.evaluate(COVERED)})
            info = page.locator('main [aria-haspopup="dialog"]:visible')
            if info.count() and language == 'en':
                info.first.click()
                page.wait_for_timeout(600)
                rows.append({'language': language, 'state': route + ' information', **(page.evaluate(DIALOG_FIT) or {})})
                run.shot('{}-{}-info'.format(language, route))
                page.keyboard.press('Escape')
                page.wait_for_timeout(350)
        for route in ('care', 'history', 'privacy'):
            page.goto(page.url.split('/', 3)[0] + '//' + page.url.split('/', 3)[2] + '/' + route, wait_until='networkidle')
            page.wait_for_timeout(900)
            run.shot('{}-{}'.format(language, route))
            rows.append({'language': language, 'state': route, **page.evaluate(MEASURE), **page.evaluate(COVERED)})
    page.locator('#attune-language').select_option('en')
    run.report['states'] = rows
    run.check('No sideways overflow in any state', not [r for r in rows if r.get('sideways')], [r['state'] for r in rows if r.get('sideways')][:6])
    dialogs = [r for r in rows if 'fits' in r]
    run.check('Every dialog fits the screen', all(r['fits'] for r in dialogs), [(r['language'], r['state']) for r in dialogs if not r['fits']][:6])
    run.check('Dialog actions stay in view', all(r['actionsInView'] is not False for r in dialogs), [(r['language'], r['state']) for r in dialogs if r['actionsInView'] is False][:6])
    run.check('No consent text shows below the pinned buttons', not [r for r in dialogs if r.get('textBelowActions')], [(r['language'], r['state'], r['textBelowActions']) for r in dialogs if r.get('textBelowActions')][:4])
    run.check('No undersized controls or tiny text', not [r for r in rows if r.get('smallCount') or r.get('tinyText')], [(r['language'], r['state'], r.get('smallTargets'), r.get('tinyText')) for r in rows if r.get('smallCount') or r.get('tinyText')][:6])
    run.check('No font-dependent glyphs', not [r for r in rows if r.get('unsafeGlyphs')], [(r['language'], r['state']) for r in rows if r.get('unsafeGlyphs')][:6])
    run.report['status'] = 'PASS' if all(c['passed'] for c in run.report['checks']) else 'FAIL'


# ---------------------------------------------------------------- Camera states (QA-33)

CAMERA_OFF = """()=>{window.__qaCamera=navigator.mediaDevices.getUserMedia.bind(navigator.mediaDevices);navigator.mediaDevices.getUserMedia=()=>Promise.reject(new DOMException('Camera unavailable','NotReadableError'));}"""
CAMERA_ON = """()=>{if(window.__qaCamera)navigator.mediaDevices.getUserMedia=window.__qaCamera;}"""
CAMERA_READ = """()=>{const v=document.querySelector('main video');return {video:!!v,ready:v?v.readyState:0,width:v?v.videoWidth:0,
 waiting:!!document.querySelector('[data-skin-camera-waiting]'),placeholder:!!document.querySelector('[data-skin-photo-empty]'),
 pairing:!!document.querySelector('dialog[open] textarea'),text:(document.querySelector('main')?.innerText||'').replace(/\\s+/g,' ').slice(0,240)};}"""


def camera(run):
    """What the preview shows in each camera state. The failure here is injected, in this journey only, never in a recording."""
    page = run.page
    set_english(run)
    allow_local_storage(run)
    rows = []

    def state(module, name):
        reading = page.evaluate(CAMERA_READ)
        rows.append({'module': module, 'state': name, **reading})
        run.shot('{}-{}'.format(module, name.replace(' ', '-')))
        run.mark('{}: {}'.format(module, name))
        return reading

    for module, start in (('skin', '^start analysis$'), ('dental', '^start dental scan$')):
        run.adapter.home(page)
        enter_module(run, module)
        state(module, 'fresh entry')
        button = page.get_by_role('button', name=re.compile(start, re.I))
        # Camera unavailable. WEB: the browser refuses the camera. AAOS: the person cancels the demo camera pairing.
        if run.args.platform == 'web':
            page.evaluate(CAMERA_OFF)
            button.click()
        else:
            button.click()
            page.locator('dialog[open] textarea').wait_for()
            state(module, 'pairing')
            page.locator('dialog[open] button').click()
        again = page.get_by_role('button', name=re.compile('try again|scan again', re.I))
        # A person should not be left waiting. Twenty seconds covers the analysis start before the camera request.
        limit = time.time() + 20
        while time.time() < limit and not again.count():
            page.wait_for_timeout(250)
        run.report.setdefault('secondsToFailure', {})[module] = round(20 - (limit - time.time()), 1)
        unavailable = state(module, 'camera unavailable')
        run.check('{}: unavailable camera says so and shows no saved-record text'.format(module), not unavailable['placeholder'] and not unavailable['video'] and bool(re.search('camera|cancel', unavailable['text'], re.I)), unavailable['text'][:160])
        # Try again, with the camera back.
        if run.args.platform == 'web':
            page.evaluate(CAMERA_ON)
        run.check('{}: a retry control is offered'.format(module), again.count() > 0, again.count())
        again.first.click()
        page.wait_for_timeout(500)
        if page.get_by_role('button', name=re.compile(start, re.I)).count():
            page.get_by_role('button', name=re.compile(start, re.I)).click()
        if run.args.platform == 'aaos':
            run.adapter.set_pose(page, 'FRONT')
            run.adapter.pair(page)
        waiting = leaked = 0
        deadline = time.time() + 45
        reading = {}
        while time.time() < deadline:
            reading = page.evaluate(CAMERA_READ)
            waiting += 1 if reading['waiting'] else 0
            leaked += 1 if reading['placeholder'] else 0
            if reading['video'] and reading['ready'] >= 2 and reading['width'] > 0:
                break
            page.wait_for_timeout(250)
        run.dwell(1200)
        state(module, 'live after retry')
        run.report.setdefault('waitingPolls', {})[module] = waiting
        run.check('{}: the camera recovers after retry'.format(module), reading.get('ready', 0) >= 2 and reading.get('width', 0) > 0, {'ready': reading.get('ready'), 'width': reading.get('width')})
        run.check('{}: no saved-record text during the live start'.format(module), leaked == 0, {'occurrences': leaked})
    run.adapter.home(page)
    run.report['states'] = rows
    run.report['status'] = 'PASS' if all(c['passed'] for c in run.report['checks']) else 'FAIL'


JOURNEYS = {'skin': skin, 'dental': dental, 'din': din, 'tone': tone, 'mental': mental, 'care': care, 'ui': ui, 'camera': camera}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--module', choices=sorted(JOURNEYS), required=True)
    parser.add_argument('--platform', choices=['web', 'aaos'], required=True)
    parser.add_argument('--out', required=True)
    parser.add_argument('--frames', help='y4m path with POSE in it, for the WEB camera')
    parser.add_argument('--poses', default='FRONT,RIGHT,LEFT')
    parser.add_argument('--input-map', type=json.loads, default={})
    parser.add_argument('--clips', default=str(QA))
    parser.add_argument('--record', action='store_true')
    parser.add_argument('--fps', type=int, default=12)
    parser.add_argument('--dwell', type=int, default=1500)
    parser.add_argument('--display', default=':99')
    parser.add_argument('--video-size', default='1280x800')
    parser.add_argument('--timezone', default='Europe/Berlin')
    parser.add_argument('--profile', default=str(QA / 'profile-web'))
    parser.add_argument('--pose-file', default=str(QA / 'camera-pose.txt'))
    parser.add_argument('--pair-file', default=str(QA / 'camera-pair.json'))
    args = parser.parse_args()
    run = Run(args)
    adapter = Web(args) if args.platform == 'web' else Aaos(args)
    run.adapter = adapter
    with sync_playwright() as playwright:
        page, close = adapter.open(playwright)
        page.set_default_timeout(30000)
        run.page = page
        page.on('pageerror', lambda e: run.report['errors'].append(str(e)[:300]))
        run.start_recording()
        try:
            JOURNEYS[args.module](run)
        except Exception as error:
            run.report['status'] = 'ERROR'
            run.report['failure'] = str(error)[:900]
            print('ERROR', str(error)[:900], flush=True)
            try:
                run.shot('failure')
                run.report['failurePageText'] = page.locator('body').inner_text()[:1200]
            except Exception:
                pass
        finally:
            run.stop_recording()
            run.report['finishedAt'] = dt.datetime.now(dt.timezone.utc).isoformat()
            run.save()
            adapter.close()
            close()
    if shutil.which('ffprobe') and (run.out / 'video.mp4').exists():
        probe = subprocess.run(['ffprobe', '-v', 'error', '-show_entries', 'format=duration,size:stream=codec_type,width,height,avg_frame_rate', '-of', 'json', str(run.out / 'video.mp4')], capture_output=True, text=True)
        run.report['video'] = json.loads(probe.stdout or '{}')
        run.save()
    print(json.dumps({'status': run.report.get('status'), 'failed': [c['check'] for c in run.report['checks'] if not c['passed']], 'failure': run.report.get('failure')}, ensure_ascii=False))


if __name__ == '__main__':
    sys.exit(main())

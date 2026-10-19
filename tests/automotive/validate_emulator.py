"""Finite, synthetic-only AAOS validation. Never runs a phone or overrides Car UX.

Run only inside the manually approved disposable GitHub-hosted AAOS job.
--finalize is offline and creates explicit BLOCKED results after setup/boot failure.
"""
import json
import os
from pathlib import Path
import re
import subprocess
import sys
import time
import urllib.request
import xml.etree.ElementTree as ET

ROOT = Path(__file__).resolve().parents[2]
PACKAGE = 'more.attune.automotive.prototype.debug'
COMPONENT = PACKAGE + '/more.attune.automotive.MainActivity'
PROBE = 'more.attune.validation/more.attune.validation.RestrictionProbe'
CHECKS = [
    'aaos-runtime', 'apk-install', 'activity-start', 'platform-parked',
    'webview-backend', 'navigation', 'backend-moving-lock', 'platform-moving-lock',
    'background-lifecycle', 'backend-offline', 'web-load-error-recovery',
    'permissions-initial', 'permissions-denial', 'unsupported-hardware', 'crashes-console',
]
ROUTES = ['/', '/skin', '/dental', '/vision', '/hearing', '/mental', '/care', '/profile', '/privacy']


class Blocked(Exception):
    pass


class Unverified(Exception):
    pass


def parse_probe(text):
    return dict(re.findall(r'^INSTRUMENTATION_RESULT: ([\w]+)=(.*)$', text, re.M))


def write_reports(out, results):
    out.mkdir(parents=True, exist_ok=True)
    (out / 'results.json').write_text(json.dumps(results, ensure_ascii=False, indent=2))
    suite = ET.Element('testsuite', name='real-aaos-emulator', tests=str(len(results)),
                       failures=str(sum(r['status'] == 'FAIL' for r in results)),
                       skipped=str(sum(r['status'] in ('BLOCKED', 'UNVERIFIED') for r in results)))
    lines = ['# AAOS emulator results', '', '| Check | Status | Evidence / limitation |', '|---|---|---|']
    for result in results:
        case = ET.SubElement(suite, 'testcase', name=result['check'])
        if result['status'] == 'FAIL':
            ET.SubElement(case, 'failure', message=result['detail'])
        elif result['status'] in ('BLOCKED', 'UNVERIFIED'):
            ET.SubElement(case, 'skipped', message=result['status'] + ': ' + result['detail'])
        lines.append('| ' + ' | '.join(str(result[k]).replace('|', '/').replace('\n', ' ') for k in ('check', 'status', 'detail')) + ' |')
    lines += ['', 'PASS applies only to the named emulator observation. Physical media, real vehicles, OEM integration, clinical accuracy, and release acceptance remain UNVERIFIED.']
    ET.ElementTree(suite).write(out / 'results.xml', encoding='utf-8', xml_declaration=True)
    report = '\n'.join(lines) + '\n'
    (out / 'report.md').write_text(report)
    return report


def finalize(out):
    path = out / 'results.json'
    if path.exists():
        results = json.loads(path.read_text())
        existing = {r['check'] for r in results}
        results += [{'check': c, 'status': 'BLOCKED', 'detail': 'Harness terminated before this check.'}
                    for c in CHECKS if c not in existing]
    else:
        detail = f"Harness not reached; build={os.getenv('AAOS_BUILD_OUTCOME', 'unknown')}, emulator={os.getenv('AAOS_EMULATOR_OUTCOME', 'unknown')}. See job logs."
        results = [{'check': c, 'status': 'BLOCKED', 'detail': detail} for c in CHECKS]
    report = write_reports(out, results)
    (out / 'execution.json').write_text(json.dumps({
        'build': os.getenv('AAOS_BUILD_OUTCOME', 'unknown'),
        'emulator': os.getenv('AAOS_EMULATOR_OUTCOME', 'unknown'),
        'source': os.getenv('GITHUB_SHA', 'unknown'),
        'run_id': os.getenv('GITHUB_RUN_ID', 'offline-finalizer'),
        'hardware': 'AAOS virtual vehicle only; no physical device acceptance',
    }, indent=2))
    summary = os.getenv('GITHUB_STEP_SUMMARY')
    if summary:
        with open(summary, 'a') as stream:
            stream.write(report)


class Assessment:
    def __init__(self, out):
        self.out, self.results = out, []
        self.processes = []
        self.phase = 'setup'
        self.console = []
        self.pw = None
        self.features = {}
        self.user = None
        self.out.mkdir(parents=True, exist_ok=True)

    def command(self, args, timeout=40, check=True):
        result = subprocess.run(args, capture_output=True, timeout=timeout)
        text = result.stdout.decode('utf-8', 'replace') + result.stderr.decode('utf-8', 'replace')
        if check and result.returncode:
            raise RuntimeError(f'{args[:4]} exit {result.returncode}: {text[-2000:]}')
        return text

    def adb(self, *args, **kwargs):
        return self.command(['adb', '-s', 'emulator-5554', *args], **kwargs)

    def save(self, name, text):
        # Log evidence is explicitly bounded; never copy API data dirs or profiles.
        data = text.encode('utf-8', 'replace')
        if len(data) > 4 * 1024 * 1024:
            data = b'[Earlier log content truncated to 4 MiB]\n' + data[-4 * 1024 * 1024:]
        (self.out / name).write_bytes(data)

    def wait(self, predicate, seconds=30):
        deadline = time.monotonic() + seconds
        last = None
        while time.monotonic() < deadline:
            try:
                value = predicate()
                if value:
                    return value
            except Exception as error:
                last = error
            time.sleep(1)
        raise AssertionError(f'Timed out after {seconds}s: {last or "expected observation absent"}')

    def check(self, name, action, requires=()):
        self.phase = name
        statuses = {r['check']: r['status'] for r in self.results}
        missing = [c for c in requires if statuses.get(c) != 'PASS']
        try:
            if missing:
                raise Blocked('Required checks did not pass: ' + ', '.join(missing))
            detail = action() or 'Observed in real AAOS emulator.'
            status = 'PASS'
        except Blocked as error:
            status, detail = 'BLOCKED', str(error)
        except Unverified as error:
            status, detail = 'UNVERIFIED', str(error)
        except Exception as error:
            status, detail = 'FAIL', type(error).__name__ + ': ' + str(error)
        self.results.append({'check': name, 'status': status, 'detail': detail})
        try:
            self.capture(name)
        except Exception as error:
            self.save(name + '-evidence-error.txt', str(error))
        write_reports(self.out, self.results)
        print(f'{status}: {name}: {detail}', flush=True)

    def ui(self):
        self.adb('shell', 'uiautomator', 'dump', '/data/local/tmp/attune-qa.xml', timeout=20)
        return self.adb('shell', 'cat', '/data/local/tmp/attune-qa.xml')

    def capture(self, name):
        result = subprocess.run(['adb', '-s', 'emulator-5554', 'exec-out', 'screencap', '-p'], capture_output=True, timeout=20)
        if result.returncode == 0 and result.stdout.startswith(b'\x89PNG'):
            (self.out / (name + '.png')).write_bytes(result.stdout)
        self.save(name + '.xml', self.ui())
        self.save(name + '-activities.txt', self.adb('shell', 'dumpsys', 'activity', 'activities'))

    def tap(self, label=None, resource_suffix=None):
        root = ET.fromstring(self.ui())
        for node in root.iter('node'):
            matches = node.get('text') == label if label else node.get('resource-id', '').endswith(resource_suffix)
            if matches and node.get('enabled') == 'true':
                numbers = list(map(int, re.findall(r'\d+', node.get('bounds', ''))))
                if len(numbers) == 4:
                    self.adb('shell', 'input', 'tap', str((numbers[0] + numbers[2]) // 2), str((numbers[1] + numbers[3]) // 2))
                    return True
        return False

    def probe(self):
        raw = self.adb('shell', 'am', 'instrument', '-w', '--user', self.user, PROBE, timeout=25)
        self.save(self.phase + '-car-api.txt', raw)
        values = parse_probe(raw)
        if values.get('error') or values.get('doRequired') not in ('true', 'false'):
            raise Blocked('Read-only Car UX probe unavailable: ' + str(values or raw[-500:]))
        return values

    def vhal(self, parked):
        # Documented emulator VHAL input only; NEVER set UX policy/allowlists.
        for prop, value in [('0x11600207', '0' if parked else '10'),
                            ('0x11400400', '4' if parked else '8'),
                            ('0x11200402', 'true' if parked else 'false')]:
            reply = self.adb('shell', 'cmd', 'car_service', 'inject-vhal-event', prop, value)
            self.save(self.phase + '-vhal-' + prop + '.txt', reply)
            if re.search(r'unknown command|exception|error|not found|permission denial', reply, re.I):
                raise Blocked('Image did not accept documented VHAL command: ' + reply[-500:])

    def api(self, speed=None):
        url = 'http://127.0.0.1:8000/api/vehicle/' + ('state' if speed is None else 'speed')
        data = None if speed is None else json.dumps({'speedKmH': speed}).encode()
        request = urllib.request.Request(url, data=data, headers={'Content-Type': 'application/json'})
        with urllib.request.urlopen(request, timeout=5) as response:
            return json.load(response)

    def launch(self):
        raw = self.adb('shell', 'am', 'start', '-W', '--user', self.user, '--activity-single-top', '-n', COMPONENT)
        self.save(self.phase + '-launch.txt', raw)
        assert 'Error:' not in raw, raw
        return raw

    def connect(self):
        # Modern debuggable WebView enables CDP; no product code is changed to do so.
        pid = self.adb('shell', 'pidof', PACKAGE).strip().split()[0]
        sockets = self.adb('shell', 'cat', '/proc/net/unix')
        names = re.findall(r'@(webview_devtools_remote[\w_]*)', sockets)
        name = next((n for n in names if n.endswith('_' + pid)), None)
        if name is None:
            raise Blocked('Debug WebView CDP socket absent; DOM checks cannot be inferred from native UI.')
        self.adb('forward', 'tcp:9222', 'localabstract:' + name)
        try:
            browser = self.pw.chromium.connect_over_cdp('http://127.0.0.1:9222', timeout=10000)
        except Exception as error:
            raise Blocked('Real WebView CDP attachment unavailable: ' + str(error)[-700:]) from error
        page = next((p for c in browser.contexts for p in c.pages if p.url.startswith('http://localhost:3000')), None)
        if page is None:
            raise Blocked('No trusted-origin WebView page available over CDP.')
        page.on('pageerror', lambda error: self.console.append({'phase': self.phase, 'kind': 'pageerror', 'text': str(error)}))
        page.on('console', lambda message: self.console.append({'phase': self.phase, 'kind': message.type, 'text': message.text}) if message.type == 'error' else None)
        # No remote model/provider traffic. Only these loopback app/API resources.
        def network(route):
            if route.request.url.startswith(('http://localhost:3000/', 'http://localhost:8000/', 'http://127.0.0.1:8000/')):
                route.continue_()
            else:
                self.console.append({'phase': self.phase, 'kind': 'external-request-blocked', 'text': route.request.url.split('?')[0]})
                route.abort()
        page.route('**/*', network)
        return page

    def parked_page(self):
        self.vhal(True)
        self.api(0)
        self.wait(lambda: self.probe()['doRequired'] == 'false')
        self.launch()
        self.wait(lambda: 'PARK doğrulandı' in self.ui())
        page = self.connect()
        page.wait_for_load_state('domcontentloaded')
        return page

    def runtime(self):
        assert self.adb('shell', 'getprop', 'ro.build.version.sdk').strip() == '35'
        assert self.adb('shell', 'getprop', 'ro.kernel.qemu').strip() == '1'
        self.user = self.adb('shell', 'am', 'get-current-user').strip()
        assert self.user.isdigit(), 'Cannot determine current AAOS driver user'
        features = self.adb('shell', 'pm', 'list', 'features')
        assert 'android.hardware.type.automotive' in features
        assert 'android.software.webview' in features
        self.save('system-features.txt', features)
        self.save('display-and-user.txt', 'Current emulator user: ' + self.user + '\n' +
                  self.adb('shell', 'wm', 'size') + self.adb('shell', 'wm', 'density'))
        self.save('system-image.txt', self.adb('shell', 'getprop', 'ro.build.fingerprint'))
        image_metadata = Path(os.environ['ANDROID_HOME']) / 'system-images/android-35-ext15/android-automotive/x86_64/source.properties'
        self.save('system-image-package.txt', image_metadata.read_text())
        self.save('webview-provider.txt', self.adb('shell', 'dumpsys', 'webviewupdate'))
        self.save('emulator-version.txt', self.command(['emulator', '-version'], check=False))
        return 'API 35 real automotive emulator with WebView feature; fingerprint/provider recorded.'

    def install(self):
        probes = sorted((ROOT / 'tests/automotive/emulator-probe/build/outputs/apk/debug').glob('*.apk'))
        assert len(probes) == 1, f'Expected one test probe APK, found {probes}'
        for apk in [ROOT / 'apps/automotive/app/build/outputs/apk/debug/app-debug.apk', *probes]:
            assert apk.is_file(), str(apk)
            assert 'Success' in self.adb('install', '-r', '--user', self.user, str(apk), timeout=60)
        self.features = self.probe()
        assert self.features['automotive'] == 'true'
        self.save('debug-package.txt', self.adb('shell', 'dumpsys', 'package', PACKAGE))
        return 'Debug app and separate self-targeted read-only Car API probe installed.'

    def start_services(self):
        for port in (3000, 8000):
            # Refuse unrelated listeners rather than reusing or killing a service.
            import socket
            with socket.socket() as test:
                test.bind(('127.0.0.1', port))
        for name, args in [('backend', [sys.executable, '-m', 'uvicorn', 'main:app', '--app-dir', 'services/core-api', '--host', '127.0.0.1', '--port', '8000']),
                           ('frontend', ['npm', 'start', '--', '--hostname', '127.0.0.1'])]:
            stream = open(self.out / (name + '.log'), 'wb')
            process = subprocess.Popen(args, cwd=ROOT, stdout=stream, stderr=subprocess.STDOUT, start_new_session=True)
            stream.close()
            self.processes.append(process)
        self.wait(lambda: self.api().get('vehicleParked') is True, 60)
        def web_ready():
            with urllib.request.urlopen('http://127.0.0.1:3000/', timeout=3) as response:
                return response.status == 200
        self.wait(web_ready, 60)
        for port in (3000, 8000):
            self.adb('reverse', f'tcp:{port}', f'tcp:{port}')

    def start_activity(self):
        self.start_services()
        self.vhal(True)
        self.launch()
        self.wait(lambda: any(PACKAGE in line for line in self.adb('shell', 'dumpsys', 'activity', 'activities').splitlines() if 'topResumedActivity' in line))
        assert self.adb('shell', 'pidof', PACKAGE).strip()
        return 'am start -W succeeded; process and Activity observed. App-private callbacks checked separately.'

    def parked(self):
        self.wait(lambda: self.probe()['doRequired'] == 'false')
        self.wait(lambda: 'PARK doğrulandı' in self.ui())
        return 'Real Car UX unrestricted AND fresh backend simulation Park; no UX override.'

    def web_backend(self):
        page = self.connect()
        page.wait_for_selector('[data-vehicle-status]', timeout=20000)
        self.wait(lambda: page.locator('[data-vehicle-status]').inner_text() == 'PARK')
        assert page.evaluate("fetch('http://localhost:8000/api/vehicle/state').then(r=>r.ok)")
        assert 'Attune.more' in page.title()
        return 'Actual Android WebView rendered Attune.more and fetched existing API via adb reverse.'

    def navigation(self):
        page = self.connect()
        visited = []
        for route in ROUTES:
            if route == '/':
                self.wait(lambda: self.tap('Attune.more'))
            else:
                link = page.locator(f'nav a[href="{route}"]')
                if not link.count():
                    link = page.locator(f'a[href="{route}"]').first
                link.click(timeout=10000)
            page.wait_for_url('http://localhost:3000' + route, timeout=10000)
            gate = page.get_by_role('dialog').filter(has=page.get_by_role('button', name='İzin ver ve devam et', exact=True))
            if gate.count():
                # Fresh disposable CI profile only; no saved human consent/data.
                for box in gate.get_by_role('checkbox').all():
                    box.check()
                gate.get_by_role('button', name='İzin ver ve devam et', exact=True).click()
            page.locator('h1').first.wait_for(state='visible')
            geometry = page.evaluate('({width:innerWidth,scroll:document.documentElement.scrollWidth,headings:[...document.querySelectorAll("h1")].map(x=>x.textContent)})')
            assert geometry['scroll'] <= geometry['width'] + 1, geometry
            visited.append({'path': route, **geometry})
            self.capture('route-' + (route.strip('/') or 'dashboard'))
        self.save('navigation.json', json.dumps(visited, ensure_ascii=False, indent=2))
        self.wait(lambda: self.tap('Geri'))
        self.wait(lambda: page.url == 'http://localhost:3000/profile')
        self.wait(lambda: self.tap('Attune.more'))
        self.wait(lambda: page.url == 'http://localhost:3000/')
        return 'Nine real WebView routes, visible headings, overflow check, native Back/Home; screenshots recorded. One AAOS viewport only.'

    def backend_moving(self):
        self.api(75)
        try:
            self.wait(lambda: 'Araç hareket ediyor' in self.ui() and 'android.webkit.WebView' not in self.ui())
            assert self.probe()['doRequired'] == 'false'
            return 'Backend-only simulated 75 km/h removed WebView while real Car UX remained unrestricted.'
        finally:
            self.api(0)

    def platform_moving(self):
        self.parked_page()
        self.vhal(False)
        try:
            self.wait(lambda: self.probe()['doRequired'] == 'true')
            assert self.api()['vehicleParked'] is True
            self.wait(lambda: 'android.webkit.WebView' not in self.ui())
            return 'Emulator VHAL speed=10 m/s, Drive, parking brake off; actual Car UX restricted with backend still Park; no visible health WebView.'
        finally:
            self.vhal(True)
            self.launch()

    def background(self):
        self.parked_page()
        previous = set(self.adb('logcat', '-b', 'events', '-d', '-v', 'threadtime').splitlines())
        self.adb('shell', 'input', 'keyevent', 'KEYCODE_HOME')
        self.wait(lambda: not any(PACKAGE in line for line in self.adb('shell', 'dumpsys', 'activity', 'activities').splitlines() if 'topResumedActivity' in line))
        def fresh_events():
            events = self.adb('logcat', '-b', 'events', '-d', '-v', 'threadtime')
            self.save('lifecycle-events.txt', events)
            return any(line not in previous and 'more.attune.automotive.MainActivity' in line
                       and re.search(r'(on_paused_called|on_stop_called)', line) for line in events.splitlines())
        try:
            self.wait(fresh_events, 15)
        except AssertionError:
            raise Blocked('App backgrounded, but image did not expose pause/stop lifecycle event receipts.')
        def no_web_target():
            try:
                with urllib.request.urlopen('http://127.0.0.1:9222/json/list', timeout=2) as response:
                    targets = json.load(response)
                return not any(t.get('url', '').startswith('http://localhost:3000') for t in targets)
            except (OSError, ValueError):
                # Destroyed WebView can close its debug endpoint entirely.
                return True
        self.wait(no_web_target, 15)
        self.launch()
        self.wait(lambda: 'PARK doğrulandı' in self.ui())
        return 'Home backgrounded app; fresh native pause/stop receipt and absence of trusted WebView debug target observed; foreground Park restored. No active capture session was started.'

    def backend_offline(self):
        self.parked_page()
        self.adb('reverse', '--remove', 'tcp:8000')
        try:
            self.wait(lambda: ('Araç verisi alınamadı' in self.ui() or 'Araç verisi güncel değil' in self.ui()) and 'android.webkit.WebView' not in self.ui())
            self.capture('backend-offline-locked')
        finally:
            self.adb('reverse', 'tcp:8000', 'tcp:8000')
        self.wait(lambda: 'PARK doğrulandı' in self.ui())
        page = self.connect()
        page.wait_for_selector('[data-vehicle-status]', timeout=15000)
        return 'Removed only emulator backend reverse tunnel: fail-closed gate, WebView absent, fresh Park recovered after tunnel restore.'

    def web_error(self):
        self.parked_page()
        self.adb('reverse', '--remove', 'tcp:3000')
        try:
            assert self.tap('Yeniden dene')
            self.wait(lambda: 'Sayfa yüklenemedi' in self.ui())
            assert self.api()['vehicleParked'] is True
            self.capture('web-load-failed')
        finally:
            self.adb('reverse', 'tcp:3000', 'tcp:3000')
        assert self.tap('Yeniden dene')
        self.wait(lambda: 'android.webkit.WebView' in self.ui())
        self.connect().wait_for_selector('[data-vehicle-status]', timeout=15000)
        return 'Real WebView main-frame connection failure showed native retry state; retry restored existing web app.'

    def permissions_denied(self):
        observation = self.probe()
        for permission in ['cameraPermission', 'microphonePermission']:
            result = observation.get(permission)
            if result not in ('granted', 'denied'):
                raise Blocked('Public PackageManager API did not report runtime permission: ' + str(result))
            assert result == 'denied', f'Unexpected {permission} grant; no media request will be made.'
        return 'Camera and microphone Android runtime permissions both denied; no grants or privileged vehicle permissions.'

    def permission_request(self):
        self.permissions_denied()
        page = self.parked_page()
        page.evaluate("""() => {
          window.__attuneQaPermission = 'pending';
          const button = document.createElement('button');
          button.id = 'attune-qa-denial'; button.textContent = 'QA deny media';
          button.onclick = () => navigator.mediaDevices.getUserMedia({audio:true,video:true})
            .then(s => { s.getTracks().forEach(t=>t.stop()); window.__attuneQaPermission='UNEXPECTED_GRANT'; })
            .catch(e => window.__attuneQaPermission=e.name);
          document.body.prepend(button);
        }""")
        page.locator('#attune-qa-denial').click()
        saw_dialog = False
        for _ in range(10):
            if self.tap(resource_suffix='permission_deny_button'):
                saw_dialog = True
                break
            if page.is_closed():
                break
            state = page.evaluate('window.__attuneQaPermission')
            assert state != 'UNEXPECTED_GRANT', 'Media was unexpectedly granted'
            if state != 'pending':
                break
            time.sleep(1)
        self.permissions_denied()
        if not saw_dialog:
            raise Blocked('Permissions remain denied; actual OS denial dialog not observed (missing emulator hardware or cancelled request). See screenshot/logs; no synthetic grant.')
        return 'Trusted-origin WebView requested media; actual Android denial button used; permissions remained denied. No physical media involved.'

    def unsupported(self):
        self.parked_page()
        self.features = self.probe()
        absent = [key for key in ('camera', 'microphone') if self.features.get(key) == 'false']
        if not absent:
            # AVD camera=none is NOT proof that PackageManager advertises absence.
            raise Unverified('Image advertises camera and microphone. AVD camera=none/audio muted cannot establish hardware-absence behavior.')
        raw = self.ui()
        if 'camera' in absent:
            assert 'Kamera: yok' in raw
        if 'microphone' in absent:
            assert 'Mikrofon: yok' in raw
        return 'PackageManager reports absent ' + ', '.join(absent) + '; native status labels agree. Physical hardware is unverified.'

    def crash_console(self):
        logs = self.adb('logcat', '-b', 'crash', '-d', '-v', 'threadtime')
        self.save('crash-buffer.txt', logs)
        self.save('webview-console.json', json.dumps(self.console[:200], ensure_ascii=False, indent=2))
        assert f'Process: {PACKAGE}' not in logs, 'App crash in Android crash buffer'
        blocked_phases = {c['phase'] for c in self.console if c['kind'] == 'external-request-blocked'}
        unexpected = [c for c in self.console if c['kind'] == 'pageerror' or
                      (c['kind'] == 'error' and c['phase'] not in ('backend-offline', 'web-load-error-recovery') and
                       not (c['phase'] in blocked_phases and c['text'].startswith('Failed to load resource: net::ERR_FAILED')))]
        assert not unexpected, str(unexpected[:8])
        return 'No app crash receipt or unexpected observed WebView JS/console error; intentional network fault phases logged separately.'

    def run(self):
        from playwright.sync_api import sync_playwright
        with sync_playwright() as self.pw:
            try:
                self.check('aaos-runtime', self.runtime)
                self.check('apk-install', self.install, ['aaos-runtime'])
                self.check('activity-start', self.start_activity, ['apk-install'])
                self.check('platform-parked', self.parked, ['activity-start'])
                self.check('webview-backend', self.web_backend, ['platform-parked'])
                self.check('navigation', self.navigation, ['webview-backend'])
                self.check('backend-moving-lock', self.backend_moving, ['webview-backend'])
                self.check('platform-moving-lock', self.platform_moving, ['webview-backend'])
                self.check('background-lifecycle', self.background, ['webview-backend'])
                self.check('backend-offline', self.backend_offline, ['webview-backend'])
                self.check('web-load-error-recovery', self.web_error, ['webview-backend'])
                self.check('permissions-initial', self.permissions_denied, ['apk-install'])
                self.check('permissions-denial', self.permission_request, ['webview-backend', 'permissions-initial'])
                self.check('unsupported-hardware', self.unsupported, ['platform-parked'])
                self.check('crashes-console', self.crash_console, ['webview-backend'])
            finally:
                self.phase = 'cleanup'
                for name, args in [('logcat.txt', ('logcat', '-d', '-t', '8000', '-v', 'threadtime')),
                                   ('car-service.txt', ('shell', 'dumpsys', 'car_service'))]:
                    try:
                        self.save(name, self.adb(*args))
                    except Exception as error:
                        self.save(name + '-error.txt', str(error))
                # Only this harness's process groups; never unrelated listeners.
                import signal
                for process in self.processes:
                    if process.poll() is None:
                        os.killpg(process.pid, signal.SIGTERM)
                write_reports(self.out, self.results)
        return 0 if all(r['status'] == 'PASS' for r in self.results) else 1


if __name__ == '__main__':
    output = Path(os.environ.get('ATTUNE_AAOS_EVIDENCE', '/tmp/attune-aaos-emulator-evidence'))
    if '--finalize' in sys.argv:
        finalize(output)
    else:
        raise SystemExit(Assessment(output).run())

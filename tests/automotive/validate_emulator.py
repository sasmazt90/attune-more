"""Finite, synthetic-only AAOS validation. Never runs a phone or overrides Car UX.

Run only inside the manually approved disposable GitHub-hosted AAOS job.
--finalize is offline and creates explicit BLOCKED results after setup/boot failure.
"""
import json
import hashlib
import os
from pathlib import Path
import re
import selectors
import shutil
import subprocess
import sys
import tempfile
import time
import traceback
import urllib.error
import urllib.request
import xml.etree.ElementTree as ET

ROOT = Path(__file__).resolve().parents[2]
PACKAGE = 'more.attune.automotive.prototype.debug'
COMPONENT = PACKAGE + '/more.attune.automotive.MainActivity'
PROBE = 'more.attune.validation/more.attune.validation.RestrictionProbe'
CHECKS = [
    'aaos-runtime', 'platform-compatibility', 'apk-install', 'activity-start', 'platform-parked',
    'webview-backend', 'navigation', 'backend-moving-lock', 'platform-moving-lock',
    'background-lifecycle', 'backend-offline', 'web-load-error-recovery',
    'permissions-initial', 'permissions-denial', 'unsupported-hardware', 'crashes-console',
    'evidence-capture', 'localized-webview-audio',
]
ROUTES = ['/', '/skin', '/dental', '/vision', '/hearing', '/mental', '/care', '/profile', '/privacy']


class Blocked(Exception):
    pass


class Unverified(Exception):
    pass


def sdk_tool(name):
    root = Path(os.environ.get('ANDROID_HOME', ''))
    if not os.environ.get('ANDROID_HOME') or not root.is_dir():
        raise Blocked('ANDROID_HOME must identify the installed Android SDK')
    if os.environ.get('ANDROID_SDK_ROOT', str(root)) != str(root):
        raise Blocked('ANDROID_HOME and ANDROID_SDK_ROOT disagree')
    relative = {'adb': 'platform-tools/adb', 'emulator': 'emulator/emulator'}[name]
    path = root / relative
    if not path.is_file() or not os.access(path, os.X_OK):
        raise Blocked(f'Required SDK executable absent: {path}')
    return str(path)


def playwright_package():
    import playwright
    return str(Path(playwright.__file__).parent / 'driver/package')


class WebViewClient:
    """Bounded JSON RPC to Playwright's documented Node Android/WebView API."""
    def __init__(self, out, events):
        self.events, self.phase, self.sequence = events, 'connect', 0
        self.log = open(out / 'webview-driver.log', 'ab')
        self.process = subprocess.Popen(
            ['node', str(Path(__file__).with_name('webview_driver.cjs'))],
            env={**os.environ, 'ATTUNE_PLAYWRIGHT_NODE_PACKAGE': playwright_package()},
            stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=self.log,
            text=True, bufsize=1, start_new_session=True)

    def request(self, action, timeout=35, **args):
        self.sequence += 1
        payload = {'id': self.sequence, 'action': action, 'args': args, 'phase': self.phase}
        self.process.stdin.write(json.dumps(payload) + '\n')
        self.process.stdin.flush()
        with selectors.DefaultSelector() as ready:
            ready.register(self.process.stdout, selectors.EVENT_READ)
            if not ready.select(timeout):
                raise Blocked(f'Android WebView operation timed out: {action}')
        line = self.process.stdout.readline()
        if not line:
            raise Blocked('Android WebView observer exited; see webview-driver.log')
        response = json.loads(line)
        assert response['id'] == self.sequence, 'WebView RPC response mismatch'
        self.events.extend(response.get('events', []))
        if response.get('error'):
            raise RuntimeError(response['error'])
        return response.get('result')

    def close(self):
        try:
            if self.process.poll() is None:
                try:
                    self.request('quit', timeout=4)
                    self.process.wait(timeout=4)
                except Exception:
                    self.process.terminate()
                    self.process.wait(timeout=4)
        finally:
            self.process.stdin.close()
            self.process.stdout.close()
            self.log.close()


def host_preflight(out):
    """Real host tools/APKs/imports; never boots or claims an Android device."""
    out.mkdir(parents=True, exist_ok=True)
    checks = {}
    for name, flag in [('adb', 'version'), ('emulator', '-version')]:
        path = sdk_tool(name)
        result = subprocess.run([path, flag], capture_output=True, text=True, timeout=20, check=True)
        checks[name] = {'path': path, 'version': (result.stdout + result.stderr)[:2000]}
    for name in ('node', 'java', 'javac'):
        assert shutil.which(name), f'{name} is not available'
    env = {**os.environ, 'ATTUNE_PLAYWRIGHT_NODE_PACKAGE': playwright_package()}
    subprocess.run(['node', str(Path(__file__).with_name('webview_driver.cjs')), '--self-check'], env=env, check=True, timeout=20)
    assert os.environ.get('ATTUNE_LOAD_LOCAL_ENV') == '0', 'Local credential loading must be disabled'
    assert os.environ.get('ATTUNE_DATA_DIR'), 'An isolated test data directory is required'
    for name in ('OPENAI_API_KEY', 'ATTUNE_ROBOFLOW_API_KEY', 'ROBOFLOW_API_KEY'):
        assert not os.environ.get(name), f'{name} must be empty for this validation'
    # Verify actual packaged identities, not just filenames or source manifests.
    aapt = Path(os.environ['ANDROID_HOME']) / 'build-tools/35.0.0/aapt'
    apks = [(ROOT / 'apps/automotive/app/build/outputs/apk/debug/app-debug.apk', PACKAGE)]
    probes = sorted((ROOT / 'tests/automotive/emulator-probe/build/outputs/apk/debug').glob('*.apk'))
    assert len(probes) == 1, 'Expected exactly one observer APK'
    apks.append((probes[0], 'more.attune.validation'))
    checks['apks'] = []
    for path, expected in apks:
        metadata = subprocess.check_output([str(aapt), 'dump', 'badging', str(path)], text=True)
        assert f"package: name='{expected}'" in metadata, metadata[:1000]
        assert not re.search(r"uses-library(?:-not-required)?:\'android\.car\'", metadata), \
            'Car boot-classpath APIs must not require a PackageManager shared library'
        checks['apks'].append({'path': str(path.relative_to(ROOT)), 'package': expected})
    subprocess.run([sys.executable, '-c',
                    "import sys;sys.path.insert(0,'services/core-api');import main;assert main.vehicle_state['vehicleParked'] is True;print('PASS: real backend imports, initial simulation Park')"],
                   cwd=ROOT, env=env, check=True, timeout=30)
    (out / 'host-preflight.json').write_text(json.dumps(checks, indent=2))
    print('PASS: actual SDK executables, APK identities, Node Android API and backend imports; no emulator execution')


def parse_probe(text):
    return {key: value.strip() for key, value in re.findall(r'^INSTRUMENTATION_RESULT: ([\w]+)=(.*)$', text, re.M)}


PERMISSION_PACKAGES = {'com.android.permissioncontroller', 'com.google.android.permissioncontroller'}
DENIAL_LABELS = {'Don’t allow', "Don't allow", 'İzin verme', 'Nicht zulassen'}


def permission_dialog(raw):
    root = ET.fromstring(raw)
    return any(node.get('package') in PERMISSION_PACKAGES
               and node.get('resource-id', '').split('/')[-1] in ('car_ui_alert_title', 'permission_message')
               and 'Attune.more Prototype' in node.get('text', '') for node in root.iter('node'))


def denial_target(raw):
    """Only a known OS permission dialog for this APK; never an allow action."""
    if not permission_dialog(raw):
        return None
    root = ET.fromstring(raw)
    candidates = []
    for node in root.iter('node'):
        if node.get('package') not in PERMISSION_PACKAGES:
            continue
        resource = node.get('resource-id', '').split('/')[-1]
        if resource == 'permission_deny_button':
            candidates.append(node)
        # AAOS uses a nonclickable title and a clickable sibling interceptor.
        children = list(node)
        if any(c.get('package') in PERMISSION_PACKAGES and
               c.get('resource-id', '').endswith('/car_ui_list_item_title') and
               c.get('text') in DENIAL_LABELS for c in children):
            candidates += [c for c in children if c.get('package') in PERMISSION_PACKAGES
                           and c.get('resource-id', '').endswith('/car_ui_list_item_touch_interceptor')]
    targets = []
    for node in candidates:
        bounds = list(map(int, re.findall(r'\d+', node.get('bounds', ''))))
        if node.get('enabled') == 'true' and node.get('clickable') == 'true' and len(bounds) == 4:
            x1, y1, x2, y2 = bounds
            if x2 > x1 and y2 > y1:
                targets.append({'x': (x1 + x2) // 2, 'y': (y1 + y2) // 2,
                                'resource': node.get('resource-id'), 'package': node.get('package')})
    return targets[0] if len(targets) == 1 else None


def verify_png(path):
    from PIL import Image
    with Image.open(path) as image:
        if image.format != 'PNG' or min(image.size) <= 0:
            raise Blocked('Invalid framebuffer PNG')
        image.verify()


CAR_BOOT_JARS = ('/system/framework/android.car.jar',
                 '/apex/com.android.car.framework/javalib/android.car-module.jar')


def platform_compatibility_errors(observed):
    """Boot-classpath APIs and PM shared-library registration are distinct.

    This harness supports the pinned image's boot-classpath integration. A PM
    library name alone does not make classes visible without uses-library.
    Shell observations do not replace the later public Car API observer.
    """
    errors = []
    features = set(observed.get('features', '').splitlines())
    for feature in ('android.hardware.type.automotive', 'android.software.webview'):
        if 'feature:' + feature not in features:
            errors.append('Required feature absent: ' + feature)
    boot = observed.get('bootclasspath', '').strip().split(':')
    if not any(path in boot for path in CAR_BOOT_JARS):
        errors.append('No supported Car API jar on BOOTCLASSPATH; a shared-library listing alone is insufficient')
    if not re.search(r'^Service car_service: found\s*$', observed.get('car-binder', ''), re.M):
        errors.append('car_service binder unavailable')
    car = observed.get('car-service', '')
    if '*CarUxRestrictionsManagerService*' not in car:
        errors.append('Car UX restrictions manager unavailable')
    if 'mEnableActivityBlocking:true' not in car:
        errors.append('Independent platform Activity blocking not confirmed enabled')
    if observed.get('user-state', '').strip() != 'RUNNING_UNLOCKED':
        errors.append('Current AAOS driver user is not RUNNING_UNLOCKED')
    return errors


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
        detail = result['detail']
        if result.get('evidence_warning'):
            detail += '; EVIDENCE BLOCKED: ' + result['evidence_warning']
        lines.append('| ' + ' | '.join(str(v).replace('|', '/').replace('\n', ' ') for v in (result['check'], result['status'], detail)) + ' |')
    lines += ['', 'PASS applies only to the named emulator observation. Physical media, real vehicles, OEM integration, clinical accuracy, and release acceptance remain UNVERIFIED.']
    ET.ElementTree(suite).write(out / 'results.xml', encoding='utf-8', xml_declaration=True)
    report = '\n'.join(lines) + '\n'
    (out / 'report.md').write_text(report)
    return report


def finalize(out):
    out.mkdir(parents=True, exist_ok=True)
    path = out / 'results.json'
    if path.exists():
        try:
            results = json.loads(path.read_text())
            if not isinstance(results, list) or any(
                    not isinstance(row, dict) or not all(isinstance(row.get(k), str) for k in ('check', 'status', 'detail'))
                    or row['status'] not in ('PASS', 'FAIL', 'BLOCKED', 'UNVERIFIED') for row in results):
                raise ValueError('Invalid result schema')
        except (ValueError, OSError):
            results = [{'check': 'harness-report', 'status': 'FAIL', 'detail': 'Runtime results could not be decoded; remaining checks are BLOCKED.'}]
        existing = {r['check'] for r in results}
        results += [{'check': c, 'status': 'BLOCKED', 'detail': 'Harness terminated before this check.'}
                    for c in CHECKS if c not in existing]
    else:
        stages = ', '.join(name + '=' + os.getenv('AAOS_' + name.upper() + '_OUTCOME', 'unknown')
                           for name in ('assets', 'kvm', 'sdk', 'image', 'build', 'preflight', 'emulator'))
        detail = f'Harness not reached; {stages}. See job logs and runtime-*.json.'
        results = [{'check': c, 'status': 'BLOCKED', 'detail': detail} for c in CHECKS]
    if not (out / 'navigation.json').exists():
        (out / 'navigation.json').write_text(json.dumps([
            {'path': route, 'status': 'BLOCKED', 'detail': 'Navigation was not reached; see results.json dependencies.'}
            for route in ROUTES], indent=2))
    first_failure = next((r for r in results if r['status'] == 'FAIL'), None)
    stages = {name: os.getenv('AAOS_' + name.upper() + '_OUTCOME', 'unknown')
              for name in ('assets', 'kvm', 'sdk', 'image', 'build', 'preflight', 'emulator')}
    first_failed_stage = next((name for name, outcome in stages.items() if outcome == 'failure'), None)
    report = write_reports(out, results)
    diagnostics = []
    for path in sorted([*out.glob('runtime-*.json'), *out.glob('asset-preflight.json')]):
        try:
            diagnostics += [path.name + ': ' + str(error) for error in json.loads(path.read_text()).get('errors', [])]
        except (ValueError, OSError, AttributeError):
            diagnostics.append(path.name + ': diagnostic file could not be decoded')
    if diagnostics:
        report += '\nSetup/source-packaging blockers (emulator scenarios were not executed):\n\n'
        report += '\n'.join('- ' + error.replace('\n', ' ') for error in diagnostics) + '\n'
        (out / 'report.md').write_text(report)
    (out / 'execution.json').write_text(json.dumps({
        'sdk': os.getenv('AAOS_SDK_OUTCOME', 'unknown'),
        'assets': os.getenv('AAOS_ASSETS_OUTCOME', 'unknown'),
        'image': os.getenv('AAOS_IMAGE_OUTCOME', 'unknown'),
        'kvm': os.getenv('AAOS_KVM_OUTCOME', 'unknown'),
        'build': os.getenv('AAOS_BUILD_OUTCOME', 'unknown'),
        'preflight': os.getenv('AAOS_PREFLIGHT_OUTCOME', 'unknown'),
        'emulator': os.getenv('AAOS_EMULATOR_OUTCOME', 'unknown'),
        'first_failed_stage': first_failed_stage,
        'first_failed_check': first_failure,
        'first_blocked_check': next((r for r in results if r['status'] == 'BLOCKED'), None),
        'evidence_warnings': [r['check'] for r in results if r.get('evidence_warning')],
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
        self.services = {}
        self.last_ui = None
        self.last_ui_at = None
        self.evidence = {}
        self.phase = 'setup'
        self.console = []
        self.web_client = None
        self.cdp_port = None
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
        return self.command([sdk_tool('adb'), '-s', 'emulator-5554', *args], **kwargs)

    def save(self, name, text):
        # Log evidence is explicitly bounded; never copy API data dirs or profiles.
        data = text.encode('utf-8', 'replace')
        if len(data) > 4 * 1024 * 1024:
            data = b'[Earlier log content truncated to 4 MiB]\n' + data[-4 * 1024 * 1024:]
        (self.out / name).write_bytes(data)

    def wait(self, predicate, seconds=30, label='expected observation'):
        deadline = time.monotonic() + seconds
        last = None
        while time.monotonic() < deadline:
            try:
                value = predicate()
                if value:
                    return value
                last = None
            except Exception as error:
                last = error
            time.sleep(1)
        if self.last_ui:
            self.save(self.phase + '-timeout.xml', self.last_ui)
        self.save(self.phase + '-timeout.json', json.dumps({'label': label, 'seconds': seconds,
                                                          'last_error': str(last) if last else None,
                                                          'last_ui_observed_at_unix': self.last_ui_at}))
        if isinstance(last, Blocked):
            raise Blocked(f'{label}: {last}') from last
        raise AssertionError(f'Timed out after {seconds}s: {label}: {last or "expected observation absent"}')

    def check(self, name, action, requires=(), capture=True):
        self.phase = name
        self.last_ui, self.last_ui_at = None, None
        if self.web_client is not None:
            self.web_client.phase = name
            try:
                self.web_client.request('phase', timeout=3)
            except Exception as error:
                self.save(name + '-observer-warning.txt', str(error))
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
            self.save(name + '-traceback.txt', traceback.format_exc())
        self.results.append({'check': name, 'status': status, 'detail': detail})
        if not missing and capture:
            try:
                self.capture(name)
            except Exception as error:
                self.results[-1]['evidence_warning'] = str(error)
                self.save(name + '-evidence-error.txt', str(error))
        write_reports(self.out, self.results)
        print(f'{status}: {name}: {detail}', flush=True)

    def ui(self):
        path = '/data/local/tmp/attune-qa.xml'
        self.adb('shell', 'rm', '-f', path)
        result = self.adb('shell', 'uiautomator', 'dump', path, timeout=20)
        if 'UI hierchary dumped to:' not in result and 'UI hierarchy dumped to:' not in result:
            raise Blocked('No fresh UI hierarchy: ' + result[-500:])
        raw = self.adb('shell', 'cat', path)
        if ET.fromstring(raw).tag != 'hierarchy':
            raise Blocked('Invalid fresh UI hierarchy')
        self.last_ui = raw
        self.last_ui_at = time.time()
        return raw

    def capture(self, name):
        errors = []
        components = {}
        def receipt(suffix):
            path = self.out / (name + suffix)
            components[suffix] = {'path': path.name, 'bytes': path.stat().st_size,
                                  'sha256': hashlib.sha256(path.read_bytes()).hexdigest(),
                                  'observed_at_unix': time.time()}
        # AAOS can resume an Activity before its first accessibility root exists.
        # Poll fresh dumps within a finite window, retaining no previous dump.
        def fresh_ui():
            raw = self.ui()
            if name == 'activity-start' and not any(n.get('package') == PACKAGE
                    for n in ET.fromstring(raw).iter('node')):
                raise Blocked('First application UI frame not yet accessible')
            return raw
        try:
            self.save(name + '.xml', self.wait(fresh_ui, 12, label='fresh UI hierarchy for evidence'))
            receipt('.xml')
        except Exception as error:
            errors.append('.xml: ' + str(error))
        # Guest screencap repeatedly SIGABRTed in run #118. Use the documented
        # host emulator framebuffer interface; never substitute rendered HTML.
        try:
            with tempfile.TemporaryDirectory(prefix='frame-', dir=self.out) as directory:
                reply = self.adb('emu', 'screenrecord', 'screenshot', directory, timeout=20)
                images = list(Path(directory).glob('*.png'))
                if len(images) != 1 or not images[0].read_bytes().startswith(b'\x89PNG\r\n\x1a\n'):
                    raise Blocked('No fresh emulator framebuffer PNG: ' + reply[-500:])
                verify_png(images[0])
                images[0].replace(self.out / (name + '.png'))
                receipt('.png')
        except Exception as error:
            errors.append('screenshot: ' + str(error))
        for suffix, obtain in [('-activities.txt', lambda: self.adb('shell', 'dumpsys', 'activity', 'activities'))]:
            try:
                text = obtain()
                if not text.strip():
                    raise Blocked('Empty Activity evidence')
                self.save(name + suffix, text)
                receipt(suffix)
            except Exception as error:
                errors.append(suffix + ': ' + str(error))
        self.evidence[name] = {'components': components, 'errors': errors}
        self.save('evidence-index.json', json.dumps(self.evidence, indent=2))
        if errors:
            raise Blocked('; '.join(errors))

    def tap(self, label=None, resource_suffix=None):
        root = ET.fromstring(self.ui())
        for node in root.iter('node'):
            matches = node.get('text') == label if label else node.get('resource-id', '').endswith(resource_suffix)
            if matches and node.get('enabled') == 'true' and node.get('clickable') == 'true':
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
        if self.web_client is not None:
            self.web_client.close()
        self.web_client = WebViewClient(self.out, self.console)
        self.web_client.phase = self.phase
        try:
            observation = self.web_client.request('connect')
        except Exception as error:
            raise Blocked('Real Android WebView attachment unavailable: ' + str(error)[-700:]) from error
        assert observation['pkg'] == PACKAGE
        # HTTP target discovery is used only to verify destruction on background;
        # DOM automation uses the documented Android API, not desktop CDP defaults.
        pid = self.adb('shell', 'pidof', PACKAGE).strip().split()[0]
        sockets = self.adb('shell', 'cat', '/proc/net/unix')
        names = re.findall(r'@(webview_devtools_remote[\w_]*)', sockets)
        name = next((n for n in names if n.endswith('_' + pid)), None)
        if name is None:
            raise Blocked('Debug WebView CDP socket absent; DOM checks cannot be inferred from native UI.')
        if self.cdp_port is not None:
            self.adb('forward', '--remove', f'tcp:{self.cdp_port}', check=False)
        self.cdp_port = int(self.adb('forward', 'tcp:0', 'localabstract:' + name).strip())
        return self.web_client

    def parked_ready(self):
        raw = self.ui()
        if permission_dialog(raw):
            self.save(self.phase + '-blocking-permission-dialog.xml', raw)
            raise Blocked('An unresolved OS permission dialog obstructs native Park/hardware observation; see permissions-denial')
        self.vhal(True)
        self.api(0)
        self.wait(lambda: self.probe()['doRequired'] == 'false')
        self.launch()
        self.wait(lambda: 'PARK doğrulandı' in self.ui(), label='native Park gate before scenario')
        self.wait(lambda: 'android.webkit.WebView' in self.ui(), label='native WebView before scenario')

    def parked_page(self):
        self.parked_ready()
        client = self.connect()
        client.request('ready')
        return client

    def locked(self, reasons):
        raw = self.ui()
        return any(reason in raw for reason in reasons) and 'android.webkit.WebView' not in raw

    def runtime(self):
        self.adb('wait-for-device', timeout=60)
        self.wait(lambda: self.adb('get-state').strip() == 'device' and self.adb('shell', 'getprop', 'sys.boot_completed').strip() == '1', 60)
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
        self.save('emulator-version.txt', self.command([sdk_tool('emulator'), '-version']))
        return 'API 35 real automotive emulator with WebView feature; fingerprint/provider recorded.'

    def compatibility(self):
        observed, errors = {}, []
        # Record every query even when another query fails. No root, remount,
        # framework injection, permission grant or UX-policy override is used.
        queries = {
            'properties': ('getprop',),
            'libraries': ('pm', 'list', 'libraries'),
            'features': ('pm', 'list', 'features'),
            'packages': ('pm', 'list', 'packages', '-f', '--user', self.user),
            'car-package': ('dumpsys', 'package', 'com.android.car'),
            'car-binder': ('service', 'check', 'car_service'),
            'car-service': ('dumpsys', 'car_service'),
            'bootclasspath': ('printenv', 'BOOTCLASSPATH'),
            'user-state': ('am', 'get-started-user-state', self.user),
        }
        # sys.boot_completed is insufficient: AAOS may still be starting user 10.
        try:
            self.wait(lambda: self.adb('shell', *queries['user-state']).strip() == 'RUNNING_UNLOCKED', 60)
        except Exception as error:
            errors.append('Driver user readiness: ' + str(error))
        for name, args in queries.items():
            try:
                observed[name] = self.adb('shell', *args)
            except Exception as error:
                observed[name] = ''
                errors.append(name + ': ' + str(error))
            self.save('platform-' + name + '.txt', observed[name])
        errors += platform_compatibility_errors(observed)
        boot = observed.get('bootclasspath', '').strip().split(':')
        car_jar = next((path for path in CAR_BOOT_JARS if path in boot), None)
        if car_jar:
            try:
                self.adb('shell', 'test', '-s', car_jar)
            except Exception as error:
                errors.append('Boot-classpath Car jar unreadable/absent: ' + str(error))
        shared = 'library:android.car' in observed.get('libraries', '').splitlines()
        self.save('platform-compatibility.json', json.dumps({
            'status': 'BLOCKED' if errors else 'PASS', 'errors': errors,
            'car_boot_jar': car_jar, 'pm_shared_android_car': shared,
            'integration': 'boot-classpath; no manifest shared-library dependency',
            'public_car_api': 'UNVERIFIED until post-install read-only observer succeeds',
        }, indent=2))
        if errors:
            raise Blocked('Incompatible/incompletely observed AAOS platform before APK installation: ' + '; '.join(errors))
        return ('Boot-classpath Car jar, automotive/WebView features, Car UX service, enabled platform Activity blocking '
                'and unlocked driver user observed. PM android.car shared registration=' + str(shared) +
                '; public API connectivity remains a separate post-install check.')

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
        for name in ('backend', 'frontend'):
            self.start_service(name)
        self.wait(lambda: self.api().get('vehicleParked') is True, 60)
        def web_ready():
            with urllib.request.urlopen('http://127.0.0.1:3000/', timeout=3) as response:
                return response.status == 200
        self.wait(web_ready, 60)
        for port in (3000, 8000):
            self.adb('reverse', f'tcp:{port}', f'tcp:{port}')

    def start_service(self, name):
        previous = self.services.get(name)
        if previous is not None and previous.poll() is None:
            raise Blocked('Owned service already running: ' + name)
        args = {'backend': [sys.executable, '-m', 'uvicorn', 'main:app', '--app-dir', 'services/core-api',
                            '--host', '127.0.0.1', '--port', '8000'],
                'frontend': ['npm', '--workspace=apps/vehicle-app', 'run', 'start']}[name]
        with open(self.out / (name + '.log'), 'ab') as stream:
            process = subprocess.Popen(args, cwd=ROOT, stdout=stream, stderr=subprocess.STDOUT, start_new_session=True)
        self.processes.append(process)
        self.services[name] = process
        return process

    def stop_service(self, name):
        import signal
        process = self.services.get(name)
        if process is None or process not in self.processes:
            raise Blocked('Refusing to stop a service not owned by this harness: ' + name)
        if process.poll() is None:
            os.killpg(process.pid, signal.SIGTERM)
            try:
                process.wait(timeout=10)
            except subprocess.TimeoutExpired:
                os.killpg(process.pid, signal.SIGKILL)
                process.wait(timeout=5)
        return process.returncode

    def backend_unreachable(self):
        try:
            self.api()
            return False
        except urllib.error.HTTPError as error:
            raise Blocked('HTTP error is not proof of a disconnected backend: ' + str(error)) from error
        except urllib.error.URLError as error:
            if isinstance(error.reason, (ConnectionRefusedError, ConnectionResetError)):
                return True
            raise Blocked('Backend fault injection not established: ' + str(error)) from error

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
        self.connect().request('ready')
        return 'Actual Android WebView rendered Attune.more and fetched existing API via adb reverse.'

    def navigation(self):
        client = self.connect()
        visited = []
        for route in ROUTES:
            try:
                if route == '/':
                    self.wait(lambda: self.tap('Attune.more'))
                row = client.request('navigate', route=route)
                self.capture('route-' + (route.strip('/') or 'dashboard'))
            except Exception as error:
                row = {'path': route, 'status': 'BLOCKED' if isinstance(error, Blocked) else 'FAIL', 'detail': str(error)}
            finally:
                # Persist every route, even when an earlier route cannot load.
                visited.append(row)
                self.save('navigation.json', json.dumps(visited, ensure_ascii=False, indent=2))
        assert all(row['status'] == 'PASS' for row in visited), str(visited)
        self.wait(lambda: self.tap('Geri'))
        client.request('wait-url', route='/profile')
        self.wait(lambda: self.tap('Attune.more'))
        client.request('wait-url', route='/')
        return 'Nine real WebView routes, visible headings, overflow check, native Back/Home; screenshots recorded. One AAOS viewport only.'

    def backend_moving(self):
        self.parked_ready()
        self.api(75)
        try:
            self.wait(lambda: self.locked(['Araç hareket ediyor']))
            assert self.probe()['doRequired'] == 'false'
            return 'Backend-only simulated 75 km/h removed WebView while real Car UX remained unrestricted.'
        finally:
            self.api(0)

    def platform_moving(self):
        self.parked_ready()
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
            fresh = [line for line in events.splitlines() if line not in previous
                     and 'more.attune.automotive.MainActivity' in line]
            return all(any(tag in line for line in fresh) for tag in ('on_paused_called', 'on_stop_called'))
        try:
            self.wait(fresh_events, 15)
        except AssertionError:
            raise Blocked('App backgrounded, but image did not expose both fresh pause and stop lifecycle receipts.')
        self.wait(self.no_web_target, 15)
        self.launch()
        self.wait(lambda: 'PARK doğrulandı' in self.ui())
        return 'Home backgrounded app; fresh native pause AND stop receipts and absence of trusted WebView debug target observed; foreground Park restored. No active capture session was started.'

    def no_web_target(self):
        try:
            with urllib.request.urlopen(f'http://127.0.0.1:{self.cdp_port}/json/list', timeout=2) as response:
                targets = json.load(response)
            if not isinstance(targets, list) or any(not isinstance(t, dict) for t in targets):
                raise Blocked('Invalid WebView debug target list')
            return not any(t.get('url', '').startswith('http://localhost:3000') for t in targets)
        except ValueError as error:
            raise Blocked('Invalid WebView debug JSON; destruction is not established') from error
        except urllib.error.HTTPError as error:
            raise Blocked('Debug endpoint returned HTTP error; destruction is not established: ' + str(error)) from error
        except urllib.error.URLError as error:
            if isinstance(error.reason, (ConnectionRefusedError, ConnectionResetError)):
                return True  # Destroyed WebView can close its endpoint.
            raise Blocked('Cannot observe WebView target destruction: ' + str(error)) from error

    def localized_webview_audio(self):
        """Fresh actual runtime acceptance; never infer this from desktop Chrome."""
        client = self.parked_page()
        languages, playbacks, navigation = [], [], []
        native_park = {'tr': 'PARK doğrulandı', 'en': 'PARK verified', 'de': 'PARK bestätigt'}
        try:
            decoded = client.request('localization-decode', timeout=90)
            self.save('localized-audio-decode.json', json.dumps(decoded, ensure_ascii=False, indent=2))
            assert len(decoded) == 194 and all(r['status'] == 'PASS' for r in decoded), 'Real WebView approved audio decode/integrity failed; see all 194 observations'
            for language in ('tr', 'en', 'de'):
                languages.append(client.request('localization-language', language=language))
                self.wait(lambda: native_park[language] in self.ui(), 15,
                          label='actual native toolbar/status locale ' + language)
                for route in ROUTES:
                    result = client.request('navigate', route=route)
                    result['language'] = language
                    navigation.append(result)
                    module = route.strip('/')
                    if module in ('skin', 'dental', 'vision', 'hearing', 'mental'):
                        playback = client.request('localization-recording', timeout=40,
                                                  language=language, module=module)
                        playbacks.append(playback)
                        self.save('localized-audio-playback.json', json.dumps(playbacks, ensure_ascii=False, indent=2))
                        assert playback['status'] == 'PASS', playback
                    self.capture('localized-' + language + '-' + (module or 'dashboard'))
            assert len(decoded) == 194 and len(playbacks) == 15 and len(navigation) == 27
            return 'Real Android WebView:194 approved AAC decodes,15 actual playback cases,27 localized routes and native TR/EN/DE status observed; no microphone/STT/live TTS claim.'
        finally:
            self.save('localized-language.json', json.dumps(languages, ensure_ascii=False, indent=2))
            self.save('localized-navigation.json', json.dumps(navigation, ensure_ascii=False, indent=2))
            # Existing independent safety diagnostics deliberately use their
            # historical Turkish labels; reset only the synthetic preference.
            client.request('localization-language', language='tr')

    def backend_offline(self):
        self.parked_page()
        fault = {'method': 'stop only harness-owned backend; keep adb reverse mapping',
                 'started_at_unix': time.time(), 'locked': False, 'recovered': False}
        try:
            fault['stopped_exit_code'] = self.stop_service('backend')
            self.wait(self.backend_unreachable, 10, label='backend actually disconnected')
            fault['host_unreachable'] = True
            self.wait(lambda: self.locked(['Araç verisi alınamadı', 'Araç verisi güncel değil']),
                      label='native offline/stale gate and absence of WebView')
            fault['locked'] = True
            fault['locked_at_unix'] = time.time()
            self.capture('backend-offline-locked')
        finally:
            # Restart the same isolated, keyless backend and retain both log segments.
            process = self.services.get('backend')
            if process is not None and process.poll() is not None:
                self.start_service('backend')
            self.save('backend-offline-fault.json', json.dumps(fault, indent=2))
        self.wait(lambda: self.api().get('vehicleParked') is True, 60, label='owned backend recovery')
        self.wait(lambda: 'PARK doğrulandı' in self.ui(), label='fresh native Park after backend recovery')
        self.connect().request('ready')
        fault.update(recovered=True, recovered_at_unix=time.time())
        self.save('backend-offline-fault.json', json.dumps(fault, indent=2))
        return 'Stopped owned backend and verified connection refusal; native offline/stale gate removed WebView; same isolated backend restart restored fresh Park.'

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
        self.connect().request('ready')
        return 'Real WebView main-frame connection failure showed native retry state; retry restored existing web app.'

    def permissions_denied(self):
        observation = self.probe()
        assert observation.get('targetVisible') == 'true', 'Target package visibility not established'
        for permission in ['cameraPermission', 'microphonePermission']:
            result = observation.get(permission)
            if result not in ('granted', 'denied'):
                raise Blocked('Public PackageManager API did not report runtime permission: ' + str(result))
            assert result == 'denied', f'Unexpected {permission} grant; no media request will be made.'
        return 'Camera and microphone Android runtime permissions both denied; no grants or privileged vehicle permissions.'

    def permission_request(self):
        self.permissions_denied()
        features = self.probe()
        if not any(features.get(key) == 'true' for key in ('camera', 'microphone')):
            raise Unverified('No advertised media hardware can exercise an Android permission prompt')
        client = self.parked_page()
        saw_dialog = False
        state = 'pending'
        observation = {'state': state, 'denial_clicked': False}
        try:
            client.request('permission-start', features=features)
            deadline = time.monotonic() + 30
            while time.monotonic() < deadline:
                raw = self.wait(self.ui, 12, label='fresh OS permission UI')
                self.save('permissions-denial-observed.xml', raw)
                target = denial_target(raw)
                if target:
                    self.capture('permissions-denial-prompt')
                    self.adb('shell', 'input', 'tap', str(target['x']), str(target['y']))
                    observation.update(denial_clicked=True, target=target)
                    self.wait(lambda: not permission_dialog(self.ui()), 15, label='actual OS denial dialog dismissed')
                    saw_dialog = True
                    break
                # onPause intentionally destroys the WebView when the OS prompt
                # opens. A closed page is not proof that no OS prompt exists.
                state = client.request('permission-state')
                observation['state'] = state
                assert state != 'UNEXPECTED_GRANT', 'Media was unexpectedly granted'
                time.sleep(1)
            self.permissions_denied()
            if not saw_dialog:
                raise Blocked(f'Actual OS denial action not established; WebView state={state}; permissions remain denied. See OS UI evidence; no synthetic grant.')
            return 'Actual OS permission dialog observed; its denial control clicked; dialog dismissed and camera/microphone permissions remained denied. No physical media involved.'
        finally:
            # Never leave a permission modal to contaminate the next scenario.
            # Back is cancellation only; it cannot make denial acceptance PASS.
            raw = self.wait(self.ui, 12, label='fresh UI for permission cleanup')
            if permission_dialog(raw):
                self.save('permissions-denial-cleanup-before.xml', raw)
                self.adb('shell', 'input', 'keyevent', 'KEYCODE_BACK')
                self.wait(lambda: not permission_dialog(self.ui()), 15, label='permission-modal cleanup')
                self.permissions_denied()
                observation['cleanup_cancelled'] = True
            self.save('permissions-denial-observation.json', json.dumps(observation, indent=2))

    def unsupported(self):
        self.parked_ready()
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
        if self.web_client is not None:
            self.web_client.request('events')
        logs = self.adb('logcat', '-b', 'crash', '-d', '-v', 'threadtime')
        self.save('crash-buffer.txt', logs)
        self.save('webview-console.json', json.dumps(self.console[:200], ensure_ascii=False, indent=2))
        assert f'Process: {PACKAGE}' not in logs, 'App crash in Android crash buffer'
        blocked_resources = {(c['phase'], c.get('url')) for c in self.console if c['kind'] == 'external-request-blocked' and c.get('url')}
        unexpected = [c for c in self.console if c['kind'] in ('pageerror', 'console-overflow') or
                      (c['kind'] == 'error' and c['phase'] not in ('backend-offline', 'web-load-error-recovery') and
                       not ((c['phase'], c.get('url')) in blocked_resources and c['text'].startswith('Failed to load resource: net::ERR_FAILED')))]
        assert not unexpected, str(unexpected[:8])
        return 'No app crash receipt or unexpected observed WebView JS/console error; intentional network fault phases logged separately.'

    def evidence_quality(self):
        incomplete = [r['check'] for r in self.results if r.get('evidence_warning')]
        if incomplete:
            raise Blocked('Missing screenshot/UI/activity evidence: ' + ', '.join(incomplete) + '; named behavior results remain separate.')
        required = ['route-' + (route.strip('/') or 'dashboard') for route in ROUTES]
        required += [r['check'] for r in self.results if r['status'] == 'PASS'
                     and r['check'] not in ('aaos-runtime', 'platform-compatibility', 'apk-install', 'evidence-capture')]
        for name in required:
            if not (self.out / (name + '.png')).is_file():
                raise Blocked('Route screenshot unavailable or successful-check screenshot missing: ' + name)
            try:
                verify_png(self.out / (name + '.png'))
                assert ET.parse(self.out / (name + '.xml')).getroot().tag == 'hierarchy'
                assert (self.out / (name + '-activities.txt')).read_text().strip()
                receipt = self.evidence[name]
                assert not receipt['errors']
                for suffix in ('.png', '.xml', '-activities.txt'):
                    path = self.out / (name + suffix)
                    assert hashlib.sha256(path.read_bytes()).hexdigest() == receipt['components'][suffix]['sha256']
            except Exception as error:
                raise Blocked('Incomplete or changed screenshot/UI/activity evidence for ' + name + ': ' + str(error)) from error
        return 'Valid framebuffer PNGs, fresh UI/activity evidence and matching acquisition hashes for nine routes and every passed behavioral check.'

    def run(self):
        try:
            # Startup system screens can have no accessibility root (#120).
            # Product screenshots/UI remain mandatory from activity-start onward.
            self.check('aaos-runtime', self.runtime, capture=False)
            self.check('platform-compatibility', self.compatibility, ['aaos-runtime'], capture=False)
            self.check('apk-install', self.install, ['platform-compatibility'], capture=False)
            self.check('activity-start', self.start_activity, ['apk-install'])
            self.check('platform-parked', self.parked, ['activity-start'])
            self.check('webview-backend', self.web_backend, ['platform-parked'])
            self.check('navigation', self.navigation, ['webview-backend'])
            # Independent native safety/hardware checks do not depend on DOM tooling.
            self.check('backend-moving-lock', self.backend_moving, ['platform-parked'])
            self.check('platform-moving-lock', self.platform_moving, ['platform-parked'])
            self.check('background-lifecycle', self.background, ['webview-backend'])
            self.check('backend-offline', self.backend_offline, ['webview-backend'])
            self.check('web-load-error-recovery', self.web_error, ['webview-backend'])
            self.check('permissions-initial', self.permissions_denied, ['apk-install'])
            self.check('permissions-denial', self.permission_request, ['webview-backend', 'permissions-initial'])
            self.check('unsupported-hardware', self.unsupported, ['platform-parked'])
            self.check('localized-webview-audio', self.localized_webview_audio, ['webview-backend', 'navigation'])
            self.check('crashes-console', self.crash_console, ['webview-backend'])
            self.check('evidence-capture', self.evidence_quality, ['navigation'], capture=False)
        finally:
            self.phase = 'cleanup'
            if self.web_client is not None:
                try:
                    self.web_client.close()
                except Exception as error:
                    self.save('webview-close-error.txt', str(error))
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
            self.save('webview-console.json', json.dumps(self.console, ensure_ascii=False, indent=2))
            write_reports(self.out, self.results)
        return 0 if all(r['status'] == 'PASS' for r in self.results) else 1


if __name__ == '__main__':
    output = Path(os.environ.get('ATTUNE_AAOS_EVIDENCE', '/tmp/attune-aaos-emulator-evidence'))
    if '--finalize' in sys.argv:
        finalize(output)
    elif '--preflight' in sys.argv:
        host_preflight(output)
    else:
        raise SystemExit(Assessment(output).run())

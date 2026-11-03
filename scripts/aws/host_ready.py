#!/usr/bin/env python3
"""Readiness report for one existing Attune host, run as root through SSM.

Standard library only, so it can be sent inline without being deployed first.
Reports booleans, counts and public metadata. Secret values are never printed.
This proves service availability; it is not health-module or clinical acceptance.
"""
import argparse
import datetime as dt
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import socket
import subprocess
import urllib.error
import urllib.request

TARGETS = {
    'web': {'id': 'i-0b25450afc6633494', 'type': 'r7i.2xlarge'},
    'aaos': {'id': 'i-0f4cca4e92e94c351', 'type': 'm8i.2xlarge'},
}
REGION = 'eu-central-1'
UNITS = {
    'web': ['attune-caddy', 'attune-api@web', 'attune-api@aaos', 'attune-web@web', 'attune-web@aaos', 'attune-capture'],
    'aaos': ['attune-caddy', 'attune-aaos', 'attune-audio'],
}
MODULES = ['/', '/skin', '/vision', '/dental', '/hearing', '/mental']
PACKAGE = 'more.attune.automotive.prototype.clouddemo'
ADB_SERIAL = 'emulator-5554'
ENV_ROOT = Path('/etc/attune')
TLS_ROOT = ENV_ROOT / 'tls'
CERT_WARNING_DAYS = 30
REQUIRED_GUEST_MEMORY_MIB = 3072


class Report:
    def __init__(self, role):
        self.role = role
        self.checks = []

    def add(self, check_id, label, passed, detail='', required=True):
        self.checks.append({'id': check_id, 'label': label, 'status': 'PASS' if passed else 'FAIL',
                            'required': required, 'detail': str(detail)[:300]})
        return passed

    def warn(self, check_id, label, detail=''):
        self.checks.append({'id': check_id, 'label': label, 'status': 'WARN', 'required': False, 'detail': str(detail)[:300]})

    def payload(self):
        failed = [c['id'] for c in self.checks if c['status'] == 'FAIL' and c['required']]
        return {'role': self.role, 'at': dt.datetime.now(dt.timezone.utc).isoformat(), 'ready': not failed,
                'failedRequired': failed, 'checks': self.checks}


def run(*args, timeout=20, env=None):
    try:
        done = subprocess.run(args, capture_output=True, text=True, timeout=timeout, env=env)
        return done.returncode, done.stdout.strip(), done.stderr.strip()
    except (OSError, subprocess.TimeoutExpired) as error:
        return 127, '', type(error).__name__


def http_status(url, *curl_args, timeout=10):
    code, out, err = run('curl', '-sS', '--max-time', str(timeout), '-o', '/dev/null', '-w', '%{http_code}', *curl_args, url, timeout=timeout + 5)
    return out if code == 0 else 'ERR:' + (err or str(code))[:120]


def http_json(url, *curl_args, timeout=10):
    code, out, _ = run('curl', '-sS', '--max-time', str(timeout), *curl_args, url, timeout=timeout + 5)
    if code != 0:
        return None
    try:
        return json.loads(out)
    except ValueError:
        return None


def read_env(path):
    """Parses KEY=VALUE lines. Callers must never emit values of secret keys."""
    values = {}
    try:
        for line in Path(path).read_text().splitlines():
            match = re.fullmatch(r'\s*([A-Z][A-Z0-9_]*)=(.*)', line)
            if match:
                values[match[1]] = match[2].strip().strip('"\'')
    except OSError:
        pass
    return values


def imds_identity():
    opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
    base = 'http://169.254.169.254/latest/'
    token_request = urllib.request.Request(base + 'api/token', method='PUT', headers={'X-aws-ec2-metadata-token-ttl-seconds': '60'})
    with opener.open(token_request, timeout=3) as response:
        token = response.read().decode()
    request = urllib.request.Request(base + 'dynamic/instance-identity/document', headers={'X-aws-ec2-metadata-token': token})
    with opener.open(request, timeout=3) as response:
        return json.load(response)


def port_open(port, host='127.0.0.1'):
    try:
        with socket.create_connection((host, port), timeout=3):
            return True
    except OSError:
        return False


def check_identity(report):
    target = TARGETS[report.role]
    try:
        doc = imds_identity()
        matches = doc.get('instanceId') == target['id'] and doc.get('instanceType') == target['type'] and doc.get('region') == REGION
        report.add('identity', 'EC2 identity, type and region', matches, '{} {} {}'.format(doc.get('instanceId'), doc.get('instanceType'), doc.get('region')))
    except (OSError, ValueError) as error:
        report.add('identity', 'EC2 identity, type and region', False, type(error).__name__)


def check_os(report):
    _, state, _ = run('systemctl', 'is-system-running')
    report.add('os', 'Operating system booted', state in ('running', 'degraded'), state)
    usage = shutil.disk_usage('/')
    free_gib = usage.free / 2 ** 30
    report.add('disk', 'Free disk space', free_gib >= 5, '{:.1f} GiB free'.format(free_gib))


def check_units(report):
    for unit in UNITS[report.role]:
        _, active, _ = run('systemctl', 'is-active', unit)
        _, enabled, _ = run('systemctl', 'is-enabled', unit)
        report.add('unit:' + unit, 'Service ' + unit, active == 'active', 'active={} enabled={}'.format(active, enabled))
        if enabled != 'enabled':
            report.warn('boot:' + unit, unit + ' does not start at boot', 'enabled=' + enabled)


def check_certificates(report):
    names = sorted(TLS_ROOT.glob('*.crt')) if TLS_ROOT.is_dir() else []
    if not names:
        report.add('tls-files', 'TLS certificates present', False, 'none under ' + str(TLS_ROOT))
        return
    now = dt.datetime.now(dt.timezone.utc)
    soonest = None
    expired = []
    for path in names:
        code, out, _ = run('openssl', 'x509', '-in', str(path), '-noout', '-enddate')
        if code != 0 or '=' not in out:
            expired.append(path.name + ':unreadable')
            continue
        end = dt.datetime.strptime(out.split('=', 1)[1], '%b %d %H:%M:%S %Y %Z').replace(tzinfo=dt.timezone.utc)
        days = (end - now).total_seconds() / 86400
        if soonest is None or days < soonest[1]:
            soonest = (path.name, days)
        if days <= 0:
            expired.append(path.name)
    report.add('tls-valid', 'TLS and mTLS certificates valid', not expired, 'expired: ' + ', '.join(expired) if expired else 'earliest {} in {:.1f} days'.format(*soonest))
    if soonest and 0 < soonest[1] < CERT_WARNING_DAYS:
        report.warn('tls-renewal', 'Certificates need renewal soon', '{} expires in {:.1f} days'.format(*soonest))


def check_modules(report, base, prefix, *curl_args):
    missing = []
    for path in MODULES:
        status = http_status(base + path, *curl_args, timeout=25)
        if status != '200':
            missing.append('{}={}'.format(path, status))
    report.add(prefix + '-modules', 'Five health modules reachable ({})'.format(prefix), not missing, ', '.join(missing) or 'all 200')


def check_provider(report):
    provider = read_env(ENV_ROOT / 'provider.env')
    path = ENV_ROOT / 'provider.env'
    secure = path.is_file() and not path.is_symlink() and path.stat().st_uid == 0 and (path.stat().st_mode & 0o777) == 0o600
    report.add('provider-file', 'OpenAI key file kept across restarts', secure and bool(provider.get('OPENAI_API_KEY')), 'root-owned 0600' if secure else 'missing or insecure')
    for role, port in (('web', 8000), ('aaos', 8001)):
        status = http_json('http://127.0.0.1:{}/api/mental/provider-status'.format(port))
        live = bool(status and status.get('isLiveLLM') and status.get('apiKeyConfigured'))
        report.add('provider-' + role, 'OpenAI provider active on {} backend'.format(role), live, (status or {}).get('providerName', 'no response'))
        env = read_env(ENV_ROOT / 'api-{}.env'.format(role))
        report.add('asr-' + role, 'Cloud speech recognition enabled on {} backend'.format(role), env.get('ATTUNE_CLOUD_ASR_ENABLED') == '1')
    key = provider.get('OPENAI_API_KEY', '')
    if key:
        # Curl reads the header from stdin so the key never appears in a process list.
        base = provider.get('OPENAI_BASE_URL', 'https://api.openai.com/v1').rstrip('/')
        try:
            done = subprocess.run(['curl', '-sS', '--max-time', '15', '-o', '/dev/null', '-w', '%{http_code}', '-H', '@-', base + '/models'],
                                  input='Authorization: Bearer ' + key + '\n', capture_output=True, text=True, timeout=20)
            http = done.stdout.strip()
        except (OSError, subprocess.TimeoutExpired):
            http = 'unreachable'
        report.add('provider-auth', 'OpenAI accepts the stored key', http == '200', 'HTTP ' + http)


def check_tts(report, deep):
    env = read_env(ENV_ROOT / 'api-web.env')
    python = env.get('ATTUNE_MENTAL_TTS_PYTHON', '')
    configs = [env.get('ATTUNE_MENTAL_TTS_CONFIG', ''), env.get('ATTUNE_MENTAL_TTS_FEMALE_CONFIG', '')]
    usable = [c for c in configs if c and Path(c).is_file()]
    report.add('tts-runtime', 'Chatterbox TTS runtime and voice configs installed', bool(python) and Path(python).is_file() and len(usable) == 2, '{} of 2 configs'.format(len(usable)))
    pairs = {role: (read_env(ENV_ROOT / 'api-{}.env'.format(role)).get('ATTUNE_MENTAL_TTS_TOKEN', ''),
                    read_env(ENV_ROOT / 'web-{}.env'.format(role)).get('ATTUNE_MENTAL_TTS_TOKEN', '')) for role in ('web', 'aaos')}
    report.add('tts-tokens', 'TTS frontend and backend tokens match', all(a and a == b and len(a) >= 32 for a, b in pairs.values()))
    if deep:
        origin = read_env(ENV_ROOT / 'web-web.env').get('ATTUNE_MENTAL_TTS_FRONTEND_ORIGIN', '')
        host = origin.split('//', 1)[-1]
        code, out, err = run('curl', '-sS', '--max-time', '280', '-o', '/dev/null', '-w', '%{http_code} %{size_download} %{time_total} %{content_type}',
                             '-H', 'Origin: ' + origin, '-H', 'Host: ' + host, '-H', 'Content-Type: application/json',
                             '--data', json.dumps({'text': 'Attune readiness check.', 'language': 'en', 'speechConsent': True, 'speakerProfile': 'female-calm-v1'}),
                             'http://127.0.0.1:3000/api/mental-neural-speech', timeout=290)
        parts = out.split() if code == 0 else []
        ok = len(parts) >= 4 and parts[0] == '200' and int(parts[1]) > 44 and parts[3].startswith('audio/wav')
        report.add('tts-generate', 'Chatterbox generates real speech', ok, out or err)


def check_assets(report, deep):
    evidence = Path('/var/lib/attune/evidence/assets.json')
    try:
        assets = json.loads(evidence.read_text())['assets']
    except (OSError, ValueError, KeyError):
        report.add('assets', 'Model files present', False, 'no asset record at ' + str(evidence))
        return
    bad = []
    for item in assets:
        path = Path('/opt/attune') / item['path']
        if not path.is_file() or path.stat().st_size != item.get('bytes'):
            bad.append(item['path'])
        elif deep:
            digest = hashlib.sha256()
            with path.open('rb') as stream:
                for chunk in iter(lambda: stream.read(1 << 20), b''):
                    digest.update(chunk)
            if digest.hexdigest() != item.get('sha256'):
                bad.append(item['path'] + ':hash')
    kind = 'size and SHA-256' if deep else 'size'
    report.add('assets', 'Model files verified ({})'.format(kind), bool(assets) and not bad, ', '.join(bad[:4]) or '{} files'.format(len(assets)))


def check_inference(report):
    env = read_env(ENV_ROOT / 'api-web.env')
    origin = env.get('ATTUNE_TRUSTED_ORIGINS', '').split(',')[0].strip()
    status = http_status('http://127.0.0.1:8000/api/local-health/skin/prepare', '-X', 'POST', '-H', 'Origin: ' + origin,
                         '-H', 'Content-Type: application/json', '--data', '{"step":"complete"}', timeout=120)
    # 429 means a real analysis currently holds the worker, which is also a live model runtime.
    report.add('inference', 'Skin model worker responds', status in ('200', '429'), 'HTTP ' + status)


def check_web(report, deep):
    for role, port in (('web', 8000), ('aaos', 8001)):
        health = http_json('http://127.0.0.1:{}/api/health'.format(port))
        report.add('api-' + role, '{} backend API health'.format(role.upper()), bool(health and health.get('status') == 'ok'))
    check_modules(report, 'http://127.0.0.1:3000', 'web')
    check_modules(report, 'http://127.0.0.1:3001', 'aaos-frontend', '-H', 'Host: 127.0.0.1:3000')
    check_provider(report)
    check_tts(report, deep)
    check_assets(report, deep)
    check_inference(report)
    report.add('capture-port', 'Reference-camera bridge listening', port_open(8012), '127.0.0.1:8012')
    report.add('caddy-443', 'Public HTTPS listener', port_open(443))
    report.add('mtls-8443', 'Private mTLS listener', port_open(8443))


def adb(*args, timeout=25):
    android_home = read_env(ENV_ROOT / 'aaos.env').get('ANDROID_HOME', '')
    binary = os.path.join(android_home, 'platform-tools', 'adb')
    return run(binary, '-s', ADB_SERIAL, *args, timeout=timeout)


def check_mtls(report):
    web_ip = read_env(ENV_ROOT / 'caddy.env').get('WEB_PRIVATE_IP', '')
    if not web_ip:
        report.add('mtls', 'Private mTLS to WEB', False, 'WEB_PRIVATE_IP not configured')
        return
    pin = ['--resolve', 'attune-internal:8443:' + web_ip, '--cacert', str(TLS_ROOT / 'server-ca.crt')]
    client = ['--cert', str(TLS_ROOT / 'client.crt'), '--key', str(TLS_ROOT / 'client.key')]
    accepted = http_status('https://attune-internal:8443/api/health', *pin, *client)
    report.add('mtls', 'Private mTLS accepted with client certificate', accepted == '200', 'HTTP ' + accepted)
    refused = http_status('https://attune-internal:8443/api/health', *pin)
    report.add('mtls-refusal', 'Private mTLS refuses callers without a certificate', refused != '200', refused)
    bridge = http_status('https://attune-internal:8443/bridge/pair', *pin, *client)
    report.add('camera-bridge', 'Reference-camera bridge reachable through mTLS', bridge == '405', 'HTTP ' + bridge)
    state = http_json('https://attune-internal:8443/api/vehicle/state', *pin, *client)
    report.add('park', 'Backend vehicle state is PARK', bool(state and state.get('vehicleParked') is True and state.get('vehicleMoving') is False), (state or {}).get('state', 'no response'))


def check_android(report):
    code, booted, err = adb('shell', 'getprop', 'sys.boot_completed')
    if not report.add('android-boot', 'Android finished booting', code == 0 and booted == '1', booted or err):
        return
    _, sdk, _ = adb('shell', 'getprop', 'ro.build.version.sdk')
    report.add('android-api', 'Android Automotive 15 / API 35', sdk == '35', 'API ' + sdk)
    _, features, _ = adb('shell', 'pm', 'list', 'features')
    report.add('android-automotive', 'Automotive device type', 'android.hardware.type.automotive' in features)
    report.add('android-mic-feature', 'Guest microphone feature', 'android.hardware.microphone' in features, required=False)
    _, meminfo, _ = adb('shell', 'cat', '/proc/meminfo')
    match = re.search(r'MemTotal:\s+(\d+) kB', meminfo)
    guest_mib = int(match[1]) / 1024 if match else 0
    report.add('android-memory', 'Guest memory near {} MiB'.format(REQUIRED_GUEST_MEMORY_MIB), REQUIRED_GUEST_MEMORY_MIB * 0.9 <= guest_mib <= REQUIRED_GUEST_MEMORY_MIB, '{:.0f} MiB visible'.format(guest_mib))
    _, apk, _ = adb('shell', 'pm', 'path', PACKAGE)
    report.add('apk', 'Attune APK installed', apk.startswith('package:'), PACKAGE)
    _, webview, _ = adb('shell', 'dumpsys', 'webviewupdate')
    match = re.search(r'Current WebView package \(name, version\): \(([^,]+), ([^)]+)\)', webview)
    report.add('webview', 'Android WebView available', bool(match), '{} {}'.format(match[1], match[2]) if match else 'not found')
    _, reverse, _ = adb('reverse', '--list')
    report.add('adb-reverse', 'Guest route to the Attune frontend', 'tcp:3000' in reverse)
    _, activities, _ = adb('shell', 'dumpsys', 'activity', 'activities')
    report.add('app-foreground', 'Attune app in foreground', re.search(r'(?:ResumedActivity|mFocusedApp).*' + re.escape(PACKAGE), activities) is not None, required=False)
    _, size, _ = adb('shell', 'wm', 'size')
    _, density, _ = adb('shell', 'wm', 'density')
    report.add('display', 'Guest display', True, '{}; {}'.format(size, density), required=False)


def check_audio(report):
    env = read_env(ENV_ROOT / 'aaos.env')
    report.add('audio-enabled', 'Audio bridge enabled in configuration', env.get('ATTUNE_AUDIO_ENABLED') == '1')
    code, uid, _ = run('id', '-u', 'attune')
    if code != 0:
        report.add('audio-sinks', 'Isolated audio devices', False, 'no attune user')
        return
    code, sinks, err = run('runuser', '-u', 'attune', '--', 'env', 'XDG_RUNTIME_DIR=/run/user/' + uid, 'pactl', 'list', 'short', 'sinks')
    report.add('audio-sinks', 'Isolated speaker and microphone devices', code == 0 and 'attune_out' in sinks and 'attune_mic' in sinks, err)
    report.add('audio-port', 'Audio bridge listening', port_open(6090), '127.0.0.1:6090')


def check_aaos(report):
    report.add('kvm', 'Hardware virtualization usable', os.access('/dev/kvm', os.R_OK | os.W_OK))
    check_mtls(report)
    check_modules(report, 'http://127.0.0.1:3000', 'aaos')
    check_android(report)
    check_audio(report)
    report.add('novnc', 'Remote emulator screen available', http_status('http://127.0.0.1:6080/vnc.html') == '200')
    report.add('caddy-443', 'Public HTTPS listener', port_open(443))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--role', choices=sorted(TARGETS), required=True)
    parser.add_argument('--deep', action='store_true', help='Also hash model files and generate real speech')
    args = parser.parse_args()
    report = Report(args.role)
    check_identity(report)
    check_os(report)
    check_units(report)
    check_certificates(report)
    if args.role == 'web':
        check_web(report, args.deep)
    else:
        check_aaos(report)
    print(json.dumps(report.payload()))


if __name__ == '__main__':
    main()

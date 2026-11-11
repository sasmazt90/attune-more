#!/usr/bin/env python3
"""Live closing runs on the WEB host: system Chrome -> test Next server -> test API -> real provider and real TTS.

Nothing is replayed except the microphone: the recognition result carries one synthetic, non-personal utterance (the
user turns of a closing_realpath_probe conversation). The test Next server (port 3190, a build of the same checkout
made with NEXT_PUBLIC_MENTAL_CLOSING_BRIDGE=technical-preview and NEXT_PUBLIC_ATTUNE_LOCAL_API_PORT=8190) and the test
API (port 8190, product API environment, fresh token) run as the service user; product services are not touched.
Timeline: scripts/qa/mental_closing_bridge_timeline.cjs in live mode.

Closings per language, each kind in its own fresh API process unless stated:
  cold       first female-calm-v1 request after the API's own start-up warm-up of the default model (as the service
             starts today), one closing per process (--cold-runs processes);
  prepared   API started with ATTUNE_MENTAL_TTS_WARM_PROFILES=female-calm-v1: the closing voice is prepared at start;
             the closing starts after the warm-up log rows are complete (--profile-runs processes). The warm-up times
             are recorded on their own and are never part of a closing's numbers;
  warm       further closings in the last prepared process (--warm-runs).
With --remote-tts the test API's resident worker runs on a GPU host behind remote_resident_bridge.py (private address,
one-off handshake file); the API, its gates, speaker verification and timing stay on this host.
"""
import argparse
import concurrent.futures as cf
import json
import os
from pathlib import Path
import pwd
import re
import secrets
import subprocess
import sys
import time
import urllib.request

sys.path.insert(0, str(Path(__file__).resolve().parent))
from closing_realpath_probe import CONVERSATIONS, TestApi, product_api_environment  # noqa: E402

PLAYWRIGHT = '/opt/attune-venv/lib/python3.11/site-packages/playwright/driver/package'
WARM_ROW = re.compile(r'Resident speech warm-up (\{.*\})')


def warm_rows(log_path, offset):
    with open(log_path, 'rb') as stream:
        stream.seek(offset)
        text = stream.read().decode('utf-8', 'replace')
    return [json.loads(m.group(1)) for m in WARM_ROW.finditer(text)]


def warm_gate(result, profiles):
    """(ok, reason). A process's closings are measured only when every required profile has a successful warm-up row and
    the wait did not time out; otherwise they are recorded as blocked and never enter the cold/prepared/warm numbers."""
    rows = result.get('rows') or []
    if result.get('timeout'):
        return False, 'warm-up-timeout'
    failed = sorted({str(r.get('profile')) for r in rows if not r.get('ok')})
    if failed:
        return False, 'warm-up-failed:' + ','.join(failed)
    missing = [p for p in profiles if not any(r.get('profile') == p and r.get('ok') for r in rows)]
    if missing:
        return False, 'warm-up-missing:' + ','.join(missing)
    return True, None


def build_plan(languages, cold_runs, profile_runs, warm_runs):
    """Processes per language: cold ones, then prepared ones; the last of the later kind also serves the warm closings."""
    plan = []
    for language in languages:
        for kind, count in (('cold', cold_runs), ('prepared', profile_runs)):
            for i in range(count):
                last = kind == ('prepared' if profile_runs else 'cold') and i == count - 1
                plan.append({'language': language, 'process': f'{language}-{kind}-{i + 1}', 'kind': kind,
                             'required': ['default', 'female-calm-v1'] if kind == 'prepared' else ['default'],
                             'closings': [(f'{language}-{kind}-{i + 1}', kind)] + ([(f'{language}-warm-{w + 1}', 'warm') for w in range(warm_runs)] if last else [])})
    return plan


def wait_warm_rows(log_path, offset, profiles, timeout=300):
    """The API logs one numerical row per warm-up step; wait until every expected profile has one (or one failed)."""
    started, rows = time.time(), []
    while time.time() - started < timeout:
        rows = warm_rows(log_path, offset)
        if any(not r.get('ok') for r in rows) or {r['profile'] for r in rows} >= set(profiles):
            return {'rows': rows, 'waitedSeconds': round(time.time() - started, 3)}
        time.sleep(0.5)
    return {'rows': rows, 'waitedSeconds': round(time.time() - started, 3), 'timeout': True}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source', required=True)
    parser.add_argument('--out', required=True)
    parser.add_argument('--languages', default='tr,en,de')
    parser.add_argument('--autoplay', default='default')
    parser.add_argument('--cold-runs', type=int, default=1, help='fresh API processes per language, one cold closing each')
    parser.add_argument('--profile-runs', type=int, default=0, help='fresh API processes per language with the closing voice prepared at start')
    parser.add_argument('--warm-runs', type=int, default=1, help='warm closings after the last cold or prepared one, per language')
    parser.add_argument('--remote-tts', help='host:port of remote_resident_server.py (private address)')
    parser.add_argument('--handshake-file', help='one-off handshake file readable by the service user')
    parser.add_argument('--concurrency-pairs', type=int, default=0, help='pairs of simultaneous female requests after the last language')
    args = parser.parse_args()
    source, out = Path(args.source), Path(args.out)
    out.mkdir(parents=True, exist_ok=False)
    user = pwd.getpwnam('attune')
    os.chown(out, user.pw_uid, user.pw_gid)
    audio_dir = out / 'audio'
    audio_dir.mkdir()
    os.chown(audio_dir, user.pw_uid, user.pw_gid)
    base_env, _ = product_api_environment(8000)
    remote = {}
    if args.remote_tts:
        bridge = source / 'scripts/mental_closing_abc/remote_resident_bridge.py'
        remote = {'ATTUNE_MENTAL_TTS_PYTHON': str(bridge), 'ATTUNE_REMOTE_TTS_ADDRESS': args.remote_tts,
                  'ATTUNE_REMOTE_TTS_HANDSHAKE_FILE': args.handshake_file, 'ATTUNE_MENTAL_TTS_RESIDENT': '1'}
    token = secrets.token_hex(32)
    plan = build_plan(args.languages.split(','), args.cold_runs, args.profile_runs, args.warm_runs)
    scenarios, used = [], {}
    for process in plan:
        for label, _ in process['closings']:
            # The two closing conversations alternate within each language.
            n = used[process['language']] = used.get(process['language'], 0) + 1
            turns = CONVERSATIONS[process['language']][(n - 1) % len(CONVERSATIONS[process['language']])]
            scenarios.append({'label': label, 'language': process['language'], 'mode': 'live', 'conversation': f"{process['language']}-c{(n - 1) % 2 + 1}",
                              'live': {'utterances': [' '.join(text for role, text in turns if role == 'user')]}})
    spec = out / 'live-scenarios.json'
    spec.write_text(json.dumps({'description': __doc__.strip().split('\n\n')[0], 'scenarios': scenarios}, ensure_ascii=False, indent=1))
    log_path = out / 'servers.log'
    log = log_path.open('ab')

    def drop():
        os.setgid(user.pw_gid)
        os.initgroups('attune', user.pw_gid)
        os.setuid(user.pw_uid)
    web_env = {'PATH': '/opt/node/bin:/usr/bin:/bin', 'HOME': user.pw_dir, 'NODE_ENV': 'production', 'NEXT_TELEMETRY_DISABLED': '1',
               'ATTUNE_MENTAL_TTS_TOKEN': token, 'ATTUNE_MENTAL_TTS_BACKEND_URL': 'http://127.0.0.1:8190'}
    web = subprocess.Popen(['/opt/node/bin/node', str(source / 'node_modules/next/dist/bin/next'), 'start', '--hostname', '127.0.0.1',
                            '--port', '3190'], cwd=str(source / 'apps/vehicle-app'), env=web_env, stdin=subprocess.DEVNULL,
                           stdout=log, stderr=subprocess.STDOUT, preexec_fn=drop, start_new_session=True)
    result = {'schema': 'attune-mental-closing-live-web-v2', 'autoplay': args.autoplay, 'remoteTts': bool(args.remote_tts),
              'plan': [{k: p[k] for k in ('language', 'process', 'kind')} | {'closings': [c[0] for c in p['closings']]} for p in plan],
              'runs': [], 'processes': [], 'concurrency': []}
    save = lambda: (out / 'live.json').write_text(json.dumps(result, ensure_ascii=False, indent=1))
    try:
        for _ in range(120):
            try:
                with urllib.request.urlopen('http://127.0.0.1:3190/mental', timeout=2) as r:
                    if r.status == 200:
                        break
            except OSError:
                time.sleep(0.5)
        for index, process in enumerate(plan):
            prepared = process['kind'] == 'prepared'
            extra = {**remote, 'ATTUNE_MENTAL_TTS_WARM_PROFILES': 'female-calm-v1' if prepared else None}
            log.flush()
            offset = log_path.stat().st_size
            api = TestApi(str(source), base_env, 8190, log, token, extra_env=extra)
            record = {'process': process['process'], 'kind': process['kind'], 'language': process['language'], 'loadAtStart': os.getloadavg()}
            try:
                record['readySeconds'] = api.wait_ready()
                # Start-up warm-up: the default model always; the closing voice too when prepared. Logged by the API.
                record['warmUp'] = wait_warm_rows(log_path, offset, process['required'])
                record['secondsFromStartToWarm'] = round(time.time() - api.started, 3)
                ok, reason = warm_gate(record['warmUp'], process['required'])
                record['warmGate'] = {'ok': ok, 'reason': reason, 'required': process['required']}
                if not ok:
                    # Blocked, not measured: no closing of this process runs or enters any number.
                    for label, kind in process['closings']:
                        result['runs'].append({'label': label, 'process': process['process'], 'closing': kind, 'status': 'blocked', 'reason': reason})
                    if index == len(plan) - 1 and args.concurrency_pairs:
                        result['concurrency'].append({'status': 'blocked', 'reason': reason})
                    save()
                    continue
                for label, kind in process['closings']:
                    started = time.time()
                    env = {'PATH': '/opt/node/bin:/usr/bin:/bin', 'HOME': user.pw_dir, 'PLAYWRIGHT_MODULE': PLAYWRIGHT,
                           'CHROME_PATH': '/usr/bin/google-chrome', 'ONLY': label, 'LIVE_AUDIO_DIR': str(audio_dir)}
                    done = subprocess.run(['/opt/node/bin/node', str(source / 'scripts/qa/mental_closing_bridge_timeline.cjs'),
                                           'http://127.0.0.1:3190', str(spec), str(out / f'{label}.json'), args.autoplay],
                                          env=env, preexec_fn=drop, capture_output=True, text=True, timeout=420)
                    result['runs'].append({'label': label, 'process': process['process'], 'closing': kind, 'exit': done.returncode,
                                           'status': 'measured' if done.returncode == 0 else 'failed',
                                           'seconds': round(time.time() - started, 1), 'stdout': done.stdout[-600:], 'stderr': done.stderr[-800:]})
                    save()
                if index == len(plan) - 1 and args.concurrency_pairs:
                    # Two simultaneous closing-voice requests to one API: the product admits one (the other gets 429).
                    line = {'tr': 'İşten ve uykudan söz ettin.', 'en': 'You talked about work and sleep.', 'de': 'Sie sprachen über Arbeit und Schlaf.'}[process['language']]
                    body = {'text': line, 'language': process['language'], 'speechConsent': True, 'speakerProfile': 'female-calm-v1'}
                    for pair in range(args.concurrency_pairs):
                        with cf.ThreadPoolExecutor(2) as pool:
                            futures = [pool.submit(api.post, '/api/mental/neural-speech', body, process['language'], True) for _ in range(2)]
                            rows = [f.result() for f in futures]
                        result['concurrency'].append({'pair': pair + 1, 'language': process['language'],
                                                      'statuses': sorted(r[0] for r in rows), 'seconds': [r[3] for r in rows],
                                                      'serverTiming': [r[1].get('Server-Timing') for r in rows]})
                        time.sleep(1)
                    save()
            finally:
                record['leftoverAfterStop'] = api.stop()
                result['processes'].append(record)
                save()
    finally:
        try:
            os.killpg(web.pid, 15)
            web.wait(20)
        except Exception:
            pass
        result['finishedAt'] = time.time()
        save()
        log.close()


if __name__ == '__main__':
    main()

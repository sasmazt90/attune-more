#!/usr/bin/env python3
"""Live closing runs on the WEB host: system Chrome -> test Next server -> test API -> real provider and real TTS.

Nothing is replayed except the microphone: the recognition result carries one synthetic, non-personal utterance (the
user turns of a closing_realpath_probe conversation). The test Next server (port 3190, a build of the same checkout
made with NEXT_PUBLIC_MENTAL_CLOSING_BRIDGE=technical-preview and NEXT_PUBLIC_ATTUNE_LOCAL_API_PORT=8190) and the test
API (port 8190, product API environment, fresh token) run as the service user on loopback; product services are not
touched. Per language a fresh API process serves two closings: the first one is cold (first female-calm-v1 request of
the process), the second one warm. Timeline: scripts/qa/mental_closing_bridge_timeline.cjs in live mode.
"""
import argparse
import json
import os
from pathlib import Path
import pwd
import secrets
import subprocess
import sys
import time
import urllib.request

sys.path.insert(0, str(Path(__file__).resolve().parent))
from closing_realpath_probe import CONVERSATIONS, TestApi, product_api_environment  # noqa: E402

PLAYWRIGHT = '/opt/attune-venv/lib/python3.11/site-packages/playwright/driver/package'


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source', required=True)
    parser.add_argument('--out', required=True)
    parser.add_argument('--languages', default='tr,en,de')
    parser.add_argument('--autoplay', default='default')
    args = parser.parse_args()
    source, out = Path(args.source), Path(args.out)
    out.mkdir(parents=True, exist_ok=False)
    user = pwd.getpwnam('attune')
    os.chown(out, user.pw_uid, user.pw_gid)
    base_env, _ = product_api_environment(8000)
    token = secrets.token_hex(32)
    scenarios = []
    for language in args.languages.split(','):
        for n, turns in enumerate(CONVERSATIONS[language], 1):
            scenarios.append({'label': f'{language}-live-{n}', 'language': language, 'mode': 'live',
                              'live': {'utterances': [' '.join(text for role, text in turns if role == 'user')]}})
    spec = out / 'live-scenarios.json'
    spec.write_text(json.dumps({'description': __doc__.strip().split('\n\n')[0], 'scenarios': scenarios}, ensure_ascii=False, indent=1))
    log = (out / 'servers.log').open('ab')

    def drop():
        os.setgid(user.pw_gid)
        os.initgroups('attune', user.pw_gid)
        os.setuid(user.pw_uid)
    web_env = {'PATH': '/opt/node/bin:/usr/bin:/bin', 'HOME': user.pw_dir, 'NODE_ENV': 'production', 'NEXT_TELEMETRY_DISABLED': '1',
               'ATTUNE_MENTAL_TTS_TOKEN': token, 'ATTUNE_MENTAL_TTS_BACKEND_URL': 'http://127.0.0.1:8190'}
    web = subprocess.Popen(['/opt/node/bin/node', str(source / 'node_modules/next/dist/bin/next'), 'start', '--hostname', '127.0.0.1',
                            '--port', '3190'], cwd=str(source / 'apps/vehicle-app'), env=web_env, stdin=subprocess.DEVNULL,
                           stdout=log, stderr=subprocess.STDOUT, preexec_fn=drop, start_new_session=True)
    result = {'schema': 'attune-mental-closing-live-web-v1', 'autoplay': args.autoplay, 'runs': [], 'processes': []}
    try:
        for _ in range(120):
            try:
                with urllib.request.urlopen('http://127.0.0.1:3190/mental', timeout=2) as r:
                    if r.status == 200:
                        break
            except OSError:
                time.sleep(0.5)
        for language in args.languages.split(','):
            api = TestApi(str(source), base_env, 8190, log, token)
            record = {'language': language, 'loadAtStart': os.getloadavg()}
            try:
                record['readySeconds'] = api.wait_ready()
                record['warm'] = api.wait_warm()
                for n in (1, 2):
                    label = f'{language}-live-{n}'
                    started = time.time()
                    env = {'PATH': '/opt/node/bin:/usr/bin:/bin', 'HOME': user.pw_dir, 'PLAYWRIGHT_MODULE': PLAYWRIGHT,
                           'CHROME_PATH': '/usr/bin/google-chrome', 'ONLY': label}
                    done = subprocess.run(['/opt/node/bin/node', str(source / 'scripts/qa/mental_closing_bridge_timeline.cjs'),
                                           'http://127.0.0.1:3190', str(spec), str(out / f'{label}.json'), args.autoplay],
                                          env=env, preexec_fn=drop, capture_output=True, text=True, timeout=420)
                    result['runs'].append({'label': label, 'closing': 'cold' if n == 1 else 'warm', 'exit': done.returncode,
                                           'seconds': round(time.time() - started, 1), 'stdout': done.stdout[-600:], 'stderr': done.stderr[-800:]})
                    (out / 'live.json').write_text(json.dumps(result, ensure_ascii=False, indent=1))
            finally:
                record['leftoverAfterStop'] = api.stop()
                result['processes'].append(record)
                (out / 'live.json').write_text(json.dumps(result, ensure_ascii=False, indent=1))
    finally:
        try:
            os.killpg(web.pid, 15)
            web.wait(20)
        except Exception:
            pass
        result['finishedAt'] = time.time()
        (out / 'live.json').write_text(json.dumps(result, ensure_ascii=False, indent=1))
        log.close()


if __name__ == '__main__':
    main()

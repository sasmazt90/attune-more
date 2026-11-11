#!/usr/bin/env python3
"""Test API for the live AAOS closing, on the WEB host: the branch's API with the product API environment (read in
memory, as closing_realpath_probe.TestApi does), a one-off bearer from a file, the resident worker on a GPU host
(remote_resident_bridge.py, round 4) or, without --remote-tts (round 6, no GPU), the WEB host's own CPU worker as in the
product, and the closing voice prepared at start. It listens on --host:--port (the security group
admits only the AAOS group on that port) until --minutes have passed or the stop file appears, then stops.

No closing is served before the warm-up rows of both profiles are successful (closing_live_probe.warm_gate); otherwise
status.json says blocked and the process stops at once. Product services are not touched.
Usage: closing_test_api_serve.py --source <checkout> --out <dir> --token-file F [--remote-tts host:8191 --handshake-file H]
"""
import argparse
import json
import os
from pathlib import Path
import sys
import time

sys.path.insert(0, str(Path(__file__).resolve().parent))
from closing_live_probe import wait_warm_rows, warm_gate  # noqa: E402
from closing_realpath_probe import TestApi, product_api_environment  # noqa: E402


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source', required=True)
    parser.add_argument('--out', required=True)
    parser.add_argument('--host', default='0.0.0.0')
    parser.add_argument('--port', type=int, default=8190)
    parser.add_argument('--token-file', required=True)
    parser.add_argument('--remote-tts', default=None, help='GPU worker address (round 4); omitted: the local CPU worker')
    parser.add_argument('--handshake-file', default=None)
    parser.add_argument('--trusted-origins', default='http://127.0.0.1:3000,http://localhost:3000')
    parser.add_argument('--minutes', type=float, default=45)
    args = parser.parse_args()
    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    status_path, stop_path, log_path = out / 'status.json', out / 'stop', out / 'servers.log'
    status = {'schema': 'attune-closing-test-api-v1', 'startedAt': time.time(), 'port': args.port, 'ready': False}
    save = lambda: status_path.write_text(json.dumps(status, indent=1))
    base_env, _ = product_api_environment(8000)
    if bool(args.remote_tts) != bool(args.handshake_file):
        raise SystemExit('--remote-tts and --handshake-file go together')
    remote = {'ATTUNE_MENTAL_TTS_PYTHON': str(Path(args.source) / 'scripts/mental_closing_abc/remote_resident_bridge.py'),
              'ATTUNE_REMOTE_TTS_ADDRESS': args.remote_tts, 'ATTUNE_REMOTE_TTS_HANDSHAKE_FILE': args.handshake_file} if args.remote_tts else {}
    extra = {**remote, 'ATTUNE_MENTAL_TTS_RESIDENT': '1', 'ATTUNE_MENTAL_TTS_WARM_PROFILES': 'female-calm-v1',
             'ATTUNE_TRUSTED_ORIGINS': args.trusted_origins}
    status['worker'] = 'remote-gpu' if args.remote_tts else 'local-cpu'
    token = Path(args.token_file).read_text('utf-8').strip()
    log = log_path.open('ab')
    offset = log_path.stat().st_size
    api = TestApi(args.source, base_env, args.port, log, token, extra_env=extra, host=args.host)
    try:
        status['readySeconds'] = api.wait_ready()
        status['warmUp'] = wait_warm_rows(log_path, offset, ['default', 'female-calm-v1'])
        ok, reason = warm_gate(status['warmUp'], ['default', 'female-calm-v1'])
        status['warmGate'] = {'ok': ok, 'reason': reason}
        if not ok:
            status['blocked'] = reason
            save()
            return 2
        status['ready'] = True
        status['readyAt'] = time.time()
        save()
        deadline = time.time() + args.minutes * 60
        while time.time() < deadline and not stop_path.exists() and api.proc.poll() is None:
            time.sleep(2)
        status['endedBy'] = 'stop-file' if stop_path.exists() else 'exited' if api.proc.poll() is not None else 'minutes'
        return 0
    finally:
        status['leftoverAfterStop'] = api.stop()
        status['stoppedAt'] = time.time()
        save()
        log.close()


if __name__ == '__main__':
    sys.exit(main())

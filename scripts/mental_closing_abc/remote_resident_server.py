#!/usr/bin/env python3
"""Test infrastructure, GPU host side: serves the branch's resident speech worker to one API process at a time over a
private TCP connection (see remote_resident_bridge.py). Not product code and not started by any service.

Per connection: a one-off handshake line (compared in constant time), then a fresh worker process
(`--worker ...`, normally the branch's services/core-api/mental_neural_resident.py in the GPU venv) whose stdin/stdout
carry the unchanged line protocol. Each request's `config` (a path on the API host) is mapped to this host's
configuration of the same profile (`--config-map`, a JSON object); an unknown path ends the connection. When the
connection closes, the worker's process group is killed: a cancelled request leaves no computation behind, as with
the local resident worker.

Log (JSON lines, numbers and fixed names only, never text): connections, request/reply byte counts and times, worker
exit, and a memory series every second (worker process-group RSS and GPU memory in use from nvidia-smi).
Usage: remote_resident_server.py --listen 172.31.x.y:8191 --handshake-file F --config-map M --log L --peer 172.31.a.b
       --cwd <src>/services/core-api -- <python> mental_neural_resident.py
"""
import argparse
import hmac
import json
import os
from pathlib import Path
import signal
import socket
import subprocess
import sys
import threading
import time


def now():
    return round(time.time(), 3)


class Log:
    def __init__(self, path):
        self.stream, self.lock = open(path, 'a', buffering=1), threading.Lock()

    def __call__(self, kind, **fields):
        with self.lock:
            self.stream.write(json.dumps({'at': now(), 'kind': kind, **fields}) + '\n')


def group_rss_kib(pgid):
    total = 0
    for pid in filter(str.isdigit, os.listdir('/proc')):
        try:
            if os.getpgid(int(pid)) != pgid:
                continue
            for line in Path(f'/proc/{pid}/status').read_text().splitlines():
                if line.startswith('VmRSS:'):
                    total += int(line.split()[1])
        except (OSError, ValueError):
            continue
    return total


def gpu_memory_mib():
    try:
        out = subprocess.run(['nvidia-smi', '--query-gpu=memory.used,memory.total', '--format=csv,noheader,nounits'],
                             capture_output=True, text=True, timeout=5).stdout.strip().split(',')
        return int(out[0]), int(out[1])
    except (OSError, ValueError, IndexError, subprocess.TimeoutExpired):
        return None, None


def serve_connection(connection, peer, args, mapping, log):
    started = time.time()
    connection.settimeout(5)
    reader = connection.makefile('rb')
    try:
        line = reader.readline(512).strip()
    except OSError:
        line = b''
    if not hmac.compare_digest(line, args.handshake):
        log('handshake-refused', peer=peer)
        connection.close()
        return
    connection.settimeout(None)
    connection.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)
    worker = subprocess.Popen(args.worker, cwd=args.cwd, stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                              stderr=subprocess.DEVNULL, start_new_session=True)
    log('connection', peer=peer, workerPid=worker.pid)
    state = {'requests': 0, 'replies': 0, 'last': None}
    stop = threading.Event()

    def memory():
        while not stop.wait(1.0):
            used, total = gpu_memory_mib()
            log('memory', workerPid=worker.pid, rssKiB=group_rss_kib(worker.pid), gpuMiB=used, gpuTotalMiB=total)

    def downstream():
        try:
            for reply in iter(worker.stdout.readline, b''):
                state['replies'] += 1
                log('reply', bytes=len(reply), afterRequestSeconds=round(time.time() - state['last'], 3) if state['last'] else None)
                connection.sendall(reply)
        except OSError:
            pass
        finally:
            try:
                connection.shutdown(socket.SHUT_WR)
            except OSError:
                pass
    threading.Thread(target=memory, daemon=True).start()
    out = threading.Thread(target=downstream, daemon=True)
    out.start()
    reason = 'peer-closed'
    try:
        for raw in iter(lambda: reader.readline(64 * 1024), b''):
            try:
                job = json.loads(raw)
                job['config'] = mapping[job['config']]
            except (ValueError, KeyError, TypeError):
                reason = 'unmapped-or-invalid-request'
                break
            state['requests'] += 1
            state['last'] = time.time()
            log('request', bytes=len(raw), warm=job.get('warm') is True, language=job.get('language') if job.get('language') in ('tr', 'en', 'de') else None,
                profile=job.get('speakerProfile') if job.get('speakerProfile') in ('female-calm-v1', 'official-default') else None)
            worker.stdin.write(json.dumps(job, ensure_ascii=False).encode() + b'\n')
            worker.stdin.flush()
    except OSError:
        reason = 'connection-error'
    finally:
        stop.set()
        try:
            os.killpg(worker.pid, signal.SIGKILL)
        except ProcessLookupError:
            pass
        code = worker.wait()
        connection.close()
        log('connection-end', peer=peer, reason=reason, requests=state['requests'], replies=state['replies'],
            workerExit=code, seconds=round(time.time() - started, 3))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--listen', required=True)
    parser.add_argument('--handshake-file', required=True)
    parser.add_argument('--config-map', required=True)
    parser.add_argument('--log', required=True)
    parser.add_argument('--peer', action='append', default=[], help='allowed peer address (in addition to the security group)')
    parser.add_argument('--cwd', required=True)
    parser.add_argument('worker', nargs='+')
    args = parser.parse_args()
    args.handshake = Path(args.handshake_file).read_text('utf-8').strip().encode()
    mapping = json.loads(Path(args.config_map).read_text('utf-8'))
    log = Log(args.log)
    host, port = args.listen.rsplit(':', 1)
    server = socket.create_server((host, int(port)), backlog=4)
    log('listening', port=int(port), peers=len(args.peer), mapped=len(mapping))
    while True:
        connection, (peer, _) = server.accept()
        if args.peer and peer not in args.peer:
            log('peer-refused')
            connection.close()
            continue
        # One API process at a time: the API stops its worker before it starts the next one.
        serve_connection(connection, peer, args, mapping, log)


if __name__ == '__main__':
    sys.exit(main())

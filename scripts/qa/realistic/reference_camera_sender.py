#!/usr/bin/env python3
"""Streams approved reference photos to the AAOS demo camera bridge over mTLS.

The photo sent follows the pose file, so a journey can switch views. Reference input only:
it stands in for a camera and proves nothing about a physical one. The pairing key comes
from a private file that is removed on read, and is never logged.
"""
import argparse
import json
from pathlib import Path
import socket
import ssl
import time

from websockets.sync.client import connect

TLS = '/etc/attune/tls/'


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--prefix', required=True, help='Frame files are <prefix>POSE.png, for example /var/lib/attune/qa/vision-')
    parser.add_argument('--poses', default='FRONT,RIGHT,LEFT')
    parser.add_argument('--pose-file', default='/var/lib/attune/qa/camera-pose.txt')
    parser.add_argument('--pair-file', default='/var/lib/attune/qa/camera-pair.json')
    parser.add_argument('--web-ip', default='172.31.11.240')
    parser.add_argument('--origin', default='https://aaos.sasmaz.digital')
    parser.add_argument('--wait', type=int, default=600)
    args = parser.parse_args()
    pair = Path(args.pair_file)
    for _ in range(args.wait):
        if pair.exists():
            break
        time.sleep(1)
    else:
        raise SystemExit('No pairing key arrived')
    key = json.loads(pair.read_text())['key']
    pair.unlink()
    context = ssl.create_default_context(cafile=TLS + 'server-ca.crt')
    context.load_cert_chain(TLS + 'client.crt', TLS + 'client.key')
    frames = {pose: Path(args.prefix + pose + '.png').read_bytes() for pose in args.poses.split(',')}
    pose_file = Path(args.pose_file)
    sent = 0
    try:
        with connect('wss://attune-internal:8443/bridge/sender', sock=socket.create_connection((args.web_ip, 8443)), ssl=context,
                     origin=args.origin, max_size=8388608) as ws:
            ws.send(json.dumps({'key': key, 'consent': True}))
            while True:
                request = json.loads(ws.recv(timeout=10))
                current = pose_file.read_text().strip()
                ws.send(json.dumps({'challenge': request['challenge']}))
                ws.send(frames[current])
                sent += 1
    except Exception as error:
        print(json.dumps({'senderFinished': True, 'framesSent': sent, 'endClass': type(error).__name__}))


if __name__ == '__main__':
    main()

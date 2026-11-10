#!/usr/bin/env python3
"""Test infrastructure, API host side: stands in for the resident speech worker executable and carries its line
protocol to remote_resident_server.py on a GPU host over a private TCP connection.

The API starts the resident worker as [ATTUNE_MENTAL_TTS_PYTHON, mental_neural_resident.py] with stdin/stdout pipes.
Setting ATTUNE_MENTAL_TTS_PYTHON to this file (test API process only) keeps the whole product request path on the API
host (HTTP endpoint, consent and park gates, speaker verification, admission, timing headers, cancellation by killing
the worker) and moves only the worker's computation to the GPU host. Killing this process, which is how the API cancels
inference, closes the connection; the server then kills the remote worker.

Environment (names carry no TOKEN/SECRET/API_KEY/PASSWORD, so the API's worker environment keeps them):
  ATTUNE_REMOTE_TTS_ADDRESS         private host:port of the server
  ATTUNE_REMOTE_TTS_HANDSHAKE_FILE  file holding a one-off random handshake line made for one test window
No text is logged. The argument (the resident worker path) is ignored.
"""
import os
from pathlib import Path
import socket
import sys
import threading


def main():
    host, port = os.environ['ATTUNE_REMOTE_TTS_ADDRESS'].rsplit(':', 1)
    handshake = Path(os.environ['ATTUNE_REMOTE_TTS_HANDSHAKE_FILE']).read_text('utf-8').strip()
    connection = socket.create_connection((host, int(port)), timeout=10)
    connection.settimeout(None)
    connection.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)
    connection.sendall(handshake.encode() + b'\n')

    def upstream():
        try:
            for line in iter(sys.stdin.buffer.readline, b''):
                connection.sendall(line)
        except OSError:
            pass
        finally:
            try:
                connection.shutdown(socket.SHUT_WR)
            except OSError:
                pass
    threading.Thread(target=upstream, daemon=True).start()
    out = sys.stdout.buffer
    while True:
        chunk = connection.recv(1 << 16)
        if not chunk:
            break
        out.write(chunk)
        out.flush()


if __name__ == '__main__':
    try:
        main()
    except Exception:
        sys.exit(1)

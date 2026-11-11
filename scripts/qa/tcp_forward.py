#!/usr/bin/env python3
"""Test infrastructure: a loopback TCP forward (listen on 127.0.0.1:PORT, connect to TARGET_HOST:TARGET_PORT).

Used on the AAOS host for the live closing: the branch's Next speech route insists on a loopback backend
(ATTUNE_MENTAL_TTS_BACKEND_URL=http://127.0.0.1:8190), and the test API runs on the WEB host. Bytes are copied
unchanged in both directions; when either side closes or fails, both connections are closed, so a cancelled request
reaches the API as a closed connection. No content is logged; only connection counts and durations.
Usage: tcp_forward.py --listen 8190 --target 172.31.x.y:8190 --log forward.jsonl
"""
import argparse
import asyncio
import json
import time


async def pipe(reader, writer):
    try:
        while True:
            data = await reader.read(1 << 16)
            if not data:
                break
            writer.write(data)
            await writer.drain()
    except (ConnectionError, asyncio.CancelledError):
        pass
    finally:
        try:
            writer.close()
        except Exception:
            pass


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--listen', type=int, required=True)
    parser.add_argument('--target', required=True)
    parser.add_argument('--log', required=True)
    args = parser.parse_args()
    host, port = args.target.rsplit(':', 1)
    log = open(args.log, 'a', buffering=1)

    async def handle(client_reader, client_writer):
        started = time.time()
        try:
            upstream_reader, upstream_writer = await asyncio.open_connection(host, int(port))
        except OSError as error:
            log.write(json.dumps({'at': round(started, 3), 'kind': 'connect-failed', 'error': type(error).__name__}) + '\n')
            client_writer.close()
            return
        a = asyncio.ensure_future(pipe(client_reader, upstream_writer))
        b = asyncio.ensure_future(pipe(upstream_reader, client_writer))
        done, pending = await asyncio.wait({a, b}, return_when=asyncio.FIRST_COMPLETED)
        # One side ended: close both, so a client that gave up closes the upstream connection at once.
        for task in pending:
            task.cancel()
        for writer in (upstream_writer, client_writer):
            try:
                writer.close()
            except Exception:
                pass
        log.write(json.dumps({'at': round(started, 3), 'kind': 'connection', 'seconds': round(time.time() - started, 3),
                              'firstClosed': 'client' if a in done else 'upstream'}) + '\n')

    async def run():
        server = await asyncio.start_server(handle, '127.0.0.1', args.listen)
        log.write(json.dumps({'at': round(time.time(), 3), 'kind': 'listening', 'port': args.listen}) + '\n')
        async with server:
            await server.serve_forever()
    asyncio.run(run())


if __name__ == '__main__':
    main()

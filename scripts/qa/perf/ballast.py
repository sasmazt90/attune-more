#!/usr/bin/env python
"""Controlled load for causal tests: reproduces only the memory footprint or only the
CPU load of another process, so the two can be separated. Memory is allocated in fixed
chunks without reallocation, and the available-RAM floor is polled four times a second,
so the ballast gives its memory back before the host is put at risk.

    python ballast.py --memory-mib 2100 --seconds 300 --floor-mib 450
    python ballast.py --cpu-processes 2 --duty 0.6 --seconds 300
"""
import argparse
import multiprocessing
from pathlib import Path
import time

import psutil

PAGE = 4096
CHUNK = 32 * 2**20
TOUCH_SECONDS = 2.0
POLL_SECONDS = .25


def spin(duty, seconds):
    end = time.monotonic() + seconds
    while time.monotonic() < end:
        window = time.monotonic()
        while time.monotonic() - window < .1 * duty:
            pass
        time.sleep(max(0.0, .1 * (1 - duty)))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--memory-mib', type=int, default=0)
    parser.add_argument('--cpu-processes', type=int, default=0)
    parser.add_argument('--duty', type=float, default=1.0)
    parser.add_argument('--seconds', type=float, required=True)
    parser.add_argument('--floor-mib', type=int, default=500)
    parser.add_argument('--stop-file', type=Path)
    arguments = parser.parse_args()
    floor = arguments.floor_mib * 2**20

    def below_floor():
        return psutil.virtual_memory().available < floor

    workers = [multiprocessing.Process(target=spin, args=(arguments.duty, arguments.seconds), daemon=True) for _ in range(arguments.cpu_processes)]
    for worker in workers:
        worker.start()

    chunks = []
    released = False
    for _ in range(arguments.memory_mib * 2**20 // CHUNK):
        if below_floor():
            released = True
            break
        chunks.append(bytearray(b'\1') * CHUNK)
    print(dict(allocatedMiB=len(chunks) * CHUNK // 2**20, floorHitDuringAllocation=released), flush=True)

    end = time.monotonic() + arguments.seconds
    last_touch = 0.0
    releases = 0
    while time.monotonic() < end and not (arguments.stop_file and arguments.stop_file.exists()):
        if chunks and below_floor():
            # Give back a quarter and re-check: enough for the host, keeps the pressure.
            del chunks[len(chunks) * 3 // 4:]
            releases += 1
            print(dict(releasedTo=len(chunks) * CHUNK // 2**20, at=round(time.time(), 1)), flush=True)
        if time.monotonic() - last_touch >= TOUCH_SECONDS:
            # Touching keeps the pages referenced, as an active guest would.
            for chunk in chunks:
                for offset in range(0, CHUNK, PAGE * 16):
                    chunk[offset] = 1
            last_touch = time.monotonic()
        time.sleep(POLL_SECONDS)
    for worker in workers:
        worker.terminate()
    print(dict(releases=releases), flush=True)


if __name__ == '__main__':
    multiprocessing.freeze_support()
    main()

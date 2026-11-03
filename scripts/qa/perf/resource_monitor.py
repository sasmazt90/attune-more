#!/usr/bin/env python
"""Bounded host resource sampler for QA runs. Counters only: no frames, results or
command-line arguments are written, so the output is safe to archive.

Separates what a peak RSS alone cannot: private commit vs resident set, soft vs hard
page faults, CPU per process group, and system paging from English PDH counters.
"""
import argparse
import ctypes
from ctypes import wintypes
import json
from pathlib import Path
import time

import psutil

PDH_FMT_DOUBLE = 0x00000200
COUNTERS = {
    'availableMiB': r'\Memory\Available MBytes',
    'committedBytes': r'\Memory\Committed Bytes',
    'commitLimitBytes': r'\Memory\Commit Limit',
    'pageFaultsPerSec': r'\Memory\Page Faults/sec',
    'hardFaultReadsPerSec': r'\Memory\Page Reads/sec',
    'pagesInputPerSec': r'\Memory\Pages Input/sec',
    'pagesOutputPerSec': r'\Memory\Pages Output/sec',
    'transitionFaultsPerSec': r'\Memory\Transition Faults/sec',
    'demandZeroFaultsPerSec': r'\Memory\Demand Zero Faults/sec',
    'pagefileUsagePercent': r'\Paging File(_Total)\% Usage',
    'cpuPercent': r'\Processor(_Total)\% Processor Time',
    # Above 100 is turbo; a drop under load is the package power or thermal limit.
    'processorPerformancePercent': r'\Processor Information(_Total)\% Processor Performance',
    'processorFrequencyMHz': r'\Processor Information(_Total)\Processor Frequency',
    'privilegedCpuPercent': r'\Processor(_Total)\% Privileged Time',
    'processorQueueLength': r'\System\Processor Queue Length',
    'contextSwitchesPerSec': r'\System\Context Switches/sec',
    'diskReadsPerSec': r'\PhysicalDisk(_Total)\Disk Reads/sec',
    'diskSecPerRead': r'\PhysicalDisk(_Total)\Avg. Disk sec/Read',
    'diskQueueLength': r'\PhysicalDisk(_Total)\Current Disk Queue Length',
}


class _FmtValue(ctypes.Structure):
    _fields_ = [('CStatus', wintypes.DWORD), ('doubleValue', ctypes.c_double)]


class SystemCounters:
    def __init__(self):
        self.pdh = ctypes.windll.pdh
        self.query = wintypes.HANDLE()
        if self.pdh.PdhOpenQueryW(None, None, ctypes.byref(self.query)):
            raise OSError('PdhOpenQuery failed')
        self.handles = {}
        for name, path in COUNTERS.items():
            handle = wintypes.HANDLE()
            if not self.pdh.PdhAddEnglishCounterW(self.query, path, None, ctypes.byref(handle)):
                self.handles[name] = handle
        self.pdh.PdhCollectQueryData(self.query)

    def read(self):
        self.pdh.PdhCollectQueryData(self.query)
        values = {}
        for name, handle in self.handles.items():
            value = _FmtValue()
            status = self.pdh.PdhGetFormattedCounterValue(handle, PDH_FMT_DOUBLE, None, ctypes.byref(value))
            values[name] = round(value.doubleValue, 3) if status == 0 else None
        return values


def classify(info, command):
    name = (info.get('name') or '').lower()
    text = command.lower()
    if name.startswith('python'):
        if 'local_native_worker' in text:
            return 'worker'
        if 'run_local_backend' in text or 'main:app' in text or 'run_repair_backend' in text:
            return 'api'
        return 'other_python'
    if name.startswith(('qemu-system', 'emulator', 'crosvm', 'netsimd')):
        return 'emulator'
    if name.startswith('adb'):
        return 'adb'
    if name.startswith('node'):
        if 'next' in text and ' start' in text:
            return 'next'
        if '@gitkraken' in text or 'mcp' in text:
            return 'other'
        return 'test_runner'
    if name.startswith(('chrome', 'chromium', 'headless_shell')):
        if 'playwright' in text or '--remote-debugging-pipe' in text or 'attune-qa-profile' in text:
            return 'test_browser'
        return 'user_chrome'
    if name.startswith('java') and 'gradle' in text:
        return 'gradle'
    return 'other'


# Querying ~400 Windows processes costs seconds of CPU per sample and would disturb the
# run being measured. Only these names are attributed; the rest is derived from totals.
ATTRIBUTED = ('python', 'node', 'chrome', 'chromium', 'headless_shell', 'qemu-system', 'emulator', 'crosvm', 'netsimd', 'adb', 'java', 'claude', 'onedrive', 'msmpeng', 'memory compression')


class ProcessGroups:
    def __init__(self):
        self.known = {}
        self.previous = {}

    def discover(self):
        alive = set(psutil.pids())
        for pid in set(self.known) - alive:
            del self.known[pid]
            self.previous.pop(pid, None)
        new = [pid for pid in alive if pid not in self.known and pid != 0]
        # Oldest first, so a browser process is labelled before its helpers.
        entries = []
        for pid in new:
            try:
                process = psutil.Process(pid)
                entries.append((process.create_time(), pid, process, process.name()))
            except (psutil.Error, OSError):
                self.known[pid] = None
        for _, pid, process, name in sorted(entries, key=lambda row: row[:2]):
            lowered = name.lower()
            if not lowered.startswith(ATTRIBUTED):
                self.known[pid] = None
                continue
            try:
                command = ' '.join(process.cmdline())
            except (psutil.Error, OSError):
                command = ''
            label = classify(dict(name=name), command)
            if label == 'user_chrome':
                try:
                    parent = self.known.get(process.ppid())
                except (psutil.Error, OSError):
                    parent = None
                if parent and parent[1] == 'test_browser':
                    label = 'test_browser'
            if label == 'other':
                label = lowered.split('.')[0].replace(' ', '_')
            self.known[pid] = (process, label)

    def sample(self, elapsed):
        self.discover()
        groups = {}
        for pid, entry in list(self.known.items()):
            if entry is None:
                continue
            process, label = entry
            try:
                memory = process.memory_info()
                cpu = process.cpu_times()
            except (psutil.Error, OSError):
                continue
            last = self.previous.get(pid)
            user = (cpu.user - last[0]) / elapsed if last and elapsed > 0 else 0.0
            kernel = (cpu.system - last[1]) / elapsed if last and elapsed > 0 else 0.0
            faults = (memory.num_page_faults - last[2]) / elapsed if last and elapsed > 0 else 0.0
            self.previous[pid] = (cpu.user, cpu.system, memory.num_page_faults)
            row = groups.setdefault(label, dict(count=0, rssMiB=0.0, privateMiB=0.0, cores=0.0, kernelCores=0.0, faultsPerSec=0.0))
            row['count'] += 1
            row['rssMiB'] += memory.rss / 2**20
            row['privateMiB'] += memory.private / 2**20
            row['cores'] += max(0.0, user + kernel)
            row['kernelCores'] += max(0.0, kernel)
            row['faultsPerSec'] += max(0.0, faults)
            if label == 'worker':
                try:
                    row['threads'] = process.num_threads()
                except (psutil.Error, OSError):
                    pass
                row['peakWorkingSetMiB'] = round(memory.peak_wset / 2**20, 1)
                row['peakPrivateMiB'] = round(memory.peak_pagefile / 2**20, 1)
        for row in groups.values():
            for field in ('rssMiB', 'privateMiB', 'cores', 'kernelCores', 'faultsPerSec'):
                row[field] = round(row[field], 2)
        return groups


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--out', required=True, type=Path)
    parser.add_argument('--interval', type=float, default=2.0)
    parser.add_argument('--stop-file', required=True, type=Path)
    parser.add_argument('--max-seconds', type=float, default=3600.0)
    arguments = parser.parse_args()
    arguments.out.parent.mkdir(parents=True, exist_ok=True)
    system = SystemCounters()
    groups = ProcessGroups()
    groups.sample(0)
    last = time.monotonic()
    started = last
    with arguments.out.open('a', encoding='utf8') as output:
        while not arguments.stop_file.exists() and time.monotonic() - started < arguments.max_seconds:
            time.sleep(arguments.interval)
            now = time.monotonic()
            elapsed = now - last
            last = now
            output.write(json.dumps(dict(ts=round(time.time(), 2), system=system.read(), groups=groups.sample(elapsed)), separators=(',', ':')) + '\n')
            output.flush()


if __name__ == '__main__':
    main()

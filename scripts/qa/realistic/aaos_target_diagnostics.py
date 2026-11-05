"""Read-only Android/CDP observations for a targeted journey. Never retries or restarts the app."""
import datetime as dt
import json
from pathlib import Path
import subprocess
import threading
import time
import urllib.request

PACKAGE = 'more.attune.automotive.prototype.clouddemo'
ADB = ['/opt/android-sdk/platform-tools/adb', '-s', 'emulator-5554']


class TargetDiagnostics:
    def __init__(self, out, interval=3):
        self.out = Path(out)
        self.out.mkdir(parents=True, exist_ok=False)
        self.interval = interval
        self.stop = threading.Event()
        self.lock = threading.Lock()
        self.processes = []
        self.files = []
        self.thread = None

    def event(self, kind, **data):
        row = {'utc': dt.datetime.now(dt.timezone.utc).isoformat(), 'monotonic': time.monotonic(), 'event': kind, **data}
        with self.lock, (self.out / 'events.jsonl').open('a') as log:
            log.write(json.dumps(row) + '\n')

    def read(self, *args):
        try:
            done = subprocess.run([*ADB, *args], capture_output=True, text=True, timeout=8)
            return {'exit': done.returncode, 'output': done.stdout[:24000]}
        except subprocess.TimeoutExpired:
            return {'timeout': True}

    def snapshot(self):
        self.event('snapshot', app=self.read('shell', 'pidof', PACKAGE),
                   memory=self.read('shell', 'dumpsys', 'meminfo', PACKAGE),
                   systemMemory=self.read('shell', 'cat', '/proc/meminfo'),
                   processes=self.read('shell', 'ps', '-A', '-o', 'PID,PPID,RSS,NAME'))
        activities = self.read('shell', 'dumpsys', 'activity', 'activities')
        self.event('resumed-activity', lines=[line.strip() for line in activities.get('output', '').splitlines() if 'topResumedActivity=' in line])
        started = time.monotonic()
        try:
            with urllib.request.urlopen('http://127.0.0.1:3000/api/vehicle/state', timeout=3) as response:
                state = json.loads(response.read(65537))
            self.event('vehicle-observation', seconds=time.monotonic() - started,
                       state={key: state.get(key) for key in ('vehicleMoving', 'vehicleParked', 'gear', 'currentSpeed')})
        except Exception as error:
            self.event('vehicle-observation-error', seconds=time.monotonic() - started, errorType=type(error).__name__)

    def attach(self, page, browser):
        # Deliberately exclude console text, URLs, requests, cookies and health data.
        page.on('close', lambda *_: self.event('cdp-page-close'))
        page.on('crash', lambda *_: self.event('cdp-page-crash'))
        browser.on('disconnected', lambda *_: self.event('cdp-browser-disconnected'))
        session = page.context.new_cdp_session(page)
        session.send('Inspector.enable')
        session.on('Inspector.targetCrashed', lambda *_: self.event('cdp-target-crashed'))
        session.on('Inspector.detached', lambda event: self.event('cdp-inspector-detached', reason=str(event.get('reason', ''))[:100]))
        self.event('cdp-attached')

    def __enter__(self):
        commands = [
            ['logcat', '-b', 'events', '-v', 'epoch', '-T', '1', 'am_proc_died:I', 'am_kill:I', 'am_crash:I', 'am_anr:I', 'am_on_pause_called:I', 'am_on_stop_called:I', 'am_on_resume_called:I', 'am_on_destroy_called:I', '*:S'],
            ['logcat', '-v', 'epoch', '-T', '1', 'chromium:E', 'AndroidRuntime:E', 'libc:F', 'lmkd:I', '*:S'],
        ]
        for index, args in enumerate(commands):
            log = (self.out / ('android-' + str(index) + '.log')).open('w')
            self.files.append(log)
            self.processes.append(subprocess.Popen([*ADB, *args], stdout=log, stderr=subprocess.STDOUT))
        def watch():
            while not self.stop.is_set():
                self.snapshot()
                self.stop.wait(self.interval)
        self.thread = threading.Thread(target=watch, daemon=True)
        self.thread.start()
        self.event('capture-start')
        return self

    def __exit__(self, *error):
        self.stop.set()
        if self.thread:
            self.thread.join(timeout=55)
        for process in self.processes:
            process.terminate()
            try:
                process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                process.kill()
                process.wait()
        for file in self.files:
            file.close()
        self.event('capture-end', raised=error[0].__name__ if error[0] else None)

#!/usr/bin/env python
"""Boot and stop the isolated AAOS 15 test AVD for QA. The AVD runs read-only, so an
installed test package and its data vanish with the session; the backing image and
any other emulator are never modified.

    python aaos_session.py boot --config aaos-config.json --apk app-debug.apk --out DIR
    python aaos_session.py stop --config aaos-config.json
"""
import argparse
import json
import os
from pathlib import Path
import subprocess
import sys
import time
import urllib.request

import psutil

COMPONENT_CLASS = 'more.attune.automotive.MainActivity'


def adb(config, *arguments, timeout=40, check=True):
    return subprocess.run([config['adb'], '-s', config['serial'], *arguments], timeout=timeout, capture_output=True, check=check).stdout.decode('utf8', 'replace').strip()


def devices(config):
    return subprocess.check_output([config['adb'], 'devices'], text=True, timeout=30)


def web_ready(config, package):
    pid = adb(config, 'shell', 'pidof', package, check=False).split()
    if not pid or f'@webview_devtools_remote_{pid[0]}' not in adb(config, 'shell', 'cat', '/proc/net/unix', check=False):
        return False
    adb(config, 'forward', f"tcp:{config['devtoolsPort']}", f'localabstract:webview_devtools_remote_{pid[0]}')
    try:
        with urllib.request.urlopen(f"http://127.0.0.1:{config['devtoolsPort']}/json/list", timeout=3) as response:
            targets = json.load(response)
    except (OSError, ValueError):
        return False
    return any(t.get('url', '').startswith(config['webOrigin']) and t.get('title', '').startswith('Attune') for t in targets)


def match_worker_priority(launcher_pid):
    """The Skin worker runs above normal on Windows. Below it, this AVD's QEMU loses its vCPUs
    on a saturated host: vehicle observations pass the 2.5 s limit and the gate closes the page."""
    emulators = [p for p in psutil.Process(launcher_pid).children(recursive=True) if p.name().startswith('qemu-system')]
    for emulator in emulators:
        emulator.nice(psutil.ABOVE_NORMAL_PRIORITY_CLASS)
    return [emulator.pid for emulator in emulators]


def boot(arguments, config):
    if config['serial'] in devices(config):
        raise SystemExit(f"{config['serial']} is already running; preserved")
    arguments.out.mkdir(parents=True, exist_ok=True)
    environment = dict(os.environ, ANDROID_HOME=config['sdk'], ANDROID_SDK_ROOT=config['sdk'], ANDROID_AVD_HOME=config['avdHome'])
    command = [str(Path(config['sdk']) / 'emulator/emulator.exe'), '-avd', config['avd'], '-read-only', '-port', str(config['port']), '-no-window',
               '-skin', '1280x720', '-memory', str(arguments.memory), '-cores', str(arguments.cores), '-gpu', config.get('gpu', 'host'),
               '-feature', '-Vulkan', '-feature', '-QuickbootFileBacked', '-no-snapshot', '-no-boot-anim', '-camera-front', 'none', '-camera-back', 'none']
    log = (arguments.out / 'emulator.log').open('w', encoding='utf8')
    process = subprocess.Popen(command, env=environment, stdout=log, stderr=subprocess.STDOUT, creationflags=subprocess.CREATE_NO_WINDOW | subprocess.DETACHED_PROCESS)
    report = dict(pid=process.pid, command=command[1:], bootStarted=time.time())
    end = time.monotonic() + 300
    while time.monotonic() < end:
        if process.poll() is not None:
            raise SystemExit('Emulator exited; see emulator.log')
        if adb(config, 'shell', 'getprop', 'sys.boot_completed', check=False) == '1':
            break
        time.sleep(3)
    else:
        raise SystemExit('AVD did not finish booting')
    report['bootSeconds'] = round(time.time() - report['bootStarted'], 1)
    report['aboveNormalPids'] = match_worker_priority(process.pid)
    # CarLauncher initialises user 10 after sys.boot_completed.
    time.sleep(15)
    for port in ('3000', '8000'):
        adb(config, 'reverse', f'tcp:{port}', f'tcp:{port}')
    report['runtime'] = dict(release=adb(config, 'shell', 'getprop', 'ro.build.version.release'), sdk=adb(config, 'shell', 'getprop', 'ro.build.version.sdk'),
                             automotive='android.hardware.type.automotive' in adb(config, 'shell', 'pm', 'list', 'features'), display=adb(config, 'shell', 'wm', 'size'),
                             user=adb(config, 'shell', 'am', 'get-current-user'),
                             cameraDevices=[line.strip() for line in adb(config, 'shell', 'dumpsys', 'media.camera').splitlines() if 'Number of camera devices' in line][:1])
    if arguments.apk:
        report['install'] = adb(config, 'install', '-r', str(arguments.apk), timeout=180)
        if 'Success' not in report['install']:
            raise SystemExit('APK install failed: ' + report['install'])
        package = config['package']
        report['installedSHA256'] = adb(config, 'shell', 'sha256sum', adb(config, 'shell', 'pm', 'path', '--user', report['runtime']['user'], package).split(':', 1)[1]).split()[0]
        if not arguments.no_launch:
            component = f'{package}/{COMPONENT_CLASS}'
            end = time.monotonic() + 180
            launched = 0
            while time.monotonic() < end and not web_ready(config, package):
                if not adb(config, 'shell', 'pidof', package, check=False).split() and time.monotonic() - launched > 8:
                    adb(config, 'shell', 'am', 'start', '-W', '--user', 'current', '-n', component, timeout=45, check=False)
                    launched = time.monotonic()
                time.sleep(1)
            report['webviewReady'] = web_ready(config, package)
            report['webviewReadySeconds'] = round(time.time() - report['bootStarted'], 1)
    (arguments.out / 'session.json').write_text(json.dumps(report, indent=1), 'utf8')
    print(json.dumps(report))


def stop(_arguments, config):
    if config['serial'] not in devices(config):
        print('not running')
        return
    adb(config, 'emu', 'kill', check=False)
    for _ in range(30):
        if config['serial'] not in devices(config):
            print('stopped')
            return
        time.sleep(1)
    raise SystemExit('Emulator still listed after emu kill')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action', choices=('boot', 'stop'))
    parser.add_argument('--config', required=True, type=Path)
    parser.add_argument('--apk', type=Path)
    parser.add_argument('--out', type=Path, default=Path('.'))
    parser.add_argument('--memory', type=int, default=2048)
    parser.add_argument('--cores', type=int, default=3)
    parser.add_argument('--no-launch', action='store_true')
    arguments = parser.parse_args()
    config = json.loads(arguments.config.read_text('utf8'))
    config.setdefault('adb', str(Path(config['sdk']) / 'platform-tools/adb.exe'))
    config.setdefault('devtoolsPort', 19226)
    config.setdefault('webOrigin', 'http://localhost:3000')
    (boot if arguments.action == 'boot' else stop)(arguments, config)


if __name__ == '__main__':
    sys.exit(main())

"""Single-launch AAOS runner. No SDK updates, retries or software-acceleration fallback."""
import json
import os
from pathlib import Path
import signal
import socket
import subprocess
import sys
import time

from runtime_preflight import POLICY, audit, command

SERIAL = 'emulator-5554'
NAME = 'attune-aaos'
OPTIONS = ['-no-window', '-no-snapshot', '-no-boot-anim', '-noaudio', '-gpu', 'swiftshader_indirect',
           '-camera-back', 'none', '-camera-front', 'none', '-accel', 'on',
           '-skin', '1280x800', '-dpi-device', '160']


def boot_observed(adb):
    code, state = command([str(adb), '-s', SERIAL, 'get-state'], timeout=5)
    if code or state.strip() != 'device':
        return False
    code, completed = command([str(adb), '-s', SERIAL, 'shell', 'getprop', 'sys.boot_completed'], timeout=5)
    return code == 0 and completed.strip() == '1'


def wait_boot(adb, process, seconds=600):
    deadline = time.monotonic() + seconds
    while time.monotonic() < deadline:
        if process.poll() is not None:
            raise RuntimeError(f'Emulator exited before boot: {process.returncode}; see emulator-host.log')
        if boot_observed(adb):
            return
        time.sleep(2)  # Readiness polling, never a second emulator/job launch.
    raise TimeoutError('AAOS did not complete boot within 600 seconds')


def free_port(port):
    with socket.socket() as test:
        test.bind(('127.0.0.1', port))


def configure_avd(path):
    settings = {'hw.cpu.ncore': '2', 'hw.ramSize': '3072M', 'hw.keyboard': 'no', 'disk.dataPartition.size': '4096M'}
    lines = [line for line in path.read_text().splitlines() if line.split('=', 1)[0].strip() not in settings]
    path.write_text('\n'.join(lines + [key + '=' + value for key, value in settings.items()]) + '\n')


def prepare_avd(sdk, out):
    # SDK 22 avdmanager registers under the default user Android directory even
    # when a custom ANDROID_AVD_HOME is exported. Match the original action's
    # directory, and give the data path explicitly; never repurpose HOME.
    avd_home = Path.home() / '.android/avd'
    os.environ['ANDROID_AVD_HOME'] = str(avd_home)
    avd_home.mkdir(parents=True, exist_ok=True)
    avd = avd_home / (NAME + '.avd')
    # A fresh named disposable AVD is required; never overwrite another AVD.
    if avd.exists():
        raise RuntimeError('Refusing to overwrite an existing validation AVD')
    subprocess.run([str(sdk / 'cmdline-tools/22.0/bin/avdmanager'), 'create', 'avd', '-n', NAME,
                    '--path', str(avd), '--package', POLICY['system_image']], input='no\n', text=True, timeout=90, check=True)
    configure_avd(avd / 'config.ini')
    (out / 'avd-config.ini').write_text((avd / 'config.ini').read_text())


def run():
    sdk = Path(os.environ['ANDROID_HOME'])
    out = Path(os.environ['ATTUNE_AAOS_EVIDENCE'])
    out.mkdir(parents=True, exist_ok=True)
    if os.getenv('ATTUNE_AAOS_REQUIRE_NEURAL') == '1':
        try:
            readiness = json.loads((out / 'neural-readiness.json').read_text())
            if readiness.get('status') != 'PASS':
                raise ValueError('Neural readiness did not pass')
        except (OSError, ValueError):
            print('BLOCKED: successful real neural readiness is required before emulator launch')
            return 69
    report = audit(sdk, 'image')
    (out / 'runtime-before-boot.json').write_text(json.dumps(report, indent=2))
    if report['errors']:
        for error in report['errors']:
            print('BLOCKED:', error)
        return 69
    # Validate all host prerequisites before creating a device or launching QEMU.
    blockers = []
    kvm = Path('/dev/kvm')
    if not kvm.is_char_device() or not os.access(kvm, os.R_OK | os.W_OK):
        blockers.append('/dev/kvm is not a readable/writable character device')
    for port in (3000, 8000, 5554, 5555):
        try:
            free_port(port)
        except OSError as error:
            blockers.append(f'Port {port} unavailable: {error}')
    code, acceleration = command([str(sdk / 'emulator/emulator'), '-accel-check'])
    (out / 'acceleration.txt').write_text(acceleration)
    if code:
        blockers.append('Emulator acceleration check failed: ' + acceleration[-800:])
    import shutil
    if shutil.disk_usage(out).free < 5 * 1024 ** 3:
        blockers.append('Less than 5 GiB free for emulator startup')
    if blockers:
        (out / 'boot-blockers.json').write_text(json.dumps(blockers, indent=2))
        print('BLOCKED: ' + '\nBLOCKED: '.join(blockers))
        return 69
    adb = sdk / 'platform-tools/adb'
    prepare_avd(sdk, out)
    launch = [str(sdk / 'emulator/emulator'), '-port', '5554', '-avd', NAME, *OPTIONS]
    (out / 'emulator-command.json').write_text(json.dumps(launch, indent=2))
    process = None
    started = time.monotonic()
    try:
        with open(out / 'emulator-host.log', 'wb') as log:
            process = subprocess.Popen(launch, stdout=log, stderr=subprocess.STDOUT, start_new_session=True)
            wait_boot(adb, process)
            (out / 'boot.json').write_text(json.dumps({'status': 'PASS', 'seconds': round(time.monotonic() - started, 3),
                                                       'serial': SERIAL, 'single_launch': True}, indent=2))
            for args in [('shell', 'input', 'keyevent', '82'),
                         ('shell', 'settings', 'put', 'global', 'window_animation_scale', '0.0'),
                         ('shell', 'settings', 'put', 'global', 'transition_animation_scale', '0.0'),
                         ('shell', 'settings', 'put', 'global', 'animator_duration_scale', '0.0')]:
                subprocess.run([str(adb), '-s', SERIAL, *args], timeout=15, check=True)
            # The existing harness still requires real automotive/Car UX evidence.
            return subprocess.run([sys.executable, str(Path(__file__).with_name('validate_emulator.py'))],
                                  env={**os.environ, 'ANDROID_SERIAL': SERIAL}, check=False).returncode
    finally:
        if process is not None:
            # Only this process group. Never adb kill-server or unrelated PIDs.
            if process.poll() is None:
                command([str(adb), '-s', SERIAL, 'emu', 'kill'], timeout=10)
                try:
                    process.wait(timeout=15)
                except subprocess.TimeoutExpired:
                    os.killpg(process.pid, signal.SIGTERM)
                    try:
                        process.wait(timeout=5)
                    except subprocess.TimeoutExpired:
                        os.killpg(process.pid, signal.SIGKILL)
                        process.wait(timeout=5)


if __name__ == '__main__':
    def stop(signum, _frame):
        raise SystemExit(128 + signum)
    signal.signal(signal.SIGTERM, stop)
    raise SystemExit(run())

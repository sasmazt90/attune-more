#!/usr/bin/env python3
"""Installs a new cloudDemo APK on the AAOS emulator without touching the app's data. Run as root on the AAOS host.

The normal path is an in-place update. It never uninstalls, so Health History, consents and preferences stay. If the
signing certificate differs, Android would refuse the update, so this stops first with nothing changed.

One exception is --migrate-signing: moving an app from an old certificate to the pinned one once. Android has no in-place
route for that when the old key is gone, so the app data is copied out, the app replaced, and the data restored and compared.
It must be asked for by name, and it refuses to run unless the certificates really differ. Before touching anything it offers
the APK to Android and expects one refusal only, the certificate. If the move stops after the old app is gone, the data stays
in the backup, the message says so, and --resume-migration finishes the job.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
import tarfile
import tempfile
import time

from apk_identity import NotSigned, signing_identity

ADB = ['/opt/android-sdk/platform-tools/adb', '-s', 'emulator-5554']
PACKAGE = 'more.attune.automotive.prototype.clouddemo'
ACTIVITY = PACKAGE + '/more.attune.automotive.MainActivity'
STAGE = Path('/opt/attune-staging/app-cloudDemo.apk')
MIGRATIONS = Path('/var/lib/attune/apk-migration')
MICROPHONE = 'android.permission.RECORD_AUDIO'
# Rebuilt by the app and WebView. Copying them would only carry stale compiled code across.
NOT_DATA = {'cache', 'code_cache'}


class Refused(Exception):
    """Stopped on purpose, with the app and its data unchanged."""


class MigrationInterrupted(RuntimeError):
    """The old app is gone and the move did not finish. The data is in the backup, and --resume-migration finishes the job."""


def plan(installed_cert, new_cert, expected_cert, migrate):
    """Decides what may happen. Pure, so every refusal can be tested without a device."""
    if new_cert != expected_cert:
        raise Refused('APK_NOT_PINNED_IDENTITY: this APK is signed by {}, and the pinned identity is {}. Nothing was changed.'.format(new_cert, expected_cert))
    if installed_cert is None:
        return 'fresh-install'
    if installed_cert == new_cert:
        return 'in-place'
    if not migrate:
        raise Refused('SIGNATURE_MISMATCH: the installed app is signed by {} and this APK by {}. Android cannot update it in place, and uninstalling would delete its data. Nothing was changed. See "Moving to the stable signing identity" in docs/aws/OPERATIONS-CONTROL.md.'.format(installed_cert, new_cert))
    return 'migrate'


def parse_package(text):
    """Reads what matters from `dumpsys package`. None if the package is not installed."""
    if 'Packages:' not in text or 'Package [' + PACKAGE + ']' not in text:
        return None
    version = re.search(r'versionCode=(\d+)', text)
    name = re.search(r'versionName=(\S+)', text)
    first = re.search(r'firstInstallTime=([\d: -]+\d)', text)
    update = re.search(r'lastUpdateTime=([\d: -]+\d)', text)
    users = {}
    parts = re.split(r'\n\s*User (\d+): ', text)
    for number, section in zip(parts[1::2], parts[2::2]):
        installed = re.match(r'[^\n]*\binstalled=(true|false)', section)
        granted = re.search(re.escape(MICROPHONE) + r': granted=(true|false)', section)
        user_first = re.search(r'firstInstallTime=([\d: -]+\d)', section)
        users[number] = {'installed': bool(installed and installed.group(1) == 'true'), 'microphone': bool(granted and granted.group(1) == 'true'),
                         'firstInstallTime': user_first.group(1).strip() if user_first else None}
    return {'versionCode': int(version.group(1)) if version else None, 'versionName': name.group(1) if name else None,
            'firstInstallTime': first.group(1).strip() if first else None, 'lastUpdateTime': update.group(1).strip() if update else None, 'users': users}


class Device:
    def __init__(self, prefix=None):
        self.prefix = list(prefix or ADB)

    def run(self, *args, check=True, stdin=subprocess.DEVNULL, stdout=subprocess.PIPE, timeout=300):
        done = subprocess.run(self.prefix + list(args), stdin=stdin, stdout=stdout, stderr=subprocess.PIPE, timeout=timeout)
        if check and done.returncode != 0:
            raise RuntimeError('adb {} failed: {}'.format(args[0], (done.stderr or b'').decode('utf8', 'replace').strip()[:300]))
        return done

    def text(self, *args, **kwargs):
        return self.run(*args, **kwargs).stdout.decode('utf8', 'replace')

    def package(self):
        return parse_package(self.text('shell', 'dumpsys', 'package', PACKAGE, check=False))

    def installed_cert(self):
        """Fingerprint of the APK Android actually has installed, read from its own copy."""
        paths = re.findall(r'package:(\S+)', self.text('shell', 'pm', 'path', PACKAGE, check=False))
        base = next((p for p in paths if p.endswith('base.apk')), None)
        if not base:
            return None
        with tempfile.TemporaryDirectory() as work:
            local = str(Path(work) / 'installed.apk')
            self.run('pull', base, local)
            return signing_identity(local)

    def start(self):
        self.run('shell', 'am', 'start', '-n', ACTIVITY, check=False)


def android_install(device, apk):
    """adb install -r keeps the app's data. Returns None on success, or why it was refused."""
    done = device.run('install', '-r', str(apk), check=False, timeout=240)
    output = ((done.stdout or b'') + (done.stderr or b'')).decode('utf8', 'replace')
    if done.returncode == 0 and 'Success' in output:
        return None
    reason = re.search(r'INSTALL_[A-Z_]+', output)
    return reason.group(0) if reason else output.strip()[:160]


def install_in_place(device, apk):
    """A refusal from Android leaves the old app and its data as they were."""
    refusal = android_install(device, apk)
    if refusal:
        raise Refused('INSTALL_REFUSED: Android refused the update ({}). The installed app and its data were not changed.'.format(refusal))


def check_apk_name(apk):
    """adb installs only files with this ending, so a wrong name must stop before anything is touched."""
    if Path(apk).suffix != '.apk':
        raise Refused('APK_NAME: adb installs only files ending in .apk, and this is {}. Nothing was changed.'.format(apk))


def promote(incoming, stage=STAGE):
    """run.sh installs this file at every boot, so it changes only after the device accepted the APK."""
    if stage.exists():
        shutil.copy2(stage, stage.with_name(stage.name + '.previous'))
        shutil.copystat(stage, incoming)
        if hasattr(os, 'chown'):
            os.chown(incoming, stage.stat().st_uid, stage.stat().st_gid)
    incoming.replace(stage)


def verify_in_place(before, after, new_cert, device):
    problems = []
    if not after:
        problems.append('The app is no longer installed')
        return problems
    if device.installed_cert() != new_cert:
        problems.append('The installed app does not carry the new certificate')
    if before['firstInstallTime'] != after['firstInstallTime']:
        problems.append('firstInstallTime changed, so this was not an in-place update')
    for number, user in before['users'].items():
        now = after['users'].get(number, {})
        if user['installed'] and not now.get('installed'):
            problems.append('The app is no longer installed for user ' + number)
        if user['microphone'] and not now.get('microphone'):
            problems.append('User {} lost the microphone grant'.format(number))
    return problems


def data_names(device, user):
    listing = device.text('shell', 'run-as', PACKAGE, '--user', user, 'ls', '-A')
    return [name for name in listing.split() if name not in NOT_DATA]


def tar_inventory(path):
    """Regular files and their sizes, the part that must match after a restore. Excludes lock files the app recreates."""
    with tarfile.open(path) as archive:
        return {m.name.lstrip('./'): m.size for m in archive.getmembers() if m.isfile() and not m.name.endswith(('LOCK', '-journal', 'SingletonLock'))}


def back_up(device, before, work):
    """Copies each user's data out and checks the copy can be read. The app is still untouched if this stops."""
    backups = {}
    for user in [number for number, row in before['users'].items() if row['installed']]:
        names = data_names(device, user)
        if not names:
            continue
        path = work / 'user-{}.tar'.format(user)
        with path.open('wb') as out:
            device.run('exec-out', 'run-as', PACKAGE, '--user', user, 'tar', '-cf', '-', *names, stdout=out, timeout=280)
        path.chmod(0o600)
        inventory = tar_inventory(path)
        if not inventory:
            raise Refused('MIGRATION_BACKUP_EMPTY: the backup of user {} holds no files, so the app was not touched.'.format(user))
        backups[user] = {'path': str(path), 'files': len(inventory), 'bytes': sum(inventory.values()), 'sha256': hashlib.sha256(path.read_bytes()).hexdigest()}
    return backups


def finish_migration(device, incoming, work):
    """Installs the new app if it is not there yet, restores every user's data and compares it. Can be repeated until it succeeds."""
    path = work / 'manifest.json'
    manifest = json.loads(path.read_text())
    backups = manifest['users']
    if not device.package():
        refusal = android_install(device, incoming)
        if refusal:
            raise RuntimeError('Android refused the new APK ({})'.format(refusal))
    device.run('shell', 'am', 'force-stop', PACKAGE, check=False)
    # A user can hold the grant without having any data yet.
    for user in manifest['microphoneUsers']:
        device.run('shell', 'pm', 'grant', '--user', user, PACKAGE, MICROPHONE, check=False)
    for user, backup in backups.items():
        with open(backup['path'], 'rb') as source:
            device.run('exec-in', 'run-as', PACKAGE, '--user', user, 'tar', '-xf', '-', stdin=source, timeout=280)
        restored = work / 'user-{}-restored.tar'.format(user)
        with restored.open('wb') as out:
            device.run('exec-out', 'run-as', PACKAGE, '--user', user, 'tar', '-cf', '-', *data_names(device, user), stdout=out, timeout=280)
        restored.chmod(0o600)
        was, now = tar_inventory(backup['path']), tar_inventory(restored)
        missing = sorted(set(was) - set(now))
        changed = sorted(name for name in was if name in now and was[name] != now[name])
        backup['missingAfterRestore'] = missing[:20]
        backup['sizeChangedAfterRestore'] = changed[:20]
        restored.unlink()
        if missing or changed:
            raise RuntimeError('the restored data of user {} differs from the backup: {} files missing, {} changed in size'.format(user, len(missing), len(changed)))
    manifest['finished'] = time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime())
    path.write_text(json.dumps(manifest, indent=1))
    return {'backupFolder': str(work), 'users': backups}


def interrupted(work, failure):
    return MigrationInterrupted('MIGRATION_INTERRUPTED: the old app was removed and the move did not finish: {}. The data is safe in {}. Fix the cause, then run apk_upgrade_host.py --incoming <apk> --expected-cert <sha256> --resume-migration {}. Do not restart the AAOS host first, because its start script would install the old stage APK.'.format(failure, work, work))


def migrate(device, before, installed, incoming, folder=MIGRATIONS):
    """One-time move to the pinned certificate. The old key is gone, so the data must travel around the new install."""
    refusal = android_install(device, incoming)
    if not refusal or 'UPDATE_INCOMPATIBLE' not in refusal:
        raise Refused('MIGRATION_PREFLIGHT: Android should refuse this APK only for its certificate, and it answered {}. Nothing was changed.'.format(refusal or 'success'))
    work = folder / time.strftime('%Y%m%dT%H%M%SZ', time.gmtime())
    work.mkdir(parents=True, mode=0o700)
    device.run('shell', 'am', 'force-stop', PACKAGE, check=False)
    time.sleep(2)
    manifest = {'before': before, 'previousCertificate': installed, 'users': back_up(device, before, work),
                'microphoneUsers': [number for number, row in before['users'].items() if row['microphone']]}
    (work / 'manifest.json').write_text(json.dumps(manifest, indent=1))
    (work / 'manifest.json').chmod(0o600)
    device.run('uninstall', PACKAGE)
    try:
        return finish_migration(device, incoming, work)
    except (RuntimeError, OSError, subprocess.SubprocessError, tarfile.TarError) as failure:
        raise interrupted(work, failure) from failure


def resume_migration(incoming, expected, work, device=None, stage=STAGE):
    """Finishes a move that stopped after the old app was removed."""
    device = device or Device()
    work = Path(work)
    check_apk_name(incoming)
    new_cert = signing_identity(incoming)
    if new_cert != expected:
        raise Refused('APK_NOT_PINNED_IDENTITY: this APK is signed by {}, and the pinned identity is {}. Nothing was changed.'.format(new_cert, expected))
    manifest = json.loads((work / 'manifest.json').read_text())
    if manifest.get('finished'):
        raise Refused('MIGRATION_ALREADY_FINISHED: this move finished at {}, and restoring it now would overwrite newer data. Nothing was changed.'.format(manifest['finished']))
    for user, backup in manifest['users'].items():
        if hashlib.sha256(Path(backup['path']).read_bytes()).hexdigest() != backup['sha256']:
            raise Refused('MIGRATION_BACKUP_CHANGED: the backup of user {} no longer matches its recorded hash. Nothing was changed.'.format(user))
    installed = device.installed_cert() if device.package() else None
    if installed not in (None, new_cert):
        raise Refused('MIGRATION_OTHER_APP: the installed app is signed by {}, so restoring over it is not safe. Nothing was changed.'.format(installed))
    try:
        migration = finish_migration(device, incoming, work)
    except (RuntimeError, OSError, subprocess.SubprocessError, tarfile.TarError) as failure:
        raise interrupted(work, failure) from failure
    if device.installed_cert() != new_cert:
        raise RuntimeError('The installed app does not carry the new certificate')
    report = {'action': 'resume-migration', 'certificate': new_cert, 'previousCertificate': manifest['previousCertificate'], 'before': manifest['before'], 'migration': migration, 'after': device.package()}
    promote(Path(incoming), stage)
    device.start()
    return report


def run(incoming, expected, allow_migration, device=None, stage=STAGE, folder=MIGRATIONS):
    device = device or Device()
    check_apk_name(incoming)
    new_cert = signing_identity(incoming)
    before = device.package()
    installed = device.installed_cert() if before else None
    action = plan(installed, new_cert, expected, allow_migration)
    report = {'action': action, 'certificate': new_cert, 'previousCertificate': installed, 'before': before}
    if action == 'migrate':
        report['migration'] = migrate(device, before, installed, incoming, folder)
    else:
        install_in_place(device, incoming)
    after = device.package()
    report['after'] = after
    if action == 'in-place':
        problems = verify_in_place(before, after, new_cert, device)
        if problems:
            raise RuntimeError('UPGRADE_NOT_CLEAN: ' + '; '.join(problems))
    elif device.installed_cert() != new_cert:
        raise RuntimeError('The installed app does not carry the new certificate')
    promote(Path(incoming), stage)
    device.start()
    return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--incoming', required=True)
    parser.add_argument('--expected-cert', required=True)
    parser.add_argument('--migrate-signing', action='store_true', help='One time only: move an app signed by an old key to the pinned one, keeping its data.')
    parser.add_argument('--resume-migration', help='The backup folder of a move that stopped after the old app was removed.')
    args = parser.parse_args()
    expected = args.expected_cert.lower()
    try:
        report = resume_migration(args.incoming, expected, args.resume_migration) if args.resume_migration else run(args.incoming, expected, args.migrate_signing)
        print(json.dumps(report))
    except (Refused, NotSigned) as refusal:
        print(str(refusal), file=sys.stderr)
        return 3
    except MigrationInterrupted as failure:
        print(str(failure), file=sys.stderr)
        return 4
    return 0


if __name__ == '__main__':
    sys.exit(main())

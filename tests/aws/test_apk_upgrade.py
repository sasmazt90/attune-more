"""APK identity and upgrade rules, with a stand-in for adb. The real upgrades are recorded under QA-41."""
import hashlib
import io
import json
from pathlib import Path
import re
import struct
import subprocess
import sys
import tarfile
import zipfile

import pytest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'scripts/aws'))
import apk_identity
import apk_upgrade_host as host

A, B, OLD = b'certificate-a' * 30, b'certificate-b' * 30, b'certificate-old' * 30
sha = lambda der: hashlib.sha256(der).hexdigest()


def prefixed(data):
    return struct.pack('<I', len(data)) + data


def signer(*certificates):
    digests = prefixed(prefixed(struct.pack('<I', 0x103) + prefixed(b'digest')))
    signed = digests + prefixed(b''.join(prefixed(c) for c in certificates)) + prefixed(b'')
    return prefixed(prefixed(prefixed(signed) + prefixed(b'') + prefixed(b'public-key')))


def make_apk(path, *certificates, second=None, signed=True):
    """A ZIP holding a real v2 and v3 signing block in the documented layout."""
    with zipfile.ZipFile(path, 'w') as z:
        z.writestr('AndroidManifest.xml', b'manifest')
    data = Path(path).read_bytes()
    if not signed:
        return path
    end = data.rfind(b'PK\x05\x06')
    directory = struct.unpack_from('<I', data, end + 16)[0]
    pairs = b''
    for identifier, certs in ((apk_identity.SCHEME_V2, certificates), (apk_identity.SCHEME_V3, second or certificates)):
        value = signer(*certs)
        pairs += struct.pack('<QI', len(value) + 4, identifier) + value
    block = struct.pack('<Q', len(pairs) + 24) + pairs + struct.pack('<Q', len(pairs) + 24) + apk_identity.MAGIC
    moved = bytearray(data[:directory] + block + data[directory:])
    struct.pack_into('<I', moved, directory + len(block) + (end - directory) + 16, directory + len(block))
    Path(path).write_bytes(bytes(moved))
    return path


def test_reads_the_signing_certificate(tmp_path):
    apk = make_apk(tmp_path / 'a.apk', A)
    assert apk_identity.signing_identity(apk) == sha(A)
    assert apk_identity.signing_certificates(apk) == {'v2': [sha(A)], 'v3': [sha(A)]}


def test_refuses_an_unsigned_or_ambiguous_apk(tmp_path):
    with pytest.raises(apk_identity.NotSigned):
        apk_identity.signing_identity(make_apk(tmp_path / 'none.apk', A, signed=False))
    with pytest.raises(apk_identity.NotSigned):
        apk_identity.signing_identity(make_apk(tmp_path / 'two.apk', A, second=[B]))


@pytest.mark.parametrize('installed, new, expected, migrate, action', [
    (sha(A), sha(A), sha(A), False, 'in-place'),
    (None, sha(A), sha(A), False, 'fresh-install'),
    (sha(OLD), sha(A), sha(A), True, 'migrate'),
])
def test_allowed_plans(installed, new, expected, migrate, action):
    assert host.plan(installed, new, expected, migrate) == action


@pytest.mark.parametrize('installed, new, expected, migrate, word', [
    (sha(A), sha(B), sha(A), False, 'APK_NOT_PINNED_IDENTITY'),
    (sha(A), sha(B), sha(A), True, 'APK_NOT_PINNED_IDENTITY'),
    (sha(OLD), sha(A), sha(A), False, 'SIGNATURE_MISMATCH'),
])
def test_refused_plans_say_nothing_changed(installed, new, expected, migrate, word):
    with pytest.raises(host.Refused, match=word) as refusal:
        host.plan(installed, new, expected, migrate)
    assert 'Nothing was changed' in str(refusal.value)


def dumpsys(code=1005, first='2026-11-05 09:00:00', update='2026-11-05 09:00:00', microphone=True, user10=True):
    return """Packages:
  Package [{p}] (abc):
    versionCode={c} minSdk=29 targetSdk=35
    versionName=0.1-prototype-aws-demo
    firstInstallTime={f}
    lastUpdateTime={u}
    User 0: ceDataInode=1 installed=false hidden=false
      firstInstallTime={f}
    User 10: ceDataInode=2 installed={i} hidden=false
      firstInstallTime={f}
      runtime permissions:
        android.permission.RECORD_AUDIO: granted={m}, flags=[ USER_SET]
""".format(p=host.PACKAGE, c=code, f=first, u=update, m=str(microphone).lower(), i=str(user10).lower())


def test_reads_package_state():
    info = host.parse_package(dumpsys())
    assert info['versionCode'] == 1005 and info['firstInstallTime'] == '2026-11-05 09:00:00'
    assert info['users']['10'] == {'installed': True, 'microphone': True, 'firstInstallTime': '2026-11-05 09:00:00'}
    assert info['users']['0']['installed'] is False
    assert host.parse_package('Unable to find package: x\n') is None


class FakeDevice:
    """Behaves like Android: data survives an update, a different certificate is refused, uninstalling deletes data."""

    def __init__(self, tmp_path, installed):
        self.tmp = tmp_path
        self.cert = installed
        self.calls = []
        self.data = {'records': 'kept'} if installed else {}
        self.first, self.update, self.code = '2026-11-05 09:00:00', '2026-11-05 09:00:00', 1005

    def package(self):
        return host.parse_package(dumpsys(self.code, self.first, self.update)) if self.cert else None

    def installed_cert(self):
        return sha(self.cert) if self.cert else None

    def run(self, *args, check=True, **kwargs):
        self.calls.append(args)
        assert args[0] != 'uninstall', 'The normal path must never uninstall'
        if args[0] == 'install':
            new = apk_identity.signing_identity(args[-1])
            if self.cert and sha(self.cert) != new:
                return subprocess.CompletedProcess(args, 1, b'', b'Failure [INSTALL_FAILED_UPDATE_INCOMPATIBLE]')
            self.update, self.code = '2026-11-05 10:00:00', self.code + 1
            return subprocess.CompletedProcess(args, 0, b'Performing Streamed Install\nSuccess\n', b'')
        return subprocess.CompletedProcess(args, 0, b'', b'')

    def text(self, *args, **kwargs):
        return ''

    def start(self):
        self.calls.append(('start',))


def stage_files(tmp_path, current=b'old-stage'):
    stage = tmp_path / 'app-cloudDemo.apk'
    stage.write_bytes(current)
    return stage


def test_in_place_update_keeps_data_and_promotes_the_stage(tmp_path):
    device, stage = FakeDevice(tmp_path, A), stage_files(tmp_path)
    incoming = make_apk(tmp_path / 'incoming.apk', A)
    report = host.run(incoming, sha(A), False, device, stage)
    assert report['action'] == 'in-place' and device.data == {'records': 'kept'}
    assert report['after']['firstInstallTime'] == report['before']['firstInstallTime']
    assert report['after']['versionCode'] == report['before']['versionCode'] + 1
    assert apk_identity.signing_identity(stage) == sha(A)
    assert (tmp_path / 'app-cloudDemo.apk.previous').read_bytes() == b'old-stage'
    assert not any(call[0] == 'uninstall' for call in device.calls)


def test_a_different_key_stops_before_anything_changes(tmp_path):
    device, stage = FakeDevice(tmp_path, OLD), stage_files(tmp_path)
    incoming = make_apk(tmp_path / 'incoming.apk', A)
    with pytest.raises(host.Refused, match='SIGNATURE_MISMATCH'):
        host.run(incoming, sha(A), False, device, stage)
    assert device.calls == [] and device.data == {'records': 'kept'}
    assert stage.read_bytes() == b'old-stage' and incoming.exists()


def test_a_refusal_from_android_keeps_the_stage(tmp_path):
    device, stage = FakeDevice(tmp_path, A), stage_files(tmp_path)
    incoming = make_apk(tmp_path / 'incoming.apk', A)
    device.run_original = device.run
    device.run = lambda *a, **k: subprocess.CompletedProcess(a, 1, b'', b'Failure [INSTALL_FAILED_VERSION_DOWNGRADE]')
    with pytest.raises(host.Refused, match='INSTALL_FAILED_VERSION_DOWNGRADE'):
        host.run(incoming, sha(A), False, device, stage)
    assert stage.read_bytes() == b'old-stage' and device.data == {'records': 'kept'}


def test_a_lost_microphone_grant_or_new_install_time_is_not_a_clean_upgrade(tmp_path):
    device = FakeDevice(tmp_path, A)
    before = host.parse_package(dumpsys())
    assert host.verify_in_place(before, host.parse_package(dumpsys(update='2026-11-05 10:00:00')), sha(A), device) == []
    assert any('firstInstallTime' in p for p in host.verify_in_place(before, host.parse_package(dumpsys(first='2026-11-05 11:00:00')), sha(A), device))
    assert any('microphone' in p for p in host.verify_in_place(before, host.parse_package(dumpsys(microphone=False)), sha(A), device))
    assert any('no longer installed' in p for p in host.verify_in_place(before, host.parse_package(dumpsys(user10=False)), sha(A), device))


def test_only_the_named_migration_can_uninstall():
    """The one uninstall lives in migrate(), which needs --migrate-signing and a real certificate difference."""
    upgrade = (ROOT / 'scripts/aws/apk_upgrade_host.py').read_text(encoding='utf8')
    assert upgrade.count("'uninstall'") == 1
    assert upgrade.index("'uninstall'") > upgrade.index('def migrate(') and upgrade.index("'uninstall'") < upgrade.index('def run(incoming')
    for name in ('scripts/aws/deploy_release.py', 'scripts/aws/deploy_host.py', 'infra/aws/aaos/run.sh'):
        assert 'uninstall' not in (ROOT / name).read_text(encoding='utf8').lower(), name


def test_no_signing_material_or_password_in_the_repository():
    tracked = subprocess.run(['git', 'ls-files'], cwd=ROOT, capture_output=True, text=True, check=True).stdout.splitlines()
    assert not [p for p in tracked if p.lower().endswith(('.p12', '.pfx', '.jks', '.keystore'))]
    gradle = (ROOT / 'apps/automotive/app/build.gradle').read_text(encoding='utf8')
    assert "environmentVariable('ATTUNE_ANDROID_KEYSTORE_PASSWORD')" in gradle and not re.search(r"storePassword\s+['\"]", gradle)
    ignored = (ROOT / '.gitignore').read_text(encoding='utf8')
    assert '*.p12' in ignored and '*.jks' in ignored


def test_only_the_apk_job_can_read_the_key():
    workflow = (ROOT / '.github/workflows/aws-oem-preparation.yml').read_text(encoding='utf8')
    job = workflow[workflow.index('  cloud-apk:'):]
    assert 'environment: android-cloud-demo-signing' in job and 'secrets.ATTUNE_ANDROID_KEYSTORE_B64' in job
    assert 'secrets.' not in workflow[:workflow.index('  cloud-apk:')]
    assert 'head.repo.full_name == github.repository' in job
    assert job.index('Remove the signing key') < job.index('upload-artifact')


@pytest.mark.skipif(not (ROOT / apk_identity.PIN_PATH).exists(), reason='identity not created yet')
def test_pinned_identity_is_a_public_fingerprint():
    pin = json.loads((ROOT / apk_identity.PIN_PATH).read_text(encoding='utf8'))
    assert re.fullmatch(r'[0-9a-f]{64}', pin['sha256'])
    assert not {'password', 'keystore', 'privateKey'} & {k for k in pin}


def test_a_new_identity_is_a_keystore_android_tools_can_read(tmp_path):
    """Uses a throwaway key, kept in tmp_path. The real one is created once by the owner."""
    pytest.importorskip('cryptography')
    import shutil
    from cryptography.hazmat.primitives.serialization import pkcs12
    import create_android_signing_identity as identity
    keystore, password, der, certificate = identity.make_identity()
    loaded_key, loaded_cert, _ = pkcs12.load_key_and_certificates(keystore, password.encode())
    assert loaded_key.key_size == 4096 and loaded_cert == certificate and loaded_cert.subject == loaded_cert.issuer
    assert (certificate.not_valid_after_utc - certificate.not_valid_before_utc).days >= 365 * 25, 'Android asks for a key that outlives the app'
    path = tmp_path / 'throwaway.p12'
    path.write_bytes(keystore)
    tool = shutil.which('keytool')
    if tool:
        listing = subprocess.run([tool, '-list', '-keystore', str(path), '-storetype', 'pkcs12', '-storepass', password], capture_output=True, text=True)
        assert listing.returncode == 0 and identity.ALIAS in listing.stdout and 'PrivateKeyEntry' in listing.stdout, listing.stderr[:300]
    assert hashlib.sha256(der).hexdigest() == sha(der)


def test_creating_an_identity_refuses_to_replace_one():
    source = (ROOT / 'scripts/aws/create_android_signing_identity.py').read_text(encoding='utf8')
    assert 'if PIN.exists() or BACKUP.exists():' in source
    assert 'print(password' not in source and "'--body'" not in source and 'print(encoded' not in source


def load_check():
    import importlib.util
    spec = importlib.util.spec_from_file_location('apk_upgrade_check', ROOT / 'scripts/qa/realistic/apk_upgrade_check.py')
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def stored(skin=(('a', 1), ('b', 2)), language='de', consent='yes'):
    return {'storage': {'togg_health_skin_history': json.dumps([{'id': i, 'value': v} for i, v in skin]), 'attune.language.v1': language, 'attune_health_processing_v1': consent}, 'databases': [{'name': 'photos', 'version': 1, 'stores': {'p': {'keys': ['"a"'], 'values': ['blob:9:image/png']}}}], 'cookieNames': []}


def test_comparison_passes_only_when_every_record_and_setting_matches():
    check = load_check()
    base = check.summarize(stored())
    assert check.compare(base, check.summarize(stored())) == []
    assert any('records missing' in p for p in check.compare(base, check.summarize(stored(skin=(('a', 1),)))))
    assert any('records changed' in p for p in check.compare(base, check.summarize(stored(skin=(('a', 1), ('b', 9))))))
    assert any('duplicated' in p for p in check.compare(base, check.summarize(stored(skin=(('a', 1), ('b', 2), ('a', 1))))))
    assert any('unexpected new' in p for p in check.compare(base, check.summarize(stored(skin=(('a', 1), ('b', 2), ('c', 3))))))
    assert check.compare(base, check.summarize(stored(skin=(('a', 1), ('b', 2), ('c', 3)))), allow_new_records=True) == []
    assert any('Local value changed: attune.language.v1' in p for p in check.compare(base, check.summarize(stored(language='en'))))
    assert any('attune_health_processing_v1' in p for p in check.compare(base, check.summarize(stored(consent='no'))))
    lost = stored()
    lost['databases'] = []
    assert any('Database lost' in p for p in check.compare(base, check.summarize(lost)))
    assert 'value' not in json.dumps(base['records']), 'Evidence holds IDs and hashes, not record content'


def test_comparison_catches_a_reinstall_dressed_as_an_upgrade():
    check = load_check()
    row = {'certificate': 'a', 'firstInstallTime': 't1', 'lastUpdateTime': 't1', 'versionCode': 1001, 'users': {'10': {'microphone': True}}}
    good = {**row, 'lastUpdateTime': 't2', 'versionCode': 1002}
    assert check.compare_package(row, good) == []
    assert any('reinstalled' in p for p in check.compare_package(row, {**good, 'firstInstallTime': 't3'}))
    assert any('certificate' in p for p in check.compare_package(row, {**good, 'certificate': 'b'}))
    assert any('no upgrade' in p for p in check.compare_package(row, {**good, 'lastUpdateTime': 't1'}))
    assert any('versionCode' in p for p in check.compare_package(row, {**good, 'versionCode': 1001}))
    assert any('microphone' in p for p in check.compare_package(row, {**good, 'users': {'10': {'microphone': False}}}))


class MovingDevice(FakeDevice):
    """Adds what the signing move touches: real tar streams, real removal of the data, and adb's check of the file name."""

    def __init__(self, tmp_path, installed):
        super().__init__(tmp_path, installed)
        self.files = {'app_webview/Default/Local Storage/leveldb/000003.log': b'records', 'shared_prefs/app.xml': b'prefs', 'cache/old': b'x'}
        self.refuse_new_install = None
        self.refuse_every_install = None
        self.drop_on_restore = None

    def package(self):
        return host.parse_package(dumpsys(self.code, self.first, self.update, microphone=self.microphone)) if self.cert else None

    microphone = True

    def text(self, *args, **kwargs):
        return ' '.join(sorted({name.split('/')[0] for name in self.files})) if args[:2] == ('shell', 'run-as') else ''

    def run(self, *args, check=True, **kwargs):
        self.calls.append(args)
        if args[0] == 'install':
            if not str(args[-1]).endswith('.apk'):
                return subprocess.CompletedProcess(args, 1, b'Performing Streamed Install\n', b"adb: filename doesn't end .apk or .apex")
            if self.refuse_every_install:
                return subprocess.CompletedProcess(args, 1, b'', self.refuse_every_install)
            new = apk_identity.signing_identity(args[-1])
            if self.cert and sha(self.cert) != new:
                return subprocess.CompletedProcess(args, 1, b'', b'Failure [INSTALL_FAILED_UPDATE_INCOMPATIBLE]')
            if not self.cert and self.refuse_new_install:
                return subprocess.CompletedProcess(args, 1, b'', self.refuse_new_install)
            self.cert, self.microphone = self.new_cert, False
            self.first, self.update, self.code = '2026-11-05 10:00:00', '2026-11-05 10:00:00', 1056
            return subprocess.CompletedProcess(args, 0, b'Success\n', b'')
        if args[0] == 'uninstall':
            self.cert, self.files = None, {}
        elif args[0] == 'exec-out':
            with tarfile.open(fileobj=kwargs['stdout'], mode='w') as archive:
                for name, content in self.files.items():
                    if name.split('/')[0] in args[args.index('-') + 1:]:
                        info = tarfile.TarInfo(name)
                        info.size = len(content)
                        archive.addfile(info, io.BytesIO(content))
        elif args[0] == 'exec-in':
            with tarfile.open(fileobj=kwargs['stdin']) as archive:
                for member in archive.getmembers():
                    if member.name != self.drop_on_restore:
                        self.files[member.name] = archive.extractfile(member).read()
        elif args[:3] == ('shell', 'pm', 'grant'):
            self.microphone = True
        return subprocess.CompletedProcess(args, 0, b'', b'')

    new_cert = A


def moving(tmp_path, installed=OLD):
    device, stage = MovingDevice(tmp_path, installed), stage_files(tmp_path)
    return device, stage, make_apk(tmp_path / 'incoming.apk', A), tmp_path / 'moves'


def test_the_wrong_file_name_stops_before_anything_changes(tmp_path):
    """adb refuses names that do not end in .apk. This once surfaced only after the old app was gone."""
    device, stage, incoming, moves = moving(tmp_path)
    renamed = incoming.with_name('app-cloudDemo.apk.incoming')
    incoming.rename(renamed)
    with pytest.raises(host.Refused, match='APK_NAME'):
        host.run(renamed, sha(A), True, device, stage, moves)
    assert device.calls == [] and device.cert == OLD and stage.read_bytes() == b'old-stage'


def test_the_deploy_tool_uploads_under_a_name_adb_accepts():
    source = (ROOT / 'scripts/aws/deploy_release.py').read_text(encoding='utf8')
    assert re.search(r"work = '/opt/attune-staging/[^']+\.apk'", source)


def test_the_signing_move_keeps_every_file_and_the_microphone(tmp_path):
    device, stage, incoming, moves = moving(tmp_path)
    kept = {name: content for name, content in device.files.items() if not name.startswith('cache')}
    report = host.run(incoming, sha(A), True, device, stage, moves)
    assert report['action'] == 'migrate' and device.cert == A and device.microphone
    assert device.files == kept and apk_identity.signing_identity(stage) == sha(A)
    names = [call[0] for call in device.calls]
    assert names.index('install') < names.index('exec-out') < names.index('uninstall'), 'Offered to Android, then backed up, and only then removed'
    assert json.loads(next(moves.glob('*/manifest.json')).read_text())['finished']


def test_the_signing_move_stops_first_if_android_has_another_objection(tmp_path):
    device, stage, incoming, moves = moving(tmp_path)
    device.refuse_every_install = b'Failure [INSTALL_PARSE_FAILED_NO_CERTIFICATES]'
    with pytest.raises(host.Refused, match='MIGRATION_PREFLIGHT.*Nothing was changed'):
        host.run(incoming, sha(A), True, device, stage, moves)
    assert not any(call[0] in ('uninstall', 'exec-out') for call in device.calls) and device.cert == OLD and 'shared_prefs/app.xml' in device.files


def test_a_move_that_stops_after_removal_says_so_and_can_be_finished(tmp_path):
    device, stage, incoming, moves = moving(tmp_path)
    kept = {name: content for name, content in device.files.items() if not name.startswith('cache')}
    device.refuse_new_install = b'Failure [INSTALL_FAILED_INSUFFICIENT_STORAGE]'
    with pytest.raises(host.MigrationInterrupted) as stopped:
        host.run(incoming, sha(A), True, device, stage, moves)
    message = str(stopped.value)
    work = next(moves.iterdir())
    assert 'INSUFFICIENT_STORAGE' in message and str(work) in message and '--resume-migration' in message
    assert 'not changed' not in message and 'Nothing was changed' not in message, 'The old app is gone, so this must never claim otherwise'
    assert device.cert is None and device.files == {} and stage.read_bytes() == b'old-stage'
    device.refuse_new_install = None
    report = host.resume_migration(incoming, sha(A), work, device, stage)
    assert report['action'] == 'resume-migration' and report['previousCertificate'] == sha(OLD)
    assert device.cert == A and device.files == kept and device.microphone and apk_identity.signing_identity(stage) == sha(A)


def test_resume_refuses_what_it_could_damage(tmp_path):
    device, stage, incoming, moves = moving(tmp_path)
    device.refuse_new_install = b'Failure [INSTALL_FAILED_INSUFFICIENT_STORAGE]'
    with pytest.raises(host.MigrationInterrupted):
        host.run(incoming, sha(A), True, device, stage, moves)
    work = next(moves.iterdir())
    device.refuse_new_install = None
    other = make_apk(tmp_path / 'other.apk', B)
    with pytest.raises(host.Refused, match='APK_NOT_PINNED_IDENTITY'):
        host.resume_migration(other, sha(A), work, device, stage)
    device.cert = OLD
    with pytest.raises(host.Refused, match='MIGRATION_OTHER_APP'):
        host.resume_migration(incoming, sha(A), work, device, stage)
    device.cert = None
    tar = work / 'user-10.tar'
    good = tar.read_bytes()
    tar.write_bytes(good + b'x')
    with pytest.raises(host.Refused, match='MIGRATION_BACKUP_CHANGED'):
        host.resume_migration(incoming, sha(A), work, device, stage)
    tar.write_bytes(good)
    host.resume_migration(incoming, sha(A), work, device, stage)
    device.files['shared_prefs/newer.xml'] = b'made after the move'
    keep_incoming = make_apk(tmp_path / 'again.apk', A)
    with pytest.raises(host.Refused, match='MIGRATION_ALREADY_FINISHED'):
        host.resume_migration(keep_incoming, sha(A), work, device, stage)
    assert device.files['shared_prefs/newer.xml'] == b'made after the move'


def test_a_restore_that_differs_is_not_reported_as_success(tmp_path):
    device, stage, incoming, moves = moving(tmp_path)
    device.drop_on_restore = 'shared_prefs/app.xml'
    with pytest.raises(host.MigrationInterrupted, match='differs from the backup'):
        host.run(incoming, sha(A), True, device, stage, moves)
    assert stage.read_bytes() == b'old-stage' and next(moves.glob('*/user-10.tar')).exists()
    assert not json.loads(next(moves.glob('*/manifest.json')).read_text()).get('finished')


def test_the_signing_move_regrants_the_microphone_to_a_user_with_no_data(tmp_path):
    device, stage, incoming, moves = moving(tmp_path)
    before = device.package()
    before['users']['0'] = {'installed': True, 'microphone': True, 'firstInstallTime': before['firstInstallTime']}
    names = device.text
    device.text = lambda *args, **kwargs: '' if args[:5] == ('shell', 'run-as', host.PACKAGE, '--user', '0') else names(*args, **kwargs)
    host.migrate(device, before, sha(OLD), incoming, moves)
    grants = [call[4] for call in device.calls if call[:3] == ('shell', 'pm', 'grant')]
    assert sorted(grants) == ['0', '10'] and list(moves.glob('*/user-0.tar')) == []

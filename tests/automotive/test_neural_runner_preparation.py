"""Offline adversarial fixtures, never emulator or neural-inference evidence."""
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
import zipfile

HERE = Path(__file__).parent


def load(name):
    spec = importlib.util.spec_from_file_location(name, HERE / (name + '.py'))
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


provision = load('provision_neural')
runner = load('run_emulator')
assessment = load('validate_emulator')


class PrivateImportTests(unittest.TestCase):
    def test_only_explicit_google_service_account_shape_is_admitted(self):
        valid = {'type': 'service_account', 'token_uri': 'https://oauth2.googleapis.com/token',
                 'client_email': 'fixture@example.iam.gserviceaccount.com', 'private_key': 'NOT_A_REAL_KEY'}
        self.assertEqual(provision.credentials(json.dumps(valid), 'private-file-fixture'), valid)
        for key, value in [('type', 'authorized_user'), ('token_uri', 'https://untrusted.invalid/token'),
                           ('private_key', ''), ('client_email', 'owner@example.com')]:
            with self.subTest(key=key), self.assertRaises(ValueError):
                provision.credentials(json.dumps({**valid, key: value}), 'private-file-fixture')
        for raw, file_id in [('', 'fixture'), (json.dumps(valid), '../not-a-file-id'), (json.dumps(valid), '')]:
            with self.assertRaises(ValueError):
                provision.credentials(raw, file_id)

    @staticmethod
    def fixture(root, name='models/fixture', body=b'fixture', expected=None):
        archive = root / 'fixture.zip'
        with zipfile.ZipFile(archive, 'w') as out:
            out.writestr(name, body)
            out.writestr('manifest.json', '{}')
        policy = {'zip_bytes': archive.stat().st_size, 'zip_sha256': provision.sha(archive),
                  'files': [{'path': name, 'bytes': len(body), 'sha256': hashlib.sha256(expected or body).hexdigest()}]}
        return archive, policy

    def test_exact_archive_and_all_member_bytes_are_required(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            archive, policy = self.fixture(root)
            self.assertEqual(provision.extract_verified(archive, root / 'extracted', policy), 1)
            self.assertEqual((root / 'extracted/models/fixture').read_bytes(), b'fixture')
            for key, value in [('zip_bytes', 1), ('zip_sha256', '0' * 64)]:
                with self.assertRaisesRegex(ValueError, 'ZIP_INTEGRITY'):
                    provision.extract_verified(archive, root / 'rejected', {**policy, key: value})
            self.assertFalse((root / 'rejected').exists())

    def test_member_hash_and_size_failure_never_become_success(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            archive, policy = self.fixture(root, expected=b'other')
            with self.assertRaisesRegex(ValueError, 'MEMBER_HASH'):
                provision.extract_verified(archive, root / 'bad', policy)
            policy['files'][0]['bytes'] = 1
            with self.assertRaisesRegex(ValueError, 'MEMBER_SIZE'):
                provision.extract_verified(archive, root / 'bad-size', policy)

    def test_traversal_and_unlisted_members_are_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            archive, policy = self.fixture(root, '../escape')
            with self.assertRaisesRegex(ValueError, 'UNSAFE_ARCHIVE_PATH'):
                provision.extract_verified(archive, root / 'extract', policy)
            self.assertFalse((root / 'escape').exists())
            with self.assertRaisesRegex(ValueError, 'FILE_SET'):
                provision.extract_verified(archive, root / 'extract', {**policy, 'files': []})

    def test_original_zip_identity_and_manifest_are_pinned(self):
        self.assertEqual(provision.POLICY['zip_bytes'], 3283572066)
        self.assertEqual(provision.POLICY['zip_sha256'], '5e98c442627ad78ce22a9bff151b0badd2343f1392b590b42889a0beb679f3fc')
        self.assertEqual(len(provision.POLICY['files']), 117)
        paths = [row['path'] for row in provision.POLICY['files']]
        self.assertEqual(len(set(paths)), 117)
        self.assertIn('models/conds.pt', paths)

    def test_wheel_pins_exclude_vcs_and_include_hashes(self):
        for name in ('requirements.txt', 'cpu-requirements.txt'):
            for line in (HERE / 'neural-runtime' / name).read_text().splitlines():
                if not line or line.startswith('#'):
                    continue
                self.assertRegex(line, r'^[-A-Za-z0-9_]+==[^ ]+ --hash=sha256:[0-9a-f]{64}$')
                self.assertNotIn('git+', line)

    def test_upstream_packaging_files_match_recorded_hashes(self):
        for item in json.loads((HERE / 'neural-runtime/packaging-provenance.json').read_text()):
            self.assertEqual(provision.sha(HERE / 'neural-runtime' / item['file']), item['sha256'])

    def test_missing_readiness_prevents_avd_creation_and_emulator_launch(self):
        with tempfile.TemporaryDirectory() as directory:
            with patch.dict(os.environ, {'ANDROID_HOME': '/sdk', 'ATTUNE_AAOS_EVIDENCE': directory, 'ATTUNE_AAOS_REQUIRE_NEURAL': '1'}), \
                 patch.object(runner.subprocess, 'Popen') as launch, patch.object(runner, 'audit') as sdk:
                self.assertEqual(runner.run(), 69)
                launch.assert_not_called()
                sdk.assert_not_called()

    def test_new_scenarios_preserve_all_historical_checks(self):
        historical = ['aaos-runtime', 'platform-compatibility', 'apk-install', 'activity-start', 'platform-parked',
                      'webview-backend', 'navigation', 'backend-moving-lock', 'platform-moving-lock', 'background-lifecycle',
                      'backend-offline', 'web-load-error-recovery', 'permissions-initial', 'permissions-denial',
                      'unsupported-hardware', 'crashes-console', 'evidence-capture']
        self.assertEqual(assessment.CHECKS[:17], historical)
        self.assertIn('hearing-scored-locales', assessment.CHECKS)
        self.assertIn('mental-neural-interruptions', assessment.CHECKS)

    def test_failed_neural_setup_remains_blocked_in_final_report(self):
        with tempfile.TemporaryDirectory() as directory:
            with patch.dict(os.environ, {'AAOS_NEURAL_IMPORT_OUTCOME': 'failure'}):
                assessment.finalize(Path(directory))
            report = json.loads((Path(directory) / 'execution.json').read_text())
            self.assertEqual(report['first_failed_stage'], 'neural_import')
            self.assertTrue(all(r['status'] == 'BLOCKED' for r in json.loads((Path(directory) / 'results.json').read_text())))


if __name__ == '__main__':
    unittest.main()

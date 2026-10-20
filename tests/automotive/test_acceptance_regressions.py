"""Focused host tests. XML replay is not an Android execution result."""
import hashlib
import importlib.util
import itertools
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import Mock, patch

HERE = Path(__file__).parent


def load(name, filename):
    spec = importlib.util.spec_from_file_location(name, HERE / filename)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


qa = load('qa_acceptance', 'validate_emulator.py')
assets = load('qa_assets', 'validate_assets.py')
PROMPT = (HERE / 'fixtures/aaos_permission_denial.xml').read_text()


class AcceptanceRegressionChecks(unittest.TestCase):
    def test_real_aaos_denial_row_selects_deny_interceptor_not_allow(self):
        self.assertTrue(qa.permission_dialog(PROMPT))
        target = qa.denial_target(PROMPT)
        self.assertEqual((target['x'], target['y']), (640, 518))
        self.assertTrue(target['resource'].endswith('/car_ui_list_item_touch_interceptor'))

    def test_denial_selector_rejects_spoofed_package_and_unknown_row(self):
        self.assertIsNone(qa.denial_target(PROMPT.replace('com.android.permissioncontroller', 'example.fake')))
        self.assertIsNone(qa.denial_target(PROMPT.replace('Don’t allow', 'While using the app')))
        self.assertIsNone(qa.denial_target(PROMPT.replace('Attune.more Prototype', 'Another App')))

    def test_closed_webview_does_not_end_os_dialog_observation(self):
        with tempfile.TemporaryDirectory() as directory:
            a = qa.Assessment(Path(directory))
            a.permissions_denied = Mock()
            a.probe = lambda: {'microphone': 'true', 'camera': 'false'}
            client = Mock()
            client.request.return_value = 'closed'
            a.parked_page = lambda: client
            a.capture = Mock()
            a.ui = Mock(side_effect=['<hierarchy/>', PROMPT, '<hierarchy/>', '<hierarchy/>'])
            a.adb = Mock()
            with patch.object(qa.time, 'sleep'):
                self.assertIn('denial control clicked', a.permission_request())
            a.adb.assert_called_once_with('shell', 'input', 'tap', '640', '518')
            self.assertTrue(json.loads((Path(directory) / 'permissions-denial-observation.json').read_text())['denial_clicked'])

    def test_unknown_denial_layout_is_cancelled_but_never_passes(self):
        unknown = PROMPT.replace('Don’t allow', 'Unknown untranslated option')
        with tempfile.TemporaryDirectory() as directory:
            a = qa.Assessment(Path(directory))
            a.permissions_denied = Mock()
            a.probe = lambda: {'microphone': 'true'}
            a.parked_page = Mock(return_value=Mock())
            a.ui = Mock(side_effect=[unknown, '<hierarchy/>'])
            a.adb = Mock()
            # End the bounded observation loop immediately; exercise cleanup.
            with patch.object(qa.time, 'monotonic', side_effect=itertools.chain([0, 31], itertools.repeat(32))):
                with self.assertRaisesRegex(qa.Blocked, 'denial action not established'):
                    a.permission_request()
            a.adb.assert_called_once_with('shell', 'input', 'keyevent', 'KEYCODE_BACK')

    def test_modal_obstruction_is_blocked_before_native_park_polling(self):
        with tempfile.TemporaryDirectory() as directory:
            a = qa.Assessment(Path(directory))
            a.ui = lambda: PROMPT
            a.api = Mock(side_effect=AssertionError('Must not alter simulation behind modal'))
            with self.assertRaisesRegex(qa.Blocked, 'unresolved OS permission dialog'):
                a.parked_ready()
            a.api.assert_not_called()

    def test_backend_outage_requires_owned_process_and_real_disconnect(self):
        with tempfile.TemporaryDirectory() as directory:
            a = qa.Assessment(Path(directory))
            a.parked_page = Mock()
            a.adb = Mock(side_effect=AssertionError('Do not rely on reverse-rule removal'))
            calls = []
            a.services['backend'] = Mock(poll=lambda: 0)
            a.stop_service = lambda name: calls.append('stop:' + name) or 0
            a.backend_unreachable = lambda: calls.append('disconnected') or True
            a.locked = lambda reasons: calls.append('locked') or True
            a.capture = lambda name: calls.append('capture:' + name)
            a.start_service = lambda name: calls.append('start:' + name)
            a.api = lambda: {'vehicleParked': True}
            a.ui = lambda: 'PARK doğrulandı'
            a.connect = Mock(return_value=Mock())
            self.assertIn('verified connection refusal', a.backend_offline())
            self.assertEqual(calls[:4], ['stop:backend', 'disconnected', 'locked', 'capture:backend-offline-locked'])
            self.assertEqual(calls[4], 'start:backend')
            self.assertTrue(json.loads((Path(directory) / 'backend-offline-fault.json').read_text())['recovered'])

    def test_unowned_backend_is_never_terminated(self):
        with tempfile.TemporaryDirectory() as directory:
            a = qa.Assessment(Path(directory))
            a.services['backend'] = Mock()
            with patch.object(qa.os, 'killpg') as kill:
                with self.assertRaisesRegex(qa.Blocked, 'not owned'):
                    a.stop_service('backend')
                kill.assert_not_called()

    def test_asset_inspection_rejects_missing_and_changed_approved_bytes(self):
        with tempfile.TemporaryDirectory() as directory:
            public = Path(directory)
            folder = public / 'audio/guidance'
            folder.mkdir(parents=True)
            approved = b'approved fixture bytes; not an audio substitution'
            manifest = {'entries': {'sample': {'url': '/audio/guidance/sample.mp3',
                                              'sha256': hashlib.sha256(approved).hexdigest()}}}
            (folder / 'manifest.json').write_text(json.dumps(manifest))
            self.assertIn('absent', assets.inspect_guidance(public)['errors'][0])
            (folder / 'sample.mp3').write_bytes(b'different')
            self.assertIn('differs', assets.inspect_guidance(public)['errors'][0])
            (folder / 'sample.mp3').write_bytes(approved)
            self.assertEqual(assets.inspect_guidance(public)['errors'], [])

    def test_source_asset_blocker_is_reported_without_emulator_passes(self):
        with tempfile.TemporaryDirectory() as directory:
            out = Path(directory)
            (out / 'asset-preflight.json').write_text(json.dumps({'errors': ['approved MP3 absent']}))
            with patch.dict(qa.os.environ, {'AAOS_ASSETS_OUTCOME': 'failure'}):
                qa.finalize(out)
            self.assertEqual(json.loads((out / 'execution.json').read_text())['first_failed_stage'], 'assets')
            self.assertTrue(all(r['status'] == 'BLOCKED' for r in json.loads((out / 'results.json').read_text())))
            self.assertIn('approved MP3 absent', (out / 'report.md').read_text())

    def test_localized_source_gate_checks_count_hash_size_and_path(self):
        public = assets.ROOT / 'apps/vehicle-app/public'
        report = assets.inspect_localized(public)
        self.assertEqual(len(report['assets']), 194)
        self.assertEqual(report['errors'], [])
        with tempfile.TemporaryDirectory() as directory:
            public = Path(directory)
            folder = public / 'audio/user-approved/tr-en-de-20261020-v1'
            folder.mkdir(parents=True)
            data = b'synthetic integrity fixture; never deployed audio'
            manifest = {'approvalStatus': 'USER_APPROVED_FOR_INTEGRATION', 'recordings': [
                {'recordingId': 'fixture', 'url': '/audio/user-approved/tr-en-de-20261020-v1/fixture.m4a',
                 'bytes': len(data), 'sha256': hashlib.sha256(data).hexdigest()}]}
            def inspect():
                (folder / 'manifest.json').write_text(json.dumps(manifest))
                return assets.inspect_localized(public)['errors']
            self.assertTrue(any('194' in e for e in inspect()))
            self.assertTrue(any('absent' in e for e in inspect()))
            (folder / 'fixture.m4a').write_bytes(b'wrong')
            self.assertTrue(any('differs' in e for e in inspect()))
            (folder / 'fixture.m4a').write_bytes(data)
            self.assertFalse(any('differs' in e for e in inspect()))
            manifest['recordings'][0]['url'] = '/audio/user-approved/tr-en-de-20261020-v1/../../outside.m4a'
            self.assertTrue(any('escapes' in e for e in inspect()))

    def test_localized_codec_failure_retains_all_observations_and_restores_locale(self):
        with tempfile.TemporaryDirectory() as directory:
            a = qa.Assessment(Path(directory))
            rows = [{'status': 'PASS', 'id': str(i)} for i in range(194)]
            rows[3] = {'status': 'FAIL', 'id': '3', 'error': 'Actual codec unavailable fixture'}
            client = Mock()
            client.request.side_effect = lambda action, **args: rows if action == 'localization-decode' else None
            a.parked_page = lambda: client
            with self.assertRaisesRegex(AssertionError, 'decode/integrity failed'):
                a.localized_webview_audio()
            self.assertEqual(json.loads((Path(directory) / 'localized-audio-decode.json').read_text()), rows)
            client.request.assert_any_call('localization-language', language='tr')
            self.assertFalse(any(call.args[0] == 'navigate' for call in client.request.call_args_list))

    def test_activity_capture_waits_for_fresh_ui_and_records_complete_hashes(self):
        from PIL import Image
        with tempfile.TemporaryDirectory() as directory:
            a = qa.Assessment(Path(directory))
            a.phase = 'activity-start'
            a.ui = Mock(side_effect=[qa.Blocked('No fresh UI root'),
                                     '<hierarchy><node package="' + qa.PACKAGE + '"/></hierarchy>'])
            def adb(*args, **kw):
                if args[:3] == ('emu', 'screenrecord', 'screenshot'):
                    Image.new('RGB', (2, 2)).save(Path(args[3]) / 'frame.png')
                    return 'OK'
                return 'Actual Activity fixture'
            a.adb = adb
            with patch.object(qa.time, 'sleep'):
                a.capture('activity-start')
            index = json.loads((Path(directory) / 'evidence-index.json').read_text())
            self.assertEqual(len(index['activity-start']['components']), 3)
            self.assertFalse(index['activity-start']['errors'])
            self.assertEqual(a.ui.call_count, 2)

    def test_route_png_alone_does_not_establish_complete_evidence(self):
        from PIL import Image
        with tempfile.TemporaryDirectory() as directory:
            a = qa.Assessment(Path(directory))
            Image.new('RGB', (2, 2)).save(Path(directory) / 'route-dashboard.png')
            with self.assertRaisesRegex(qa.Blocked, 'Incomplete or changed'):
                a.evidence_quality()

    def test_complete_evidence_passes_and_changed_activity_receipt_blocks(self):
        from PIL import Image
        with tempfile.TemporaryDirectory() as directory:
            a = qa.Assessment(Path(directory))
            a.ui = lambda: '<hierarchy><node package="' + qa.PACKAGE + '"/></hierarchy>'
            def adb(*args, **kw):
                if args[:3] == ('emu', 'screenrecord', 'screenshot'):
                    Image.new('RGB', (2, 2)).save(Path(args[3]) / 'frame.png')
                    return 'fixture framebuffer, not an emulator observation'
                return 'fixture Activity receipt'
            a.adb = adb
            for route in qa.ROUTES:
                a.capture('route-' + (route.strip('/') or 'dashboard'))
            a.capture('activity-start')
            a.results = [{'check': 'activity-start', 'status': 'PASS', 'detail': 'unit fixture only'}]
            self.assertIn('nine routes', a.evidence_quality())
            (Path(directory) / 'activity-start-activities.txt').write_text('changed fixture')
            with self.assertRaisesRegex(qa.Blocked, 'Incomplete or changed'):
                a.evidence_quality()

    def test_blocked_wait_preserves_phase_label_and_diagnostic_receipt(self):
        with tempfile.TemporaryDirectory() as directory:
            a = qa.Assessment(Path(directory))
            a.phase = 'permissions-denial'
            def unavailable():
                raise qa.Blocked('fresh OS hierarchy unavailable')
            with patch.object(qa.time, 'monotonic', side_effect=[0, 0, 1]), patch.object(qa.time, 'sleep'):
                with self.assertRaises(qa.Blocked):
                    a.wait(unavailable, 1, label='permission OS UI readiness')
            receipt = json.loads((Path(directory) / 'permissions-denial-timeout.json').read_text())
            self.assertEqual(receipt['label'], 'permission OS UI readiness')
            self.assertIn('fresh OS hierarchy unavailable', receipt['last_error'])


if __name__ == '__main__':
    unittest.main()

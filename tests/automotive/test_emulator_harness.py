"""Offline reporting checks only; never imply that an emulator ran."""
import importlib.util
import io
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
import xml.etree.ElementTree as ET

spec = importlib.util.spec_from_file_location('aaos_validation', Path(__file__).with_name('validate_emulator.py'))
qa = importlib.util.module_from_spec(spec)
spec.loader.exec_module(qa)


class ReportingChecks(unittest.TestCase):
    @staticmethod
    def compatible_platform():
        # Fixture, not a claim that these commands were executed on a device.
        return {'features': 'feature:android.hardware.type.automotive\nfeature:android.software.webview\n',
                'bootclasspath': '/system/framework/framework.jar:/system/framework/android.car.jar\n',
                'libraries': 'library:org.apache.http.legacy\n',
                'car-binder': 'Service car_service: found\n',
                'car-service': '*CarUxRestrictionsManagerService*\nmEnableActivityBlocking:true\n',
                'user-state': 'RUNNING_UNLOCKED\n'}

    def test_boot_classpath_does_not_require_pm_shared_library_registration(self):
        self.assertEqual(qa.platform_compatibility_errors(self.compatible_platform()), [])

    def test_shared_library_does_not_substitute_for_boot_classpath_integration(self):
        observed = self.compatible_platform()
        observed.update(bootclasspath='', libraries='library:android.car\n')
        self.assertIn('No supported Car API jar', ';'.join(qa.platform_compatibility_errors(observed)))

    def test_incompatible_platform_lists_all_missing_safety_requirements(self):
        errors = qa.platform_compatibility_errors({})
        self.assertEqual(len(errors), 7)
        self.assertIn('Activity blocking', ';'.join(errors))

    def test_platform_names_and_classpath_paths_must_match_exactly(self):
        observed = self.compatible_platform()
        observed.update(features='feature:android.hardware.type.automotive.fake\nfeature:android.software.webview.fake\n',
                        bootclasspath='/system/framework/android.car.jar.backup',
                        **{'car-binder': 'Service car_service: not found\n'})
        self.assertEqual(len(qa.platform_compatibility_errors(observed)), 4)

    def test_compatibility_blocker_prevents_every_apk_install(self):
        with tempfile.TemporaryDirectory() as directory:
            assessment = qa.Assessment(Path(directory))
            assessment.user = '10'
            observations = self.compatible_platform()
            observations.update(bootclasspath='', **{'car-binder': 'Service car_service: not found\n'})
            def adb(*args, **kw):
                if args == ('shell', 'am', 'get-started-user-state', '10'):
                    return observations['user-state']
                if args == ('shell', 'printenv', 'BOOTCLASSPATH'):
                    return observations['bootclasspath']
                if args == ('shell', 'service', 'check', 'car_service'):
                    return observations['car-binder']
                if args == ('shell', 'dumpsys', 'car_service'):
                    return observations['car-service']
                if args == ('shell', 'pm', 'list', 'features'):
                    return observations['features']
                return 'fixture diagnostic'
            assessment.adb = adb
            assessment.check('platform-compatibility', assessment.compatibility, capture=False)
            assessment.check('apk-install', lambda: self.fail('Must never install'),
                             ['platform-compatibility'], capture=False)
            self.assertEqual([r['status'] for r in assessment.results], ['BLOCKED', 'BLOCKED'])
            evidence = json.loads((Path(directory) / 'platform-compatibility.json').read_text())
            self.assertEqual(len(evidence['errors']), 2)
            self.assertTrue((Path(directory) / 'platform-libraries.txt').exists())
            qa.finalize(Path(directory))
            execution = json.loads((Path(directory) / 'execution.json').read_text())
            self.assertEqual(execution['first_blocked_check']['check'], 'platform-compatibility')
            self.assertIsNone(execution['first_failed_check'])

    def test_probe_reads_only_explicit_instrumentation_results(self):
        raw = 'INSTRUMENTATION_STATUS: doRequired=false\nINSTRUMENTATION_RESULT: doRequired=true\nINSTRUMENTATION_RESULT: camera=false\nINSTRUMENTATION_CODE: -1\n'
        self.assertEqual(qa.parse_probe(raw), {'doRequired': 'true', 'camera': 'false'})

    def test_missing_probe_does_not_invent_unrestricted_state(self):
        self.assertNotIn('doRequired', qa.parse_probe('INSTRUMENTATION_FAILED: no instrumentation'))

    def test_setup_failure_marks_every_emulator_check_blocked(self):
        with tempfile.TemporaryDirectory() as directory:
            out = Path(directory)
            qa.finalize(out)
            result = json.loads((out / 'results.json').read_text())
            self.assertEqual(len(result), len(qa.CHECKS))
            self.assertTrue(all(r['status'] == 'BLOCKED' for r in result))
            self.assertEqual(ET.parse(out / 'results.xml').getroot().get('skipped'), str(len(qa.CHECKS)))

    def test_finalizer_creates_missing_evidence_directory(self):
        with tempfile.TemporaryDirectory() as directory:
            out = Path(directory) / 'not-initialized'
            qa.finalize(out)
            self.assertTrue((out / 'report.md').exists())
            self.assertTrue((out / 'navigation.json').exists())

    def test_sdk_blocker_lists_all_missing_libraries_without_app_failures(self):
        with tempfile.TemporaryDirectory() as directory:
            out = Path(directory)
            (out / 'runtime-sdk.json').write_text(json.dumps({'errors': ['libpulse.so.0 absent', 'libX11.so.6 absent']}))
            with patch.dict(qa.os.environ, {'AAOS_SDK_OUTCOME': 'failure'}):
                qa.finalize(out)
            self.assertEqual(json.loads((out / 'execution.json').read_text())['first_failed_stage'], 'sdk')
            self.assertTrue(all(r['status'] == 'BLOCKED' for r in json.loads((out / 'results.json').read_text())))
            self.assertIn('libpulse.so.0 absent', (out / 'report.md').read_text())
            self.assertIn('libX11.so.6 absent', (out / 'report.md').read_text())

    def test_partial_run_cannot_hide_unexecuted_checks(self):
        with tempfile.TemporaryDirectory() as directory:
            out = Path(directory)
            (out / 'results.json').write_text(json.dumps([{'check': 'aaos-runtime', 'status': 'PASS', 'detail': 'observed'}]))
            qa.finalize(out)
            rows = json.loads((out / 'results.json').read_text())
            self.assertEqual(rows[0]['status'], 'PASS')
            self.assertEqual(len(rows), len(qa.CHECKS))
            self.assertTrue(all(r['status'] == 'BLOCKED' for r in rows[1:]))

    def test_junit_preserves_failure_and_unverified_distinction(self):
        with tempfile.TemporaryDirectory() as directory:
            out = Path(directory)
            rows = [{'check': name, 'status': status, 'detail': 'actual <observation>'}
                    for name, status in [('works', 'PASS'), ('bug', 'FAIL'), ('infra', 'BLOCKED'), ('hardware', 'UNVERIFIED')]]
            qa.write_reports(out, rows)
            root = ET.parse(out / 'results.xml').getroot()
            self.assertEqual(root.get('failures'), '1')
            self.assertEqual(root.get('skipped'), '2')
            self.assertEqual(json.loads((out / 'results.json').read_text()), rows)

    def test_unverified_observation_does_not_become_pass(self):
        with tempfile.TemporaryDirectory() as directory:
            assessment = qa.Assessment(Path(directory))
            assessment.capture = lambda _: None
            def unavailable():
                raise qa.Unverified('Hardware absent-state cannot be established')
            assessment.check('unsupported-hardware', unavailable)
            self.assertEqual([r['status'] for r in assessment.results], ['UNVERIFIED'])

    def test_dependency_failure_blocks_instead_of_running_dependent_check(self):
        with tempfile.TemporaryDirectory() as directory:
            assessment = qa.Assessment(Path(directory))
            assessment.capture = lambda _: None
            assessment.results = [{'check': 'setup', 'status': 'FAIL', 'detail': 'failed'}]
            assessment.check('dependent', lambda: self.fail('Must not execute'), ['setup'])
            self.assertEqual(assessment.results[-1]['status'], 'BLOCKED')

    def test_sdk_resolution_does_not_depend_on_path(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            tool = root / 'emulator/emulator'
            tool.parent.mkdir()
            tool.write_text('#!/bin/sh\nexit 0\n')
            tool.chmod(0o755)
            with patch.dict(qa.os.environ, {'ANDROID_HOME': directory, 'ANDROID_SDK_ROOT': directory, 'PATH': ''}):
                self.assertEqual(qa.sdk_tool('emulator'), str(tool))
                with self.assertRaises(qa.Blocked):
                    qa.sdk_tool('adb')
            with patch.dict(qa.os.environ, {'ANDROID_HOME': directory, 'ANDROID_SDK_ROOT': directory + '/other'}):
                with self.assertRaises(qa.Blocked):
                    qa.sdk_tool('emulator')

    def test_windows_style_probe_output_is_normalized(self):
        self.assertEqual(qa.parse_probe('INSTRUMENTATION_RESULT: doRequired=false\r\n'), {'doRequired': 'false'})

    def test_fresh_ui_failure_never_reads_stale_dump(self):
        with tempfile.TemporaryDirectory() as directory:
            assessment = qa.Assessment(Path(directory))
            calls = []
            def adb(*args, **kwargs):
                calls.append(args)
                return 'ERROR: could not get idle state.'
            assessment.adb = adb
            with self.assertRaises(qa.Blocked):
                assessment.ui()
            self.assertEqual(calls[0], ('shell', 'rm', '-f', '/data/local/tmp/attune-qa.xml'))
            self.assertFalse(any('cat' in call for call in calls))

    def test_tap_ignores_passive_text_with_same_label(self):
        with tempfile.TemporaryDirectory() as directory:
            assessment = qa.Assessment(Path(directory))
            assessment.ui = lambda: '<hierarchy><node text="Attune.more" enabled="true" clickable="false" bounds="[0,0][20,20]"/><node text="Attune.more" enabled="true" clickable="true" bounds="[40,40][60,60]"/></hierarchy>'
            calls = []
            assessment.adb = lambda *args: calls.append(args)
            self.assertTrue(assessment.tap('Attune.more'))
            self.assertEqual(calls, [('shell', 'input', 'tap', '50', '50')])

    def test_capture_errors_preserve_other_evidence_and_surface_warning(self):
        with tempfile.TemporaryDirectory() as directory:
            out = Path(directory)
            assessment = qa.Assessment(out)
            assessment.ui = lambda: '<hierarchy/>'
            assessment.adb = lambda *args, **kw: 'KO: screenshot unavailable' if args[0] == 'emu' else 'Activities observed'
            assessment.check('observation', lambda: 'Named behavior observed')
            row = assessment.results[0]
            self.assertEqual(row['status'], 'PASS')
            self.assertIn('No fresh emulator framebuffer PNG', row['evidence_warning'])
            self.assertTrue((out / 'observation.xml').exists())
            self.assertFalse((out / 'observation.png').exists())
            self.assertIn('EVIDENCE BLOCKED', (out / 'report.md').read_text())

    def test_unavailable_sdk_does_not_turn_ui_capture_into_app_failure(self):
        with tempfile.TemporaryDirectory() as directory:
            assessment = qa.Assessment(Path(directory))
            assessment.adb = lambda *args, **kw: '<hierarchy/>'
            assessment.ui = lambda: '<hierarchy/>'
            assessment.check('aaos-runtime', lambda: (_ for _ in ()).throw(qa.Blocked('SDK absent')))
            self.assertEqual(assessment.results[0]['status'], 'BLOCKED')

    def test_finalizer_identifies_first_failure_and_all_nine_blocked_routes(self):
        with tempfile.TemporaryDirectory() as directory:
            out = Path(directory)
            (out / 'results.json').write_text(json.dumps([
                {'check': 'aaos-runtime', 'status': 'FAIL', 'detail': 'tool absent'}]))
            qa.finalize(out)
            execution = json.loads((out / 'execution.json').read_text())
            self.assertEqual(execution['first_failed_check']['check'], 'aaos-runtime')
            routes = json.loads((out / 'navigation.json').read_text())
            self.assertEqual([r['path'] for r in routes], qa.ROUTES)
            self.assertTrue(all(r['status'] == 'BLOCKED' for r in routes))

    def test_corrupt_results_are_reported_and_not_silently_passed(self):
        with tempfile.TemporaryDirectory() as directory:
            out = Path(directory)
            (out / 'results.json').write_text('{')
            qa.finalize(out)
            rows = json.loads((out / 'results.json').read_text())
            self.assertEqual(rows[0]['check'], 'harness-report')
            self.assertEqual(rows[0]['status'], 'FAIL')
            self.assertEqual(len(rows), len(qa.CHECKS) + 1)

    def test_invalid_result_schema_is_a_reporting_failure(self):
        with tempfile.TemporaryDirectory() as directory:
            out = Path(directory)
            (out / 'results.json').write_text('{}')
            qa.finalize(out)
            self.assertEqual(json.loads((out / 'execution.json').read_text())['first_failed_check']['check'], 'harness-report')

    def test_missing_png_cannot_silently_pass_evidence_acceptance(self):
        with tempfile.TemporaryDirectory() as directory:
            assessment = qa.Assessment(Path(directory))
            with self.assertRaisesRegex(qa.Blocked, 'Route screenshot unavailable'):
                assessment.evidence_quality()

    def test_blocked_remote_resource_does_not_hide_local_console_error(self):
        with tempfile.TemporaryDirectory() as directory:
            assessment = qa.Assessment(Path(directory))
            assessment.adb = lambda *args, **kwargs: ''
            assessment.console = [
                {'phase': 'navigation', 'kind': 'external-request-blocked', 'url': 'https://example.com/font', 'text': 'blocked'},
                {'phase': 'navigation', 'kind': 'error', 'url': 'http://localhost:3000/app.js', 'text': 'Failed to load resource: net::ERR_FAILED'}]
            with self.assertRaises(AssertionError):
                assessment.crash_console()
            assessment.console[1]['url'] = 'https://example.com/font'
            self.assertIn('No app crash', assessment.crash_console())

    def test_one_failed_route_does_not_hide_remaining_route_results(self):
        with tempfile.TemporaryDirectory() as directory:
            assessment = qa.Assessment(Path(directory))
            class Observer:
                def request(self, action, **args):
                    if args['route'] == '/dental':
                        raise RuntimeError('Fixture: dental link unavailable')
                    return {'path': args['route'], 'status': 'PASS'}
            assessment.connect = lambda: Observer()
            assessment.tap = lambda *args: True
            assessment.capture = lambda *args: None
            with self.assertRaises(AssertionError):
                assessment.navigation()
            rows = json.loads((Path(directory) / 'navigation.json').read_text())
            self.assertEqual([r['path'] for r in rows], qa.ROUTES)
            self.assertEqual(rows[2]['status'], 'FAIL')
            self.assertEqual(rows[-1]['status'], 'PASS')

    def test_endpoint_observation_errors_do_not_prove_webview_destruction(self):
        with tempfile.TemporaryDirectory() as directory:
            assessment = qa.Assessment(Path(directory))
            assessment.cdp_port = 12345
            errors = [qa.urllib.error.HTTPError('http://localhost', 500, 'fault', {}, None),
                      qa.urllib.error.URLError(TimeoutError('timeout'))]
            for error in errors:
                with self.subTest(error=type(error).__name__), patch.object(qa.urllib.request, 'urlopen', side_effect=error):
                    with self.assertRaises(qa.Blocked):
                        assessment.no_web_target()
            for invalid in [b'{', b'{}']:
                with self.subTest(invalid=invalid), patch.object(qa.urllib.request, 'urlopen', return_value=io.BytesIO(invalid)):
                    with self.assertRaises(qa.Blocked):
                        assessment.no_web_target()
            with patch.object(qa.urllib.request, 'urlopen', side_effect=qa.urllib.error.URLError(ConnectionRefusedError())):
                self.assertTrue(assessment.no_web_target())
            with patch.object(qa.urllib.request, 'urlopen', return_value=io.BytesIO(b'[{"url":"http://localhost:3000/"}]')):
                self.assertFalse(assessment.no_web_target())


if __name__ == '__main__':
    unittest.main()

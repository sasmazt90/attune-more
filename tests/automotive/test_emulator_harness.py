"""Offline reporting checks only; never imply that an emulator ran."""
import importlib.util
import json
from pathlib import Path
import tempfile
import unittest
import xml.etree.ElementTree as ET

spec = importlib.util.spec_from_file_location('aaos_validation', Path(__file__).with_name('validate_emulator.py'))
qa = importlib.util.module_from_spec(spec)
spec.loader.exec_module(qa)


class ReportingChecks(unittest.TestCase):
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


if __name__ == '__main__':
    unittest.main()

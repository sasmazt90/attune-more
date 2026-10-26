import unittest
from pathlib import Path

import yaml


ROOT = Path(__file__).parents[3]
WORKFLOW = ROOT / ".github" / "workflows" / "ci.yml"
COMMAND = "python -m unittest discover -s scripts/skin-research/tests -p 'test_*.py'"


class PhysicalCameraAcceptanceCIWiringTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.text = WORKFLOW.read_text(encoding="utf-8")
        cls.workflow = yaml.safe_load(cls.text)
        cls.steps = cls.workflow["jobs"]["backend-test"]["steps"]

    def test_work_branch_push_runs_the_evidence_suite(self):
        # PyYAML 1.1 reads the unquoted GitHub Actions `on` key as boolean True.
        triggers = self.workflow.get("on", self.workflow.get(True))
        self.assertIsInstance(triggers, dict)
        self.assertEqual(
            triggers["push"]["branches"],
            ["main", "work/skin-roadmap-20261023"],
        )
        self.assertEqual(triggers["pull_request"]["branches"], ["main"])

    def test_workflow_parses_and_has_one_full_skin_suite_step(self):
        matching = [step for step in self.steps if step.get("name") == "Run complete skin research evidence suite"]
        self.assertEqual(len(matching), 1)
        self.assertEqual(matching[0].get("run"), COMMAND)
        self.assertEqual(self.text.count(COMMAND), 1)

    def test_full_suite_runs_after_python_and_dependencies(self):
        names = [step.get("name") for step in self.steps]
        full_index = names.index("Run complete skin research evidence suite")
        self.assertLess(names.index("Set up Python 3.11"), full_index)
        self.assertLess(names.index("Install dependencies"), full_index)
        self.assertLess(names.index("Run deterministic unit test suite"), full_index)

    def test_discovery_covers_camera_manifest_truth_metrics_and_acceptance(self):
        required = {
            "test_build_physical_camera_benchmark_manifest.py",
            "test_build_physical_camera_expert_truth.py",
            "test_evaluate_physical_camera_predictions.py",
            "test_evaluate_physical_camera_localization.py",
            "test_check_physical_camera_acceptance.py",
        }
        discovered = {path.name for path in (ROOT / "scripts" / "skin-research" / "tests").glob("test_*.py")}
        self.assertTrue(required.issubset(discovered))

    def test_ci_step_does_not_start_training_upload_or_inference(self):
        step = next(step for step in self.steps if step.get("name") == "Run complete skin research evidence suite")
        command = step["run"].lower()
        for forbidden in ("train", "upload", "infer", "roboflow"):
            self.assertNotIn(forbidden, command)


if __name__ == "__main__":
    unittest.main()

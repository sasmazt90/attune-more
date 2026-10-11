"""Stale or altered export evidence cannot qualify a newly selected model."""
import json,tempfile,unittest
from pathlib import Path
from unittest.mock import patch
from update_acceptance_progress import current_mask_export_plan,sha


class ExportEvidenceTests(unittest.TestCase):
 def setUp(self):
  self.temp=tempfile.TemporaryDirectory();self.out=Path(self.temp.name);self.d=self.out/'interim-diagnosis';self.d.mkdir()
  self.selection=self.d/'corrected-selection-v4.json';self.selection.write_text('{"selected":"old-full-model"}')
  self.plan=self.d/'plan.json';self.plan.write_text('{"targets":{"bags":{"export":{"weightsSHA256":"old-full-model"}}}}')
  self.index=self.d/'selected-full-export-current.json'
  self.index.write_text(json.dumps(dict(planPath=str(self.plan),planSHA256=sha(self.plan),selectionSHA256=sha(self.selection))))
  self.patcher=patch('update_acceptance_progress.OUT',self.out);self.patcher.start()
 def tearDown(self):self.patcher.stop();self.temp.cleanup()
 def test_valid_full_model_receipt_is_read(self):
  self.assertEqual(current_mask_export_plan()['targets']['bags']['export']['weightsSHA256'],'old-full-model')
 def test_new_selection_cannot_reuse_old_export_status(self):
  self.selection.write_text('{"selected":"new-full-model"}')
  self.assertEqual(current_mask_export_plan(),{})
 def test_changed_plan_fails_closed(self):
  self.plan.write_text('{"targets":{"bags":{"export":{"numericalParity":true}}}}')
  self.assertEqual(current_mask_export_plan(),{})
 def test_external_plan_cannot_enter_acceptance(self):
  external=self.out/'external.json';external.write_text('{}');self.index.write_text(json.dumps(dict(planPath=str(external),planSHA256=sha(external),selectionSHA256=sha(self.selection))))
  with self.assertRaisesRegex(ValueError,'EXPORT_PLAN_PATH_ESCAPE'):current_mask_export_plan()

if __name__=='__main__':unittest.main()

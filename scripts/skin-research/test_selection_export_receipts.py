"""Stale or altered export evidence cannot qualify a newly selected model."""
import json,tempfile,unittest
from pathlib import Path
from unittest.mock import patch
from update_acceptance_progress import current_mask_export_plan,sha
from export_selected_full_masks import reusable_receipt


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

class ExportReuseTests(unittest.TestCase):
 def setUp(self):
  self.temp=tempfile.TemporaryDirectory();self.out=Path(self.temp.name);self.d=self.out/'interim-diagnosis'/'old';self.d.mkdir(parents=True)
  self.model=self.d/'model.onnx';self.model.write_bytes(b'unit-test export bytes')
  self.protocol=dict(dataSHA256='data',adapterSHA256='adapter',contract={'inputSize':256},threshold=.5,atol=.003,rtol=.0001)
  self.pp=self.d/'protocol.json';self.pp.write_text(json.dumps(self.protocol))
  self.record=dict(onnxPath=str(self.model),weightsSHA256='full-model',modelSHA256=sha(self.model),protocolSHA256=sha(self.pp),checks=[dict(target='bags',positive=p) for p in [True,False]])
  self.patcher=patch('export_selected_full_masks.OUT',self.out);self.patcher.start()
 def tearDown(self):self.patcher.stop();self.temp.cleanup()
 def test_same_full_weights_and_contract_reuse(self):
  self.assertTrue(reusable_receipt(self.record,self.protocol,'full-model',['bags']))
 def test_different_weights_cannot_reuse(self):
  self.assertFalse(reusable_receipt(self.record,self.protocol,'new-full-model',['bags']))
 def test_changed_preprocessing_cannot_reuse(self):
  protocol={**self.protocol,'contract':{'inputSize':128}}
  self.assertFalse(reusable_receipt(self.record,protocol,'full-model',['bags']))
 def test_missing_negative_source_check_cannot_reuse(self):
  self.record['checks']=self.record['checks'][:1]
  self.assertFalse(reusable_receipt(self.record,self.protocol,'full-model',['bags']))

if __name__=='__main__':unittest.main()

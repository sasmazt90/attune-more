"""Research boundary/math checks only, never simulated clinical acceptance."""
import importlib.util,json,sys
from pathlib import Path
import numpy as np
ROOT=Path(__file__).resolve().parents[2]

def load(name):
 spec=importlib.util.spec_from_file_location(name,ROOT/'scripts/skin-research'/f'{name}.py');module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module);return module

def test_expert_label_does_not_use_self_report():
 fn=load('prepare_scin').labels_for
 row={'related_category':'ACNE','dermatologist_skin_condition_on_label_name':"['Eczema']",'dermatologist_skin_condition_confidence':'[4]','dermatologist_gradable_for_skin_condition_1':'DEFAULT_YES_IMAGE_QUALITY_SUFFICIENT'}
 assert fn(row)==(True,0)
 assert fn({**row,'dermatologist_skin_condition_on_label_name':"['Acne']",'dermatologist_skin_condition_confidence':'[2]'})==(True,None)
 assert fn({**row,'dermatologist_skin_condition_on_label_name':"['Acne']"})==(True,1)
 assert fn({**row,'dermatologist_skin_condition_on_label_name':"['Rosacea']"})==(True,None)

def test_probability_metrics_calibration_and_ties():
 fn=load('train_acne').binary_metrics
 m=fn([0,0,1,1],[.1,.8,.7,.4],.5)
 assert (m['tp'],m['fp'],m['fn'],m['tn'])==(1,1,1,1)
 assert m['precision']==m['recall']==m['F1']==.5 and m['AUC']==.5
 assert abs(m['Brier']-.275)<1e-10 and abs(m['ECE']-.45)<1e-10
 assert 0<m['recallWilsonLower']<.5
 assert fn([0,1],[.5,.5],.5)['AUC']==.5

def test_empty_and_invalid_expert_rights_are_rejected():
 fn=load('prepare_annotations').validate;protocol=json.loads((ROOT/'docs/skin-research/annotation-protocol.json').read_text())
 assert fn([],'dry',protocol)==([],[])
 for target in ['dry','sag']:
  rows=[{'target':target,'region':'chin','pose':'FRONT','visibility':'gradable','groundTruthSource':'machine-generated','synthetic':True}, {'target':target,'region':'chin','pose':'FRONT','visibility':'gradable','groundTruthSource':'independent-human-experts','expertGrades':[1,1],'expertReviewerIds':['same','same'],'consensusGrade':1}]
  accepted,rejected=fn(rows,target,protocol);assert accepted==[] and len(rejected)==2

def test_acceptance_is_explicit_and_closed():
 criteria=json.loads((ROOT/'scripts/skin-research/acceptance.json').read_text())
 assert criteria['preregisteredBeforeTraining'] and criteria['minIndependentTestCasesEachClass']==50
 assert criteria['minPrecision']==criteria['minRecall']==criteria['minF1']==.8
 assert 'closed' in criteria['deploymentDefault']

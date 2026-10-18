"""Read-only AG review and bounded replay of selected production functions.
No bulk cherry-pick, AG writes, external weight access or training.
"""
import importlib.util,json,sys,subprocess,os
from pathlib import Path
from expanded_sources import ROOT,OUT,sha,write
sys.path.insert(0,str(ROOT/'services/core-api'));sys.path.insert(0,str(ROOT/'.runtime/python-packages'))
import appearance_analysis as A
import cv2

def main():
 cv2.setNumThreads(1);ag=ROOT.parent/'attune-antigravity-skin';d=OUT/'interim-diagnosis';checks={};evidence={}
 for name in ['dry-empirical-comparison.json','sag-calibrated-true-results.json']:
  receipt=json.loads((ag/'audit-results'/name).read_text());evidence[name]=receipt
  for k,v in receipt['executionMetadata']['codeSHA256'].items():
   file=ag/('scripts' if k.startswith('run_') else 'services/core-api')/k;checks[name+':'+k]=sha(file)==v
 assert all(checks.values()),'AG_EVIDENCE_CODE_DRIFT'
 spec=importlib.util.spec_from_file_location('ag_dry_review',ag/'scripts/run_dry_evaluation.py');module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
 patch=module.evaluate_patches();assert patch['datasetFiles']==evidence['dry-empirical-comparison.json']['patchLevelBenchmark']['datasetFiles']
 assert patch['productionAnalytic']['confusionMatrix']==[[17,2],[1,6]]
 full=module.evaluate_full_photos()
 # Execute the unchanged committed finite sag benchmark in THIS checkout,
 # with production module already resolved to A and an explicit local output.
 code=(ag/'scripts/run_sag_evaluation.py').read_text();code=code.replace("out_file = Path('audit-results/sag-calibrated-true-results.json')","out_file = Path("+repr(str(d/'ag-sag-production-replay.json'))+")")
 code=code.replace("compute_file_sha256('services/core-api/instant_appearance.py')","compute_file_sha256("+repr(str(ROOT/'services/core-api/instant_appearance.py'))+")").replace("compute_file_sha256('services/core-api/appearance_analysis.py')","compute_file_sha256("+repr(str(ROOT/'services/core-api/appearance_analysis.py'))+")")
 runtime=d/'ag-sag-readonly-replay.py';runtime.write_text(code,'utf8');previous=Path.cwd()
 try:os.chdir(ag);exec(compile(code,str(runtime),'exec'),{'__name__':'__main__','__file__':str(runtime)})
 finally:os.chdir(previous)
 sag=json.loads((d/'ag-sag-production-replay.json').read_text());r57=next(r for r in sag['rows'] if r['index']==57);assert r57['declaredLabel']=='positive' and r57['sag_overview']==0
 negatives=[r for r in sag['rows'] if r['declaredLabel']=='negative' and r['quality']=='valid'];positive=[r for r in sag['rows'] if r['declaredLabel']=='positive'];summary=dict(positiveControls=len(positive),positiveNonzero=sum(r['sag_overview'] is not None and r['sag_overview']>0 for r in positive),measuredNegativeControls=len(negatives),negativeIntegerNonzero=sum(r['sag_overview']>=.5 for r in negatives),photo57StillMissed=True,photo57NotRelabelled=True,expertClinicalLabels=False)
 write('interim-diagnosis/ag-selected-delivery-review.json',dict(commit='f4ded9f1024f5f8a48e0411ba1a1075c52cc9374',committedEvidenceHashes=checks,productionCodeSHA256=sha(ROOT/'services/core-api/appearance_analysis.py'),instantCodeSHA256=sha(ROOT/'services/core-api/instant_appearance.py'),dryPatchBenchmark=patch,dryFullPhotoReplay=full,sagSummary=summary,integratedPieces=['six-return shared dryness function and same-production benchmark contract','versioned lower-face fold appearance v6 only'],notIntegrated=['skin type adapter/config/model','whole AG package'],skinTypeAccessPending=True,AGWorktreeModified=False,userRecordsRescaled=False,newLongTraining=False,clinicalReadiness=False))
 print('AG SELECTED REVIEW',patch['productionAnalytic']['confusionMatrix'],summary,flush=True)
if __name__=='__main__':main()

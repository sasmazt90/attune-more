"""Preregister exactly two methods before opening their predictions. No fit."""
import ast,hashlib,importlib.metadata,json,subprocess
from pathlib import Path
from acne_lab_dog import VERSION,CONFIG
ROOT=Path(__file__).resolve().parents[2]
OUT=ROOT/'audit-results/acne-classical-comparison-20261015'
BASE=ROOT/'audit-results/acne-takeover-20261015'
def read(p):return json.loads(p.read_text('utf8'))
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def a_identity():
 path=ROOT/'services/core-api/appearance_analysis.py';source=path.read_text('utf8');tree=ast.parse(source);node=next(v for v in tree.body if isinstance(v,ast.FunctionDef) and v.name=='acne_candidates')
 return dict(path=str(path.relative_to(ROOT)),sourceSHA256=sha(path),functionSHA256=hashlib.sha256(ast.get_source_segment(source,node).encode()).hexdigest(),config='unmodified original call, face-analysis320, original overall support; shared current ROI ownership after detection')
def main():
 OUT.mkdir(exist_ok=True);target=OUT/'preregistered-manifest.json'
 if target.exists():raise RuntimeError('MANIFEST_ALREADY_FROZEN')
 pre=read(BASE/'browser-preflight.json');original=read(BASE/'inputs/original-reviewed-detector-data.json');bysha={r['sha256']:r for r in original['rows']}
 evaluation=read(BASE/'evaluation-step0/summary.json');evalby={r['sha256']:r for r in evaluation['rows']};rows=[]
 for a in pre['rows']:
  if a['cohort'] not in ['scope-B-development','heldout-train'] or a['sha256'] not in evalby:continue
  r=bysha[a['sha256']];snapshot=BASE/'product-inputs'/a['sha256']/'snapshot.png'
  rows.append(dict(sha256=a['sha256'],group=r['group'],source=r['source'],sourcePath=r['absolutePath'],sourceFileSHA256=sha(Path(r['absolutePath'])),snapshotSHA256=sha(snapshot) if snapshot.exists() else None,role='exposed-development-regression',cohort=a['cohort'],split=r['split'],staticProductPass=evalby[a['sha256']]['fullStaticProductPass'],rights=dict(publisherDeclaration=r.get('reviewDecision',{}).get('rightsBasis',r.get('rights')),individualConsent='not-recorded',independentIndividualRights='unverified',use='local private engineering only; no redistribution or product admission'),annotationSHA256=hashlib.sha256(json.dumps(r.get('annotations',[]),sort_keys=True).encode()).hexdigest()))
 inputs=['browser-preflight.json','inputs/original-reviewed-detector-data.json','inputs/annotation-scope-manifest.json','inputs/controlled_train_cohort.json']
 manifest=dict(version='acne-classical-ab-preregistered-v1',head=subprocess.check_output(['git','rev-parse','HEAD'],cwd=ROOT,text=True).strip(),A=a_identity(),B=dict(version=VERSION,config=CONFIG,implementationSHA256=sha(Path(__file__).with_name('acne_lab_dog.py'))),calibration=dict(fits=0,parameterChoices=1,selection='single a-priori config; no result-based calibration or TRAIN/validation mining'),inputs={n:sha(BASE/n) for n in inputs},priorProductEvaluationSHA256=sha(BASE/'evaluation-step0/summary.json'),geometrySourceHashes=pre['sourceHashes'],rows=rows,scope=dict(fixedScopeBTargets=14,visibility='same current triangle-union, exclusion, hair/exposure and native source-crop; center visibility separately reported',originalPimpleOnly=True,pseudo401='UNKNOWN; unused',unknownOutsideBoxes=True,personIndependent=False,independentTest=False,appearanceSubtypeLabels='absent; red/pale truth cannot be inferred from detector',physicalRepeatCapture=False,multiframe='one snapshot per pose; no N/K or summed-pose count'),metrics=dict(primary='greedy source-box IoU>=.50 one-to-one',secondary='candidate center inside source box; not pixel segmentation',negatives='center in explicit reviewed negative intersect current eligible ROI; >=80% box area separately',sizeBands='max source-box side: micro<8,small<16,medium>=16',timing='fresh subprocess per method: decode, production preprocessing/geometry, detector, component-map, JSON; repeat same file; frontend capture/MediaPipe excluded'),decision=dict(positive='source recall increases with no reviewed-negative FP increase; or recall maintained and FP reduced',guard='no scope-B/visible/heldout regression; at least two positive-source gains for recall-increase admission',admission='rights-cleared camera-domain evidence and same-list API/UI/history verification also required',stop='no gain -> no new method, fit, threshold search or activation'),dependencies={p:importlib.metadata.version(p) for p in ['numpy','opencv-python','scikit-image']},weights='none for A/B; existing MediaPipe identity frozen in preflight; no new weights')
 target.write_text(json.dumps(manifest,indent=2,ensure_ascii=False),'utf8');print(json.dumps(dict(manifest=str(target),sha256=sha(target),photos=len(rows),A=manifest['A']['functionSHA256'],B=VERSION)))
if __name__=='__main__':main()
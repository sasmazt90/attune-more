"""Replay five already reviewed eye/lash/nostril/lip/clothing source boxes."""
import base64,json,sys,subprocess,shutil
from pathlib import Path
import cv2
from expanded_sources import ROOT,OUT,sha,write
sys.path.insert(0,str(ROOT/'services/core-api'))
import appearance_analysis as A

def main():
 cv2.setNumThreads(1);d=OUT/'interim-diagnosis';chain=json.loads((d/'yolo-chain.json').read_text());landmarks=json.loads((d/'positive-product-chain.json').read_text())['rows'];reviews=json.loads((d/'visual-review.json').read_text())['rows'];results=[];saved=A.infer_acne
 try:
  for old in landmarks:
   idx=old['sourceIndex'];source=chain['sources'][idx];src=source['source'];im=cv2.imread(src['absolutePath']);assert sha(Path(src['absolutePath']))==src['sha256'];points=old['realDerivedLandmarks'];boxes=source['finalBoxes'];A.infer_acne=lambda *args:dict(valid=True,boxes=boxes,modelVersion='isolated-saved-source-exclusion-replay',modelHash=old['modelSHA256'],tileCount=0,loadMs=0,inferenceMs=0)
   mesh=json.loads(subprocess.check_output([shutil.which('node'),str(ROOT/'scripts/skin-research/focused_meshes.cjs')],input=json.dumps([dict(sha256=src['sha256'],landmarks=points,width=im.shape[1],height=im.shape[0])]).encode(),cwd=ROOT))[0]['meshes'];_,encoded=cv2.imencode('.png',im);photo='data:image/png;base64,'+base64.b64encode(encoded).decode();_,capture=A.decode_photo(photo)
   result=A.analyze_skin(dict(photo=photo,photoId=capture,pose='FRONT',landmarks=points,meshes=mesh,exclusions=[],qualityValid=True,conditions={}));accepted=[b for rs in result['measurements'].values() for r in rs if r['id']=='acne' for b in r['components']['bounds']]
   for review in reviews:
    if review['sourceIndex']!=idx or review['visualCategory']!='off_task':continue
    box=boxes[review['index']];kept=any(abs(b['x']-box[0])+abs(b['y']-box[1])+abs(b['width']-(box[2]-box[0]))+abs(b['height']-(box[3]-box[1]))<.01 for b in accepted)
    results.append(dict(sourceSHA256=src['sha256'],box=box,observation=review['observation'],survived=kept))
 finally:A.infer_acne=saved
 write('interim-diagnosis/detector-exclusion-verification.json',dict(rows=results,reviewedOffTaskBoxes=len(results),rejected=sum(not r['survived'] for r in results),remainingOffTaskBoxes=sum(r['survived'] for r in results),allOffTaskRejected=not any(r['survived'] for r in results),codeSHA256=sha(ROOT/'services/core-api/appearance_analysis.py'),normalAPIInstalled=False,unknownBoxesNotRelabelled=True));print('OFF TASK REPLAY',results,flush=True)
if __name__=='__main__':main()

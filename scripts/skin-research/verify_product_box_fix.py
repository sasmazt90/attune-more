"""Replay immutable real development detections through the production filter.
No new inference/training and no accepted-model registry change.
"""
import base64,json,sys,subprocess,shutil
from pathlib import Path
import cv2,numpy as np
from expanded_sources import ROOT,OUT,sha,write
from complete_saved_diagnosis import match
sys.path.insert(0,str(ROOT/'services/core-api'))
import appearance_analysis as A

def main():
 cv2.setNumThreads(1);d=OUT/'interim-diagnosis';saved=json.loads((d/'front-filter-control.json').read_text())['rows'];sources={r['sha256']:r for r in json.loads((OUT/'negative-expanded-detector-data.json').read_text())['rows']};results=[]
 original=A.infer_acne
 try:
  for old in saved:
   src=sources[old['sha256']];assert sha(Path(src['absolutePath']))==src['sha256'];im=cv2.imread(src['absolutePath']);points=old['landmarks'];boxes=[r['box'] for r in old['decoder']['rows']]
   A.infer_acne=lambda *args:dict(valid=True,boxes=boxes,modelVersion='isolated-saved-development-replay',modelHash=old['modelSHA256'],tileCount=0,loadMs=0,inferenceMs=0)
   meshes=json.loads(subprocess.check_output([shutil.which('node'),str(ROOT/'scripts/skin-research/focused_meshes.cjs')],input=json.dumps([dict(sha256=src['sha256'],landmarks=points,width=im.shape[1],height=im.shape[0])]).encode(),cwd=ROOT))[0]['meshes']
   _,encoded=cv2.imencode('.png',im);photo='data:image/png;base64,'+base64.b64encode(encoded).decode();_,capture=A.decode_photo(photo)
   result=A.analyze_skin(dict(photo=photo,photoId=capture,pose='FRONT',landmarks=points,meshes=meshes,exclusions=[],qualityValid=True,conditions={}))
   rows=[r for rs in result['measurements'].values() for r in rs if r['id']=='acne'];final=[b for r in rows for b in r['components']['bounds']];overview=next(r for r in result['general']['measurements'] if r['id']=='acne')
   assert len({b['candidateId'] for b in final})==len(final)==overview['components']['candidateCount']
   assert {b['candidateId'] for b in final}=={b['candidateId'] for b in overview['components']['bounds']}
   assert all(r['value']==r['components']['candidateBoxCoveragePercent'] for r in rows if r['quality']=='valid')
   assert overview['localMap'] and 'overview:acne' in result['maps']
   after=match([[b['x'],b['y'],b['x']+b['width'],b['y']+b['height'],b['confidence']] for b in final],old['sourceLabels'])
   # Reconstruct old/new clipping at matched real source lesions, plus inspectable crop.
   saturation=[]
   for r in old['decoder']['rows']:
    if r['category']!='matched_source_box':continue
    bx,by,ex,ey,_=r['box'];crop=im[max(0,int(by)):int(np.ceil(ey)),max(0,int(bx)):int(np.ceil(ex))];rgb=crop[:,:,::-1]/255
    path=d/f"filter-fix-{src['sha256'][:12]}-truth{r['matchedTruth']}.png";cv2.imwrite(str(path),crop)
    saturation.append(dict(truth=r['matchedTruth'],oldMaxChannelClipped=float((rgb.max(2)>.975).mean()),allChannelLost=float((rgb.min(2)>.975).mean()),crop=str(path),cropSHA256=sha(path)))
   results.append(dict(sourceSHA256=src['sha256'],sourcePath=src['absolutePath'],aligned=old['alignment']['isAligned'],before=old['afterProductFilter'],decoder=old['decoder'],after=after,overview=overview,regions=rows,mapKeys=sorted(k for k in result['maps'] if k.endswith(':acne')),realClipping=saturation,normalModelInstalled=False))
   print('FILTER REAL REPLAY',src['sha256'][:12],len(old['decoder']['matchedTruth']),len(old['afterProductFilter']['matchedTruth']),len(after['matchedTruth']),flush=True)
 finally:A.infer_acne=original
 write('interim-diagnosis/product-box-fix-verification.json',dict(rows=results,codeSHA256=sha(ROOT/'services/core-api/appearance_analysis.py'),supportSHA256=sha(ROOT/'services/core-api/acne_box_support.py'),noNewTrainingOrInference=True,confidenceThresholdUnchanged=True,unknownNotNegative=True,productionRegistryUnchanged=True))
if __name__=='__main__':main()

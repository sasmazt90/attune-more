"""Natural partial-forehead signal review. Real pixels and actual production
filter statements, manually declared skin ROI; never fake facial landmarks or
claim complete capture/history/whole-face acceptance.
"""
from pathlib import Path
import ast, json, hashlib, sys
import cv2, numpy as np
ROOT=Path(__file__).resolve().parents[2];sys.path.insert(0,str(ROOT/'services/core-api'))
import appearance_analysis as A
OUT=ROOT/'audit-results/all-health-20261010/natural-partial';OUT.mkdir(parents=True,exist_ok=True)
source=ROOT/'audit-results/all-health-20261010/natural-confounders/0.jpg'
image=cv2.imread(str(source));assert image.shape[:2]==(1932,2576)
mask=np.zeros(image.shape[:2],np.uint8)
# Visible forehead skin, above the eyebrow/eye boundary. Declared engineering
# ROI only; this is not the automatic anatomical mask or a diagnostic label.
cv2.fillPoly(mask,[np.array([[650,380],[2050,380],[2280,950],[1760,1230],[1300,1280],[600,920]],np.int32)],255)
node=next(n for n in ast.parse((ROOT/'services/core-api/appearance_analysis.py').read_text('utf8')).body if isinstance(n,ast.FunctionDef) and n.name=='analyze_skin')
start=next(i for i,n in enumerate(node.body) if isinstance(n,ast.Assign) and any(isinstance(t,ast.Name) and t.id=='gray8' for t in n.targets))
end=next(i for i,n in enumerate(node.body) if isinstance(n,ast.Assign) and any(isinstance(t,ast.Name) and t.id=='masks' for t in n.targets))
ns={**vars(A),'image':image};exec(compile(ast.fix_missing_locations(ast.Module(body=node.body[start:end],type_ignores=[])),'production-filter-statements','exec'),ns)
shine=ns['shine']* (A.oiliness_map(image,{'forehead':mask})>0)
valid=(mask>0)&~ns['hair']&~ns['clipping']&(ns['gray']>.12)
clipped=float(np.mean(ns['clipping'][mask>0]));value=float(np.mean(shine[valid]>.12)*100)
dark=cv2.dilate((cv2.morphologyEx(ns['gray8'],cv2.MORPH_BLACKHAT,np.ones((7,7),np.uint8))>35).astype(np.uint8),np.ones((7,7),np.uint8))>0
flakes=A.eligible_flake_components(ns['flakes'],valid&~dark)
overlay=image.copy();overlay[(shine>.12)&valid]=(0,190,240)
cv2.imwrite(str(OUT/'natural-forehead-highlight.png'),overlay)
cv2.imwrite(str(OUT/'declared-skin-roi.png'),mask)
proof=dict(buildId=(ROOT/'apps/vehicle-app/.next/BUILD_ID').read_text().strip(),sourceSHA256=hashlib.sha256(source.read_bytes()).hexdigest(),sourceLicense='CC BY-SA4.0',attribution='Roshu Bangal',sourceURL='https://commons.wikimedia.org/wiki/File:Acne_vulgaris_on_a_very_oily_skin.jpg',partialNaturalSource=True,manualEngineeringSkinROI=True,fakeLandmarks=False,automaticWholeFaceAcceptance=False,clinicalLabelAdopted=False,sourceResolution=[2576,1932],oilPercentVisibleHighlight=value,clippedFraction=clipped,dryCandidateAreaPercent=float(np.mean(flakes[valid]>.04)*100),scope='actual unchanged production signal code, natural partial forehead only; not automatic gates/card/history acceptance')
(OUT/'proof.json').write_text(json.dumps(proof,indent=2),'utf8');print(json.dumps(proof),flush=True)

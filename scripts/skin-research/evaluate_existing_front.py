"""Current method on existing licensed NASA front pixels and recorded landmarks.
Front-only engineering sensitivity, NOT new physical or three-pose acceptance.
Uses the current unchanged anatomical graph. No images or labels are generated.
"""
import hashlib,json,subprocess,shutil,sys
from pathlib import Path
import numpy as np
from PIL import Image
ROOT=Path(__file__).resolve().parents[2]
NODE=r'''
const fs=require('fs'),ts=require('typescript'),Module=require('module'),m=new Module('mesh',module);m.paths=module.paths;m._compile(ts.transpileModule(fs.readFileSync('apps/vehicle-app/src/utils/skinMesh.ts','utf8'),{compilerOptions:{module:ts.ModuleKind.CommonJS,target:ts.ScriptTarget.ES2022}}).outputText,'mesh');
const v=JSON.parse(fs.readFileSync(0,'utf8')),S=m.exports;process.stdout.write(JSON.stringify(Object.fromEntries(['forehead','nose','chin','rightCheek','leftCheek'].map(id=>[id,S.supportedSkinMesh(S.buildSkinMesh(id,v.landmarks,v.width,v.height),v.landmarks,v.width,v.height)]))));
'''
for label,kind in [('digital-front','digital-detail'),('film-front','high-detail')]:
 original=ROOT/'audit-results/user-followup-20261005'/kind/'accepted-original-1-0.png'
 saved=ROOT/'audit-results/remediation-20261005/comparison'
 alignment=json.loads((saved/(label+'-landmarks.json')).read_text());meta=json.loads((saved/(label+'-snapshot.json')).read_text())
 im=np.array(Image.open(original).convert('RGBA'));height,width=im.shape[:2]
 result=subprocess.run(['node','-e',NODE],cwd=ROOT,input=json.dumps({'landmarks':alignment['landmarks'],'width':width,'height':height}),text=True,capture_output=True,encoding='utf8',check=True);meshes=json.loads(result.stdout)
 # One source per call bounds memory even for 1920x2160 native pixels.
 for region in ['forehead','nose','chin','rightCheek','leftCheek']:
  dest=ROOT/'audit-results/skin-capabilities-20261008/front-research'/label/region;dest.mkdir(parents=True,exist_ok=True)
  name='source-front-'+region;shutil.copyfile(original,dest/(name+'.png'))
  (dest/(name+'.json')).write_text(json.dumps({'width':width,'height':height,'pose':'FRONT','meshes':meshes,'exclusions':meta['exclusions'],'qualityValid':True,'region':region,'photoId':hashlib.sha256(im.tobytes()).hexdigest(),'provenance':'existing licensed NASA front source; recorded model landmarks; current mesh code; not physical acceptance'}),'utf8')
  subprocess.run([sys.executable,str(Path(__file__).parent/'evaluate_surface.py'),'--captures',str(dest.relative_to(ROOT)),'--out',str((dest/'evaluation').relative_to(ROOT))],cwd=ROOT,check=True)

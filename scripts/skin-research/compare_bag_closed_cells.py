"""Same captured browser payload, same source RGB, additive eye-cell support."""
import json,sys,subprocess,copy,hashlib
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2];sys.path.insert(0,str(ROOT/'scripts'))
import evaluate_periorbital_and_acne_comparative as audit
import appearance_analysis as A
OUT=ROOT/'audit-results/bag-label-followup-20261012';OUT.mkdir(parents=True,exist_ok=True)
rows=[]
for prefix in audit.PREFIXES:
 old=json.loads((audit.OUT/(prefix+'-browser-api.json')).read_text('utf8'));p=copy.deepcopy(old['productPayload']);mesh=p['meshes']['periorbital']
 code="require('./tests/unit/ts_loader.js');const fs=require('fs'),M=require('./apps/vehicle-app/src/utils/skinMesh.ts'),p=JSON.parse(fs.readFileSync(0,'utf8'));console.log(JSON.stringify(M.supportedSkinMesh(M.buildSkinMesh('periorbital',p.landmarks,p.width,p.height),p.landmarks,p.width,p.height)));"
 r=subprocess.run(['node','-e',code],cwd=ROOT,input=json.dumps(dict(landmarks=p['landmarks'],width=old['response']['sourceWidth'],height=old['response']['sourceHeight'])),capture_output=True,text=True,encoding='utf8',check=True)
 new_mesh=json.loads(r.stdout);preserved={k:new_mesh[k]==mesh[k] for k in mesh};assert all(preserved.values()),(prefix,preserved)
 p['meshes']['periorbital']=new_mesh;actual=A.analyze_skin(p);pairs={};untouched=[]
 for region,values in actual['measurements'].items():
  for value in values:
   before=next(v for v in old['response']['measurements'][region] if v['id']==value['id']);key=region+':'+value['id']
   if value['id']=='bags':pairs[region]=dict(before=before['value'],after=value['value'],beforeReason=before['limitationCode'],afterReason=value['limitationCode'],samplingVersion=value['components'].get('samplingSupportVersion'))
   else:
    match=value==before and actual['maps'].get(key)==old['response']['maps'].get(key);assert match,(prefix,key);untouched.append(dict(key=key,exactMatch=match))
 (OUT/(prefix+'-v2-payload.json')).write_text(json.dumps(p,ensure_ascii=False,indent=2),'utf8');(OUT/(prefix+'-v2-offline.json')).write_text(json.dumps(actual,ensure_ascii=False,indent=2),'utf8')
 row=dict(source=prefix,meshOriginalFieldsMatch=preserved,bagCellCount=len(new_mesh.get('bagCells',[])),pairs=pairs,nonBagPreservation=untouched);rows.append(row);print(json.dumps(dict(source=prefix,bags=pairs['periorbital'],nonBagPreserved=sum(v['exactMatch'] for v in untouched))),flush=True)
(OUT/'same-input-comparison.json').write_text(json.dumps(rows,ensure_ascii=False,indent=2),'utf8')

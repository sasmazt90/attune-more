import json,sys,importlib.util,hashlib
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2];sys.path.insert(0,str(ROOT/"scripts"))
import evaluate_periorbital_and_acne_comparative
import appearance_analysis as A
def preservation():
 # Nine previous lines/bags inputs, frozen source code instead of stale metrics.
 frozen=ROOT/'.runtime/dry-sag-native-baseline-20261013';saved={n:sys.modules[n] for n in ('instant_appearance','skin_general')}
 def load(n,path):
  spec=importlib.util.spec_from_file_location(n,path);m=importlib.util.module_from_spec(spec);sys.modules[n]=m;spec.loader.exec_module(m);return m
 load('instant_appearance',frozen/'instant_appearance.py');load('skin_general',frozen/'skin_general.py');B=load('frozen_appearance',frozen/'appearance_analysis.py')
 sys.modules.update(saved);proof=[]
 files=[*(ROOT/'audit-results/lines-bags-followup-20261012').glob('*-payload.json'),*(ROOT/'audit-results/bag-label-followup-20261012').glob('*-v2-payload.json')]
 seen=set()
 for f in files:
  digest=hashlib.sha256(f.read_bytes()).hexdigest()
  if digest in seen:continue
  seen.add(digest)
  p=json.loads(f.read_text('utf8'));old=B.analyze_skin(p);new=A.analyze_skin(p);count=0
  for region,items in new['measurements'].items():
   for item in items:
    if item['id'] in ('dry','sag'):continue
    assert item==next(v for v in old['measurements'][region] if v['id']==item['id']),(f.name,region,item['id']);count+=1
  old_maps={k:v for k,v in old['maps'].items() if k.split(':')[-1] not in ('dry','sag')};new_maps={k:v for k,v in new['maps'].items() if k.split(':')[-1] not in ('dry','sag')};same=old_maps==new_maps;assert same,f.name
  before_general=[v for v in old['general']['measurements'] if v['id'] not in ('dry','sag')];after_general=[v for v in new['general']['measurements'] if v['id'] not in ('dry','sag')];general_same=before_general==after_general;assert general_same,f.name
  proof.append(dict(input=f.name,payloadSHA256=digest,preservedRegionalMeasurements=count,preservedGeneralMeasurements=len(after_general),unrelatedGeneralEqual=general_same,unrelatedMapsEqual=same))
 return proof
if __name__=="__main__":
 proof=preservation();out=ROOT/"audit-results/dry-sag-native-followup-20261013/previous-input-preservation.json";out.write_text(json.dumps(proof,indent=2),"utf8");print(json.dumps({"sources":len(proof),"preservedMeasurements":sum(p["preservedRegionalMeasurements"]+p["preservedGeneralMeasurements"] for p in proof),"allMapsEqual":all(p["unrelatedMapsEqual"] for p in proof)}))

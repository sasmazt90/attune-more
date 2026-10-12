"""Freeze the detector winner from separate curves with identical validation data."""
import json
from pathlib import Path
from expanded_sources import OUT,sha,write

def read(p):return json.loads(p.read_text('utf8'))
def main():
 old=OUT/'negative-yolox';new=OUT/'corrected-scope-yolox-v2';assert read(new/'selection.json')['trainingComplete']
 p0=read(old/'protocol.json');p1=read(new/'protocol.json');data=OUT/'negative-expanded-detector-data.json'
 assert p0['dataSHA256']==p1['dataSHA256']==sha(data),'VALIDATION_DATA_IDENTITY_CHANGED'
 state=read(old/(old/'CURRENT').read_text('utf8').strip()/'state.json');best=max(state['history'],key=lambda r:r['validation']['F1'])
 digest=sha(old/'selected.safetensors');matches=[]
 for f in old.glob('checkpoint-*/state.json'):
  s=read(f)
  if s['modelSHA256']==digest and s['epoch']==best['epoch'] and (f.parent/'model.safetensors').exists():matches.append(f.parent)
 assert matches,'SELECTED_FULL_CHECKPOINT_MISSING'
 folder=sorted(matches)[0];assert sha(folder/'model.safetensors')==digest
 legacy=dict(phase=old.name,metrics=best['validation'],model=dict(folder=str(folder),sha256=digest,epoch=best['epoch']),protocolSHA256=sha(old/'protocol.json'))
 ref=read(new/'target-best-checkpoints.json')['acne'];folder=new/ref['checkpoint'];s=read(folder/'state.json')
 assert s['identity']==sha(new/'protocol.json') and sha(folder/'model.safetensors')==ref['modelSHA256']
 current=dict(phase=new.name,metrics=ref['metrics'],model=dict(folder=str(folder),sha256=ref['modelSHA256'],epoch=s['epoch']),protocolSHA256=sha(new/'protocol.json'))
 for choice in [legacy,current]:
  assert choice['metrics']['threshold']==p1['selection']['threshold']==.7 and choice['metrics']['images']==43 and choice['metrics']['sourceGroups']==43
  assert choice['metrics']['unlabelledAreasKnownHealthy'] is False
 winner=max([legacy,current],key=lambda r:r['metrics']['F1'])
 write('interim-diagnosis/frozen-detector-selection.json',dict(selected=winner,comparisons=[legacy,current],validationDataSHA256=sha(data),matchingIoU=.5,oldAndNewLearningCurvesMerged=False,weightsMixed=False,newestNotPreferred=True,productionInstalled=False,finalOpened=False))
 print('FROZEN DETECTOR FULL MODEL',winner['phase'],winner['metrics']['F1'],winner['model']['sha256'])
if __name__=='__main__':main()

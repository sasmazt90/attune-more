"""Compare full checkpoints across separately recorded corrected phases.
Never silently merges learning curves or promotes a model.
"""
import json
from pathlib import Path
from expanded_sources import OUT,sha,write
from mask_scope_metrics import RULE
from selected_sources import TARGETS

def read(p):return json.loads(p.read_text('utf8'))
def main():
 baseline=read(OUT/'interim-diagnosis/scope-v4/selection.json');folder=OUT/'corrected-scope-mask-v4';protocol=read(folder/'protocol.json');assert protocol['dataSHA256']==sha(OUT/'scope-v4-mask-data.json') and protocol['selection']==RULE
 refs=read(folder/'target-best-checkpoints.json') if (folder/'target-best-checkpoints.json').exists() else {};targets={}
 for t in TARGETS:
  old=baseline['targets'][t];choices=[]
  if old['metrics'] and old['metrics']['rankingUsable']:choices.append(dict(phase='preserved-baseline-re-evaluation-v4',model=old['selectedFullModel'],metrics=old['metrics']))
  if t in refs:
   r=refs[t];state=read(folder/r['checkpoint']/'state.json');assert state['identity']==sha(folder/'protocol.json');choices.append(dict(phase=folder.name,model=dict(folder=str(folder/r['checkpoint']),sha256=r['modelSHA256'],epoch=state['epoch'],cursor=state['cursor'],step=state['step']),metrics=r['metrics']))
  for r in choices:assert sha(Path(r['model']['folder'])/'model.safetensors')==r['model']['sha256']
  best=max(choices,key=lambda r:r['metrics']['developmentScore'],default=None);targets[t]=dict(selectedFullModel=best['model'] if best else None,metrics=best['metrics'] if best else None,channel=TARGETS.index(t),phase=best['phase'] if best else None,comparisons=[dict(phase=r['phase'],model=r['model'],developmentScore=r['metrics']['developmentScore']) for r in choices],weightsMixed=False,productAccepted=False)
 write('interim-diagnosis/corrected-selection-v4.json',dict(targets=targets,selectionRule=RULE,allSuitableValidationRecordsCovered=True,dataSHA256=protocol['dataSHA256'],baselineProtocolSHA256=baseline['protocolSHA256'],newPhaseProtocolSHA256=sha(folder/'protocol.json'),newPhaseComplete=(folder/'selection.json').exists(),oldAndNewLearningCurvesMerged=False,productionInstalled=False,finalOpened=False))
 print('CORRECTED FULL-MODEL SELECTION COMPARED')
if __name__=='__main__':main()

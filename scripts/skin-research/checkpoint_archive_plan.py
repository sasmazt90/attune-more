"""Plan cold checkpoint byte archival while preserving every resume/selection input.

This only lists immutable generations in the two negative phases. Upload and
full cloud-byte verification happen outside this script; it never deletes data.
"""
import hashlib,json,re,sys,time
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2]
OUT=ROOT/'audit-results/skin-expanded-20261011'
PHASES=('negative-yolox','negative-mask-continuation','corrected-scope-yolox-v2','corrected-scope-mask-v4')

def sha(path):
 h=hashlib.sha256()
 with path.open('rb') as f:
  for b in iter(lambda:f.read(4*1024**2),b''):h.update(b)
 return h.hexdigest()

def plan():
 rows=[];protected={};retained=0;blocked=[]
 pending={}
 for receipt in (ROOT/'.runtime/storage-20261011').glob('incomplete-archive-*.json'):
  value=json.loads(receipt.read_text('utf-8-sig'))
  if value.get('localSourceRemoved') is False and value.get('cloudVerificationComplete') is False:pending[(value.get('phase'),value.get('generation'))]=value.get('errorObserved','Incomplete cloud copy; preserve source and do not retry implicitly')
 for phase in PHASES:
  folder=OUT/phase
  if not (folder/'CURRENT').exists():continue
  current=(folder/'CURRENT').read_text('utf8').strip()
  if not re.fullmatch(r'checkpoint-\d{7}-\d{20}',current):raise RuntimeError('CURRENT_PATH_SCOPE_FAILED')
  generations=sorted([p for p in folder.glob('checkpoint-*') if p.is_dir() and re.fullmatch(r'checkpoint-\d{7}-\d{20}',p.name)],key=lambda p:p.name)
  complete=[p for p in generations if all((p/n).exists() for n in ('model.safetensors','optimizer.safetensors','state.json'))]
  keep={current}|{p.name for p in complete[-2:]}
  refs=folder/'target-best-checkpoints.json'
  if refs.exists():keep.update(v['checkpoint'] for v in json.loads(refs.read_text('utf8')).values())
  # Re-evaluation inputs and selected full-model channels are real external
  # readers. Preserve them, including the parent of every corrected phase.
  protocol=OUT/'interim-diagnosis/scope-v2/protocol.json'
  if protocol.exists():
   for ref in json.loads(protocol.read_text('utf8')).get('models',[]):
    path=Path(ref['folder'])
    if path.resolve().parent==folder.resolve():keep.add(path.name)
  for name in ('corrected-scope-yolox-v2','corrected-scope-mask-v4'):
   receipt=OUT/name/'transition.json'
   if receipt.exists() and json.loads((OUT/name/'protocol.json').read_text('utf8'))['parentPhase']==phase:keep.add(json.loads(receipt.read_text('utf8'))['parentCheckpoint'])
  # Selection dependency is proven by actual tensor hash, not metric inference.
  selected=folder/'selected.safetensors'
  selected_sha=sha(selected) if selected.exists() else None
  for p in generations:
   sp=p/'state.json'
   if not sp.exists():keep.add(p.name);continue
   state=json.loads(sp.read_text('utf8'))
   if selected_sha is not None and state['modelSHA256']==selected_sha:keep.add(p.name)
  protected[phase]=sorted(keep)
  for p in generations:
   files=[p/n for n in ('model.safetensors','optimizer.safetensors','state.json')]
   if p.resolve().parent!=folder.resolve() or getattr(p.stat(follow_symlinks=False),'st_file_attributes',0)&0x400:raise RuntimeError('ARCHIVE_REPARSE_OR_PATH_ESCAPE')
   if any(f.exists() and (f.resolve().parent!=p.resolve() or getattr(f.stat(follow_symlinks=False),'st_file_attributes',0)&0x400) for f in files):raise RuntimeError('ARCHIVE_REPARSE_OR_PATH_ESCAPE')
   if p.name in keep:
    retained+=sum(f.stat().st_size for f in files if f.exists());continue
   if (phase,p.name) in pending:
    retained+=sum(f.stat().st_size for f in files if f.exists());blocked.append(dict(phase=phase,generation=p.name,reason=pending[(phase,p.name)],sourcesRetained=True));continue
   if not all(f.exists() for f in files) or (p/'cloud-archive.json').exists():continue
   if any(time.time()-f.stat().st_mtime<300 for f in files):continue
   state=json.loads(files[-1].read_text('utf8'))
   if sha(files[0])!=state['modelSHA256'] or sha(files[1])!=state['optimizerSHA256']:raise RuntimeError('CHECKPOINT_INTEGRITY_FAILED')
   rows.append({'phase':phase,'generation':p.name,'sourceFolder':str(p.resolve()),'files':[{'source':str(f.resolve()),'name':f.name,'bytes':f.stat().st_size,'sha256':sha(f)} for f in files]})
 return {'version':'cold-unreferenced-negative-checkpoint-archive-v1','generatedAt':time.time(),'protected':protected,'protectedLocalCheckpointBytes':retained,'candidates':rows,'blockedArchives':blocked,'allCheckpointStateReceiptsRemainLocal':True,'archiveRequiresFullCloudSHA256':True}
if __name__=='__main__':
 sys.stdout.reconfigure(encoding='utf8');print(json.dumps(plan(),indent=2))

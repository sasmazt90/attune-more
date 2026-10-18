"""Pinned public code/license documents only. No photo collection or paid API."""
import hashlib,json,urllib.request
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2]
FILES=[('skin-scan','afc55f5cb87fcc644f36b472c37083b254bd3fe4','LICENSE','06dcddbb6908a0c6dd4a9e8ec822eea41d5a460a53089fecccc8a68049e99241'),('skin-scan','afc55f5cb87fcc644f36b472c37083b254bd3fe4','src/pipeline/maps/oiliness.py','b80d78c6e0701a70052b3e5a6a5866c4427e9a70a868cf4aa7031dbb8597e814'),('scin','b5a498233ef23b24c2f9fdb41b53e162c6eeb98d','LICENSE','e29f7f0a84f0ad50e4920fa195e852bcd14c9e8b9e6c899ce9e3276be0b75da4')]
def main():
 out=ROOT/'audit-results/skin-capabilities-20261008/sources';proof=[]
 for repo,revision,file,expected in FILES:
  owner='DurtyDhiana' if repo=='skin-scan' else 'google-research-datasets';url=f'https://raw.githubusercontent.com/{owner}/{repo}/{revision}/{file}';path=out/repo/file
  if not path.exists():
   path.parent.mkdir(parents=True,exist_ok=True)
   with urllib.request.urlopen(url,timeout=40) as response:data=response.read(1024*1024+1)
   assert len(data)<1024*1024;path.write_bytes(data)
  assert hashlib.sha256(path.read_bytes()).hexdigest()==expected,'Pinned source mismatch'
  proof.append({'url':url,'sha256':expected})
 (out/'pinned-source-proof.json').write_text(json.dumps(proof,indent=2),'utf8');print('PASS: pinned MIT baseline and SCIN license sources')
if __name__=='__main__':main()

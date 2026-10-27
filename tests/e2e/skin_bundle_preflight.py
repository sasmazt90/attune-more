"""Read-only file integrity preflight. No downloads, credentials, model imports or inference."""
from pathlib import Path,PurePosixPath
import argparse,hashlib,json,os
ROOT=Path(__file__).resolve().parents[2]

def digest(path):
 h=hashlib.sha256()
 with path.open('rb') as f:
  for block in iter(lambda:f.read(1024*1024),b''):h.update(block)
 return h.hexdigest()

def verify(bundle):
 bundle=Path(bundle).resolve();issues=[];checked=[]
 findings=json.loads((ROOT/'research/skin-findings/export/FINDINGS_V2_MANIFEST.json').read_text())['files']
 models=json.loads((ROOT/'research/skin-findings/MODEL_MANIFEST.json').read_text())['models']
 expected={k:dict(v) for k,v in findings.items()}
 for m in models:
  if m.get('runtimeName') in ('acnes.pt','findings.pt','regional.pt','skinmap.pt','wrinkles.pt'):
   expected[m['runtimeName']]={'sha256':m['sha256'],'bytes':m['sizeBytes']}
 for name,spec in expected.items():
  rel=PurePosixPath(name)
  if rel.is_absolute() or '..' in rel.parts or '\\' in name:raise ValueError('UNSAFE_MANIFEST_PATH')
  path=bundle/name
  if path.is_symlink() or not path.resolve().is_relative_to(bundle):issues.append(name+': unsafe path');continue
  if not path.is_file():issues.append(name+': missing');continue
  if path.stat().st_size!=spec['bytes']:issues.append(name+': byte-size mismatch');continue
  if digest(path)!=spec['sha256']:issues.append(name+': SHA-256 mismatch');continue
  checked.append(name)
 for name in ('params.json','k_classifier.json','dinov2-small/config.json','dinov2-small/model.safetensors'):
  path=bundle/name
  if not path.is_file() or path.is_symlink() or not path.resolve().is_relative_to(bundle):issues.append(name+': missing or unsafe')
 return dict(status='BLOCKED' if issues else 'PASS',verifiedManifestFiles=len(checked),expectedManifestFiles=len(expected),issues=issues,modelsLoaded=False,inferenceExecuted=False)

if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('--bundle',default=os.getenv('ATTUNE_REGIONAL_V3_DIR',str(ROOT/'services/core-api/models/regional-skin-v3')));args=p.parse_args()
 result=verify(args.bundle);print(json.dumps(result,indent=2));raise SystemExit(69 if result['issues'] else 0)

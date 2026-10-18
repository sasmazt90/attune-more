"""Snapshot only the user's pinned dryness package; never import AG code."""
import hashlib,json,subprocess,datetime
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2];AG=ROOT.parent/'attune-antigravity-skin'
from pinned_dry_contract import contract
CONTRACT=contract();COMMIT=CONTRACT['commit'];BASE=CONTRACT['base'];OUT=CONTRACT['out']/'delivery-snapshot';EXPECTED=CONTRACT['hashes']
assert subprocess.check_output(['git','-C',str(AG),'cat-file','-t',COMMIT],text=True).strip()=='commit'
OUT.mkdir(parents=True,exist_ok=True);rows=[]
for name,expected in EXPECTED.items():
    tracked=subprocess.run(['git','-C',str(AG),'cat-file','-e',COMMIT+':'+BASE+'/'+name],capture_output=True).returncode==0
    raw=subprocess.check_output(['git','-C',str(AG),'show',COMMIT+':'+BASE+'/'+name]) if tracked else (AG/BASE/name).read_bytes()
    actual=hashlib.sha256(raw).hexdigest();assert actual==expected,(name,actual)
    target=OUT/name;target.parent.mkdir(parents=True,exist_ok=True)
    if target.exists():assert target.read_bytes()==raw,'Existing snapshot preserved on mismatch'
    else:target.write_bytes(raw)
    assert hashlib.sha256(target.read_bytes()).hexdigest()==expected
    rows.append(dict(file=name,sha256=actual,bytes=len(raw),inFrozenGitTree=tracked,identityAuthority='frozen-git-blob' if tracked else 'explicit-user-pinned-package-sha256'))
manifest=json.loads((AG/BASE/'delivery-manifest.json').read_text('utf8'))
reported=manifest.get('workspaceContext',{}).get('agHeadCommit',manifest.get('agHeadCommit'))
receipt=dict(createdUTC=datetime.datetime.now(datetime.timezone.utc).isoformat(),sourceCommit=COMMIT,
    manifestAgHeadCommit=reported,manifestMetadataPath='workspaceContext.agHeadCommit',metadataMismatch=reported!=COMMIT,
    note='Package artifacts absent from Git tree are pinned by explicit user SHA-256, not represented as Git blobs. No moving AG code is imported.',files=rows)
(OUT/'transfer-receipt.json').write_text(json.dumps(receipt,indent=2),'utf8')
frozen='scripts/skin-research/compare_three_heads.py'
(OUT/'frozen-compare-three-heads.py').write_bytes(subprocess.check_output(['git','-C',str(AG),'show',COMMIT+':'+frozen]))
print(json.dumps(receipt))

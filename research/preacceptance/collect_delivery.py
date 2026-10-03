"""Archive public metadata and content-free historical evidence; never secret/media files."""
import datetime, gzip, hashlib, json, os, subprocess, urllib.request
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2];PRODUCT=ROOT.parent/'attune-live-test';OUT=ROOT/'research/preacceptance'
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
sources={
 'models':'https://developers.openai.com/api/reference/resources/models/methods/list',
 'authentication':'https://developers.openai.com/api/reference/overview',
 'administration':'https://developers.openai.com/api/reference/administration/overview',
 'dataControls':'https://developers.openai.com/api/docs/guides/your-data',
 'advisory':'https://github.com/advisories/GHSA-vfj7-8cjw-p6xm',
 'eslintSupport':'https://eslint.org/version-support/'}
(OUT/'official-sources.json').write_text(json.dumps({'checkedAt':datetime.datetime.now(datetime.timezone.utc).isoformat(),'sources':sources},indent=2),encoding='utf-8')
with urllib.request.urlopen(urllib.request.Request(sources['eslintSupport'],headers={'User-Agent':'attune-readonly-review'}),timeout=25) as r:
    support=r.read()
archive=gzip.compress(support,mtime=0)
(OUT/'official-eslint-support.raw.html.gz').write_bytes(archive)
readable=b'\n'.join(line.rstrip(b' \t\r') for line in support.split(b'\n'))
(OUT/'official-eslint-support.html').write_bytes(readable)
(OUT/'official-eslint-support-source-proof.json').write_text(json.dumps({'source':sources['eslintSupport'],
    'originalHtmlSha256':hashlib.sha256(support).hexdigest(),'rawArchiveSha256':hashlib.sha256(archive).hexdigest(),
    'readableHtmlSha256':hashlib.sha256(readable).hexdigest(),'readableTransformation':'trailing whitespace only; original response preserved losslessly in raw gzip'},indent=2),encoding='utf-8')
env={k:v for k,v in os.environ.items() if not k.startswith('OPENAI_')}
for run in ['37140873242','37140875623']:
    raw=subprocess.check_output(['gh','run','view',run,'--repo','sasmazt90/togg-health-mvp','--json','headSha,conclusion,status,url,jobs'],env=env)
    (OUT/('historical-ci-'+run+'.json')).write_bytes(raw)
pr=subprocess.check_output(['gh','pr','view','2','--repo','sasmazt90/togg-health-mvp','--json','url,isDraft,state,mergedAt,headRefOid,baseRefName'],env=env)
(OUT/'pr-state.json').write_bytes(pr)
remote=subprocess.check_output(['git','-C',str(PRODUCT),'ls-remote','origin','refs/heads/main','refs/heads/fix/live-test-followup'],env=env).decode()
(OUT/'remote-state.txt').write_text(remote,encoding='utf-8')
refs=['audit-results/ci-37140873242-matrix-proof.json','audit-results/uat-closure-20261003/windows-launcher.json',
    'audit-results/live-provider/20261003-uat-01/egress-proof.json','audit-results/live-provider/20261003-uat-01/ui-proof.json',
    'audit-results/live-provider/20261003-uat-01/cleanup-proof.json','audit-results/uat-closure-20261003/FINAL_REPORT.md',
    'docs/dependency-closure-decision.md']
proof={'historicalEvidence':{p:sha(PRODUCT/p) for p in refs},'historicalLiveSource':'71309f4044e1115c80f799701df3135ec319d9d4','historicalLiveRun':'20261003-uat-01',
    'currentProductSource':'f8f08d98cf23eb23c5a171b5b50411364d79adf6','servicesDiffFromHistoricalLive':subprocess.check_output(['git','-C',str(PRODUCT),'diff','--name-only','71309f4044e1115c80f799701df3135ec319d9d4','f8f08d98cf23eb23c5a171b5b50411364d79adf6','--','services']).decode().splitlines(),
    'currentPaidChatTTSRun':False,'historicalPaidCounts':{'conversation':3,'tts':3,'summary':1},'historicalSourceIsNotCurrentLiveAcceptance':True}
assert proof['servicesDiffFromHistoricalLive']==[]
(OUT/'historical-evidence-index.json').write_text(json.dumps(proof,indent=2),encoding='utf-8')
print(json.dumps({'publicAndHistoricalEvidenceCollected':True,'historicalServicesDiff':0,'currentPaidRun':False}))

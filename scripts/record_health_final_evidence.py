"""Bind actual bounded proof files to the final build, without raw photo payloads."""
import hashlib,json
from datetime import datetime,timezone
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT.parent/'cdc-progress/health-final-technical-closeout-20261017'
def read(name):return json.loads((OUT/name).read_text('utf-8-sig'))
build=read('build-receipt.json');build_time=(OUT/'build-receipt.json').stat().st_mtime
names=['consent-proof.json','capture-revocation-proof.json','audio-lifecycle-proof.json','hearing-revoke-proof.json','delivered-screens.json','native200-proof.json','common-proof.json','supplement-proof.json','ownership-proof.json','print-proof.json','upload-partial.json']
proof={name:read(name) for name in names}
for name in names:assert (OUT/name).stat().st_mtime>=build_time,name+' was not rerun on this build'
assert len(proof['consent-proof.json']['rows'])==5
assert all(v['consentNoAutostart'] and v['crossTabPrivacyRevoke'] for v in proof['consent-proof.json']['rows'])
assert all(s['mediaCalls']==0 for s in proof['delivered-screens.json']['screens'])
assert len(proof['delivered-screens.json']['screens'])==10
assert proof['native200-proof.json']['BUILD_ID']==build['BUILD_ID']
assert proof['upload-partial.json']['BUILD_ID']==build['BUILD_ID']
assert all(proof['audio-lifecycle-proof.json']['checks'].values())
assert all(r['trackStates']==['ended'] for r in proof['capture-revocation-proof.json']['rows'])
assert proof['hearing-revoke-proof.json']['after']['records']==0
assert proof['ownership-proof.json']['unrelated']==['live']
assert len(proof['supplement-proof.json']['storageFailures'])==5 and proof['supplement-proof.json']['pendingTurnRouteAbort']
assert proof['print-proof.json']['sentToAnyone'] is False
dental=proof['upload-partial.json'];assert dental['historyReopened'] and dental['sameBoxes'] and dental['sameSourceImage']
receipts=[dict(path=name,sha256=hashlib.sha256((OUT/name).read_bytes()).hexdigest()) for name in names]
value=dict(recordedAt=datetime.now(timezone.utc).isoformat(),startCommit='09d3cd159c1c614f27cb9911e975b7b1eb0d52d9',BUILD_ID=build['BUILD_ID'],proofFiles=receipts,entryScreens=10,consentModules=5,storageFailureModules=5,captureRevocationModules=3,mentalChecks=proof['audio-lifecycle-proof.json']['checks'],common=proof['common-proof.json']['checks'],unrelatedStream=proof['ownership-proof.json']['unrelated'],dental=dict(candidates=len(dental['view']['caries']['candidates']),sourcePhotoId=dental['view']['photoId'],modelHash=dental['view']['caries']['modelHash'],historyReopened=dental['historyReopened'],sameBoxes=dental['sameBoxes'],cameraCalls=dental['cameraCalls']),productionAudit=read('npm-audit-production-final.json')['metadata']['vulnerabilities'],developmentAudit=read('npm-audit-final.json')['metadata']['vulnerabilities'],resource=build['resource'],physicalUserAcceptance=False,clinicalAcceptance=False,liveProviderCampaign=False,normalWindowsShortcutChanged=False)
(ROOT/'docs/health-final-technical-evidence-20261017.json').write_text(json.dumps(value,ensure_ascii=False,indent=2)+'\n','utf8')
(OUT/'evidence-summary.json').write_text(json.dumps(value,ensure_ascii=False,indent=2)+'\n','utf8')
print(json.dumps(dict(BUILD_ID=build['BUILD_ID'],boundProofFiles=len(receipts),dentalCandidates=value['dental']['candidates'],physicalUserAcceptance=False)))

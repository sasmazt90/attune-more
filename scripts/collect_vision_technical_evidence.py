"""Collect local metadata only; never reads photos, audio or user profiles."""
import hashlib,json,xml.etree.ElementTree as ET
from datetime import datetime,timezone
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];OUT=ROOT.parent/'cdc-progress/vision-technical-closeout-20261017';BROWSER=ROOT/'output/playwright/vision'
def read(p):return json.loads(p.read_text('utf-8-sig'))
def atomic(p,value):
    t=p.with_suffix('.tmp');t.write_text(json.dumps(value,indent=2,ensure_ascii=False)+'\n',encoding='utf8');t.replace(p)
def main():
    tests=[]
    for name in ('focused-tests.xml','local-api-test.xml','tracking-geometry-test.xml'):
        root=ET.parse(OUT/name).getroot();suite=root.find('testsuite');assert int(suite.attrib['failures'])==0 and int(suite.attrib['errors'])==0
        tests.extend((t.attrib['classname'],t.attrib['name']) for t in suite.findall('testcase'))
    assert len(tests)==len(set(tests))==65
    browser={name:read(BROWSER/(name+'.json')) for name in ('desktop-proof','narrow-proof','native200-proof','native200-surface','native100-control','models-proof','lifecycle-proof','voice-failure-proof','pause-before','pause-after')}
    valid=[t for t in browser['desktop-proof']['record']['trials'] if t['valid']]
    assert len(valid)==24 and all(sum(t['eye']==eye for t in valid)==12 for eye in ('RIGHT','LEFT'))
    scores={}
    for eye in ('RIGHT','LEFT'):
        rows=[t for t in valid if t['eye']==eye];letter=sum(t['letterCorrect'] for t in rows);direction=sum(t['orientationCorrect'] for t in rows)
        scores[eye]=dict(valid=len(rows),letterCorrect=letter,directionCorrect=direction,averagePercent=(letter+direction)*100/(2*len(rows)))
    normal=browser['native100-control'];zoom=browser['native200-surface'];ratio=zoom['dpr']/normal['dpr'];assert ratio==2 and zoom['cssZoom']==normal['cssZoom']=='1' and zoom['visualScale']==normal['visualScale']==1
    assert normal['noTestOverrides'] and normal['noRecord']
    files=[ROOT/'docs/vision-technical-closeout-20261017.md',OUT/'build.log',OUT/'typecheck.log',OUT/'build-receipt.json',OUT/'served-protection-receipt.json',OUT/'local-assets.json',OUT/'before-nonfinite.xml',OUT/'after-nonfinite.xml']+[OUT/n for n in ('focused-tests.xml','local-api-test.xml','tracking-geometry-test.xml')]+[BROWSER/(n+'.json') for n in browser]
    # Only UI screenshots of generated geometry are indexed, never source photos.
    files+=[BROWSER/n for n in ('desktop-active.png','desktop-result.png','desktop-history.png','narrow-active.png','native200-surface.png')]
    value=dict(timeUTC=datetime.now(timezone.utc).isoformat(),sourceCommit=read(OUT/'start.json')['startCommit'],branch='research/vision-technical-closeout-20261017',BUILD_ID=read(OUT/'build-receipt.json')['BUILD_ID'],technicalChecksPassed=True,physicalUserAcceptance=False,uniqueFocusedTests=65,scores=scores,nativeZoomRatio=ratio,browser=browser,served=read(OUT/'served-protection-receipt.json'),evidenceFiles=[dict(path=str(p),bytes=p.stat().st_size,sha256=hashlib.sha256(p.read_bytes()).hexdigest()) for p in files])
    atomic(ROOT/'docs/vision-technical-closeout-20261017.json',value);atomic(OUT/'evidence.json',value)
    report=(ROOT/'docs/vision-technical-closeout-20261017.md').read_text('utf8');temp=OUT/'report.tmp';temp.write_text(report,encoding='utf8');temp.replace(OUT/'report.md')
    status=read(OUT/'status.json');status.update(timeUTC=value['timeUTC'],stage='technical-complete-local-commit-pending',build=value['BUILD_ID'],blocker=None,modelVoiceBuild=dict(faceSHA256='64184e229b263107bc2b804c6625db1341ff2bb731874b0bcc2fe6544e0bc9ff',handSHA256='fbc2a30080c3c557093b5ddfc334698132eb341044ccee322ccf8bcf3607cde1',voice='tr-TR-AhmetNeural',rate='-10%',pitch='-10Hz',BUILD_ID=value['BUILD_ID']),completed=['Source/protected checkout ownership and hashes verified','Pause/resume and nonfinite failures reproduced, fixed and verified','65 focused regressions; standalone typecheck; production build','Actual recorded-pixel Face/Hand worker, lost/stale source and SPA cleanup','24 valid trials, adaptive real SVG geometry, one record and same history','Narrow and native 200%; lifecycle, permissions, drive and voice failure','38 served JS files, 2 served model hashes, 4 fixed-bank API byte hashes','Report and metadata-only evidence collected'],remaining=['Local commit; final clean-tree/protection receipt','Physical acceptance only at the end of all modules'],physicalUserAcceptance=False)
    atomic(OUT/'status.json',status);print('COLLECTED 65 tests, 24 trials, native zoom ratio',ratio,scores)
if __name__=='__main__':main()

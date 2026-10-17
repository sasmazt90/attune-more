"""Metadata-only local handoff. Never embeds photographs, audio or conversations."""
import datetime,hashlib,json,subprocess,xml.etree.ElementTree as ET
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];OUT=ROOT.parent/'cdc-progress/health-ui-consent-audio-followup-20261017'
def read(name):return json.loads((OUT/name).read_text('utf-8-sig'))
def digest(path):return hashlib.sha256(path.read_bytes()).hexdigest()
def atomic(path,value):
    tmp=path.with_suffix('.tmp');tmp.write_text(json.dumps(value,ensure_ascii=False,indent=2)+'\n','utf8');tmp.replace(path)
build=read('build-receipt.json');served=read('served-protection-receipt.json')
assert served['BUILD_ID']==build['BUILD_ID'] and served['servedJSCount']>=20
suite=ET.parse(OUT/'focused-tests.xml').getroot();cases=suite.findall('.//testcase')
assert cases and not suite.findall('.//failure') and not suite.findall('.//error')
evidence={name:read(name) for name in ['consent-proof.json','long-session-proof.json','final-context-smoke.json','long-message-proof.json','audio-lifecycle-proof.json','capture-revocation-proof.json','hearing-revoke-proof.json','audio-passthrough-proof.json','screen-proof.json']}
assert evidence['long-session-proof.json']['controlledTurns']==110
assert evidence['final-context-smoke.json']['contextFailureRetainedPrior']
assert evidence['consent-proof.json']['healthCallsBeforeConsent']==0
assert evidence['audio-passthrough-proof.json']['bitExact']
tts1=read('tts-first-diagnostic.json');tts2=read('tts-second-diagnostic.json');tts3=read('tts-third-browser.json')
assert tts2['status']==200 and tts3['speechRequests']==1 and tts3['peak']>.003 and tts3['idle']==0
assets=read('local-assets.json')
generated=[]
for module,prompt in [
 ('dental','Create a production website hero asset, photorealistic natural editorial portrait. A fictional adult woman, shoulders and entire head visible, looking toward the camera, natural warm smile with upper teeth clearly and realistically visible, healthy ordinary unretouched skin. Dark navy studio background #0c1424, soft light, portrait 3:4 composition, no text, no logos, no cards. Add a delicate subtle turquoise triangular scanning mesh only on the mouth and visible teeth area, do not place mesh on eyes forehead cheeks or neck. This is an illustrative preparation portrait for a dental photo flow, not a diagnostic result. Natural anatomy, realistic teeth, no tools or medical devices, premium understated styling.'),
 ('hearing','Production website hero asset, photorealistic natural editorial portrait. Fictional adult man with short hair, head and shoulders in subtle three-quarter side view, visible natural ear clearly exposed toward the camera, calm expression. Dark navy studio background #0c1424 and soft photographic lighting, understated premium health app style, portrait 3:4 composition. Fine delicate turquoise sound wave arcs traveling through air toward the ear from the left side of the image. No text, no labels, no diagrams over the face, no headphones covering the ear, no medical devices, no cartoon or illustration rendering. Ordinary natural skin texture. Educational preparation image for a headphone hearing test, never a diagnostic result.')]:
    path=ROOT/f'apps/vehicle-app/public/assets/{module}-preparation-v1.png'
    generated.append({'path':str(path.relative_to(ROOT)),'sha256':digest(path),'bytes':path.stat().st_size,'source':'built-in image_gen; generated for this authorized task','use':'local illustrative preparation portrait; fictional, not a patient/result','prompt':prompt,'inGit':False})
value={'schemaVersion':1,'timeUTC':datetime.datetime.now(datetime.timezone.utc).isoformat(),
 'checkout':str(ROOT),'branch':'research/health-ui-consent-audio-20261017','sourceBase':'5f11c111e3f6547e6420ddf37db477190d232f10',
 'integration':{'acneAncestry':['ebd44bc','29b9979','f230cce','2637d1b'],'visionFrozen':'1cdb95ebdddd3a2fd4b83cca7408a1ae6cd3b502','visionApplied':'57d4a75','mentalFrozen':'eead4b23d92dc40887a3ed223628b2e1297cddea','mentalApplied':'88e5b8d'},
 'BUILD_ID':build['BUILD_ID'],'frontend':'http://127.0.0.1:3308/','backend':'http://127.0.0.1:8308',
 'tests':{'passed':len(cases),'typecheck':'PASS','productionBuild':'PASS'},'checks':evidence,
 'tts':{'attempts':3,'before':{'stages':tts1['stages'],'error':tts1['error']},'dependency':'edge-tts==7.3.1; isolated target only','fixedEntry':tts2,'dynamicPlayback':{'requests':tts3['speechRequests'],'peak':tts3['peak'],'idle':tts3['idle'],'zeroSamplesDuringPlayback':sum(s['amplitude']==0 for s in tts3['samples'])},'liveLlmUsedInThisPlaybackTest':False,'replySource':'controlled nonpersonal reply; actual live TTS endpoint and native playback'},
 'sourceBuildServed':{'files':served['sourceHashesVerified'],'servedJS':served['servedJSCount'],'receiptSHA256':digest(OUT/'served-protection-receipt.json')},
 'protected':served['protected'],'sourceTaskFiles':served['sourceTaskFiles'],'preservedAnalysisFiles':served['preservedMethods'],
 'assets':assets,'generatedAssets':generated,'normalLauncherChanged':False,'push':False,'mergeMain':False,
 'technicalBlocker':None,'physicalAcceptance':'PENDING: final shared camera, natural ASR, hearing and pronunciation session',
 'contextContract':{'version':'extractive-user-quotes-v1','recentMessageTrigger':32,'characterTrigger':80000,'recentKeepMaximumMessages':16,'recentKeepMaximumChars':48000,'maximumMemoryQuotes':32,'maximumQuoteChars':2000,'maximumMemoryChars':16000,'perRequestTimeoutSeconds':30,'providerRetries':0,'permanentMemory':False}}
atomic(ROOT/'docs/health-ui-consent-audio-followup-20261017.json',value)
atomic(OUT/'delivery-evidence.json',value)
atomic(OUT/'status.json',{'stage':'verified-awaiting-local-commit','timeUTC':value['timeUTC'],'checkout':str(ROOT),'branch':value['branch'],'commit':subprocess.check_output(['git','rev-parse','HEAD'],cwd=ROOT,text=True).strip(),'completed':['selective integration','live exact Emel restored','voice-only UI','bounded rolling context','five persistent consent gates','dental/hearing preparation','real playback meter','focused tests/typecheck/build','source/served/protected hash checks'],'remaining':['local commit and clean delivery profile'],'blocker':None,'BUILD_ID':build['BUILD_ID'],'generatedAssetSHA256':[g['sha256'] for g in generated]})
print(json.dumps({'tests':len(cases),'BUILD_ID':build['BUILD_ID'],'technicalBlocker':None}))

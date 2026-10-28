"""Probe native Chrome SpeechRecognition with a browser fake microphone.

Camera/model events are controlled. Recognition itself is never replaced.
This is a provider/permission lifecycle probe, not speech accuracy evidence.
"""
import os,json
from pathlib import Path
from playwright.sync_api import sync_playwright
source=Path('tests/e2e/vision_technical_boot.js').read_text()
a=source.index('class SR{');b=source.index('navigator.mediaDevices.getUserMedia=',a)
source=source[:a]+source[b:]
seed="localStorage.setItem('attune_health_processing_v1',JSON.stringify({version:1,services:{vision:{permissions:['local','speech']}}}));window.nativeSpeechEvents=[];window.addEventListener('attune-vision-speech-timing',e=>nativeSpeechEvents.push(e.detail.stage));"
with sync_playwright() as pw:
 browser=pw.chromium.launch(executable_path=os.getenv('CHROME_PATH') or None,channel=None if os.getenv('CHROME_PATH') else 'chrome',headless=True,args=['--use-fake-device-for-media-stream','--autoplay-policy=no-user-gesture-required','--no-sandbox'])
 try:
  context=browser.new_context(permissions=['microphone','camera']);context.add_init_script(seed+source);p=context.new_page();p.goto(os.getenv('VISION_TEST_URL','http://127.0.0.1:3306')+'/vision')
  available=p.evaluate("!!(window.SpeechRecognition||window.webkitSpeechRecognition)")
  p.get_by_role('button',name='Başlat',exact=True).click()
  status='unsupported'
  if available:
   try:p.wait_for_function("()=>nativeSpeechEvents.some(s=>s.startsWith('asr-error:'))",timeout=45000);status='provider-error-observed'
   except Exception:status='no-terminal-provider-event-within-45s'
  events=p.evaluate('nativeSpeechEvents');assert p.evaluate('probe.events.filter(e=>e.combinedCorrect!==undefined).length')==0
  result={'kind':'actual Chrome SpeechRecognition with fake microphone; camera/model fixtures only','apiAvailable':available,'status':status,'events':events,'scoredTrials':0,'realUtteranceAccuracy':'NOT_TESTED','physicalMicrophone':'NOT_AVAILABLE'}
  denied=browser.new_context(permissions=['camera']);denied.add_init_script(seed+source);q=denied.new_page();q.goto(os.getenv('VISION_TEST_URL','http://127.0.0.1:3306')+'/vision')
  denied.new_cdp_session(q).send('Browser.setPermission',{'permission':{'name':'microphone'},'setting':'denied','origin':os.getenv('VISION_TEST_URL','http://127.0.0.1:3306')})
  q.get_by_role('button',name='Başlat',exact=True).click()
  if available:
   try:q.wait_for_function("()=>nativeSpeechEvents.some(s=>s.startsWith('asr-error:'))",timeout=45000)
   except Exception:pass
  denied_errors=q.evaluate("nativeSpeechEvents.filter(s=>s.startsWith('asr-error:'))")
  result['nativeMicrophonePermissionDenial']={'status':'PASS' if 'asr-error:not-allowed' in denied_errors else 'BLOCKED','observedErrors':denied_errors,'scoredTrials':q.evaluate('probe.events.filter(e=>e.combinedCorrect!==undefined).length')}
  assert result['nativeMicrophonePermissionDenial']['scoredTrials']==0
  Path('docs/vision-conversation-evidence/native-speech.json').write_text(json.dumps(result,indent=2)+'\n');print(json.dumps(result))
 finally:browser.close()

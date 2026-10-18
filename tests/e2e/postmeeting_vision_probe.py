"""Real model/pixel fixture camera; real Edge speech; no transcript or condition PASS injection."""
import json,time
from pathlib import Path
from playwright.sync_api import sync_playwright,expect
OUT=Path('audit-results/postmeeting/vision');OUT.mkdir(parents=True,exist_ok=True)
with sync_playwright() as pw:
 b=pw.chromium.launch(channel='chrome',headless=True,args=['--use-fake-device-for-media-stream','--use-file-for-fake-video-capture='+str(Path('audit-fixtures/valid-face.y4m').resolve()),'--autoplay-policy=no-user-gesture-required','--enable-unsafe-swiftshader'])
 c=b.new_context(permissions=['camera'],viewport={'width':1600,'height':1000});p=c.new_page();errors=[];p.on('pageerror',lambda e:errors.append(str(e)))
 c.add_init_script("window.timings=[];window.recognitionStarts=0;window.addEventListener('attune-vision-speech-timing',e=>window.timings.push(e.detail));const SR=window.SpeechRecognition||window.webkitSpeechRecognition;if(SR){const start=SR.prototype.start;SR.prototype.start=function(){window.recognitionStarts++;throw Error('Fixture cannot acquire physical microphone');};}")
 voices=[]
 def capture(r):
  if '/api/vision/speech' in r.url:voices.append({'status':r.status,'voice':r.headers.get('x-tts-voice'),'rate':r.headers.get('x-tts-rate'),'pitch':r.headers.get('x-tts-pitch')})
 p.on('response',capture);c.request.post('http://127.0.0.1:8000/api/vehicle/speed',data={'speedKmH':0});p.goto('http://127.0.0.1:3000/vision');p.get_by_role('button',name='Başlat',exact=True).click()
 rows=[]
 for i in range(18):
  p.wait_for_timeout(2000)
  row=p.evaluate('''()=>{const canvas=document.querySelector('canvas'),preview=document.querySelector('[data-camera-preview]'),v=document.querySelector('video');return {at:performance.now(),data:{...canvas?.dataset},voice:document.querySelector('[data-vision-voice]')?.getAttribute('data-vision-voice'),crop:preview?.getAttribute('data-preview-crop'),target:preview?.getAttribute('data-target-crop'),video:v?{width:v.videoWidth,height:v.videoHeight,time:v.currentTime}:null,letter:!!document.querySelector('[data-letter-optotype]')};}''');rows.append(row)
  if i==10:p.screenshot(path=str(OUT/'preparation-desktop.png'),full_page=True)
 assert any(r['data'].get('visionModelActive')=='true' for r in rows)
 assert any(r['data'].get('visionQualityComparison') for r in rows)
 assert all(r['voice']!='listening' for r in rows if not r['letter'])
 assert all(v['voice']=='tr-TR-AhmetNeural' and v['rate']=='-10%' and v['pitch']=='-10Hz' for v in voices if v['status']==200)
 timing=p.evaluate('window.timings');assert any(t['stage']=='playing' for t in timing) and any(t['stage']=='ended' for t in timing)
 p.locator('video').evaluate('v=>v.pause()');p.wait_for_timeout(1000);expect(p.locator('[data-letter-condition]')).to_have_attribute('data-letter-condition','camera');assert p.locator('[data-vision-voice]').get_attribute('data-vision-voice')!='listening'
 p.locator('video').evaluate('v=>v.play()');p.wait_for_timeout(1200);p.get_by_role('button',name='Bitir',exact=True).click();expect(p.get_by_role('dialog')).to_be_visible();p.get_by_role('button',name='Tamam',exact=True).click()
 p.set_viewport_size({'width':720,'height':900});p.screenshot(path=str(OUT/'narrow.png'),full_page=True);assert p.evaluate('document.documentElement.scrollWidth<=innerWidth')
 p.set_viewport_size({'width':1600,'height':1000});p.evaluate("document.documentElement.style.zoom='2'");p.screenshot(path=str(OUT/'zoom200.png'),full_page=True);assert p.evaluate('document.documentElement.scrollWidth<=innerWidth')
 assert not errors,errors
 proof={'status':'PASS','controlledFixture':True,'physicalCamera':False,'physicalMic':False,'qualityOverride':False,'transcriptInjected':False,'scoredTrials':0,'rows':rows,'timing':timing,'voiceHeaders':voices,'recognitionStarts':p.evaluate('window.recognitionStarts'),'positiveEyeAndSTTAcceptance':'OPEN'}
 (OUT/'proof.json').write_text(json.dumps(proof,ensure_ascii=False,indent=2),'utf8');c.close();b.close()
print('PASS: actual model focus/crop evidence, Edge playing/ended, no listening before letter, stale camera stop; positive physical acceptance OPEN')

"""Real production face/hand inference, real Edge native ended, open-eye gate.
No conditions are substituted. This probe cannot accept closed/covered eyes.
"""
import json,time,hashlib
from pathlib import Path
from playwright.sync_api import sync_playwright,expect
OUT=Path('audit-results/vision-usable');OUT.mkdir(parents=True,exist_ok=True)
with sync_playwright() as pw:
 b=pw.chromium.launch(channel='chrome',headless=True,args=['--use-fake-device-for-media-stream','--use-file-for-fake-video-capture='+str(Path('audit-fixtures/valid-face.y4m').resolve()),'--autoplay-policy=no-user-gesture-required','--enable-unsafe-swiftshader'])
 c=b.new_context(permissions=['camera'],viewport={'width':1600,'height':1100});p=c.new_page();errors=[];p.on('pageerror',lambda e:errors.append(str(e)))
 c.add_init_script("window.timings=[];window.starts=0;window.addEventListener('attune-vision-speech-timing',e=>window.timings.push(e.detail));const SR=window.SpeechRecognition||window.webkitSpeechRecognition;if(SR){SR.prototype.start=function(){window.starts++;throw Error('Physical mic not admitted in fixture');};}")
 voices=[];p.on('response',lambda r:voices.append({'status':r.status,'voice':r.headers.get('x-tts-voice'),'rate':r.headers.get('x-tts-rate'),'pitch':r.headers.get('x-tts-pitch')}) if '/api/vision/speech' in r.url else None)
 requested=[];p.on('request',lambda r:requested.append(r.post_data_json['text']) if '/api/vision/speech' in r.url and r.method=='POST' else None)
 c.request.post('http://127.0.0.1:8000/api/vehicle/speed',data={'speedKmH':0});p.goto('http://127.0.0.1:3000/vision');p.get_by_role('button',name='Başlat',exact=True).click()
 rows=[]
 # Physical GPU startup plus the explicit screen-gaze eye instruction took
 # about 40 seconds. Bound the complete negative startup, not just inference.
 for i in range(45):
  p.wait_for_timeout(1000);row=p.evaluate("()=>({at:performance.now(),evidence:JSON.parse(document.querySelector('canvas')?.dataset.visionEvidence||'null'),stage:document.querySelector('[data-vision-stage]')?.dataset.visionStage,letter:!!document.querySelector('[data-letter-optotype]'),placeholder:document.querySelector('[data-letter-placeholder]')?.textContent})");rows.append(row)
  if row['stage']=='idle' or row['stage']=='error':
   (OUT/'startup-failure.json').write_text(json.dumps({'row':row,'body':p.locator('body').inner_text(),'errors':errors,'failure':p.locator('canvas').get_attribute('data-vision-failure')},ensure_ascii=False,indent=2),'utf8');raise AssertionError('Production startup failed; see startup-failure.json')
  if i==20:p.locator('[data-letter-area]').locator('..').screenshot(path=str(OUT/'both-open-desktop.png'))
  if row['stage']=='eye-check' and i>18:break
 layouts=[]
 for tag,width,height,zoom in [('desktop',1600,1100,1),('narrow',640,900,1),('zoom200',1600,1100,2)]:
  p.set_viewport_size({'width':width,'height':height});p.evaluate('(z)=>document.documentElement.style.zoom=String(z)',zoom);p.wait_for_timeout(300)
  box=p.locator('[data-letter-area]').bounding_box();horizontal=p.evaluate('document.documentElement.scrollWidth<=innerWidth+1');p.locator('[data-letter-area]').screenshot(path=str(OUT/(tag+'-blocked-area.png')));layouts.append({'tag':tag,'area':box,'horizontalOverflow':not horizontal,'actualLetterVisible':False});assert horizontal and box['width']>0 and box['height']>0
 p.evaluate("document.documentElement.style.zoom='1'");p.set_viewport_size({'width':1600,'height':1100})
 (OUT/'open-probe.json').write_text(json.dumps({'buildId':Path('apps/vehicle-app/.next/BUILD_ID').read_text().strip(),'sourceHashes':{n:hashlib.sha256(Path('apps/vehicle-app/src/'+n).read_bytes()).hexdigest() for n in ['app/vision/SpokenLetterPage.tsx','utils/visionTracking.ts','utils/visionFlow.ts','utils/visionInference.worker.ts','utils/spokenVision.ts']},'rows':rows,'errors':errors,'voices':voices,'requestedCodes':requested,'layouts':layouts,'timings':p.evaluate('window.timings'),'starts':p.evaluate('window.starts')},ensure_ascii=False,indent=2),'utf8')
 assert not errors,errors
 assert any(r['evidence'] and r['evidence']['conditions']['positionValid'] for r in rows),'Initial head/eye baseline never became ready'
 assert any(r['stage']=='eye-check' for r in rows),'Anatomical eye instruction did not finish'
 assert all(not r['letter'] for r in rows),'Both-open face must not admit eye trial'
 assert p.evaluate('window.starts')==0,'STT before valid eye/stimulus'
 assert set(requested)<=set(['prepare','right']),'Response prompt before visible letter'
 assert all(v['voice']=='tr-TR-AhmetNeural' and v['rate']=='-10%' and v['pitch']=='-10Hz' for v in voices if v['status']==200)
 p.locator('video').evaluate('v=>v.pause()');p.wait_for_timeout(1000);assert p.evaluate('window.starts')==0
 p.get_by_role('button',name='Bitir',exact=True).click();expect(p.get_by_role('dialog')).to_be_visible();p.get_by_role('button',name='Tamam',exact=True).click();expect(p.get_by_role('button',name='Başlat',exact=True)).to_be_visible()
 c.close();b.close()
print('PASS: real open-eye baseline, unchanged Edge profile, no stimulus/STT for both-open; physical and positive covered acceptance remain separate')

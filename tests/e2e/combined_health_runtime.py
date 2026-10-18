"""Production UI/audio lifecycle; simulated replies, no human hearing claim."""
import hashlib,json,math,tempfile,time
from pathlib import Path
from playwright.sync_api import sync_playwright,expect
OUT=Path('audit-results/combined-health-20261008/runtime');OUT.mkdir(parents=True,exist_ok=True)
AUDIO=r'''window.signals=[];window.ownedStreams=[];
const start=AudioBufferSourceNode.prototype.start;AudioBufferSourceNode.prototype.start=function(...args){const b=this.buffer;if(b){const channels=[];for(let k=0;k<b.numberOfChannels;k++){const v=b.getChannelData(k);let sum=0,peak=0;for(const x of v){sum+=x*x;peak=Math.max(peak,Math.abs(x));}channels.push({rms:Math.sqrt(sum/v.length),peak,first:v[0],last:v.at(-1)});}const row={rate:b.sampleRate,duration:b.duration,channels,ended:false};window.signals.push(row);this.addEventListener('ended',()=>row.ended=true);}return start.apply(this,args);};
const media=navigator.mediaDevices.getUserMedia.bind(navigator.mediaDevices);navigator.mediaDevices.getUserMedia=async c=>{const s=await media(c);window.ownedStreams.push(s);return s;};'''
LABELS=['Kokpit','Göz Sağlığı','Cilt Sağlığı','Diş Sağlığı','İşitme Sağlığı','Ruhsal Sağlık','Uzman & Randevu','Sağlık Geçmişim']
with sync_playwright() as pw:
 b=pw.chromium.launch(channel='chrome',headless=True,args=['--use-fake-device-for-media-stream','--use-file-for-fake-video-capture='+str(Path('audit-fixtures/three-angle.y4m').resolve()),'--autoplay-policy=no-user-gesture-required'])
 c=b.new_context(permissions=['camera'],viewport={'width':1600,'height':1000});c.add_init_script(AUDIO);p=c.new_page();errors=[];p.on('pageerror',lambda e:errors.append(str(e)))
 c.request.post('http://127.0.0.1:8000/api/vehicle/speed',data={'speedKmH':0})
 p.goto('http://127.0.0.1:3000/dental');expect(p.get_by_role('button',name='Kamerayı aç ve taramayı başlat')).to_be_disabled()
 assert p.locator('nav a').all_text_contents()==LABELS
 assert not p.locator('nav a[href="/privacy"]').count()
 footer=p.get_by_role('link',name='Gizlilik & İzinler',exact=True);footer.focus();p.keyboard.press('Enter');expect(p).to_have_url('http://127.0.0.1:3000/privacy');p.go_back();expect(p).to_have_url('http://127.0.0.1:3000/dental')
 p.get_by_label('Kamerayı açıp fotoğraflarımı yalnız bu cihazda geçici işlemeyi kabul ediyorum.').check();p.get_by_role('button',name='Kamerayı aç ve taramayı başlat').click();expect(p.locator('[data-dental-live-video]')).to_be_visible(timeout=30000);p.wait_for_timeout(3000)
 assert not p.locator('[data-dental-result]').count(),'Closed-mouth fixture must not force a dental result'
 p.get_by_role('button',name='İptal et',exact=True).click();assert p.evaluate('window.ownedStreams.every(s=>s.getTracks().every(t=>t.readyState==="ended"))')
 assert 'data:image' not in p.evaluate('JSON.stringify(localStorage)')
 p.screenshot(path=str(OUT/'dental-ready.png'),full_page=True)
 p.goto('http://127.0.0.1:3000/hearing');expect(p.get_by_role('button',name='Ses hazırlığını başlat')).to_be_disabled();p.get_by_label('Yerel ses testi işlemini başlatmayı kabul ediyorum.').check();p.get_by_role('button',name='Ses hazırlığını başlat').click()
 def prepare_channels():
  p.get_by_label('Stereo kulaklık kullanıyorum; mono/speaker kullanmıyorum.').check()
  for ear in ('sol','sağ'):
   checkbox=p.get_by_label('Yalnız '+ear+' kulağımda duydum.');expect(checkbox).to_be_disabled();p.get_by_role('button',name=ear.capitalize()+' kanalı dinle').click();expect(checkbox).to_be_enabled(timeout=10000);checkbox.check()
 prepare_channels()
 signals=p.evaluate('window.signals');assert len(signals)==2
 assert signals[0]['channels'][1]['rms']==0 and signals[0]['channels'][0]['rms']>.006
 assert signals[1]['channels'][0]['rms']==0 and signals[1]['channels'][1]['rms']>.006
 assert all(s['ended'] and max(c['peak'] for c in s['channels'])<=.010001 for s in signals)
 p.get_by_role('button',name='Gürültüde Türkçe sayılar',exact=True).click();answer=p.get_by_role('textbox',name='Üç sayı yanıtı');expect(answer).to_be_enabled(timeout=30000)
 p.get_by_role('button',name='Tekrar · skor dışı',exact=True).click();expect(answer).to_be_enabled(timeout=10000)
 answer.fill('000');p.get_by_role('button',name='Yanıtı gönder',exact=True).click()
 # Synthetic replies exercise every real production transition/playback.
 for i in range(24):
  expect(answer).to_be_enabled(timeout=10000);answer.fill('000');p.get_by_role('button',name='Yanıtı gönder',exact=True).click()
 expect(p.locator('[data-hearing-result]')).to_be_visible(timeout=10000);expect(p.get_by_text('24 geçerli deneme.',exact=False)).to_be_visible();expect(p.get_by_text('Tekrar edilen skor dışı deneme: 1.',exact=True)).to_be_visible()
 signals=p.evaluate('window.signals');assert len(signals)==28 and all(s['ended'] for s in signals)
 for s in signals[2:]:
  assert s['rate']==48000 and s['channels'][0]==s['channels'][1] and 0<s['channels'][0]['peak']<=.080001
  assert s['channels'][0]['first']==0 and s['channels'][0]['last']==0
 assert p.evaluate('window.ownedStreams.length')==0,'Hearing must not open a microphone'
 assert p.evaluate('localStorage.getItem("attune_hearing_history_v1")') is None
 p.get_by_label('Sayısal sonucu bu tarayıcıdaki geçmişe kaydet.').check();p.get_by_role('button',name='Sonucu kaydet',exact=True).click();expect(p.get_by_text('Sayısal sonuç yerel geçmişe kaydedildi.',exact=True)).to_be_visible()
 stored=p.evaluate('JSON.parse(localStorage.getItem("attune_hearing_latest_v1"))');assert stored['validTrials']==24 and stored['repeated']==1 and stored['auditoryAcceptance']=='pending'
 p.screenshot(path=str(OUT/'hearing-result.png'),full_page=True)
 p.evaluate('navigator.mediaDevices.dispatchEvent(new Event("devicechange"))');expect(p.locator('[data-hearing-result]')).to_be_visible();assert len(p.evaluate('window.signals'))==28
 p.get_by_role('button',name='Yeni test',exact=True).click();p.get_by_role('button',name='Ses hazırlığını başlat').click();prepare_channels();p.get_by_role('button',name='Saf ses testi',exact=True).click();p.keyboard.press('Space');p.get_by_role('button',name='Durdur',exact=True).click();count=p.evaluate('window.signals.length');p.wait_for_timeout(4000);assert p.evaluate('window.signals.length')==count
 p.get_by_role('button',name='Ses hazırlığını başlat').click();p.evaluate('navigator.mediaDevices.dispatchEvent(new Event("devicechange"))');expect(p.get_by_text('Ses aygıtı değişti; sol/sağ kanalı yeniden doğrulayın.',exact=True)).to_be_visible()
 assert p.evaluate('localStorage.getItem("attune_hearing_audio_focus")') is None
 # Delay the real AudioContext resume once. Space before node.start must not
 # count as a heard tone: the next actually played level must ascend by 5 dB.
 p.get_by_role('button',name='Ses hazırlığını başlat').click();prepare_channels()
 early_count=p.evaluate('window.signals.length')
 p.evaluate('''()=>{window.originalAudioResume=AudioContext.prototype.resume;window.holdResumeOnce=true;AudioContext.prototype.resume=async function(){if(window.holdResumeOnce){window.holdResumeOnce=false;await new Promise(resolve=>window.releaseAudioResume=resolve);}return window.originalAudioResume.call(this);};}''')
 p.get_by_role('button',name='Saf ses testi',exact=True).click()
 p.wait_for_function('!!window.releaseAudioResume',timeout=20000)
 assert p.evaluate('window.signals.length')==early_count
 p.keyboard.press('Space');p.keyboard.press('Space')
 p.evaluate('window.releaseAudioResume()')
 p.wait_for_function('(n)=>window.signals.length>=n+2',arg=early_count,timeout=30000)
 early_tones=p.evaluate('(n)=>window.signals.slice(n,n+2)',early_count)
 assert abs(max(ch['peak'] for ch in early_tones[0]['channels'])-10**(-60/20))<1e-7
 assert abs(max(ch['peak'] for ch in early_tones[1]['channels'])-10**(-55/20))<1e-7
 p.get_by_role('button',name='Durdur',exact=True).click()
 p.evaluate('()=>{AudioContext.prototype.resume=window.originalAudioResume;}')
 # Full two-ear pure-tone UI. Virtualize only waiting timers; each production
 # AudioBuffer must really finish. No-response simulation cannot establish a
 # human threshold, and all fourteen outputs must explicitly stay unavailable.
 p.get_by_role('button',name='Ses hazırlığını başlat').click();prepare_channels();before_tones=p.evaluate('window.signals.length');p.clock.install();p.get_by_role('button',name='Saf ses testi',exact=True).click()
 for _ in range(240):
  if p.locator('[data-hearing-result]').count():break
  p.wait_for_function('window.signals.every(s=>s.ended)',timeout=5000)
  # Keep the actual backend telemetry round-trip in each accelerated step.
  # Advancing again while fetch is pending would fabricate its 5s timeout.
  with p.expect_response('http://localhost:8000/api/vehicle/state',timeout=10000) as telemetry:
   p.clock.fast_forward(2700)
  assert telemetry.value.status==200 and telemetry.value.json()['vehicleParked'] is True
  expect(p.locator('[data-vehicle-status]')).to_have_text('PARK')
 expect(p.locator('[data-hearing-result]')).to_be_visible(timeout=5000)
 expect(p.get_by_text('Üst cihaz sınırında eşik bulunamadı',exact=False)).to_have_count(14)
 actual_tones=p.evaluate('(n)=>window.signals.slice(n)',before_tones);assert len(actual_tones)==98
 assert all(max(ch['peak'] for ch in s['channels'])<=10**(-30/20)+1e-7 for s in actual_tones)
 assert all((s['channels'][0]['rms']==0)!=(s['channels'][1]['rms']==0) for s in actual_tones)
 p.screenshot(path=str(OUT/'hearing-pure-tone-result.png'),full_page=True)
 p.clock.resume()
 p.goto('http://127.0.0.1:3000/privacy');p.get_by_role('button',name='TÜM YEREL VERİLERİ SİL',exact=True).click();p.get_by_role('button',name='Evet, Tüm Verileri Sil',exact=True).click();expect(p.get_by_text('Tüm yerel veriler başarıyla temizlendi.',exact=True)).to_be_visible(timeout=30000)
 assert p.evaluate('Object.keys(localStorage).filter(k=>/attune_(dental|hearing)_(history|latest)/.test(k)).length')==0
 p.set_viewport_size({'width':600,'height':900});p.goto('http://127.0.0.1:3000/hearing');assert p.evaluate('document.documentElement.scrollWidth<=innerWidth')
 for label in LABELS:
  link=p.locator('nav').get_by_role('link',name=label,exact=True);link.focus();assert link.evaluate('(e)=>{const r=e.getBoundingClientRect();return r.left>=0&&r.right<=innerWidth;}')
 p.screenshot(path=str(OUT/'navigation-narrow.png'),full_page=True)
 assert not errors,errors
 proof={'status':'PASS','productionUI':True,'syntheticDigitReplies':True,'humanHearingAcceptance':False,'physicalCamera':False,'clinicalValidation':False,'digitTrials':24,'replayExcluded':1,'actualPCM':signals,'pureToneTrials':actual_tones,'pureToneTimerSimulation':True,'pureToneNoResponseSimulation':True,'pureToneUnavailableResults':14,'cameraCancelTracksEnded':True,'newHistoryWiped':True,'navigationLabels':LABELS,'pageErrors':errors}
 proof['buildId']=Path('apps/vehicle-app/.next/BUILD_ID').read_text().strip()
 proof['actualTelemetryAwaitedEachVirtualStep']=True
 proof['earlySpaceBeforeActualAudioStartRejected']=True
 proof['earlyReplyFaultInjectionToneLevelsDbFS']=[-60,-55]
 (OUT/'proof.json').write_text(json.dumps(proof,indent=2),'utf8');c.close();b.close()
print('PASS production navigation, dental cancellation, real PCM stereo and 24 DIN UI trials, deletion')

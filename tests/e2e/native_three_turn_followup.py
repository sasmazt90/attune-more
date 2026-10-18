"""Linux OS microphone and native Turkish STT and production MPEG playback (explicit tone fixture), one start and three turns.
Generated non-personal PCM is played only into the isolated audit_mic sink.
Native results/events are observed, never replaced; CI remains keyless.
"""
import json,os,subprocess,time
from pathlib import Path
from playwright.sync_api import sync_playwright,expect
OUT=Path('audit-results/native-three-turn');OUT.mkdir(parents=True,exist_ok=True)
TEXTS=['Bugün yeni bir kitap okudum.','Bugün yeni bir film izledim.','Bugün yeni bir şarkı dinledim.']
for i,text in enumerate(TEXTS):
    subprocess.run(['espeak-ng','-v','tr','-s','135','-w',str(OUT/f'original-{i}.wav'),text],check=True)
    subprocess.run(['ffmpeg','-hide_banner','-loglevel','error','-y','-i',str(OUT/f'original-{i}.wav'),'-ar','48000','-ac','1','-c:a','pcm_s16le',str(OUT/f'input-{i}.wav')],check=True)
INIT=r'''(()=>{window.nativeProof={stt:[],tts:[]};const SR=window.SpeechRecognition||window.webkitSpeechRecognition;if(SR){const W=function(){const r=new SR();window.currentNativeRecognition=r;r.audioStarted=false;for(const type of ['start','audiostart','soundstart','speechstart','speechend','soundend','audioend','nomatch','result','error','end'])r.addEventListener(type,e=>{if(type==='audiostart')r.audioStarted=true;if(type==='end'||type==='error')r.audioStarted=false;window.nativeProof.stt.push({type,time:performance.now(),error:e.error||null,transcript:e.results?.[e.resultIndex]?.[0]?.transcript||null});});return r;};window.SpeechRecognition=W;window.webkitSpeechRecognition=W;}const play=HTMLMediaElement.prototype.play;HTMLMediaElement.prototype.play=function(){for(const type of ['playing','ended','error'])this.addEventListener(type,e=>window.nativeProof.tts.push({type,time:performance.now(),error:e.error||null}));return play.call(this);};})();'''
with sync_playwright() as pw:
    browser=pw.chromium.launch(channel='chromium',headless=False,args=['--enable-speech-dispatcher','--autoplay-policy=no-user-gesture-required'])
    context=browser.new_context(permissions=['microphone'],locale='tr-TR');context.add_init_script(INIT)
    context.route('**/api/mental/speech',lambda r:r.fulfill(content_type='audio/mpeg',body=Path('tests/fixtures/synthetic-tone.mp3').read_bytes()))
    context.request.post('http://localhost:8000/api/vehicle/speed',data={'speedKmH':0})
    page=context.new_page();requests=[];page.on('request',lambda r:requests.append(r.post_data_json) if r.url.endswith('/mental/converse') else None)
    try:
        page.goto('http://localhost:3000/mental?demo=1')
        page.get_by_role('checkbox',name='TOGG Attune hizmet onayı',exact=True).check();page.get_by_role('button',name='Görüşmeyi Başlat',exact=True).click()
        for i in range(3):
            expect(page.locator('[data-conversation-phase]')).to_have_attribute('data-conversation-phase','listening',timeout=20000)
            page.wait_for_function('window.currentNativeRecognition?.audioStarted===true',timeout=20000)
            page.wait_for_timeout(600)
            subprocess.run(['paplay','--device=audit_mic',str(OUT/f'input-{i}.wav')],check=True)
            expect(page.locator('[data-chat-author="USER"]')).to_have_count(i+1,timeout=25000)
            expect(page.locator('[data-chat-author="AI"]')).to_have_count(i+1,timeout=30000)
            page.wait_for_function('(n)=>window.nativeProof.tts.filter(e=>e.type==="ended").length===n',arg=i+1,timeout=60000)
            assert page.evaluate('localStorage.getItem("togg_health_mental_history")') is None
        page.get_by_role('button',name='Görüşmeyi Bitir',exact=True).click();expect(page.locator('[data-conversation-phase]')).to_have_attribute('data-conversation-phase','completed')
        page.wait_for_timeout(1200);assert page.locator('[data-live-transcript]').count()==0
        assert [len(r['history']) for r in requests]==[0,2,4]
        assert page.evaluate('localStorage.getItem("togg_health_mental_history")') is None # Explicit demo never persists a personal summary.
        proof=page.evaluate('window.nativeProof');assert len([e for e in proof['stt'] if e['type']=='result'])==3
        assert len({e['transcript'] for e in proof['stt'] if e['type']=='result'})==3
        assert len([e for e in proof['tts'] if e['type']=='playing'])==3
        starts=[e['time'] for e in proof['stt'] if e['type']=='start'];plays=[e['time'] for e in proof['tts'] if e['type']=='playing'];ends=[e['time'] for e in proof['tts'] if e['type']=='ended'];assert len(ends)==3 and all(not any(a<=t<=z for t in starts) for a,z in zip(plays,ends))
        (OUT/'results.json').write_text(json.dumps({'status':'PASS','events':proof,'provider':'LOCAL_DEMO','ttsTransportFixture':'synthetic-tone','exactVoiceAcceptance':False,'openAIKeyUsed':False},ensure_ascii=False,indent=2),encoding='utf-8')
        page.screenshot(path=str(OUT/'completed.png'),full_page=True)
    except Exception:
        (OUT/'failure-events.json').write_text(json.dumps({'status':'FAIL','events':page.evaluate('window.nativeProof'),'phase':page.locator('[data-conversation-phase]').get_attribute('data-conversation-phase'),'voiceState':page.locator('[data-voice-state]').get_attribute('data-voice-state'),'historyLengths':[len(r['history']) for r in requests]},ensure_ascii=False,indent=2),encoding='utf-8')
        page.screenshot(path=str(OUT/'failure.png'),full_page=True)
        raise
    finally:context.close();browser.close()
print('PASS: one start, three real native STT turns with real MPEG events; synthetic output fixture, history 0/2/4, no duplicate or post-finish restart')

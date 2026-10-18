"""Isolated real product UI/API/MediaPipe; disclosed local canvas camera controls.

The controlled stream switches between two recorded development photographs.
It tests removal-state handling, not a physical same-person glasses removal or
natural-camera accuracy. No landmarks, API scores or model answers are mocked.
"""
import json,time,base64,hashlib,subprocess,math
from pathlib import Path
from heavy_job_lease import HeavyJobLease
ROOT=Path(__file__).resolve().parents[2];DATA=ROOT/'audit-results/material-closeout-20261013';OUT=ROOT/'output/playwright/material-closeout-20261014';OUT.mkdir(parents=True,exist_ok=True)
PROFILE=OUT/('isolated-'+str(time.time_ns()))
# The first real MediaPipe browser run stopped at 561.6 MiB private, above
# the 550 MiB estimate (2.79 GiB still available). Budget the measured browser
# plus its local utility process explicitly; retain the 400 MiB hard reserve
# and require more free RAM before starting this larger owned process tree.
with HeavyJobLease('CDC-eyewear-product-browser',peak_mib=850,minimum_available_mib=1400,include_children=True,memory_metric='private') as lease:
    from playwright.sync_api import sync_playwright,expect
    subprocess.run(['C:/nvm4w/nodejs/node.exe','scripts/skin-research/bundle_periorbital_browser.cjs'],cwd=ROOT,check=True,capture_output=True)
    bundle=(ROOT/'.runtime/periorbital-v5-browser-support/utilities.js').read_text('utf8')
    glass=json.loads((ROOT/'audit-results/dry-sag-component-followup-20261013/product/9bab7ab2/9bab7ab2-automatic-payload.json').read_text('utf8'))['photo']
    clear='data:image/png;base64,'+base64.b64encode((DATA/'0642-camera-source.png').read_bytes()).decode()
    injection="""window.__scanRequests=[];window.__scanResponses=[];window.__scanTiming=[];window.__eyeChecks=[];window.__voice=[];
window.addEventListener('attune-guidance-event',e=>__voice.push(e.detail));
const originalFetch=window.fetch;window.fetch=async(...args)=>{const started=performance.now(),url=String(args[0]),scan=url.endsWith('/api/local-health/skin'),eye=url.endsWith('/skin/capture-check');
if(scan){const p=JSON.parse(args[1].body);if(p.hostedProcessingConsent!==false)throw Error('UNEXPECTED_HOSTED_CONSENT');__scanRequests.push(p);}
const r=await originalFetch(...args);if(r.ok&&(scan||eye)){const d=await r.clone().json();(scan?__scanResponses:__eyeChecks).push(d);}if(scan)__scanTiming.push({seconds:(performance.now()-started)/1000,status:r.status});return r;};
const gum=navigator.mediaDevices.getUserMedia.bind(navigator.mediaDevices);
navigator.mediaDevices.getUserMedia=async constraints=>{if(!constraints.video)return gum(constraints);
const im=await Promise.all(IMAGES.map(src=>new Promise((resolve,reject)=>{const i=new Image();i.onload=()=>resolve(i);i.onerror=reject;i.src=src;})));
const c=document.createElement('canvas');c.width=c.height=640;const x=c.getContext('2d');let selected=0;
const stream=c.captureStream(30);window.__controlledCamera={kind:'licensed development canvas stream; no physical acceptance',showClear:()=>selected=1,settings:()=>stream.getVideoTracks()[0].getSettings()};
function draw(){x.drawImage(im[selected],0,0);if(stream.getVideoTracks()[0].readyState==='live')requestAnimationFrame(draw);}draw();return stream;};
""".replace('IMAGES',json.dumps([glass,clear]))
    errors=[];proof={}
    def progress(phase):
        (DATA/'eyewear-browser-progress.json').write_text(json.dumps(dict(phase=phase,time=time.time(),profile=str(PROFILE.relative_to(ROOT)),proof=proof,pageErrors=errors),ensure_ascii=False,indent=2),'utf8')
        print(json.dumps(dict(phase=phase)),flush=True)
    with sync_playwright() as pw:
        context=pw.chromium.launch_persistent_context(str(PROFILE),channel='chrome',headless=False,viewport=dict(width=1600,height=1000),args=['--window-size=1600,1000','--enable-unsafe-swiftshader'])
        try:
            context.add_init_script(injection);page=context.pages[0] if context.pages else context.new_page();page.on('pageerror',lambda e:errors.append(str(e)))
            page.goto('http://127.0.0.1:3000/privacy')
            expect(page.get_by_label('Cilt tipi için yüz fotoğrafımın Roboflow tarafından işlenmesine izin ver',exact=True)).not_to_be_checked()
            for label in ['Cilt ölçümlerini ve kişisel sayısal referansı bu tarayıcıda sakla','Yeni cilt kayıtlarının fotoğraflarını bu cihazda sakla']:
                box=page.get_by_label(label,exact=True)
                if not box.is_checked():
                    # Photo permission is committed inside the existing async
                    # records lock; wait for its real controlled state update.
                    box.click();expect(box).to_be_checked()
            page.goto('http://127.0.0.1:3000/skin')
            expect(page.get_by_text('Gözlüğünüzü çıkarın. Kameraya doğru bakın ve başınızı sabit tutun.',exact=True)).to_be_visible()
            page.get_by_role('button',name='Cilt taraması hakkında bilgi',exact=True).click();page.get_by_label('Üç açılı tarama',exact=True).uncheck();page.get_by_role('button',name='Bilgi penceresini kapat',exact=True).click()
            page.get_by_role('button',name='Analizi Başlat',exact=True).click();started=time.monotonic()
            progress('actual-camera-started')
            deadline=time.monotonic()+90
            while time.monotonic()<deadline:
                lease.check()
                if page.get_by_text('Cilt analizi için gözlüğünüzü çıkarın',exact=True).count() and page.evaluate('__eyeChecks.length>=3'):break
                page.wait_for_timeout(300)
            expect(page.get_by_text('Cilt analizi için gözlüğünüzü çıkarın',exact=True)).to_be_visible()
            blocked=page.evaluate("({requests:__scanRequests.length,records:JSON.parse(localStorage.getItem('togg_health_skin_history')||'[]').length,checks:__eyeChecks,canvas:{...document.querySelector('canvas').dataset},track:__controlledCamera.settings()})")
            assert blocked['requests']==0 and blocked['records']==0
            assert blocked['canvas']['skinEyewearState']=='EYEWEAR_PRESENT'
            proof['blocked']=blocked;progress('actual-glasses-blocked')
            page.screenshot(path=str(OUT/'glasses-blocked-desktop.png'),full_page=True)
            page.evaluate('__controlledCamera.showClear()');clear_at=time.monotonic()
            deadline=time.monotonic()+120
            while time.monotonic()<deadline and not page.get_by_text('Cilt Analizi Tamamlandı',exact=True).count():
                lease.check();page.wait_for_timeout(400)
            expect(page.get_by_text('Cilt Analizi Tamamlandı',exact=True)).to_be_visible()
            actual=page.evaluate("({requests:__scanRequests,responses:__scanResponses,timing:__scanTiming,checks:__eyeChecks,voice:__voice,record:JSON.parse(localStorage.getItem('togg_health_latest_skin'))})")
            assert len(actual['requests'])==len(actual['responses'])==1 and actual['record']['usedMediaPipe']
            response=actual['responses'][0];record=actual['record'];identity=response['photoId']
            assert identity==actual['requests'][0]['photoId']==record['captures']['FRONT']['captureId']
            assert response['captureScopeVersion']=='glasses-free-skin-capture-v1'
            assert all(v['captureConditions']['skinCapturePolicy']==response['captureScopeVersion'] for rows in response['measurements'].values() for v in rows)
            proof['voiceEvents']=actual['voice'];progress('actual-result-received')
            (DATA/'new-camera-normal-payload.json').write_text(json.dumps(actual['requests'][0]),'utf8');(DATA/'new-camera-normal-result.json').write_text(json.dumps(response),'utf8')
            voice_count=sum(e['id']=='skin-front' and e['event']=='playing' for e in actual['voice']);assert voice_count==1,actual['voice']
            page.screenshot(path=str(OUT/'clear-source-result-desktop.png'),full_page=True)
            (DATA/'new-camera-normal-payload.json').write_text(json.dumps(actual['requests'][0]),'utf8');(DATA/'new-camera-normal-result.json').write_text(json.dumps(response),'utf8')
            proof.update(blocked=blocked,resumedAfterActualClearSeconds=time.monotonic()-clear_at,normalSkinHTTP=actual['timing'],voiceStartCount=voice_count,actualPhotoId=identity,newRecordId=record['id'],normalization={region:{r['id']:r.get('normalizationVersion') for r in rows} for region,rows in response['measurements'].items()},sourceSize=[response['sourceWidth'],response['sourceHeight']],hostedRequests=sum(p['hostedProcessingConsent'] for p in actual['requests']))
            page.goto('http://127.0.0.1:3000/profile');before=page.evaluate('localStorage.getItem("togg_health_skin_history")')
            page.locator('[data-record-id="'+record['id']+'"]').get_by_role('button',name='Sonucu Aç',exact=True).click()
            dialog=page.get_by_role('dialog',name='Cilt Sağlığı sonucu',exact=True);expect(dialog.locator('[data-skin-snapshot]')).to_be_visible()
            dialog.locator('[data-skin-record-indicator="tone"]').click();fill=dialog.locator('[data-skin-local-fill="tone"]');expect(fill).to_be_visible();assert fill.get_attribute('data-map-photo')==identity
            dialog.get_by_role('button',name='Sonraki Bölge',exact=True).click();assert dialog.locator('[data-skin-local-fill="tone"]').count()==0
            page.screenshot(path=str(OUT/'new-record-history-desktop.png'),full_page=True)
            page.set_viewport_size(dict(width=720,height=900));assert page.evaluate('document.documentElement.scrollWidth<=innerWidth');page.screenshot(path=str(OUT/'new-record-history-narrow.png'),full_page=True)
            assert before==page.evaluate('localStorage.getItem("togg_health_skin_history")')
            page.add_script_tag(content=bundle)
            comparisons=page.evaluate("""record=>{const I=__auditRequire('apps/vehicle-app/src/utils/skinIndicators.ts'),H=__auditRequire('apps/vehicle-app/src/utils/healthHistorySeries.ts');const old=structuredClone(record);old.id='isolated-legacy-scope';for(const rows of [...Object.values(old.indicators),old.general.indicators])for(const r of rows){delete r.appearance.captureConditions.skinCapturePolicy;delete r.appearance.captureConditions.skinEyewearModelHash;}return ['overview','chin'].map(scope=>{const row=r=>(scope==='overview'?r.general.indicators:r.indicators.chin).find(x=>x.id==='dry');return {scope,comparable:I.canCompareIndicator(row(record),row(old)),series:H.buildHistorySeries('skin',[old,record]).filter(s=>s.criterion==='dry'&&s.region===scope).length};});}""",record)
            assert all(not r['comparable'] and r['series']==2 for r in comparisons)
            proof.update(historyUnchanged=before==page.evaluate('localStorage.getItem("togg_health_skin_history")'),historySHA256=hashlib.sha256(before.encode()).hexdigest(),scopeComparisons=comparisons,mapClearedOnRegionChange=dialog.locator('[data-skin-local-fill="tone"]').count()==0)
        finally:
            progress('first-browser-closed');context.close()
        pref=PROFILE/'Default/Preferences';settings=json.loads(pref.read_text('utf8'));settings.setdefault('partition',{})['default_zoom_level']={'x':math.log(2)/math.log(1.2)};pref.write_text(json.dumps(settings),'utf8')
        context=pw.chromium.launch_persistent_context(str(PROFILE),channel='chrome',headless=False,viewport=None,no_viewport=True,args=['--window-size=1600,1000','--enable-unsafe-swiftshader'])
        try:
            page=context.pages[0] if context.pages else context.new_page();page.goto('http://127.0.0.1:3000/profile');page.locator('[data-record-id="'+proof['newRecordId']+'"]').get_by_role('button',name='Sonucu Aç',exact=True).click();expect(page.get_by_role('dialog',name='Cilt Sağlığı sonucu',exact=True).locator('[data-skin-snapshot]')).to_be_visible()
            geometry=page.evaluate('({innerWidth,outerWidth,dpr:devicePixelRatio,zoom:getComputedStyle(document.documentElement).zoom,scroll:document.documentElement.scrollWidth})')
            assert geometry['dpr']>=2 and geometry['innerWidth']<geometry['outerWidth']*.65 and geometry['zoom']=='1' and geometry['scroll']<=geometry['innerWidth']
            page.screenshot(path=str(OUT/'new-record-history-native200.png'),full_page=True);proof['native200']=geometry
        finally:context.close()
    proof.update(buildId=(ROOT/'apps/vehicle-app/.next/BUILD_ID').read_text('utf8').strip(),profile=str(PROFILE.relative_to(ROOT)),resource=lease.receipt(),pageErrors=errors,normalUserProfileTouched=False,physicalCameraAccuracyTest=False)
    assert not errors
    (DATA/'eyewear-product-browser.json').write_text(json.dumps(proof,ensure_ascii=False,indent=2),'utf8');print(json.dumps(dict(buildId=proof['buildId'],blockedRequests=proof['blocked']['requests'],blockedRecords=proof['blocked']['records'],newRecordId=proof['newRecordId'],voiceStartCount=proof['voiceStartCount'],scopeComparisons=proof['scopeComparisons'])),flush=True)

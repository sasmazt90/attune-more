"""Real production worker timings and cancellation; no model response mocks."""
import json, time
from pathlib import Path
from playwright.sync_api import sync_playwright, expect

OUT=Path('audit-results/remediation-20261005/preparation');OUT.mkdir(parents=True,exist_ok=True)
INIT="""window.workerEvents=[];window.cameraTracks=[];window.animationFrames=0;const tick=()=>{window.animationFrames++;requestAnimationFrame(tick)};requestAnimationFrame(tick);
const get=navigator.mediaDevices.getUserMedia.bind(navigator.mediaDevices);navigator.mediaDevices.getUserMedia=async(...a)=>{const s=await get(...a);window.cameraTracks.push(...s.getTracks());return s;};
const post=Worker.prototype.postMessage;Worker.prototype.postMessage=function(m,...a){window.workerEvents.push({type:m.type,id:m.id,at:performance.now()});if(!this.observed){this.observed=true;this.addEventListener('message',e=>{const {segmentation,...data}=e.data;window.workerEvents.push({reply:true,at:performance.now(),...data,...(segmentation?{loadMs:segmentation.loadMs,inferenceMs:segmentation.elapsedMs,refinementMs:segmentation.refinementMs,refinementBytes:segmentation.refinementBytes}: {})});});}if(m.type==='initializeSegmentation'&&window.deferPreparation){window.releasePreparation=()=>{window.deferPreparation=false;post.call(this,m,...a);};return;}return post.call(this,m,...a);};"""
rows=[]
with sync_playwright() as pw:
    browser=pw.chromium.launch(channel='chromium',headless=True,args=['--use-fake-device-for-media-stream','--use-file-for-fake-video-capture='+str(Path('audit-fixtures/digital-detail.y4m').resolve()),'--use-gl=angle','--use-angle=swiftshader','--enable-unsafe-swiftshader'])
    for deferred in [False]:
      for repetition in range(2):
        c=browser.new_context(permissions=['camera'],viewport={'width':1600,'height':1000});c.add_init_script(INIT+f'window.deferPreparation={str(deferred).lower()};');p=c.new_page();errors=[];p.on('pageerror',lambda e:errors.append(str(e)))
        c.request.post('http://localhost:8000/api/vehicle/speed',data={'speedKmH':0});p.goto('http://localhost:3000/skin')
        p.get_by_role('button',name='Cilt taraması hakkında bilgi',exact=True).click();p.get_by_role('checkbox',name='Üç açılı tarama',exact=True).uncheck();p.keyboard.press('Escape')
        click=time.perf_counter();p.get_by_role('button',name='Analizi Başlat',exact=True).click()
        expect(p.locator('[data-portrait-preparation]')).to_be_visible(timeout=60000)
        start=p.evaluate('animationFrames');p.screenshot(path=str(OUT/f'waiting-{deferred}-{repetition}.png'),full_page=True)
        # Release the real model only at accepted-frame preparation in the
        # controlled deferred variant. No fake progress/result is inserted.
        if deferred:p.evaluate('releasePreparation()')
        expect(p.get_by_text('Cilt Analizi Tamamlandı',exact=True)).to_be_visible(timeout=60000)
        assert p.evaluate('animationFrames')>start+2,'UI must continue repainting during preparation'
        assert p.evaluate('cameraTracks.every(t=>t.readyState==="ended")')
        (OUT/f'worker-events-{repetition}.json').write_text(json.dumps(p.evaluate('workerEvents'),indent=2),encoding='utf-8')
        expect(p.locator('[data-skin-snapshot]')).to_be_visible()
        events=p.evaluate('workerEvents');assert len([e for e in events if e.get('type')=='initializeSegmentation'])==1,'One preparation request per worker'
        result=p.evaluate('JSON.parse(localStorage.getItem("togg_health_latest_skin"))');assert result['quality']['isValid']
        assert not errors,errors
        rows.append({'deferredUntilAcceptedFrame':deferred,'repetition':repetition,'clickToResultMs':(time.perf_counter()-click)*1000,'events':events,'repaintsDuringPreparation':p.evaluate('animationFrames')-start,'controlledFixture':True})
        c.close()
    # Cancel during the real cold MODEL wait, then allow the actual model to
    # finish. Late output must not write a snapshot, reference or result.
    c=browser.new_context(permissions=['camera']);c.add_init_script(INIT+'window.deferPreparation=true;');p=c.new_page();p.goto('http://localhost:3000/skin');p.get_by_role('button',name='Cilt taraması hakkında bilgi',exact=True).click();p.get_by_role('checkbox',name='Üç açılı tarama',exact=True).uncheck();p.keyboard.press('Escape');p.get_by_role('button',name='Analizi Başlat',exact=True).click();expect(p.locator('[data-portrait-preparation="MODEL"]')).to_be_visible(timeout=60000)
    before=p.evaluate('JSON.stringify(Object.fromEntries(Object.entries(localStorage)))');p.get_by_role('button',name='Taramayı İptal Et',exact=True).click();p.evaluate('releasePreparation()');expect(p.get_by_role('button',name='Analizi Başlat',exact=True)).to_be_visible();p.wait_for_function('cameraTracks.every(t=>t.readyState==="ended")');p.wait_for_function('workerEvents.some(e=>e.reply&&e.ready&&e.id===workerEvents.filter(v=>v.type==="initializeSegmentation").at(-1).id)',timeout=30000);p.wait_for_timeout(1500)
    assert p.evaluate('JSON.stringify(Object.fromEntries(Object.entries(localStorage)))')==before
    assert p.locator('[data-skin-snapshot]').count()==0 and p.locator('[data-portrait-preparation]').count()==0
    c.close();browser.close()
(OUT/'measurements.json').write_text(json.dumps({'runs':rows,'cancelDuringModelWait':'PASS','paidCalls':0,'physicalCapture':0,'buildId':Path('apps/vehicle-app/.next/BUILD_ID').read_text().strip()},indent=2),encoding='utf-8')
print('PASS actual model timings, repainting, single warmup, cold cancellation without late writes')

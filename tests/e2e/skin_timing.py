from vehicle_controls import toggle_vehicle, vehicle_status
"""Controlled trace-on/off measurements; fixed functional assertions stay intact."""
import json
import os
from pathlib import Path
import time
from playwright.sync_api import sync_playwright, expect

BASE=os.environ.get('ATTUNE_AUDIT_BASE','http://localhost:3000')
API=os.environ.get('ATTUNE_API_BASE','http://localhost:8000')
OUT=Path(os.environ.get('ATTUNE_TIMING_OUT','audit-results/skin-timing'))
OUT.mkdir(parents=True,exist_ok=True)
INIT='''(()=>{window.timing={tracks:[],longTasks:[],draw:0};new PerformanceObserver(list=>window.timing.longTasks.push(...list.getEntries().map(e=>({start:e.startTime,duration:e.duration})))).observe({type:'longtask',buffered:true});const g=navigator.mediaDevices.getUserMedia.bind(navigator.mediaDevices);navigator.mediaDevices.getUserMedia=async(...a)=>{const s=await g(...a);window.timing.tracks.push(...s.getTracks());return s;};const draw=CanvasRenderingContext2D.prototype.drawImage;CanvasRenderingContext2D.prototype.drawImage=function(...a){window.timing.draw++;return draw.apply(this,a);};})()'''
rows=[]
with sync_playwright() as pw:
    browser=pw.chromium.launch(channel='chromium',headless=True,args=[
        '--use-fake-device-for-media-stream','--use-file-for-fake-video-capture='+str(Path('audit-fixtures/face.y4m').resolve()),
        '--use-gl=angle','--use-angle=swiftshader','--enable-unsafe-swiftshader'])
    for trace in [False,True]:
        for kind in ['demo','driving']:
            for repetition in range(2):
                context=browser.new_context(permissions=['camera'],viewport={'width':1600,'height':1000})
                context.add_init_script(INIT)
                if trace:context.tracing.start(screenshots=True,snapshots=True,sources=True)
                page=context.new_page();errors=[];page.on('pageerror',lambda e:errors.append(str(e)))
                assert context.request.post(API+'/api/vehicle/speed',data={'speedKmH':0}).ok
                page.goto(BASE+('/skin?demo=1' if kind=='demo' else '/skin'))
                expect(vehicle_status(page)).to_contain_text('PARK')
                t0=time.perf_counter()
                (page.get_by_role('button',name='Cilt taraması hakkında bilgi',exact=True).click(), page.get_by_role('checkbox',name='Üç açılı tarama',exact=True).uncheck(), page.keyboard.press('Escape'));page.get_by_role('button',name='Analizi Başlat',exact=True).click()
                try:
                    if kind=='demo':
                        page.wait_for_function('localStorage.getItem("attune_demo_skin_result")!==null',timeout=12000)
                        assert not page.evaluate('localStorage.getItem("togg_health_latest_skin")')
                        assert page.evaluate('JSON.parse(localStorage.getItem("attune_demo_skin_result")).usedMediaPipe') is False
                    else:
                        page.wait_for_function('window.timing.tracks.some(t=>t.readyState==="live")')
                        # Do not let a never-started camera satisfy the stop assertion.
                        page.wait_for_function('window.timing.draw>0')
                        t0=time.perf_counter()
                        toggle_vehicle(page)
                        expect(page.get_by_text('Cilt Kontrolü Kilitlendi',exact=True)).to_be_visible()
                        page.wait_for_function('window.timing.tracks.every(t=>t.readyState==="ended")')
                    row={'status':'PASS'}
                except Exception as error:row={'status':'FAIL','error':str(error)}
                row.update(trace=trace,kind=kind,repetition=repetition,seconds=time.perf_counter()-t0,
                    telemetry=page.evaluate('({longTasks:window.timing.longTasks,draw:window.timing.draw,tracks:window.timing.tracks.map(t=>t.readyState)})'),errors=errors)
                rows.append(row);print(json.dumps(row),flush=True)
                if trace:context.tracing.stop(path=str(OUT/f'{kind}-{repetition}.zip'))
                assert context.request.post(API+'/api/vehicle/speed',data={'speedKmH':0}).ok
                context.close()
    browser.close()
(OUT/'timings.json').write_text(json.dumps(rows,indent=2))
raise SystemExit(1 if any(r['status']=='FAIL' or r['errors'] for r in rows) else 0)

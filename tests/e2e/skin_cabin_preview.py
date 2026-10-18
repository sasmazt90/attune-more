"""Actual production camera/model with licensed small-face pixels.
Controlled fixture, no physical user acceptance, no model/gate substitutions.
Use the real three-pose flow; the fixed front fixture naturally waits for a side
pose, allowing preview inspection and cancellation without a gate override.
"""
import json,math,tempfile,base64
from pathlib import Path
from playwright.sync_api import sync_playwright,expect
OUT=Path('audit-results/vision-physical-20261007/skin-cabin');OUT.mkdir(parents=True,exist_ok=True)
INIT="""window.previewAlignments=[];window.previewStreams=[];
const gum=navigator.mediaDevices.getUserMedia.bind(navigator.mediaDevices);navigator.mediaDevices.getUserMedia=async(...args)=>{const s=await gum(...args);window.previewStreams.push(s);return s};
const post=Worker.prototype.postMessage;Worker.prototype.postMessage=function(m,...args){if(!this.previewObserved){this.previewObserved=true;this.addEventListener('message',e=>{if(e.data.alignment)window.previewAlignments.push(e.data.alignment);});}return post.call(this,m,...args);};"""
rows=[]
with sync_playwright() as pw:
 for zoom in [1,2]:
  with tempfile.TemporaryDirectory(prefix='attune-cabin-') as profile:
   pref=Path(profile)/'Default';pref.mkdir();(pref/'Preferences').write_text(json.dumps({'partition':{'default_zoom_level':{'x':math.log(zoom)/math.log(1.2)}}}),encoding='utf8')
   c=pw.chromium.launch_persistent_context(profile,channel='chrome',headless=False,no_viewport=True,permissions=['camera'],args=['--window-size=1280,900','--use-fake-device-for-media-stream','--use-file-for-fake-video-capture='+str(Path('audit-fixtures/cabin-small-face.y4m').resolve()),'--enable-unsafe-swiftshader'])
   try:
    c.add_init_script(INIT);p=c.new_page();errors=[];p.on('pageerror',lambda e:errors.append(str(e)))
    c.request.post('http://127.0.0.1:8000/api/vehicle/speed',data={'speedKmH':0});p.goto('http://127.0.0.1:3000/skin')
    p.get_by_role('button',name='Cilt taraması hakkında bilgi',exact=True).click();p.get_by_role('checkbox',name='Üç açılı tarama',exact=True).check();p.get_by_role('button',name='Bilgi penceresini kapat',exact=True).click()
    p.get_by_role('button',name='Analizi Başlat',exact=True).click()
    p.wait_for_function('previewAlignments.some(a=>a.landmarks?.length>=468)',timeout=45000)
    p.locator('[data-skin-live-landmarks] circle').first.wait_for(state='attached')
    geometry=p.locator('[data-skin-live-video]').evaluate("""v=>{const panel=v.closest('[data-face-panel]'),b=v.getBoundingClientRect(),s=panel.querySelector('svg').getBoundingClientRect(),circle=panel.querySelector('circle'),q=circle.getBoundingClientRect();return {sourceWidth:v.videoWidth,sourceHeight:v.videoHeight,sourceAspect:v.videoWidth/v.videoHeight,video:b.toJSON(),svg:s.toJSON(),panel:panel.getBoundingClientRect().toJSON(),crop:JSON.parse(panel.dataset.previewCrop),firstPoint:{expectedX:b.x+Number(circle.getAttribute('cx'))/100*b.width,expectedY:b.y+Number(circle.getAttribute('cy'))/100*b.height,actualX:q.x+q.width/2,actualY:q.y+q.height/2},viewport:{innerWidth,innerHeight,dpr:devicePixelRatio,scrollWidth:document.documentElement.scrollWidth,cssZoom:getComputedStyle(document.documentElement).zoom}}}""")
    a=p.evaluate('previewAlignments.at(-1)');assert a['sourceFramed'] and a['scaleRatio']<.28,{k:a[k] for k in ['sourceFramed','scaleRatio','isAligned']}
    assert geometry['crop']['width']<.8 and geometry['crop']['height']<.8,geometry
    assert abs(geometry['video']['width']/geometry['video']['height']-geometry['sourceAspect'])<.01
    assert abs(geometry['svg']['x']-geometry['video']['x'])<.1 and abs(geometry['svg']['width']-geometry['video']['width'])<.1
    assert abs(geometry['firstPoint']['expectedX']-geometry['firstPoint']['actualX'])<.2
    assert abs(geometry['firstPoint']['expectedY']-geometry['firstPoint']['actualY'])<.2
    assert geometry['viewport']['scrollWidth']<=geometry['viewport']['innerWidth']+1
    assert geometry['sourceWidth']==640 and geometry['sourceHeight']==480
    p.locator('[data-face-panel]').evaluate("e=>e.scrollIntoView({block:'center',behavior:'instant'})");raw=c.new_cdp_session(p).send('Page.captureScreenshot',{'format':'png','fromSurface':False})['data'];(OUT/f'preview-{zoom}.png').write_bytes(base64.b64decode(raw))
    p.get_by_role('button',name='Taramayı İptal Et',exact=True).click();p.wait_for_function('previewStreams.every(s=>s.getTracks().every(t=>t.readyState==="ended"))')
    assert not errors,errors;assert p.locator('[data-skin-snapshot]').count()==0
    rows.append({'zoom':zoom,'geometry':geometry,'actualAlignment':{k:a[k] for k in ['sourceFramed','scaleRatio','isAligned','yaw','pitch','roll']},'tracksEnded':True,'errors':errors})
   finally:c.close()
assert rows[1]['geometry']['viewport']['dpr']/rows[0]['geometry']['viewport']['dpr']>1.99
proof={'status':'PASS','physicalCameraAcceptance':False,'fixture':'CC BY-SA 4.0 NMu11er Head_Shake full source first frame, aspect-preserving fit 640x480','modelOutputReplaced':False,'sourceQualityGatesChanged':False,'portraitPreparationDeferredForDisplayInspection':False,'buildId':Path('apps/vehicle-app/.next/BUILD_ID').read_text().strip(),'runs':rows}
(OUT/'proof.json').write_text(json.dumps(proof,ensure_ascii=False,indent=2),encoding='utf8');print(json.dumps({k:v for k,v in proof.items() if k!='runs'}))

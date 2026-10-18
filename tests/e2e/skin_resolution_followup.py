"""Native-pixel licensed source through actual production MediaPipe and browser zoom.

No pose injection, fabricated mask, photo enhancement, physical camera or paid API.
Structural assertions do not confer visual/user acceptance.
"""
import subprocess
import base64
import sys
import os
import json
import math
import shutil
import re
from itertools import combinations
from pathlib import Path
import tempfile
from PIL import Image, ImageChops
from playwright.sync_api import sync_playwright, expect

LOW='--low-quality' in sys.argv
DIGITAL='--digital-source' in sys.argv
WIDTH,HEIGHT=(640,480) if LOW else (1920,2160) if DIGITAL else (1280,960)
OUT = Path(os.environ.get('ATTUNE_RESOLUTION_OUT','audit-results/user-followup-20261005')+'/' +('low-detail' if LOW else 'digital-detail' if DIGITAL else 'high-detail')); OUT.mkdir(parents=True, exist_ok=True)
OBSERVE = """window.acceptedSources=[];window.segmentResults=[];window.cameraSettings=[];window.workerErrors=[];
const get=navigator.mediaDevices.getUserMedia.bind(navigator.mediaDevices);
navigator.mediaDevices.getUserMedia=async(...args)=>{const s=await get(...args),t=s.getVideoTracks()[0],v=t.getSettings(),c=t.getCapabilities();window.cameraSettings.push({width:v.width,height:v.height,resizeMode:v.resizeMode,maxWidth:c.width?.max,maxHeight:c.height?.max});return s;};
const post=Worker.prototype.postMessage;Worker.prototype.postMessage=function(v,...rest){
if(v.type==='initializeSegmentation')this.segmentationLoadStarted=performance.now();
if(v.type==='segment'){this.segmentStarted??=new Map();this.segmentStarted.set(v.id,this.segmentationLoadStarted??performance.now());const canvas=document.querySelector('canvas'),video=document.querySelector('video');window.acceptedSources.push({data:canvas.toDataURL('image/png'),width:canvas.width,height:canvas.height,decodedWidth:video.videoWidth,decodedHeight:video.videoHeight,bitmapWidth:v.frame.width,bitmapHeight:v.frame.height,alignment:window.lastAlignment});}
if(!this.observed){this.observed=true;this.addEventListener('message',e=>{const s=e.data.segmentation;if(e.data.error)window.workerErrors.push(e.data.error);if(e.data.alignment)window.lastAlignment=e.data.alignment;if(s)window.segmentResults.push({width:s.width,height:s.height,elapsedMs:s.elapsedMs,loadMs:s.loadMs,refinementMs:s.refinementMs,modelMaskWidth:s.modelMaskWidth,modelMaskHeight:s.modelMaskHeight,requestToResultMs:performance.now()-this.segmentStarted.get(e.data.id),categories:s.categories.length,confidence:s.confidence.length});});}
return post.call(this,v,...rest);};"""
source_head=subprocess.check_output(['git','rev-parse','HEAD'],text=True).strip()
source_dirty=bool(subprocess.check_output(['git','status','--porcelain'],text=True).strip())
build_id=Path('apps/vehicle-app/.next/BUILD_ID').read_text().strip()
proof=[]
fixture=Path('audit-fixtures/three-angle.y4m' if LOW else 'audit-fixtures/digital-detail.y4m' if DIGITAL else 'audit-fixtures/high-detail.y4m')
if LOW:
    # Retain the original poor source byte-for-byte. Longer transport holds let
    # cold model initialization and native 200% rendering finish before pose change.
    extended=fixture.with_name('three-angle-resolution.y4m')
    ffmpeg=shutil.which('ffmpeg')
    if not ffmpeg:
        import imageio_ffmpeg
        ffmpeg=imageio_ffmpeg.get_ffmpeg_exe()
    subprocess.run([ffmpeg,'-hide_banner','-loglevel','error','-y','-i',str(fixture),'-vf','setpts=3*PTS,fps=15','-t','135','-pix_fmt','yuv420p',str(extended)],check=True)
    fixture=extended
with sync_playwright() as pw:
    for zoom in (1, 2):
        with tempfile.TemporaryDirectory(prefix='attune-resolution-') as profile:
            prefs=Path(profile)/'Default'; prefs.mkdir()
            (prefs/'Preferences').write_text(json.dumps({'partition':{'default_zoom_level': {'x':math.log(zoom)/math.log(1.2)}}}))
            c=pw.chromium.launch_persistent_context(profile,channel='chromium',headless=False,no_viewport=True,permissions=['camera'],args=[
                '--window-size=1920,1080','--use-fake-device-for-media-stream',
                '--use-file-for-fake-video-capture='+str(fixture.resolve()),
                '--use-gl=angle','--use-angle=swiftshader','--enable-unsafe-swiftshader'])
            try:
                c.add_init_script(OBSERVE);p=c.new_page();errors=[];p.on('pageerror',lambda e:errors.append(str(e)))
                c.request.post('http://localhost:8000/api/vehicle/speed',data={'speedKmH':0})
                p.goto('http://localhost:3000/skin')
                p.get_by_role('button',name='Cilt taraması hakkında bilgi',exact=True).click()
                expect(p.get_by_role('dialog',name='Cilt taraması',exact=True)).to_be_visible()
                if not LOW: p.get_by_role('checkbox',name='Üç açılı tarama',exact=True).uncheck()
                p.get_by_role('button',name='Bilgi penceresini kapat',exact=True).click()
                expect(p.get_by_role('dialog')).to_have_count(0)
                p.get_by_role('button',name='Analizi Başlat',exact=True).click()
                try:
                    expect(p.get_by_text('Cilt Analizi Tamamlandı',exact=True)).to_be_visible(timeout=180000)
                except Exception:
                    p.screenshot(path=str(OUT/f'capture-failure-{zoom}.png'),full_page=True)
                    (OUT/f'capture-failure-{zoom}.txt').write_text(p.locator('main').inner_text(),encoding='utf-8')
                    raise
                p.screenshot(path=str(OUT/f'completed-before-assert-{zoom}.png'),full_page=True)
                (OUT/f'worker-errors-{zoom}.json').write_text(json.dumps(p.evaluate('workerErrors')),encoding='utf-8')
                (OUT/f'completed-before-assert-{zoom}.txt').write_text(p.locator('main').inner_text(),encoding='utf-8')
                sources=p.evaluate('acceptedSources');assert len(sources)==(3 if LOW else 1)
                for index,source in enumerate(sources):
                    assert all(source[k]==WIDTH for k in ('width','decodedWidth','bitmapWidth'))
                    assert all(source[k]==HEIGHT for k in ('height','decodedHeight','bitmapHeight'))
                    (OUT/f'accepted-original-{zoom}-{index}.png').write_bytes(base64.b64decode(source.pop('data').split(',')[1]))
                    (OUT/f'accepted-landmarks-{zoom}-{index}.json').write_text(json.dumps(source.pop('alignment')),encoding='utf-8')
                result=p.evaluate('JSON.parse(localStorage.getItem("togg_health_latest_skin"))')
                assert result['usedMediaPipe'] and result['comparisonScope']==('three-angle-v2' if LOW else 'single-front-v1') and result['quality']['isValid']
                (OUT/f'actual-landmarks-{zoom}.json').write_text(json.dumps(p.evaluate('lastAlignment')),encoding='utf-8')
                regions=[]
                for _ in range(6):
                    svg=p.locator('[data-skin-snapshot]');mesh=p.locator('[data-skin-mesh]');assert mesh.count()==1
                    region=mesh.get_attribute('data-skin-mesh');assert region not in [r['region'] for r in regions]
                    assert svg.get_attribute('data-snapshot-width')==str(WIDTH) and svg.get_attribute('data-snapshot-height')==str(HEIGHT)
                    photo=svg.locator('image').get_attribute('href')
                    (OUT/f'{region}-masked-{zoom}.png').write_bytes(base64.b64decode(photo.split(',')[1]))
                    sourceIndex=(2 if region=='rightCheek' else 1 if region=='leftCheek' else 0) if LOW else 0
                    original=Image.open(OUT/f'accepted-original-{zoom}-{sourceIndex}.png').convert('RGB')
                    masked=Image.open(OUT/f'{region}-masked-{zoom}.png').convert('RGBA')
                    opaque=masked.getchannel('A').point(lambda a:255 if a==255 else 0)
                    difference=ImageChops.multiply(ImageChops.difference(original,masked.convert('RGB')),Image.merge('RGB',[opaque]*3))
                    assert not difference.getbbox(),'Opaque facial RGB must remain original'
                    p.bring_to_front()
                    p.locator('[data-face-panel]').scroll_into_view_if_needed()
                    p.evaluate('()=>new Promise(r=>requestAnimationFrame(()=>requestAnimationFrame(r)))')
                    raw=c.new_cdp_session(p).send('Page.captureScreenshot',{'format':'png','fromSurface':True,'captureBeyondViewport':False})['data']
                    (OUT/f'{region}-ui-{zoom}.png').write_bytes(base64.b64decode(raw))
                    from PIL import ImageStat
                    assert sum(ImageStat.Stat(Image.open(OUT/f'{region}-ui-{zoom}.png')).var)>20,'Empty/occluded screen is not visual evidence'
                    (OUT/f'{region}-actual-{zoom}.svg').write_text(svg.evaluate('e=>e.outerHTML'),encoding='utf-8')
                    if region=='rightCheek':
                        mesh.evaluate("e=>e.style.visibility='hidden'")
                        rawNoMesh=c.new_cdp_session(p).send('Page.captureScreenshot',{'format':'png','fromSurface':True,'captureBeyondViewport':False})['data']
                        (OUT/f'ui-no-mesh-{zoom}.png').write_bytes(base64.b64decode(rawNoMesh))
                        mesh.evaluate("e=>e.style.visibility=''")
                    box=svg.bounding_box();dpr=p.evaluate('devicePixelRatio');crop=list(map(float,svg.get_attribute('viewBox').split()))
                    assert box['width']*dpr<=crop[2]+1,'Native pixels must not be upsampled'
                    if region in ('rightCheek','leftCheek'):
                        paths=mesh.locator('path[data-mesh-edge]').evaluate_all('es=>es.map(e=>e.getAttribute("d"))')
                        segments=[list(map(float,re.findall(r'[-+]?\d*\.?\d+(?:e[-+]?\d+)?',path))) for path in paths]
                        def cross(a,b,c):return (b[0]-a[0])*(c[1]-a[1])-(b[1]-a[1])*(c[0]-a[0])
                        for first,second in combinations(segments,2):
                            a,b=tuple(first[:2]),tuple(first[2:]);u,v=tuple(second[:2]),tuple(second[2:])
                            if {a,b}&{u,v}:continue
                            assert not (cross(a,b,u)*cross(a,b,v)<-1e-6 and cross(u,v,a)*cross(u,v,b)<-1e-6),'Crossed non-node cheek edges'
                        assert max(y for path in segments for y in path[1::2])-min(y for path in segments for y in path[1::2])>.12*HEIGHT,'Cheek graph cannot collapse to a small patch'
                    regions.append({'region':region,'viewBox':crop,'display':box,'dpr':dpr,'edges':mesh.locator('path[data-mesh-edge]').count(),'paths':mesh.locator('path[data-mesh-edge]').evaluate_all('es=>es.map(e=>e.getAttribute("d"))')})
                    p.get_by_role('button',name='Sonraki Bölge',exact=True).click()
                assert p.evaluate('document.documentElement.scrollWidth<=innerWidth'),'Horizontal layout overflow'
                assert not errors,errors
                if zoom==1: baseDpr=p.evaluate('devicePixelRatio')
                else: assert p.evaluate('devicePixelRatio')/baseDpr>1.99,'200% browser zoom must be measured, not assumed'
                assert 'data:image' not in p.evaluate('JSON.stringify(Object.fromEntries(Object.entries(localStorage)))')
                assert all(s['modelMaskWidth']==256 and s['modelMaskHeight']==256 for s in p.evaluate('segmentResults')),'SDK confidence maps must stay on the actual tensor grid'
                proof.append({'zoom':zoom,'sources':sources,'camera':p.evaluate('cameraSettings'),'segmentation':p.evaluate('segmentResults'),'regions':regions,'quality':result['quality'],'pose':result['capturePose'],'viewport':p.evaluate('({innerWidth,innerHeight,outerWidth,outerHeight,devicePixelRatio})')})
            finally:
                c.close()
(OUT/'resolution-proof.json').write_text(json.dumps({'sourceHead':source_head,'sourceTrackedChanges':source_dirty,'buildId':build_id,'technicalChecks':'PASS','visualAcceptance':'FAIL','controlledFixture':True,'fixtureTransportHoldSeconds':45 if LOW else 3,'userPhotoAcceptance':False,'runs':proof},indent=2),encoding='utf-8')
print(f'PASS technical chain: native {WIDTH}x{HEIGHT}, actual MediaPipe, six regions, measured browser 100%/200%; visual acceptance remains FAIL')

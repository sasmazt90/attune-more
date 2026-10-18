"""Nonzero source-support rendering in the normal camera/API/history path.
Licensed existing NASA development control; rendering evidence, not a dry-skin label.
"""
import json,time,base64,hashlib
from pathlib import Path
from heavy_job_lease import HeavyJobLease
ROOT=Path(__file__).resolve().parents[2];DATA=ROOT/'audit-results/dryness-integration-v2-20261014';OUT=ROOT/'output/playwright/dryness-integration-v2-20261014'
prior=json.loads((DATA/'eyewear-product-browser.json').read_text('utf8'));profile=ROOT/prior['profile'];assert profile.resolve().is_relative_to(OUT.resolve())
photo=json.loads((ROOT/'audit-results/material-closeout-20261013/camera-native-payload.json').read_text('utf8'))['photo']
with HeavyJobLease('CDC-dry-nonzero-camera-map-history',peak_mib=1450,minimum_available_mib=2100,include_children=True,memory_metric='private') as lease:
 from playwright.sync_api import sync_playwright,expect
 prefs=profile/'Default/Preferences';settings=json.loads(prefs.read_text('utf8'));settings.setdefault('partition',{})['default_zoom_level']={'x':0};prefs.write_text(json.dumps(settings),'utf8')
 injection="""window.__request=null;window.__response=null;window.__timing=null;const original=fetch;
 window.fetch=async(...args)=>{const scan=String(args[0]).endsWith('/api/local-health/skin');if(scan){window.__request=JSON.parse(args[1].body);window.__trackAtRequest=window.__track();window.__videoAtRequest={width:document.querySelector('video')?.videoWidth,height:document.querySelector('video')?.videoHeight};if(__request.hostedProcessingConsent!==false)throw Error('HOSTED_NOT_ALLOWED');}const t=performance.now();const r=await original(...args);if(scan){__response=await r.clone().json();__timing={status:r.status,seconds:(performance.now()-t)/1000};}return r;};
 const gum=navigator.mediaDevices.getUserMedia.bind(navigator.mediaDevices);navigator.mediaDevices.getUserMedia=async c=>{if(!c.video)return gum(c);window.__requested=c.video;const im=new Image();im.src=PHOTO;await im.decode();const canvas=document.createElement('canvas');canvas.width=im.naturalWidth;canvas.height=im.naturalHeight;canvas.getContext('2d').drawImage(im,0,0);const s=canvas.captureStream(30);window.__track=()=>s.getVideoTracks()[0].getSettings();function draw(){canvas.getContext('2d').drawImage(im,0,0);if(s.getVideoTracks()[0].readyState==='live')requestAnimationFrame(draw);}draw();return s;};""".replace('PHOTO',json.dumps(photo))
 with sync_playwright() as pw:
  context=pw.chromium.launch_persistent_context(str(profile),channel='chrome',headless=False,viewport=dict(width=1600,height=1000),args=['--window-size=1600,1000','--enable-unsafe-swiftshader'])
  try:
   context.add_init_script(injection);page=context.pages[0];errors=[];page.on('pageerror',lambda e:errors.append(str(e)));page.goto('http://127.0.0.1:3000/skin')
   before=page.evaluate("JSON.parse(localStorage.getItem('togg_health_skin_history')||'[]')");assert any(r['id']==prior['newRecordId'] for r in before)
   page.get_by_role('button',name='Cilt taraması hakkında bilgi',exact=True).click();page.get_by_label('Üç açılı tarama',exact=True).uncheck();page.get_by_role('button',name='Bilgi penceresini kapat',exact=True).click();page.get_by_role('button',name='Analizi Başlat',exact=True).click()
   deadline=time.monotonic()+100
   while time.monotonic()<deadline and not page.get_by_text('Cilt Analizi Tamamlandı',exact=True).count():lease.check();page.wait_for_timeout(300)
   expect(page.get_by_text('Cilt Analizi Tamamlandı',exact=True)).to_be_visible()
   observed=page.evaluate("({request:__request,response:__response,timing:__timing,track:__trackAtRequest,video:__videoAtRequest,requested:__requested,record:JSON.parse(localStorage.getItem('togg_health_latest_skin')),history:JSON.parse(localStorage.getItem('togg_health_skin_history'))})")
   (DATA/'nonzero-camera-observed-metadata.json').write_text(json.dumps({k:observed[k] for k in ['timing','track','video','requested']},indent=2),'utf8')
   response=observed['response'];record=observed['record'];identity=response['photoId'];(DATA/'nonzero-camera-payload.json').write_text(json.dumps(observed['request']),'utf8');(DATA/'nonzero-camera-result.json').write_text(json.dumps(response),'utf8');dry=next(r for r in response['general']['measurements'] if r['id']=='dry')
   assert observed['timing']['status']==200 and observed['timing']['seconds']<45 and dry['value']>0
   assert response['sourceWidth']==observed['track']['width']==1280 and response['sourceHeight']==observed['track']['height']==960
   assert identity==record['captures']['FRONT']['captureId']==observed['request']['expressionObservation']['photoId'] and record['usedMediaPipe']
   for old in before:assert next(r for r in observed['history'] if r['id']==old['id'])==old
   (DATA/'nonzero-camera-payload.json').write_text(json.dumps(observed['request']),'utf8');(DATA/'nonzero-camera-result.json').write_text(json.dumps(response),'utf8')
   page.goto('http://127.0.0.1:3000/profile');page.locator('[data-record-id="'+record['id']+'"]').get_by_role('button',name='Sonucu Aç',exact=True).click();dialog=page.get_by_role('dialog',name='Cilt Sağlığı sonucu',exact=True)
   dialog.locator('[data-skin-record-indicator="dry"]').click();fill=dialog.locator('[data-skin-local-fill="dry"]');expect(fill).to_be_visible();layer=response['maps']['overview:dry']
   actual=fill.locator('image').evaluate('(e)=>Object.fromEntries(["x","y","width","height"].map(k=>[k,Number(e.getAttribute(k))]))');wanted=dict(x=layer['x'],y=layer['y'],width=layer['width']*layer['step'],height=layer['height']*layer['step']);assert actual==wanted and fill.get_attribute('data-map-photo')==identity
   assert fill.locator('image').get_attribute('href')==layer['dataUrl']
   clip=fill.evaluate("""async(el,layer)=>{
    const id=el.getAttribute('clip-path').replace('url(#','').replace(')','');const paths=[...document.getElementById(id).querySelectorAll('path')];
    const image=new Image();image.src=layer.dataUrl;await image.decode();const canvas=document.createElement('canvas');canvas.width=layer.width;canvas.height=layer.height;const ctx=canvas.getContext('2d');ctx.drawImage(image,0,0);const pixels=ctx.getImageData(0,0,canvas.width,canvas.height).data;
    let active=0,centers=0,intersected=0;const lost=[];
    const point=el.ownerSVGElement.createSVGPoint();const contains=(x,y)=>{point.x=x;point.y=y;return paths.some(path=>path.isPointInFill(point));};
    for(let y=0;y<layer.height;y++)for(let x=0;x<layer.width;x++){if(!pixels[(y*layer.width+x)*4+3])continue;active++;const a=layer.x+(x+.5)*layer.step,b=layer.y+(y+.5)*layer.step;const center=contains(a,b);if(center)centers++;const visible=center||[-.49,0,.49].some(dx=>[-.49,0,.49].some(dy=>contains(a+dx*layer.step,b+dy*layer.step)));if(visible)intersected++;else if(lost.length<20)lost.push([a,b]);}
    return {actualSVGClipPaths:paths.length,activeNativePixels:active,centerRetained:centers,pixelsWithInteriorClipSample:intersected,fullyClipped:active-intersected,lostSourceCenters:lost};
   }""",layer)
   (DATA/'nonzero-camera-svg-clip.json').write_text(json.dumps(clip,indent=2),'utf8')
   assert clip['activeNativePixels']==dry['components']['acceptedMaterialSourcePixels'] and clip['fullyClipped']==0,clip
   page.evaluate('new Promise(resolve=>requestAnimationFrame(()=>requestAnimationFrame(resolve)))');page.wait_for_timeout(200)
   cdp=context.new_cdp_session(page);page.bring_to_front();fill.scroll_into_view_if_needed();page.wait_for_timeout(200)
   captured=cdp.send('Page.captureScreenshot',dict(format='png',fromSurface=False));(OUT/'nonzero-map-actual-viewport.png').write_bytes(base64.b64decode(captured['data']))

   page.screenshot(path=str(OUT/'nonzero-source-map-history-desktop.png'),full_page=True)
   dialog.locator('[data-skin-record-indicator="tone"]').click();assert dialog.locator('[data-skin-local-fill="dry"]').count()==0;expect(dialog.locator('[data-skin-local-fill="tone"]')).to_be_visible()
   assert not errors
   proof=dict(normalProductAPI=True,actualBrowserMediaPipe=True,physicalCameraAccuracyClaim=False,source='existing NASA controlled camera source; no semantic dryness ground truth',photoId=identity,recordId=record['id'],normalHTTP=observed['timing'],track=observed['track'],video=observed['video'],requested=observed['requested'],sourceFacePixels=dry['evaluatedArea']['sourceFacePixels'],overviewValue=dry['value'],acceptedSourcePixels=dry['components']['acceptedMaterialSourcePixels'],eligibleSourcePixels=dry['components']['uniqueVisibleSourcePixels'],nativeMetadata=response['drynessRuntime'],mapPhotoIdMatched=True,actualMapSourceCoordinates=actual,expectedAPISourceCoordinates=wanted,actualMapImageBytesMatched=True,actualSVGClip=clip,oldRecordsPreserved=True,oldClearRecordId=prior['newRecordId'],mapClearedOnCriterionChange=True,buildId=(ROOT/'apps/vehicle-app/.next/BUILD_ID').read_text('utf8').strip(),resource=lease.receipt())
   (DATA/'nonzero-camera-browser.json').write_text(json.dumps(proof,indent=2),'utf8');print(json.dumps(dict(seconds=proof['normalHTTP']['seconds'],sourceSize=[1280,960],overview=dry['value'],accepted=proof['acceptedSourcePixels'],oldRecordsPreserved=True)),flush=True)
  finally:context.close()

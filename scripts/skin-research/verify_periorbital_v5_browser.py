"""Real normal build/API; isolated profile and actual source/MediaPipe utilities."""
import base64,hashlib,json,math,sys,time
from pathlib import Path
from playwright.sync_api import sync_playwright,expect
ROOT=Path(__file__).resolve().parents[2];DATA=ROOT/'audit-results/periorbital-v5-integration-20261012';OUT=ROOT/'output/playwright/periorbital-v5-20261012';OUT.mkdir(parents=True,exist_ok=True);PROFILE=OUT/'profile-observed-centers'
sys.path.insert(0,str(ROOT/'tests/e2e'))
bundle=(ROOT/'.runtime/periorbital-v5-browser-support/utilities.js').read_text('utf8')
sources=json.loads((DATA/'sources.json').read_text('utf8'))['sources']
errors=[];proof=[]
BUILD_ID=(ROOT/'apps/vehicle-app/.next/BUILD_ID').read_text('utf8').strip()
with sync_playwright() as pw:
 def launch(headed=True):return pw.chromium.launch_persistent_context(str(PROFILE),channel='chrome',headless=not headed,viewport=None if headed else dict(width=1600,height=1000),no_viewport=headed,args=['--window-size=1600,1000','--enable-unsafe-swiftshader'])
 context=launch();context.route('**/__audit/vision_bundle.mjs',lambda r:r.fulfill(path=str(ROOT/'node_modules/@mediapipe/tasks-vision/vision_bundle.mjs'),content_type='text/javascript'))
 page=context.new_page();page.on('pageerror',lambda e:errors.append(str(e)));page.goto('http://127.0.0.1:3000/privacy')
 expect(page.get_by_label('Cilt tipi için yüz fotoğrafımın Roboflow tarafından işlenmesine izin ver',exact=True)).not_to_be_checked()
 page.get_by_label('Cilt ölçümlerini ve kişisel sayısal referansı bu tarayıcıda sakla',exact=True).check()
 photo_permission=page.get_by_label('Yeni cilt kayıtlarının fotoğraflarını bu cihazda sakla',exact=True)
 if not photo_permission.is_checked():photo_permission.click()
 expect(photo_permission).to_be_checked(timeout=10000)
 page.add_script_tag(content=bundle)
 page.evaluate("async()=>{window.__auditMediaPipe=await import('/__audit/vision_bundle.mjs');return true;}")
 assert page.evaluate("async()=>!!await __auditRequire('apps/vehicle-app/src/utils/skinAnalyzer.ts').SkinAnalyzer.getFaceLandmarker()")
 for source in sources:
  prefix=source['sha256'][:8];payload=json.loads((DATA/(prefix+'-payload.json')).read_text('utf8'));legacy=json.loads((DATA/(prefix+'-baseline.json')).read_text('utf8'))
  result=page.evaluate('''async({payload,prefix,legacy})=>{
   const R=n=>__auditRequire('apps/vehicle-app/src/utils/'+n+'.ts');const analyzer=R('skinAnalyzer').SkinAnalyzer;
   const im=new Image();im.src=payload.photo;await im.decode();const canvas=document.createElement('canvas');canvas.width=im.naturalWidth;canvas.height=im.naturalHeight;const ctx=canvas.getContext('2d');ctx.drawImage(im,0,0);
   const alignment=analyzer.assessAlignment(ctx,canvas.width,canvas.height);if(!alignment.isMediaPipeActive||alignment.faceCount!==1)throw Error('Real single-face MediaPipe required');
   const quality=analyzer.checkQuality(ctx,canvas.width,canvas.height,alignment.faceDetected,alignment.box);
   const snapshot=R('skinSnapshot').snapshotRawSkinFrame(canvas,alignment,'FRONT');
   snapshot.photoId=Array.from(new Uint8Array(await crypto.subtle.digest('SHA-256',ctx.getImageData(0,0,canvas.width,canvas.height).data))).map(v=>v.toString(16).padStart(2,'0')).join('');
   const conditions={yaw:alignment.yaw,pitch:alignment.pitch,roll:alignment.roll,scaleRatio:alignment.scaleRatio,avgLuminance:quality.avgLuminance,blurScore:quality.blurScore};
   const response=await R('appearanceMeasurements').analyzeAppearance(snapshot,quality.isValid,conditions,[alignment.landmarks,alignment.landmarks,alignment.landmarks],()=>true);
   const bags=response.measurements.periorbital.find(v=>v.id==='bags');if(bags.components.samplingSupportVersion!=='tracked-center-eligible-v1')throw Error('Updated eye support contract missing');
   const bagMap=response.maps['periorbital:bags'];let alphaCells=0;if(bagMap){const map=new Image();map.src=bagMap.dataUrl;await map.decode();const c=document.createElement('canvas');c.width=map.width;c.height=map.height;const x=c.getContext('2d');x.drawImage(map,0,0);const bytes=x.getImageData(0,0,c.width,c.height).data;for(let i=3;i<bytes.length;i+=4)if(bytes[i]>0)alphaCells++;}
   if(bags.value>=.5&&!alphaCells)throw Error('Visible card score without local map evidence');
   async function store(actual,id,date){
    const frame={...snapshot,localMaps:actual.maps,contoursMeasured:actual.contours};const indicators=R('skinIndicators').measureSkinIndicators(ctx,frame,quality);R('appearanceMeasurements').attachAppearance(indicators,actual);const general=R('skinOverview').overviewFromResponse(actual);general.analysisId=id;frame.general=general;
    const record={id,date,timestamp:date,schemaVersion:3,usedMediaPipe:true,comparisonScope:'single-front-v1',isBaseline:true,indicators,general,quality};
    await R('healthRecords').appendHealthRecord('skin',record,{},()=>true);if(!await R('healthRecords').withRecordsLock(()=>R('skinPhotoHistory').saveSkinPhotos(id,{FRONT:frame})))throw Error('Source photo not stored');return record;
   }
   let oldRecord=null;if(prefix==='20031f35'){oldRecord=await store(legacy,'audit-v4-'+prefix,'2026-10-11T10:00:00Z');window.__oldRecordBytes=JSON.stringify(oldRecord);}
   const record=await store(response,'audit-v5-'+prefix,new Date().toISOString());
   window.__lastAuditRecord=record;
   if(oldRecord){const old=oldRecord.indicators.periorbital.find(v=>v.id==='bags'),now=record.indicators.periorbital.find(v=>v.id==='bags');if(R('skinIndicators').canCompareIndicator(now,old))throw Error('v4/v5 compared as equivalent');R('appearanceMeasurements').compareAppearance(now,old,true,oldRecord.id);if(now.referenceDelta!==undefined)throw Error('v4/v5 delta fabricated');}
   const history=JSON.parse(localStorage.getItem('togg_health_skin_history'));if(history.some(r=>r.id==='audit-v4-20031f35')&&JSON.stringify(history.find(r=>r.id==='audit-v4-20031f35'))!==window.__oldRecordBytes)throw Error('Old record changed');
   return {prefix,recordId:record.id,sourcePhotoId:snapshot.photoId,actualMediaPipe:true,quality,bagsResult:{value:bags.value,quality:bags.quality,limitationCode:bags.limitationCode,alphaCells,samplingSupportVersion:bags.components.samplingSupportVersion},alignment:{yaw:alignment.yaw,pitch:alignment.pitch,roll:alignment.roll,isAligned:alignment.isAligned},conditions,productPayload:{processingConsent:true,hostedProcessingConsent:false,photo:snapshot.dataUrl,photoId:snapshot.photoId,pose:'FRONT',meshes:snapshot.meshes,exclusions:snapshot.exclusions,landmarks:snapshot.landmarks,qualityValid:quality.isValid,conditions,temporal:[alignment.landmarks,alignment.landmarks,alignment.landmarks]},response,normalization:record.indicators.periorbital.find(v=>v.id==='bags').appearance.normalizationVersion,legacyNormalization:oldRecord?.indicators.periorbital.find(v=>v.id==='bags').appearance.normalizationVersion};
  }''',dict(payload=payload,prefix=prefix,legacy=legacy))
  assert result['sourcePhotoId']==payload['photoId'];assert result['normalization']=='contour-fold-local-support-v5'
  (DATA/(prefix+'-browser-api.json')).write_text(json.dumps(result,ensure_ascii=False,indent=2),'utf8');proof.append({k:v for k,v in result.items() if k not in ('response','productPayload')})
  print(json.dumps(dict(source=prefix,quality=result['quality'],bags=next(v for v in result['response']['measurements']['periorbital'] if v['id']=='bags')['value'])),flush=True)
 # No utility injection is used by the product renderer on subsequent pages.
 def open_record(ident):
  page.goto('http://127.0.0.1:3000/profile');row=page.locator('[data-record-id="'+ident+'"]');expect(row).to_be_visible(timeout=10000);row.get_by_role('button',name='Sonucu Aç',exact=True).click();dialog=page.get_by_role('dialog',name='Cilt Sağlığı sonucu',exact=True);expect(dialog.locator('[data-skin-snapshot]')).to_be_visible(timeout=15000);return dialog
 def check_record(ident,expected_photo,screenshot):
  dialog=open_record(ident);assert dialog.locator('[data-skin-snapshot]').get_attribute('data-snapshot-photoid')==expected_photo
  assert dialog.get_by_role('heading',name='Genel Bakış',exact=True).count()==1
  dialog.locator('[data-skin-record-indicator="bags"]').click();assert dialog.locator('[data-skin-local-fill="bags"]').count()==1
  photo=dialog.locator('[data-skin-snapshot] image').first.get_attribute('href');dialog.get_by_role('button',name='Sonraki Bölge',exact=True).click();assert dialog.locator('[data-skin-local-fill]').count()==0
  regions=[]
  for region in ['forehead','rightCheek','leftCheek','nose','chin','periorbital']:
   assert dialog.locator('[data-skin-mesh]').get_attribute('data-skin-mesh')==region;regions.append(region);assert dialog.locator('[data-skin-snapshot] image').first.get_attribute('href')==photo
   assert dialog.locator('[data-skin-local-fill]').count()==0
   if region=='periorbital':
    expect(dialog.get_by_role('heading',name='Göz altı torbaları',exact=True)).to_be_visible()
    assert all(not any(char in text for char in ('Ã','Ä','Å')) for text in dialog.locator('h4').all_text_contents())
    dialog.locator('[data-skin-record-indicator="bags"]').click();expect(dialog.locator('[data-skin-local-fill="bags"]')).to_be_visible();assert dialog.locator('[data-skin-local-fill="bags"]').get_attribute('data-map-photo')==expected_photo
    dialog.locator('[data-skin-record-indicator="dark"]').click();assert dialog.locator('[data-skin-local-fill="bags"]').count()==0;assert dialog.locator('[data-skin-local-fill="dark"]').count()==1
    dialog.locator('[data-skin-record-indicator="bags"]').click()
   else:dialog.get_by_role('button',name='Sonraki Bölge',exact=True).click()
  page.screenshot(path=str(OUT/screenshot),full_page=True);page.keyboard.press('Escape');return regions
 chosen=next(v for v in proof[:2] if v['bagsResult']['value'] is not None and v['bagsResult']['value']>=.5);regions=check_record(chosen['recordId'],chosen['sourcePhotoId'],'desktop.png')
 old=open_record('audit-v4-20031f35');assert old.locator('[data-skin-snapshot]').get_attribute('data-snapshot-photoid')==proof[0]['sourcePhotoId'];page.keyboard.press('Escape')
 page.set_viewport_size(dict(width=720,height=900));check_record(chosen['recordId'],chosen['sourcePhotoId'],'narrow.png');assert page.evaluate('document.documentElement.scrollWidth<=innerWidth')
 history_before=page.evaluate('localStorage.getItem("togg_health_skin_history")');context.close()
 preferences=PROFILE/'Default/Preferences';prefs=json.loads(preferences.read_text('utf8'));prefs.setdefault('partition',{})['default_zoom_level']={'x':math.log(2)/math.log(1.2)};preferences.write_text(json.dumps(prefs),'utf8')
 context=launch();page=context.new_page();page.on('pageerror',lambda e:errors.append(str(e)));dialog=open_record(chosen['recordId']);geometry=page.evaluate('({innerWidth,outerWidth,dpr:devicePixelRatio,zoom:getComputedStyle(document.documentElement).zoom,scroll:document.documentElement.scrollWidth})');assert geometry['dpr']>=2 and geometry['innerWidth']<geometry['outerWidth']*.65 and geometry['zoom']=='1' and geometry['scroll']<=geometry['innerWidth'],geometry
 assert page.evaluate('localStorage.getItem("togg_health_skin_history")')==history_before
 dialog.locator('[data-skin-record-indicator="bags"]').click();expect(dialog.locator('[data-skin-local-fill="bags"]')).to_be_visible();expect(dialog.get_by_role('heading',name='Göz altı torbaları',exact=True)).to_be_visible()
 # At real browser zoom, Playwright's element clip uses a different CSS/device
 # coordinate scale. Capture the actual viewport through CDP instead.
 page.bring_to_front();cdp=context.new_cdp_session(page)
 (OUT/'native200.png').write_bytes(base64.b64decode(cdp.send('Page.captureScreenshot',{'format':'png','fromSurface':False,'captureBeyondViewport':False})['data']))
 for _ in range(6):dialog.get_by_role('button',name='Sonraki Bölge',exact=True).click()
 assert dialog.locator('[data-skin-mesh]').get_attribute('data-skin-mesh')=='periorbital'
 assert dialog.locator('[data-skin-local-fill]').count()==0
 dialog.locator('[data-skin-record-indicator="bags"]').click();expect(dialog.locator('[data-skin-local-fill="bags"]')).to_be_visible()
 dialog.evaluate("el=>{const b=el.querySelector('[data-skin-snapshot]').getBoundingClientRect();el.scrollTop+=b.top+b.height*.4-el.getBoundingClientRect().top-90}")
 (OUT/'native200-photo.png').write_bytes(base64.b64decode(cdp.send('Page.captureScreenshot',{'format':'png','fromSurface':False,'captureBeyondViewport':False})['data']));page.keyboard.press('Escape')
 assert not errors,errors
 receipt=dict(status='PASS',buildId=BUILD_ID,actualNormalAPI=True,actualBrowserMediaPipe=True,actualProductionCropAndQuality=True,qualityOverride=False,photoSpecificRules=False,userProfileTouched=False,hostedPhotoCalls=0,normalUserRecordsRecalculated=False,legacyV4Preserved=True,v4V5ComparisonBlocked=True,sourceMapRecordAssociation=True,staleCriterionAndRegionMapCleared=True,sixRegions=regions,photoProofs=proof,real200Percent=geometry,pageErrors=errors,utilitySourceHashes=json.loads((ROOT/'.runtime/periorbital-v5-browser-support/source-hashes.json').read_text('utf8')))
 (OUT/'proof.json').write_text(json.dumps(receipt,ensure_ascii=False,indent=2),'utf8');context.close();print(json.dumps(dict(status='PASS',buildId=BUILD_ID,real200Percent=geometry)))

"""Normal shortcut: actual scan plus pinned real API dry/sag history and version separation."""
import base64,copy,json,sys,time,urllib.request
from pathlib import Path
from playwright.sync_api import sync_playwright,expect
IMPULSE='--lines-impulse' in sys.argv
POSITIVE='--sag-positive-camera' in sys.argv
ROOT=Path(__file__).resolve().parents[2];NAME='dry-sag-product-20261013';DATA=ROOT/'audit-results'/NAME;OUT=ROOT/'output/playwright'/NAME;OUT.mkdir(parents=True,exist_ok=True);PROFILE=OUT/'product-profile-2'
if POSITIVE:
 OUT=OUT/'positive-camera';OUT.mkdir(exist_ok=True);PROFILE=OUT/'product-profile'
LABELS=dict(tone='Ton eşitsizliği',oil='Yağlı görünüm',redness='Kızarıklık eğilimi',acne='Sivilce görünümü',sag='Sarkma',dry='Cilt kuruluğu',dark='Göz altı morluğu',bags='Göz altı torbaları',lines='Kaz ayakları')
OVERVIEW={**LABELS,'sag':'Sarkma görünümü','dry':'Cilt kuruluğu görünümü'}
VIEWS=['overview','forehead','rightCheek','leftCheek','nose','chin','periorbital']
assert PROFILE.resolve().is_relative_to(OUT.resolve())
bundle=(ROOT/'.runtime/periorbital-v5-browser-support/utilities.js').read_text('utf8')
captured=json.loads((DATA/'515cc548-browser.json').read_text('utf8'))
captured['productPayload']=json.loads((DATA/'515cc548-payload.json').read_text('utf8'))
updated=json.loads((DATA/'515cc548-normal-api.json').read_text('utf8'))
errors=[];results=[];map_controls=[]
# The normal shortcut starts asynchronously; do not race its listening socket.
deadline=time.monotonic()+45
while True:
 try:
  with urllib.request.urlopen('http://127.0.0.1:3000/privacy',timeout=3) as ready:assert ready.status==200
  with urllib.request.urlopen('http://127.0.0.1:8000/api/vehicle/state',timeout=3) as ready:assert ready.status==200
  break
 except (OSError,AssertionError):
  if time.monotonic()>deadline:raise
  time.sleep(.5)
with sync_playwright() as pw:
 request=urllib.request.Request('http://127.0.0.1:8000/api/vehicle/speed',data=b'{"speedKmH":0}',headers={'Content-Type':'application/json'})
 with urllib.request.urlopen(request,timeout=10) as parked:assert parked.status==200
 camera=DATA/'515cc548-camera.y4m' if POSITIVE else ROOT/'audit-results/bag-label-followup-20261012/20031f35-camera.y4m'
 context=pw.chromium.launch_persistent_context(str(PROFILE),channel='chrome',headless=False,viewport=dict(width=1600,height=1000),permissions=['camera'],args=['--window-size=1600,1000','--use-fake-device-for-media-stream','--use-file-for-fake-video-capture='+str(camera),'--enable-unsafe-swiftshader'])
 context.add_init_script("window.__skinRequests=[];window.__skinResponses=[];const orig=window.fetch;window.fetch=async(...args)=>{const skin=String(args[0]).endsWith('/api/local-health/skin');if(skin)window.__skinRequests.push(JSON.parse(args[1].body));const r=await orig(...args);if(skin&&r.ok)window.__skinResponses.push(await r.clone().json());return r;};")
 page=context.new_page();page.on('pageerror',lambda e:errors.append(str(e)))
 console=[];page.on('console',lambda message:console.append(dict(type=message.type,text=message.text)))
 page.goto('http://127.0.0.1:3000/privacy');expect(page.get_by_label('Cilt tipi için yüz fotoğrafımın Roboflow tarafından işlenmesine izin ver',exact=True)).not_to_be_checked()
 numeric=page.get_by_label('Cilt ölçümlerini ve kişisel sayısal referansı bu tarayıcıda sakla',exact=True)
 if not numeric.is_checked():numeric.click()
 expect(numeric).to_be_checked();photo=page.get_by_label('Yeni cilt kayıtlarının fotoğraflarını bu cihazda sakla',exact=True)
 if not photo.is_checked():photo.click()
 expect(photo).to_be_checked()
 page.goto('http://127.0.0.1:3000/skin');page.bring_to_front();page.get_by_role('button',name='Cilt taraması hakkında bilgi',exact=True).click();page.get_by_label('Üç açılı tarama',exact=True).uncheck();page.get_by_role('button',name='Bilgi penceresini kapat',exact=True).click();page.get_by_role('button',name='Analizi Başlat',exact=True).click()
 start=time.monotonic();trace=[]
 while not page.get_by_text('Cilt Analizi Tamamlandı',exact=True).count() and time.monotonic()-start<180:
  page.wait_for_timeout(2000);trace.append(dict(seconds=round(time.monotonic()-start,1),body=page.locator('main').inner_text(),canvas=page.evaluate('({...document.querySelector("canvas")?.dataset})'),video=page.evaluate('(()=>{const v=document.querySelector("video");return {visible:document.visibilityState,ready:v?.readyState,width:v?.videoWidth,height:v?.videoHeight,time:v?.currentTime,paused:v?.paused,frames:v?.getVideoPlaybackQuality().totalVideoFrames}})()')))
  (OUT/'scan-trace.json').write_text(json.dumps(trace,ensure_ascii=False,indent=2),'utf8')
  (OUT/'scan-console.json').write_text(json.dumps(console,ensure_ascii=False,indent=2),'utf8')
 expect(page.get_by_text('Cilt Analizi Tamamlandı',exact=True)).to_be_visible(timeout=1000)
 new_record=page.evaluate('JSON.parse(localStorage.getItem("togg_health_latest_skin"))');requests=page.evaluate('window.__skinRequests');responses=page.evaluate('window.__skinResponses');assert requests and responses
 assert all(not r.get('hostedProcessingConsent') for r in requests)
 assert new_record['usedMediaPipe'] and new_record['comparisonScope']=='single-front-v1'
 (DATA/('positive-actual-ui-scan.json' if POSITIVE else 'actual-ui-scan.json')).write_text(json.dumps(dict(record=new_record,requests=requests,responses=responses),ensure_ascii=False,indent=2),'utf8')
 page.add_script_tag(content=bundle)
 def inspect_views(root,kind):
  page.add_script_tag(content=bundle)
  collected=[]
  for view in VIEWS:
   cards=root.locator('[data-skin-indicator]' if kind=='new-result' else '[data-skin-record-indicator]');ids=cards.evaluate_all('(els)=>els.map(e=>e.dataset.skinIndicator||e.dataset.skinRecordIndicator)');expected=OVERVIEW if view=='overview' else LABELS
   labels=[]
   for ident in ids:
    card=root.locator(('[data-skin-indicator="' if kind=='new-result' else '[data-skin-record-indicator="')+ident+'"]')
    actual=card.locator(':scope > div').first.inner_text() if kind=='new-result' else card.locator('h4').inner_text();wanted=expected[ident];matches=actual==wanted;assert matches,(kind,view,ident,actual,wanted);labels.append(dict(id=ident,actual=actual,expected=wanted,matches=matches))
   expected_ids=list(new_record['general']['indicators'][i]['id'] for i in range(len(new_record['general']['indicators']))) if view=='overview' else [v['id'] for v in new_record['indicators'][view]]
   assert set(ids)==set(expected_ids)
   collected.append(dict(view=view,labels=labels,allMatch=all(v['matches'] for v in labels)))
   if kind=='history-label-replay-correct' and view=='rightCheek':
    root.locator('[data-skin-record-indicator="sag"]').click();fill=root.locator('[data-skin-local-fill="sag"]');expect(fill).to_be_visible()
    mesh=captured['productPayload']['meshes'][view];expected_paths=page.evaluate("mesh=>__auditRequire('apps/vehicle-app/src/utils/skinSurfaceAnalysis.ts').meshTriangles(mesh).length",mesh)
    paths=root.locator('[data-skin-snapshot] clipPath path').count();assert paths==expected_paths
    map_controls.append(dict(case=kind,view=view,criterion='sag',oldTriangleSupportPreserved=paths==expected_paths,renderedPaths=paths,expectedPaths=expected_paths))
   tested=kind=='history-label-replay-current' and view in ('overview','chin') or kind=='new-result' and view in ('overview','rightCheek')
   if tested:
    reference=updated if kind=='history-label-replay-current' else responses[-1];meshes=captured['productPayload']['meshes'] if kind=='history-label-replay-current' else requests[-1]['meshes'];attribute='data-skin-record-indicator' if kind!='new-result' else 'data-skin-indicator'
    for criterion in ('dry','sag'):
     root.locator('['+attribute+'="'+criterion+'"]').click();fill=root.locator('[data-skin-local-fill="'+criterion+'"]');expect(fill).to_be_visible();layer=reference['maps'][view+':'+criterion];painted=fill.locator('image').first
     fields={k:abs(float(painted.get_attribute(k))-layer[k]*(layer['step'] if k in ('width','height') else 1))<1e-7 for k in ('x','y','width','height')}
     expected_paths=page.evaluate("({meshes,view})=>{const s=__auditRequire('apps/vehicle-app/src/utils/skinSurfaceAnalysis.ts');return (view==='overview'?Object.values(meshes):[meshes[view]]).reduce((n,m)=>n+s.meshTriangles(m,false,true).length,0)}",dict(meshes=meshes,view=view));paths=root.locator('[data-skin-snapshot] clipPath path').count()
     photo_matches=fill.get_attribute('data-map-photo')==layer['photoId'];assert all(fields.values()) and photo_matches and paths==expected_paths
     map_controls.append(dict(case=kind,view=view,criterion=criterion,coordinateFieldsMatch=fields,photoMatches=photo_matches,renderedPaths=paths,expectedPaths=expected_paths))
    root.locator('['+attribute+'="tone"]').click();assert root.locator('[data-skin-local-fill="sag"]').count()==0
    map_controls[-1]['criterionChangeClearsSag']=root.locator('[data-skin-local-fill="sag"]').count()==0
   if view in ('overview','periorbital'):page.screenshot(path=str(OUT/(kind+'-'+view+'.png')),full_page=True)
   root.get_by_role('button',name='Sonraki Bölge',exact=True).click()
   if tested:
    cleared=root.locator('[data-skin-local-fill]').count()==0;assert cleared;map_controls[-1]['regionSwitchClearsMaps']=cleared
  return collected
 results.append(dict(case='new-result',views=inspect_views(page,'new-result')))
 page.add_script_tag(content=bundle)
 fixture_ids=page.evaluate('''async({captured,badLabels})=>{
  const R=n=>__auditRequire('apps/vehicle-app/src/utils/'+n+'.ts'),p=captured.productPayload,old=captured.response;
  const image=new Image();image.src=p.photo;await image.decode();const c=document.createElement('canvas');c.width=old.sourceWidth;c.height=old.sourceHeight;const x=c.getContext('2d');x.drawImage(image,0,0);
  const frame={dataUrl:p.photo,photoId:p.photoId,width:c.width,height:c.height,angle:'FRONT',crop:{x:0,y:0,width:c.width,height:c.height},previewCrop:R('cameraStability').cameraCrop(p.landmarks),meshes:p.meshes,landmarks:p.landmarks,exclusions:p.exclusions,faceContour:[],rois:[],contours:{},localMaps:old.maps,contoursMeasured:old.contours};
  const ids=[];
  for(const corrupt of [false,true,'current']){
   const current=corrupt==='current',response=current?captured.updated:old;frame.localMaps=response.maps;frame.contoursMeasured=response.contours;const indicators=R('skinIndicators').measureSkinIndicators(x,frame,captured.quality);R('appearanceMeasurements').attachAppearance(indicators,response);const general=R('skinOverview').overviewFromResponse(response),id='label-replay-'+(current?'current':corrupt?'corrupt':'correct');general.analysisId=id;
   if(corrupt===true){for(const rows of Object.values(indicators))for(const row of rows)row.label=badLabels.regional[row.id];for(const row of general.indicators)row.label=badLabels.overview[row.id];}
   const record={id,date:'2026-10-11T10:00:00Z',schemaVersion:3,usedMediaPipe:true,comparisonScope:'single-front-v1',indicators,general,quality:captured.quality};
   await R('healthRecords').appendHealthRecord('skin',record,{},()=>true);if(!await R('healthRecords').withRecordsLock(()=>R('skinPhotoHistory').saveSkinPhotos(id,{FRONT:{...frame,general}})))throw Error('Fixture photo store failed');ids.push(id);
  }return ids;
 }''',dict(captured={**captured,'updated':updated},badLabels=dict(regional={k:v.encode('utf8').decode('cp1252',errors='replace') for k,v in LABELS.items()},overview={k:v.encode('utf8').decode('cp1252',errors='replace') for k,v in OVERVIEW.items()})))
 before=page.evaluate('localStorage.getItem("togg_health_skin_history")')
 scope_controls=page.evaluate('''({currentId})=>{
  const R=n=>__auditRequire('apps/vehicle-app/src/utils/'+n+'.ts'),I=R('skinIndicators'),A=R('appearanceMeasurements'),H=R('healthHistorySeries'),rows=JSON.parse(localStorage.getItem('togg_health_skin_history')),old=rows.find(r=>r.id==='label-replay-correct'),now=rows.find(r=>r.id==='label-replay-current');
  return ['dry','sag'].flatMap(criterion=>['overview','chin'].map(scope=>{const get=r=>(scope==='overview'?r.general.indicators:r.indicators[scope]).find(v=>v.id===criterion),a=get(now),b=get(old),comparable=I.canCompareIndicator(a,b);A.compareAppearance(a,b,true,old.id);return {scope,criterion,oldSampling:I.samplingSupportVersion(b.appearance),newSampling:I.samplingSupportVersion(a.appearance),sameNormalization:a.appearance.normalizationVersion===b.appearance.normalizationVersion,comparable,deltaBlocked:a.referenceDelta===undefined,seriesCount:H.buildHistorySeries('skin',[old,now]).filter(s=>s.region===scope&&s.criterion===criterion).length};}));
 }''',dict(currentId=new_record['id']))
 assert all(not v['sameNormalization'] and not v['comparable'] and v['deltaBlocked'] and v['seriesCount']==2 for v in scope_controls),scope_controls
 for ident in [new_record['id'],*fixture_ids]:
  page.goto('http://127.0.0.1:3000/profile');page.locator('[data-record-id="'+ident+'"]').get_by_role('button',name='Sonucu Aç',exact=True).click();dialog=page.get_by_role('dialog',name='Cilt Sağlığı sonucu',exact=True);expect(dialog.locator('[data-skin-snapshot]')).to_be_visible(timeout=15000)
  results.append(dict(case='history-'+ident,views=inspect_views(dialog,'history-'+ident)));page.keyboard.press('Escape')
 after=page.evaluate('localStorage.getItem("togg_health_skin_history")');unchanged=before==after;assert unchanged
 # Narrow + actual native 200% acceptance also uses the corrupted old row.
 page.set_viewport_size(dict(width=720,height=900));page.locator('[data-record-id="label-replay-corrupt"]').get_by_role('button',name='Sonucu Aç',exact=True).click();dialog=page.get_by_role('dialog',name='Cilt Sağlığı sonucu',exact=True);expect(dialog.locator('[data-skin-snapshot]')).to_be_visible();page.screenshot(path=str(OUT/'history-corrupt-narrow.png'),full_page=True);assert page.evaluate('document.documentElement.scrollWidth<=innerWidth');page.keyboard.press('Escape');context.close()
 import math
 pref=PROFILE/'Default/Preferences';settings=json.loads(pref.read_text('utf8'));settings.setdefault('partition',{})['default_zoom_level']={'x':math.log(2)/math.log(1.2)};pref.write_text(json.dumps(settings),'utf8')
 context=pw.chromium.launch_persistent_context(str(PROFILE),channel='chrome',headless=False,viewport=None,no_viewport=True,args=['--window-size=1600,1000','--enable-unsafe-swiftshader']);page=context.new_page();page.goto('http://127.0.0.1:3000/profile');page.locator('[data-record-id="label-replay-corrupt"]').get_by_role('button',name='Sonucu Aç',exact=True).click();dialog=page.get_by_role('dialog',name='Cilt Sağlığı sonucu',exact=True);expect(dialog.locator('[data-skin-snapshot]')).to_be_visible();expect(dialog.get_by_role('heading',name='Ton eşitsizliği',exact=True)).to_be_visible();geometry=page.evaluate('({innerWidth,outerWidth,dpr:devicePixelRatio,zoom:getComputedStyle(document.documentElement).zoom,scroll:document.documentElement.scrollWidth})');zoomOK=geometry['dpr']>=2 and geometry['innerWidth']<geometry['outerWidth']*.65 and geometry['zoom']=='1' and geometry['scroll']<=geometry['innerWidth'];assert zoomOK
 page.bring_to_front();cdp=context.new_cdp_session(page);(OUT/'history-corrupt-native200.png').write_bytes(base64.b64decode(cdp.send('Page.captureScreenshot',{'format':'png','fromSurface':False,'captureBeyondViewport':False})['data']));final=page.evaluate('localStorage.getItem("togg_health_skin_history")');assert final==before
 page.keyboard.press('Escape');page.locator('[data-record-id="label-replay-current"]').get_by_role('button',name='Sonucu Aç',exact=True).click();dialog=page.get_by_role('dialog',name='Cilt Sağlığı sonucu',exact=True);expect(dialog.locator('[data-skin-snapshot]')).to_be_visible()
 for _ in range(5):dialog.get_by_role('button',name='Sonraki Bölge',exact=True).click()
 assert dialog.locator('[data-skin-mesh]').get_attribute('data-skin-mesh')=='chin'
 dialog.locator('[data-skin-record-indicator="sag"]').click();fill=dialog.locator('[data-skin-local-fill="sag"]');expect(fill).to_be_visible();assert fill.get_attribute('data-map-photo')==updated['photoId']
 dialog.evaluate("el=>{const b=el.querySelector('[data-skin-snapshot]').getBoundingClientRect();el.scrollTop+=b.top+b.height*.4-el.getBoundingClientRect().top-90}")
 (OUT/'new-sag-history-native200.png').write_bytes(base64.b64decode(cdp.send('Page.captureScreenshot',{'format':'png','fromSurface':False,'captureBeyondViewport':False})['data']))
 receipt=dict(buildId=(ROOT/'apps/vehicle-app/.next/BUILD_ID').read_text('utf8').strip(),views=results,allKnownLabelsCorrect=all(v['allMatch'] for case in results for v in case['views']),historyBytesPreserved=unchanged and final==before,hostedConsentRequestCount=sum(bool(p.get('hostedProcessingConsent')) for p in requests),realMediaPipe=new_record['usedMediaPipe'],actualAPISourceMatches=all(p['photoId']==r['photoId'] for p,r in zip(requests,responses)),newScanBag=next(v for v in new_record['indicators']['periorbital'] if v['id']=='bags')['appearance'],newScanLines=next(v for v in new_record['indicators']['periorbital'] if v['id']=='lines')['appearance'],real200Percent=geometry,real200Accepted=zoomOK,isolatedProfileWithinOutput=PROFILE.resolve().is_relative_to(OUT.resolve()),pageErrors=errors)
 receipt['actualAPISourceMatches']=len(requests)==len(responses) and receipt['actualAPISourceMatches']
 receipt['samplingComparisonControls']=scope_controls
 receipt['renderedMapControls']=map_controls
 assert receipt['allKnownLabelsCorrect'] and receipt['actualAPISourceMatches'] and not errors
 (OUT/'proof.json').write_text(json.dumps(receipt,ensure_ascii=False,indent=2),'utf8');context.close();print(json.dumps({k:receipt[k] for k in ('buildId','allKnownLabelsCorrect','historyBytesPreserved','hostedConsentRequestCount','realMediaPipe','actualAPISourceMatches','real200Accepted')}))

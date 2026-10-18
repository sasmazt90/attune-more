import sys
from pathlib import Path
sys.path.insert(0,str(Path.cwd()/'tests/e2e'))
"""Licensed video fixture, real production MediaPipe, no pose/quality override.
V3 source pixels, regional graphs, reference separation and responsive screenshots.
"""
import json,time,sys,os,math,tempfile
from pathlib import Path
from playwright.sync_api import sync_playwright,expect
from owned_window_capture import capture_owned_window
OUT=Path(os.environ.get('SKIN_RESULT_AUDIT_DIR','audit-results/feedback-four-modules-20261009/skin'));OUT.mkdir(parents=True,exist_ok=True)
INIT="window.guidanceEvents=[];window.addEventListener('attune-guidance-event',e=>window.guidanceEvents.push({...e.detail,at:performance.now()}));window.workerMessages=[];window.workerTimings=[];window.surfaceRequests=[];window.surfaceResults=[];const post=Worker.prototype.postMessage;Worker.prototype.postMessage=function(m,...args){if(!this.timingObserved){this.timingObserved=true;this.timingRequests=new Map();this.addEventListener('message',({data})=>{const pending=this.timingRequests.get(data.id);if(pending&&!data.phase){window.workerTimings.push({type:pending.type,milliseconds:performance.now()-pending.at,error:!!data.error});this.timingRequests.delete(data.id);}});}if(m.id)this.timingRequests.set(m.id,{type:m.type,at:performance.now()});window.workerMessages.push({type:m.type,at:performance.now()});if(m.pixels&&m.meshes){window.surfaceRequests.push({id:m.id,width:m.width,height:m.height,pose:m.pose,meshes:m.meshes,exclusions:m.exclusions,qualityValid:m.qualityValid});if(!this.surfaceObserved){this.surfaceObserved=true;this.addEventListener('message',({data})=>{if(data.maps)window.surfaceResults.push(data);});}}return post.call(this,m,...args);};"
APPEARANCE="window.appearanceResponses=[];window.appearanceRequests=[];const originalFetch=window.fetch;window.fetch=async(...args)=>{if(String(args[0]).endsWith('/api/local-health/skin'))window.appearanceRequests.push(JSON.parse(args[1].body));const response=await originalFetch(...args);if(String(args[0]).endsWith('/api/local-health/skin')&&response.ok)window.appearanceResponses.push(await response.clone().json());return response;};"
profile=None;native200=None
def capture(page,context,path,native=False):
 if not native:page.screenshot(path=str(path),full_page=True);return
 return capture_owned_window(page,profile.name,path)
with sync_playwright() as pw:
 gpu=['--use-gl=angle','--use-angle=swiftshader'] if '--software-gpu' in sys.argv else []
 b=pw.chromium.launch(channel='chrome',headless=True,args=['--use-fake-device-for-media-stream','--use-file-for-fake-video-capture='+str(Path('audit-fixtures/three-angle.y4m').resolve()),'--enable-unsafe-swiftshader',*gpu])
 c=b.new_context(permissions=['camera'],viewport={'width':1600,'height':1000})
 c.add_init_script(INIT)
 c.add_init_script(APPEARANCE)
 p=c.new_page();errors=[];console=[];p.on('pageerror',lambda e:errors.append(str(e)));p.on('console',lambda m:console.append({'type':m.type,'text':m.text[:1000]}));model_requests=[];p.on('request',lambda r:model_requests.append(r.url) if 'selfie_multiclass' in r.url else None)
 c.request.post('http://127.0.0.1:8000/api/vehicle/speed',data={'speedKmH':0})
 runs=[]
 for n in range(2):
  if n==1:
   saved=c.storage_state();c.close();b.close()
   profile=tempfile.TemporaryDirectory(prefix='attune-skin-result-zoom-')
   pref=Path(profile.name)/'Default';pref.mkdir();(pref/'Preferences').write_text(json.dumps({'partition':{'default_zoom_level':{'x':math.log(2)/math.log(1.2)}}}),'utf8')
   c=pw.chromium.launch_persistent_context(profile.name,channel='chrome',headless=False,no_viewport=True,permissions=['camera'],args=['--window-size=1600,1000','--use-fake-device-for-media-stream','--use-file-for-fake-video-capture='+str(Path('audit-fixtures/three-angle.y4m').resolve()),'--enable-unsafe-swiftshader',*gpu])
   c.add_init_script(INIT)
   c.add_init_script(APPEARANCE)
   storage=saved['origins'][0]['localStorage']
   c.add_init_script('if(location.origin==="http://127.0.0.1:3000" && !sessionStorage.getItem("restored-fixture-state")){for(const v of '+json.dumps(storage)+')localStorage.setItem(v.name,v.value);sessionStorage.setItem("restored-fixture-state","1");}')
   p=c.new_page();p.on('pageerror',lambda e:errors.append(str(e)));p.on('request',lambda r:model_requests.append(r.url) if 'selfie_multiclass' in r.url else None)
  if n==0:
   p.goto('http://127.0.0.1:3000/privacy');p.get_by_label('Cilt ölçümlerini ve kişisel sayısal referansı bu tarayıcıda sakla').check()
  p.goto('http://127.0.0.1:3000/skin');start=time.monotonic();p.get_by_role('button',name='Analizi Başlat',exact=True).click()
  trace=[];deadline=time.monotonic()+270
  while not p.get_by_text('Cilt Analizi Tamamlandı',exact=True).count() and time.monotonic()<deadline:
   p.wait_for_timeout(2000)
   row=p.evaluate('({at:performance.now(),canvas:{...document.querySelector("canvas")?.dataset},guidance:document.querySelector("[data-camera-preparation]")?.innerText,body:document.body.innerText})');trace.append(row)
   (OUT/f'trace-{n}.json').write_text(json.dumps(trace,ensure_ascii=False,indent=2),'utf8')
   if not row['guidance'] and ('motoru' in row['body'] or 'başarısız' in row['body']):break
  if not p.get_by_text('Cilt Analizi Tamamlandı',exact=True).count():
   p.screenshot(path=str(OUT/f'failure-{n}.png'),full_page=True);(OUT/f'failure-{n}.json').write_text(json.dumps({'console':console,'pageErrors':errors,'body':p.locator('body').inner_text()},ensure_ascii=False,indent=2),'utf8')
  expect(p.get_by_text('Cilt Analizi Tamamlandı',exact=True)).to_be_visible(timeout=1000)
  if n==1:
   native200=p.evaluate('({innerWidth,outerWidth,dpr:devicePixelRatio,cssZoom:getComputedStyle(document.documentElement).zoom})')
   assert native200['dpr']>=2 and native200['innerWidth']<native200['outerWidth']*.65 and native200['cssZoom']=='1',native200
  value=p.evaluate('JSON.parse(localStorage.getItem("togg_health_latest_skin"))');ref=p.evaluate('JSON.parse(localStorage.getItem("attune_skin_appearance_reference_v1"))')
  assert value['schemaVersion']==3 and value['indicatorContract']=='regional-appearance-v4' and value['usedMediaPipe']
  assert value['isBaseline'] is False and value['analysisMode']=='instant-appearance-v2' and len(value['indicators'])==6
  assert ref is None, 'Active analysis must not create a personal reference'
  assert len({v['photoId'] for v in p.evaluate('window.appearanceRequests')[-3:]})==3
  assert not model_requests and all(m['type'] not in ('initializeSegmentation','segment') for m in p.evaluate('window.workerMessages'))
  assert 'data:image' not in p.evaluate('JSON.stringify(Object.fromEntries(Object.entries(localStorage)))')
  general=value['general'];assert general['analysisId']==value['id'] and general['pose']=='FRONT'
  assert p.get_by_role('heading',name='Genel Bakış',exact=True).count()==1
  assert p.locator('[data-skin-indicator]').count()==9 and p.locator('[data-skin-type]').count()==1
  assert p.locator('[data-skin-mesh]').count()==0,'Overview must not stack six meshes'
  assert '1 / 7' in p.locator('[data-skin-navigation]').inner_text()
  overview_svg=p.locator('[data-skin-snapshot]');assert overview_svg.get_attribute('data-snapshot-photoid')==general['captureId']
  overview_source=overview_svg.locator('image').first.get_attribute('href')
  p.screenshot(path=str(OUT/f'overview-{n}.png'),full_page=True)
  p.locator('[data-skin-indicator="redness"]').click()
  assert p.locator('[data-skin-local-fill]').get_attribute('data-map-photo')==general['captureId']
  assert p.locator('[data-skin-mesh]').count()==0 and overview_svg.locator('image').first.get_attribute('href')==overview_source
  capture(p,c,OUT/f'overview-map-{n}.png',n==1)
  p.get_by_role('button',name='Sonraki Bölge',exact=True).click()
  graphs=[];source_by_region={};photo_by_region={}
  for i in range(6):
   svg=p.locator('[data-skin-snapshot]');mesh=p.locator('[data-skin-mesh]');assert mesh.count()==1
   region=mesh.get_attribute('data-skin-mesh');graphs.append(region);assert mesh.locator('[data-mesh-edge]').count()>0
   assert svg.locator('clipPath').count()==1 and svg.locator('mask').count()==0
   width=float(svg.get_attribute('data-snapshot-width'));height=float(svg.get_attribute('data-snapshot-height'))
   crop=json.loads(p.locator('[data-face-panel]').get_attribute('data-preview-crop'))
   box=list(map(float,svg.get_attribute('viewBox').split()))
   expected=[crop['x']*width,crop['y']*height,crop['width']*width,crop['height']*height]
   assert all(abs(a-b)<.0001 for a,b in zip(box,expected))
   assert 0<=box[0] and 0<=box[1] and box[0]+box[2]<=width+.0001 and box[1]+box[3]<=height+.0001
   assert box[2]<width*.9 and box[3]<height*.95, 'Result must use actual face framing'
   assert p.evaluate("""()=>{const s=document.querySelector('[data-skin-snapshot]'),v=s.viewBox.baseVal,m=s.querySelector('[data-skin-mesh]').getBBox();return m.x>=v.x&&m.y>=v.y&&m.x+m.width<=v.x+v.width&&m.y+m.height<=v.y+v.height;}""")
   shown=[v.removesuffix('%') for v in p.locator('[data-skin-score]').all_text_contents()]
   numeric=[v for v in value['indicators'][region] if v['score'] is not None]
   expected_scores=[]
   for indicator in numeric:
    appearance=indicator.get('appearance',{})
    if appearance.get('type')=='longitudinal_measurement':
     expected_scores.append('Referans oluşturuldu' if appearance.get('limitationCode')=='REFERENCE_CREATED' else str(math.floor(indicator['score']*1000+.5)))
    else:expected_scores.append(str(math.floor(indicator['score']+.5)))
   assert shown==expected_scores,(region,shown,expected_scores)
   assert p.get_by_role('meter').count()==sum(v.get('appearance',{}).get('type')!='longitudinal_measurement' and v.get('appearance',{}).get('unit')!='candidate-count' for v in numeric)
   for indicator in value['indicators'][region]:
    if indicator['score'] is None:assert p.locator('[data-skin-indicator="'+indicator['id']+'"]').get_by_role('meter').count()==0
   layout=p.locator('[data-skin-result-layout]').bounding_box();photo=p.locator('[data-face-panel]').bounding_box()
   p.screenshot(path=str(OUT/f'layout-{n}-{region}.png'),full_page=True)
   assert abs(photo['y']-layout['y'])<=1, ('Photo must align with summary top',n,region,photo,layout)

   alpha=p.evaluate('''async()=>{const image=new Image();image.src=document.querySelector('[data-skin-snapshot] image').getAttribute('href');await image.decode();const canvas=document.createElement('canvas');canvas.width=image.naturalWidth;canvas.height=image.naturalHeight;const ctx=canvas.getContext('2d');ctx.drawImage(image,0,0);const data=ctx.getImageData(0,0,canvas.width,canvas.height).data;let nonopaque=0;for(let i=3;i<data.length;i+=4)if(data[i]!==255)nonopaque++;return {nonopaque,width:canvas.width,height:canvas.height};}''')
   assert alpha['nonopaque']==0
   photo_id=svg.get_attribute('data-snapshot-photoid');assert photo_id
   surface=p.evaluate('(id)=>window.surfaceResults.find(v=>v.photoId===id)',photo_id);assert surface
   request=p.evaluate('(id)=>window.surfaceRequests.find(v=>v.id===id)',surface['id']);assert request
   import base64
   source=svg.locator('image').first.get_attribute('href');source_by_region[region]=source;photo_by_region[region]=photo_id;(OUT/f'source-{n}-{region}.png').write_bytes(base64.b64decode(source.split(',')[1]))
   (OUT/f'source-{n}-{region}.json').write_text(json.dumps({**request,'region':region,'photoId':photo_id,'localAnalysis':json.loads(svg.get_attribute('data-local-analysis'))}),'utf8')
   appearance_request=p.evaluate('(id)=>window.appearanceRequests?.find(v=>v.photoId===id)',photo_id)
   if appearance_request:(OUT/f'appearance-{n}-{region}.json').write_text(json.dumps(appearance_request),'utf8')
   appearance_response=p.evaluate('(id)=>window.appearanceResponses.find(v=>v.photoId===id)',photo_id);assert appearance_response
   (OUT/f'appearance-response-{n}-{region}.json').write_text(json.dumps(appearance_response),'utf8')
   if region!='periorbital':
    mapping=appearance_response['maps'][region+':redness'];assert mapping['photoId']==photo_id and mapping['region']==region and mapping['pose']==request['pose']
    # Real user-facing card interaction, no fabricated map or model result.
    source_before=svg.locator('image').first.get_attribute('href')
    p.locator('[data-skin-indicator="redness"]').click()
    fill=p.locator('[data-skin-local-fill]');assert fill.count()==1 and fill.get_attribute('data-skin-local-fill')=='redness' and fill.get_attribute('data-map-photo')==photo_id
    assert svg.locator('clipPath').count()==1 and svg.locator('mask').count()==1
    assert svg.evaluate('(s)=>s.querySelector("[data-skin-local-fill]").compareDocumentPosition(s.querySelector("[data-skin-mesh]"))&Node.DOCUMENT_POSITION_FOLLOWING')
    source_after=svg.locator('image').first.get_attribute('href');assert source_after==source_before
    raw={**mapping,'rgba':mapping['dataUrl'],'mask':mapping['validMaskUrl']}
    # Typed arrays cross evaluate as indexed objects; use Object.values below.
    (OUT/f'map-{n}-{region}.json').write_text(json.dumps(raw),'utf8')
    capture(p,c,OUT/f'fill-{n}-{region}.png',n==1)
    raster=p.evaluate('''async()=>{const s=document.querySelector('[data-skin-snapshot]').cloneNode(true);s.querySelector('image').remove();s.querySelector('[data-skin-mesh]').remove();const width=+s.dataset.snapshotWidth,height=+s.dataset.snapshotHeight;s.setAttribute('xmlns','http://www.w3.org/2000/svg');s.setAttribute('viewBox',`0 0 ${width} ${height}`);s.setAttribute('width',width);s.setAttribute('height',height);const u=URL.createObjectURL(new Blob([new XMLSerializer().serializeToString(s)],{type:'image/svg+xml'}));try{const i=new Image();i.src=u;await i.decode();const canvas=document.createElement('canvas');canvas.width=width;canvas.height=height;canvas.getContext('2d').drawImage(i,0,0);return canvas.toDataURL('image/png');}finally{URL.revokeObjectURL(u);}}''')
    (OUT/f'rendered-map-{n}-{region}.png').write_bytes(base64.b64decode(raster.split(',')[1]))
    p.locator('[data-skin-indicator="tone"]').focus();p.keyboard.press('Enter');assert p.locator('[data-skin-local-fill]').get_attribute('data-skin-local-fill')=='tone'
    if region!='nose':p.locator('[data-skin-indicator="sag"]').click()

   for criterion in ('oil','acne','dry','dark','lines','bags','sag'):
    card=p.locator('[data-skin-indicator="'+criterion+'"]')
    if not card.count():continue
    card.click();expected_map=appearance_response['maps'].get(region+':'+criterion)
    item=next(v for v in value['indicators'][region] if v['id']==criterion)
    fill=p.locator('[data-skin-local-fill]')
    assert fill.count()==int(expected_map is not None and item['score'] is not None),(region,criterion,item)
    if fill.count():assert fill.get_attribute('data-skin-local-fill')==criterion and fill.get_attribute('data-map-photo')==photo_id
    if criterion=='acne':
     row=next(v for v in appearance_response['measurements'][region] if v['id']=='acne');assert p.locator('[data-acne-candidate]').count()==len(row['components'].get('bounds',[]))
   # Preserve the same initial result view for the visual acceptance evidence.
   p.locator('[data-skin-indicator]').first.click()

   if region=='nose':assert p.get_by_role('heading',name='T-Bölgesi',exact=True).count()==1 and p.locator('[data-skin-indicator]').count()==5
   if region=='periorbital':assert p.locator('[data-skin-indicator]').count()==4
   for indicator in value['indicators'][region]:
    if indicator.get('appearance'):
     assert indicator['appearance']['region']==region
     assert indicator['score']==indicator['appearance']['value']
     if indicator['score'] is None:assert indicator['appearance']['limitationCode']
   assert p.locator('[data-skin-navigation]').bounding_box()['y']>=p.locator('[data-face-panel]').bounding_box()['y']+p.locator('[data-face-panel]').bounding_box()['height']-1
   if n==1:
    geometry=p.evaluate('({width:innerWidth,scroll:document.documentElement.scrollWidth,photo:document.querySelector("[data-face-panel]").getBoundingClientRect().toJSON(),summary:document.querySelector("[data-skin-indicators]").getBoundingClientRect().toJSON()})')
    assert geometry['scroll']<=geometry['width'] and geometry['photo']['right']<=geometry['width'] and geometry['summary']['right']<=geometry['width'],geometry
    p.locator('[data-face-panel]').scroll_into_view_if_needed()
    physical=capture(p,c,OUT/f'{n}-{region}-native200.png',True)
    p.locator('[data-skin-indicators]').scroll_into_view_if_needed()
    score_capture=capture(p,c,OUT/f'{n}-{region}-native200-scores.png',True)
    (OUT/f'{n}-{region}-native200-geometry.json').write_text(json.dumps({'dom':geometry,'physical':physical,'scoreCapture':score_capture}),'utf8')
   else:
    p.screenshot(path=str(OUT/f'{n}-{region}-desktop.png'),full_page=True)
   p.get_by_role('button',name='Sonraki Bölge',exact=True).click()
  assert graphs==['forehead','rightCheek','leftCheek','nose','chin','periorbital']
  timings=p.evaluate('window.workerTimings');initializations=[t['milliseconds'] for t in timings if t['type']=='initialize' and not t['error']];frames=[t['milliseconds'] for t in timings if t['type']=='frame' and not t['error']]
  assert initializations and frames
  runs.append({'seconds':time.monotonic()-start,'result':value,'reference':ref,'sourcePhotoOpaque':True,'graphs':graphs,'cameraWorkerTiming':{'initializeRoundTripMs':initializations,'firstFrameRoundTripMs':frames[0],'medianFrameRoundTripMs':__import__('statistics').median(frames),'measuredFrames':len(frames),'guidanceEvents':p.evaluate('window.guidanceEvents'),'definition':'actual worker request-response; initialization includes assets/runtime readiness; frame includes bitmap IPC/inference/response; no speedup claim'}})
  (OUT/f'completed-{n}.json').write_text(json.dumps(runs[-1],ensure_ascii=False,indent=2),'utf8')
  p.get_by_role('button',name='Referans ve görüntü hakkında bilgi').click();dialog=p.get_by_role('dialog');assert dialog.locator('li').count()==6
  assert 'alpha dekupe' not in dialog.inner_text() and 'Eski kayıtların sayısal' not in dialog.inner_text()
  capture(p,c,OUT/f'reference-info-{n}.png',n==1);p.keyboard.press('Escape')
  if n==0:
   p.set_viewport_size({'width':720,'height':900});capture(p,c,OUT/'narrow.png');assert p.evaluate('document.documentElement.scrollWidth<=innerWidth')
   p.set_viewport_size({'width':1600,'height':1000})
   # Deliberately unreadable historical keys must not gate the next current-photo scan.
   legacy_raw='corrupt-old-reference-preserved'
   p.evaluate('(raw)=>{for(const key of ["togg_health_skin_multi_baseline_v2","attune_skin_appearance_single_reference_v1","togg_health_skin_baseline"])localStorage.setItem(key,raw);}',legacy_raw)
  else:assert p.evaluate('localStorage.getItem("togg_health_skin_multi_baseline_v2")')==legacy_raw
  # Client navigation preserves only the in-memory current session frames.
  p.get_by_role('link',name='Sağlık Geçmişim',exact=True).click();p.locator('[data-record-id="'+value['id']+'"]').get_by_role('button',name='Sonucu Aç',exact=True).click()
  dialog=p.get_by_role('dialog',name='Cilt Sağlığı sonucu',exact=True)
  assert dialog.get_by_role('heading',name='Genel Bakış',exact=True).count()==1
  assert dialog.locator('[data-skin-mesh]').count()==0
  assert dialog.locator('[data-skin-snapshot]').get_attribute('data-snapshot-photoid')==general['captureId']
  assert dialog.locator('[data-skin-snapshot] image').first.get_attribute('href')==overview_source
  dialog.get_by_role('button',name='Sonraki Bölge',exact=True).click()
  for region in graphs:
   current=dialog.locator('[data-skin-snapshot]');assert current.get_attribute('data-snapshot-photoid')==photo_by_region[region]
   assert current.locator('image').first.get_attribute('href')==source_by_region[region]
   assert dialog.locator('[data-skin-mesh]').get_attribute('data-skin-mesh')==region
   assert dialog.locator('[data-skin-local-fill]').count()==0
   card=dialog.locator('[data-skin-record-indicator="'+('dark' if region=='periorbital' else 'redness')+'"]');card.click()
   if dialog.locator('[data-skin-local-fill]').count():assert dialog.locator('[data-skin-local-fill]').get_attribute('data-map-photo')==photo_by_region[region]
   if region=='forehead':capture(p,c,OUT/f'history-session-photo-{n}.png',n==1)
   dialog.get_by_role('button',name='Sonraki Bölge',exact=True).click()
  p.keyboard.press('Escape');assert 'data:image' not in p.evaluate('JSON.stringify(Object.fromEntries(Object.entries(localStorage)))')
 assert not errors,errors
 proof={'status':'PASS','buildId':Path('apps/vehicle-app/.next/BUILD_ID').read_text().strip(),'controlledFixture':True,'physicalCamera':False,'poseMock':False,'qualityOverride':False,'segmentationRequests':model_requests,'legacyReferencePreserved':True,'sourcePhotoOpaque':True,'faceFraming':True,'integerScores':True,'unavailableBars':False,'native200':native200,'localMaps':'actual CV appearance maps + selected-source geometry; no clinical validation','pageErrors':errors,'runs':runs}
 (OUT/'proof.json').write_text(json.dumps(proof,ensure_ascii=False,indent=2),'utf8');c.close()
 if profile:profile.cleanup()
print('PASS: current photo, actual three fixture poses, six selected meshes, no reference dependency, native 200 layout')

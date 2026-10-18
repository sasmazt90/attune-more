"""Actual local ONNX upload + disposable five-module history, no human acceptance.
Delayed responses are real responses; only transport timing is controlled.
"""
import asyncio,hashlib,io,json,os,sys,subprocess,tempfile,atexit,urllib.request,time
from pathlib import Path
from PIL import Image,ImageFilter
from playwright.async_api import async_playwright,expect
ROOT=Path(__file__).resolve().parents[2]
OUT=ROOT/'audit-results/feedback-four-modules-20261009/dental-history';OUT.mkdir(parents=True,exist_ok=True)
INFO=json.loads((ROOT/'audit-results/current-health-20261009/public-positive.json').read_text('utf8'))
PHOTO=Path(INFO['path']);assert hashlib.sha256(PHOTO.read_bytes()).hexdigest()==INFO['sourceSHA256']
KEYS={'vision':'togg_health_vision_history','skin':'togg_health_skin_history','mental':'togg_health_mental_history','dental':'attune_dental_history_v1','hearing':'attune_hearing_history_v1'}
INIT="window.guidanceEvents=[];window.addEventListener('attune-guidance-event',e=>window.guidanceEvents.push({...e.detail,at:performance.now()}));window.cameraCalls=0;const gum=navigator.mediaDevices.getUserMedia.bind(navigator.mediaDevices);navigator.mediaDevices.getUserMedia=(...a)=>{window.cameraCalls++;return gum(...a);};window.workerCalls=0;const W=window.Worker;window.Worker=class extends W{constructor(...a){super(...a);window.workerCalls++;}};"
store=tempfile.TemporaryDirectory(prefix='attune-dental-wipe-isolated-')
env={**os.environ,'ATTUNE_DATA_DIR':store.name,'ATTUNE_LOAD_LOCAL_ENV':'0','PYTHONPATH':str(ROOT/'.runtime/security-20261008')+os.pathsep+str(ROOT/'services/core-api')};env.pop('OPENAI_API_KEY',None)
log=(OUT/'isolated-backend.log').open('w',encoding='utf8')
server=subprocess.Popen([sys.executable,'-X','utf8','-m','uvicorn','main:app','--host','127.0.0.1','--port','8002'],cwd=ROOT/'services/core-api',env=env,stdout=log,stderr=log,creationflags=subprocess.CREATE_NO_WINDOW)
def cleanup():
 if server.poll() is None:server.terminate();server.wait(timeout=15)
 log.close();store.cleanup()
atexit.register(cleanup)
for _ in range(40):
 try:urllib.request.urlopen('http://127.0.0.1:8002/api/health',timeout=1);break
 except urllib.error.URLError:time.sleep(.5)
else:raise RuntimeError('Isolated backend unavailable')
async def main():
 async with async_playwright() as pw:
  browser=await pw.chromium.launch(channel='chrome',headless=True,args=['--autoplay-policy=no-user-gesture-required'])
  c=await browser.new_context(viewport={'width':1600,'height':1000});await c.add_init_script(INIT);p=await c.new_page();errors=[];p.on('pageerror',lambda e:errors.append(str(e)))
  async def isolated_wipe(route):
   response=await route.fetch(url='http://127.0.0.1:8002/api/privacy/wipe');await route.fulfill(response=response)
  await c.route('**/api/privacy/wipe',isolated_wipe)
  await c.request.post('http://127.0.0.1:8000/api/vehicle/speed',data={'speedKmH':0})
  await p.goto('http://127.0.0.1:3000/dental');await p.get_by_label('Fotoğraflarımı yalnız bu cihazda geçici işlemeyi kabul ediyorum.').check()
  inp=p.get_by_label('Diş fotoğrafı seç');await expect(p.get_by_role('button',name='Fotoğraf Yükle',exact=True)).to_be_enabled();await inp.set_input_files(str(PHOTO))
  # This covers model preparation + first frame + the existing 30s API stage.
  # A real product timeout still yields an error and cannot satisfy this check.
  await expect(p.locator('[data-dental-result]')).to_be_visible(timeout=60000)
  assert await p.evaluate('window.cameraCalls===0&&window.workerCalls>0')
  initial_workers=await p.evaluate('workerCalls')
  assert await p.locator('[data-dental-result] rect').count()>0
  svg=p.get_by_role('img',name='Gerçek diş fotoğrafı ve görünür adaylar');dims=await svg.get_attribute('viewBox');image=await svg.locator('image').get_attribute('href')
  assert dims=='0 0 1617 1212' and image.startswith('data:image/png;base64,')
  assert await p.evaluate('localStorage.getItem("attune_dental_latest_v1")') is None
  await p.get_by_label('Sayısal sonucu yerel geçmişime kaydet.').check();await p.get_by_role('button',name='Sonucu kaydet',exact=True).click()
  await expect(p.get_by_text('Yalnız sayısal ölçüm ve aday koordinatları yerel geçmişe kaydedildi.',exact=True)).to_be_visible()
  record=await p.evaluate('JSON.parse(localStorage.getItem("attune_dental_latest_v1"))')
  assert record['sourceType']=='upload' and record['measurements'][0]['caries']['value']>0 and 'data:image' not in json.dumps(record)
  assert record['measurements'][0]['accumulation']['viewSupport']==1
  await p.screenshot(path=str(OUT/'actual-upload.png'),full_page=True)
  # Native source pixels and model-coordinate bounds must agree in the actual SVG.
  bounds=await svg.locator('rect').evaluate_all('(a)=>a.map(e=>["x","y","width","height"].map(k=>+e.getAttribute(k)))')
  for x,y,w,h in bounds:assert 0<=x<x+w<=1617 and 0<=y<y+h<=1212
  # Cancel a real request held after local inference: its late result cannot reappear.
  received=asyncio.Event();release=asyncio.Event();calls=[]
  async def delay(route):
   response=await route.fetch();calls.append(response.status);received.set();await release.wait()
   try:await route.fulfill(response=response)
   except Exception:pass # The real client cancellation intentionally closes transport.
  await p.route('**/api/local-health/dental-upload',delay)
  await inp.set_input_files(str(PHOTO));await asyncio.wait_for(received.wait(),60)
  await p.get_by_role('button',name='İptal et',exact=True).click();release.set();await asyncio.sleep(.5)
  await expect(p.locator('[data-dental-result]')).to_have_count(0)
  await expect(p.get_by_role('button',name='Diş Taramasını Başlat')).to_be_visible()
  await p.unroute('**/api/local-health/dental-upload',delay)
  # File replacement: hold a real poor-quality response; the next positive source wins.
  blurred=io.BytesIO();Image.open(PHOTO).filter(ImageFilter.GaussianBlur(25)).save(blurred,format='PNG')
  received.clear();release.clear()
  async def first_only(route):
   if not received.is_set():await delay(route)
   else:await route.continue_()
  await p.route('**/api/local-health/dental-upload',first_only)
  await inp.set_input_files({'name':'actual-source-blurred.png','mimeType':'image/png','buffer':blurred.getvalue()});await asyncio.wait_for(received.wait(),60)
  await inp.set_input_files(str(PHOTO));await expect(p.locator('[data-dental-result]')).to_be_visible(timeout=60000);release.set();await asyncio.sleep(.5)
  assert await svg.locator('image').get_attribute('href')==image
  await expect(p.get_by_text('Tek fotoğrafın görünür yüzey sonucu. Çoklu açı doğrulaması yapılmadı.',exact=True)).to_be_visible()
  await p.unroute('**/api/local-health/dental-upload',first_only)
  assert await p.evaluate('window.cameraCalls===0')
  await p.get_by_role('button',name='Geçici görüntüleri temizle',exact=True).click()
  await inp.set_input_files({'name':'not-photo.png','mimeType':'image/png','buffer':b'<svg>not an image</svg>'})
  await expect(p.locator('[data-dental-page]').get_by_role('alert')).to_be_visible();await p.get_by_role('button',name='İptal et',exact=True).click()
  # Existing legacy records are declared history fixtures, not completed physical sessions.
  hearing=json.loads((ROOT/'audit-results/feedback-four-modules-20261009/hearing-positive/proof.json').read_text('utf8'))['result']
  skin=json.loads((ROOT/'audit-results/feedback-four-modules-20261009/skin/completed-0.json').read_text('utf8'))['result']
  fixtures={'vision':{'id':'legacy-vision-fixture','date':'2026-10-01T09:00:00Z','acuityRightSnellen':'20/30','acuityLeftSnellen':'20/40','controlledHistoryFixture':True},'mental':{'id':'legacy-mental-fixture','date':'2026-10-02T09:00:00Z','methodVersion':'legacy-summary','summaryText':'Sabit kişisel olmayan kayıt testi.','transcriptConsented':False},'skin':skin,'hearing':hearing}
  await p.evaluate('({fixtures,keys})=>{for(const [k,v] of Object.entries(fixtures)){localStorage.setItem(keys[k],JSON.stringify([v]));const latest={vision:"togg_health_latest_vision",skin:"togg_health_latest_skin",mental:"togg_health_latest_mental",hearing:"attune_hearing_latest_v1"}[k];if(latest)localStorage.setItem(latest,JSON.stringify(v));}localStorage.setItem("foreign_sentinel","keep");}',{'fixtures':fixtures,'keys':KEYS})
  legacy={'id':'legacy-contour-fixture','timestamp':'2026-09-01T09:00:00Z','methodVersion':'appearance-cv-1','isBaseline':False,'controlledHistoryFixture':True,'indicators':{'forehead':[{'id':'sag','label':'Sarkma','score':.02,'appearance':{'type':'longitudinal_measurement','unit':'normalized-contour-ratio','methodVersion':'appearance-cv-1','limitationCode':None}}]}}
  await p.evaluate('(legacy)=>{const k="togg_health_skin_history",a=JSON.parse(localStorage.getItem(k));a.push(legacy);localStorage.setItem(k,JSON.stringify(a));}',legacy)
  await p.goto('http://127.0.0.1:3000/profile');history=p.locator('[data-record-history=all]');await expect(history.locator('[data-record-id]')).to_have_count(6)
  rows=await history.locator('[data-record-id]').evaluate_all('(a)=>a.map(e=>({category:e.dataset.recordCategory,id:e.dataset.recordId,text:e.innerText,classes:e.className}))')
  assert len({v['classes'] for v in rows})==1 and {r['category'] for r in rows}==set(KEYS)
  names=json.loads((ROOT/'shared/healthModules.json').read_text('utf8'))
  links=[]
  for category in KEYS:
   row=history.locator('[data-record-category='+category+']').first;await row.get_by_role('button',name='Sonucu Aç',exact=True).click();dialog=p.get_by_role('dialog',name=names[category]['name']+' sonucu',exact=True);await expect(dialog).to_be_visible()
   href=await dialog.get_by_role('link',name='Uzman seçenekleri',exact=True).get_attribute('href');assert 'from='+category in href and 'recordId=' in href;links.append(href)
   if category=='hearing':await expect(dialog).to_contain_text('dB SNR')
   if category=='skin':
    await expect(dialog.get_by_role('heading',name='Alın',exact=True)).to_be_visible();await dialog.get_by_role('button',name='Sonraki Bölge').click();await expect(dialog.get_by_role('heading',name='Sağ Yanak',exact=True)).to_be_visible();await p.screenshot(path=str(OUT/'skin-history-carousel.png'),full_page=True)
   await p.keyboard.press('Escape')
  await history.locator('[data-record-id=legacy-contour-fixture]').get_by_role('button',name='Sonucu Aç',exact=True).click()
  await expect(p.get_by_role('dialog').locator('[data-skin-score]')).to_have_text('20');await expect(p.get_by_role('dialog')).to_contain_text('× 10⁻³ kontur oranı');await p.keyboard.press('Escape')
  await p.get_by_role('button',name='Hekimle Paylaşılabilir Özet',exact=True).click()
  share=p.get_by_role('dialog',name='Hekim Paylaşım Özeti',exact=True)
  for module in names.values():await expect(share.get_by_label(module['name'],exact=True)).to_be_enabled()
  await p.keyboard.press('Escape')
  await p.screenshot(path=str(OUT/'five-module-history.png'),full_page=True)
  row=history.locator('[data-record-category=dental]');await row.get_by_role('button',name='Sil',exact=False).click();await p.get_by_role('button',name='Evet, sil',exact=True).click();await expect(history.locator('[data-record-id]')).to_have_count(5)
  assert await p.evaluate('JSON.parse(localStorage.getItem("attune_dental_history_v1")).length')==0
  await p.reload();await expect(history.locator('[data-record-id]')).to_have_count(5)
  await p.goto('http://127.0.0.1:3000/privacy');await p.get_by_role('button',name='TÜM YEREL VERİLERİ SİL',exact=True).click();await p.get_by_role('button',name='Evet, Tüm Verileri Sil',exact=True).click()
  await expect(p.get_by_text('Tüm yerel veriler başarıyla temizlendi.',exact=True)).to_be_visible(timeout=15000)
  assert await p.evaluate('(keys)=>Object.values(keys).every(k=>!localStorage.getItem(k))&&localStorage.getItem("foreign_sentinel")==="keep"',KEYS)
  assert not errors,errors
  proof={'status':'PASS','buildId':(ROOT/'apps/vehicle-app/.next/BUILD_ID').read_text().strip(),'actualONNX':True,'sourceSHA256':INFO['sourceSHA256'],'nativeSource':[1617,1212],'actualCandidates':len(bounds),'optionalFaceWorkerCalls':initial_workers,'cameraCalls':0,'cancelLateRealResponse':True,'replacementLateRealError':True,'badMagicRejected':True,'numericConsentedSave':True,'noPersistentPhotos':True,'fiveCategoryHistory':rows,'careLinks':links,'legacyRatioDisplayedWithoutRelabel':True,'oneDeletePreservesOthers':True,'wipeAllFive':True,'isolatedBackendWipe':True,'foreignStoragePreserved':True,'historyFixturesDeclared':True,'physicalAcceptance':False,'pageErrors':errors}
  (OUT/'proof.json').write_text(json.dumps(proof,ensure_ascii=False,indent=2),'utf8');await c.close();await browser.close()
 print('PASS actual static upload, source pixels/ONNX bounds, cancellation/replacement, five histories/delete/wipe')
asyncio.run(main())

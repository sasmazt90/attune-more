"""Real production browser/MediaPipe/crop/API with recorded provider replies.
Only licensed camera fixture; replay is contract evidence, not subject accuracy.
Normal user profile/history and remote photo processing are never used.
"""
import hashlib,json,time,urllib.request
from contextlib import ExitStack
from pathlib import Path
from playwright.sync_api import sync_playwright,expect
ROOT=Path(__file__).resolve().parents[2]
OUT=ROOT/'output/playwright/hosted-type-20261012';OUT.mkdir(parents=True,exist_ok=True)
receipt=json.loads((ROOT/'audit-results/skin-type-integration-20261012/replay-server.json').read_text())
PROVIDER='http://127.0.0.1:'+str(receipt['providerPort'])
PERMISSION='Cilt tipi için yüz fotoğrafımın Roboflow tarafından işlenmesine izin ver'
INIT="window.workerMessages=[];window.workerTimings=[];const post=Worker.prototype.postMessage;Worker.prototype.postMessage=function(m,...args){window.workerMessages.push(m.type);if(!this.observed){this.observed=true;this.requests=new Map();this.addEventListener('message',({data})=>{const r=this.requests.get(data.id);if(r&&!data.phase)window.workerTimings.push({type:r.type,ms:performance.now()-r.at,error:!!data.error});});}if(m.id)this.requests.set(m.id,{type:m.type,at:performance.now()});return post.call(this,m,...args);};window.appearanceRequests=[];window.appearanceResponses=[];const fetchOriginal=window.fetch;window.fetch=async(...a)=>{if(String(a[0]).endsWith('/api/local-health/skin'))window.appearanceRequests.push(JSON.parse(a[1].body));const r=await fetchOriginal(...a);if(String(a[0]).endsWith('/api/local-health/skin')&&r.ok)window.appearanceResponses.push(await r.clone().json());return r;};"
def provider_state():
 with urllib.request.urlopen(PROVIDER,timeout=3) as r:return json.loads(r.read())
def mode(value):
 req=urllib.request.Request(PROVIDER+'/control',data=json.dumps({'mode':value}).encode(),headers={'Content-Type':'application/json'})
 with urllib.request.urlopen(req,timeout=3):pass
def configure_front(page):
 page.goto('http://127.0.0.1:3000/skin')
 page.get_by_role('button',name='Cilt taraması hakkında bilgi',exact=True).click()
 page.get_by_label('Üç açılı tarama',exact=True).uncheck()
 page.keyboard.press('Escape')
 page.wait_for_function('document.querySelector("canvas")?.dataset.mediapipeReady==="true"',timeout=90000)
def start(page):
 page.get_by_role('button',name='Analizi Başlat',exact=True).click()
def complete(page):
 try:expect(page.get_by_text('Cilt Analizi Tamamlandı',exact=True)).to_be_visible(timeout=150000)
 except Exception:
  page.screenshot(path=str(OUT/'failure.png'),full_page=True)
  (OUT/'failure.json').write_text(json.dumps(dict(body=page.locator('body').inner_text(),console=console,pageErrors=errors,workerTimings=page.evaluate('window.workerTimings'),requests=page.evaluate('window.appearanceRequests')),ensure_ascii=False,indent=2),'utf8')
  raise
 return page.evaluate('JSON.parse(localStorage.getItem("togg_health_latest_skin"))')
def summary(page,record):
 request=page.evaluate('window.appearanceRequests.at(-1)');response=page.evaluate('window.appearanceResponses.at(-1)')
 assert request['qualityValid'] is True and response['photoId']==request['photoId']
 assert record['usedMediaPipe'] and record['general']['captureId']==request['photoId']
 assert any(v['type']=='frame' and not v['error'] for v in page.evaluate('window.workerTimings'))
 assert 'data:image' not in page.evaluate('JSON.stringify(Object.fromEntries(Object.entries(localStorage)))')
 return dict(recordId=record['id'],photoId=request['photoId'],sourcePhotoSHA256=hashlib.sha256(request['photo'].encode()).hexdigest(),landmarks=len(request['landmarks']),qualityValid=request['qualityValid'],hostedConsent=request['hostedProcessingConsent'],skinType=record['general']['skinType'],transform=response['general'].get('modelInputTransform'),workerTimings=page.evaluate('window.workerTimings'))
def history(page,record,label):
 page.get_by_role('link',name='Sağlık Geçmişim',exact=True).click()
 page.locator('[data-record-id="'+record['id']+'"]').get_by_role('button',name='Sonucu Aç',exact=True).click()
 dialog=page.get_by_role('dialog',name='Cilt Sağlığı sonucu',exact=True)
 expect(dialog.locator('[data-skin-type] strong')).to_have_text(label)
 assert dialog.locator('[data-skin-type]').get_by_role('meter').count()==0
 assert dialog.locator('[data-skin-snapshot]').get_attribute('data-snapshot-photoid')==record['general']['captureId']
 page.screenshot(path=str(OUT/(label+'-history.png')),full_page=True)
 page.keyboard.press('Escape')
def wait_provider(page,before):
 end=time.monotonic()+90
 while len(provider_state()['calls'])==before and time.monotonic()<end:page.wait_for_timeout(250)
 assert len(provider_state()['calls'])>before
with sync_playwright() as pw, ExitStack() as cleanup:
 errors=[];console=[]
 # Every product backend request uses the real isolated API. No live key/provider.
 def route(request):
  url=request.request.url
  if url.startswith(('http://localhost:8000/','http://127.0.0.1:8000/')):
   target='http://127.0.0.1:8103/'+url.split(':8000/',1)[1]
   response=request.fetch(url=target,timeout=60000);request.fulfill(response=response)
  else:request.continue_()
 def launch(saved=None):
  browser=pw.chromium.launch(channel='chrome',headless=True,args=['--use-fake-device-for-media-stream','--use-file-for-fake-video-capture='+str(ROOT/'audit-fixtures/three-angle.y4m'),'--enable-unsafe-swiftshader'])
  cleanup.callback(browser.close)
  context=browser.new_context(permissions=['camera'],viewport={'width':1600,'height':1000},storage_state=saved);context.add_init_script(INIT)
  context.route('http://localhost:8000/**',route);context.route('http://127.0.0.1:8000/**',route)
  page=context.new_page();page.on('pageerror',lambda error:errors.append(str(error)));page.on('console',lambda message:console.append({'type':message.type,'text':message.text[:1000]}))
  return browser,context,page
 def recycle(browser,context):
  saved=context.storage_state();context.close();browser.close()
  return launch(saved)
 browser,context,page=launch()
 context.request.post('http://127.0.0.1:8103/api/vehicle/speed',data={'speedKmH':0})
 page.goto('http://127.0.0.1:3000/privacy');expect(page.get_by_label(PERMISSION,exact=True)).not_to_be_checked()
 page.get_by_label('Cilt ölçümlerini ve kişisel sayısal referansı bu tarayıcıda sakla',exact=True).check()
 baseline=len(provider_state()['calls']);configure_front(page);start(page);record=complete(page)
 assert record['general']['skinType']['value'] is None and record['general']['skinType']['limitationCode']=='HOSTED_INFERENCE_PERMISSION_DENIED'
 assert len(provider_state()['calls'])==baseline
 denied=summary(page,record)
 page.goto('http://127.0.0.1:3000/privacy');page.get_by_label(PERMISSION,exact=True).check()
 browser,context,page=recycle(browser,context)
 runs=[]
 for value,label in [('normal','Normal'),('dry','Kuru'),('oily','Yağlı'),('combination','Karma')]:
  mode(value);before=len(provider_state()['calls']);configure_front(page);start(page);record=complete(page)
  result=summary(page,record);assert result['skinType']['value']==value and result['skinType']['modelHash'] is None and result['skinType']['providerModelId']=='skin-type-axavj/1'
  assert len(provider_state()['calls'])==before+1
  expect(page.locator('[data-skin-type] strong')).to_have_text(label)
  assert page.locator('[data-skin-type]').get_by_role('meter').count()==0
  page.screenshot(path=str(OUT/(value+'-overview.png')),full_page=True)
  # Preserve natural image, six meshes and selected local gradient behavior.
  if value=='normal':
   source=page.locator('[data-skin-snapshot] image').first.get_attribute('href');regions=[]
   page.get_by_role('button',name='Sonraki Bölge',exact=True).click()
   for i in range(6):
    mesh=page.locator('[data-skin-mesh]');regions.append(mesh.get_attribute('data-skin-mesh'));assert mesh.locator('[data-mesh-edge]').count()>0
    photo=page.locator('[data-skin-snapshot] image').first.get_attribute('href')
    criterion='dark' if regions[-1]=='periorbital' else 'redness';page.locator('[data-skin-indicator="'+criterion+'"]').click()
    assert page.locator('[data-skin-snapshot] image').first.get_attribute('href')==photo
    for text in page.locator('[data-skin-score]').all_text_contents():assert '.' not in text and ',' not in text
    page.get_by_role('button',name='Sonraki Bölge',exact=True).click()
   assert regions==['forehead','rightCheek','leftCheek','nose','chin','periorbital']
   assert page.locator('[data-skin-snapshot] image').first.get_attribute('href')==source
   result['sixRegions']=regions
  history(page,record,label);result['sameRecordHistory']=True;runs.append(result)
  browser,context,page=recycle(browser,context)
 failures=[]
 for failure,code in [('429','HOSTED_RATE_LIMIT_EXCEEDED'),('401','HOSTED_AUTH_FAILED'),('timeout','HOSTED_TIMEOUT')]:
  mode(failure);before=len(provider_state()['calls']);configure_front(page);start(page);record=complete(page);result=summary(page,record)
  assert result['skinType']['value'] is None and result['skinType']['confidence'] is None and result['skinType']['limitationCode']==code
  assert len(provider_state()['calls'])==before+1
  assert page.locator('[data-skin-type] strong').inner_text()=='—'
  page.screenshot(path=str(OUT/(failure+'-unavailable.png')),full_page=True);failures.append(result)
  browser,context,page=recycle(browser,context)
 # Revoke while a real network request is in progress; no late record wins.
 mode('timeout');before=len(provider_state()['calls']);previous=record['id'];configure_front(page);start(page);wait_provider(page,before)
 privacy=context.new_page();privacy.goto('http://127.0.0.1:3000/privacy');privacy.get_by_label(PERMISSION,exact=True).uncheck()
 page.wait_for_timeout(17000);assert page.evaluate('JSON.parse(localStorage.getItem("togg_health_latest_skin")).id')==previous
 expect(page.get_by_role('button',name='Analizi Başlat',exact=True)).to_be_visible()
 privacy.close();mode('normal');before=len(provider_state()['calls']);start(page);record=complete(page)
 assert record['general']['skinType']['limitationCode']=='HOSTED_INFERENCE_PERMISSION_DENIED' and len(provider_state()['calls'])==before
 revoked=summary(page,record)
 browser,context,page=recycle(browser,context)
 # Cancel and then replace: the late request cannot persist or overwrite.
 page.goto('http://127.0.0.1:3000/privacy');page.get_by_label(PERMISSION,exact=True).check()
 mode('timeout');before=len(provider_state()['calls']);previous=record['id'];configure_front(page);start(page);wait_provider(page,before)
 page.get_by_role('button',name='Taramayı İptal Et',exact=True).click();page.wait_for_timeout(17000)
 assert page.evaluate('JSON.parse(localStorage.getItem("togg_health_latest_skin")).id')==previous
 mode('normal');start(page);record=complete(page);assert record['id']!=previous and record['general']['skinType']['value']=='normal'
 assert not errors,errors
 result=dict(status='PASS',buildId=(ROOT/'apps/vehicle-app/.next/BUILD_ID').read_text().strip(),recordedProviderReplay=True,newLiveHostedRequests=0,fixtureSubjectClassificationAccuracyNotMeasured=True,licensedFixtureSHA256=hashlib.sha256((ROOT/'audit-fixtures/three-angle.y4m').read_bytes()).hexdigest(),actualMediaPipe=True,poseMock=False,qualityOverride=False,normalUserHistoryTouched=False,defaultDenied=denied,classes=runs,failures=failures,revocation=revoked,cancelAndReplaceProtected=True,providerRequests=provider_state()['calls'][baseline:],pageErrors=errors)
 (OUT/'proof.json').write_text(json.dumps(result,ensure_ascii=False,indent=2),'utf8')
 context.close();browser.close()
 print(json.dumps({k:result[k] for k in ['status','buildId','recordedProviderReplay','newLiveHostedRequests','actualMediaPipe','cancelAndReplaceProtected']}))

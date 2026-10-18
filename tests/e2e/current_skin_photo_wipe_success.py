"""Production source/photo persistence, actual licensed video and MediaPipe.
Isolated browser profile; never creates fixture records in the user's profile.
"""
import ast,base64,json,time,tempfile,math,hashlib,sys,io,os,subprocess,urllib.request,re,atexit
from pathlib import Path
from playwright.sync_api import sync_playwright,expect
from PIL import Image
sys.path.insert(0,str(Path(__file__).parent))
from owned_window_capture import capture_owned_window
ROOT=Path.cwd();OUT=ROOT/'audit-results/acne-trained-20261010/photo-wipe-success';OUT.mkdir(parents=True,exist_ok=True)
constants={n.targets[0].id:ast.literal_eval(n.value) for n in ast.parse((ROOT/'tests/e2e/current_skin_contract.py').read_text()).body if isinstance(n,ast.Assign) and isinstance(n.targets[0],ast.Name) and n.targets[0].id in ('INIT','APPEARANCE')}
def rows(p):return p.evaluate("()=>new Promise((resolve,reject)=>{const q=indexedDB.open('attune-skin-photos');q.onsuccess=()=>{const db=q.result,t=db.transaction('records');const r=t.objectStore('records').getAll();r.onsuccess=()=>resolve(r.result);t.oncomplete=()=>db.close();t.onerror=()=>reject(t.error);};q.onerror=()=>reject(q.error);})")
def open_record(p,id):
 p.goto('http://127.0.0.1:3000/profile');p.locator('[data-record-id="'+id+'"]').get_by_role('button',name='Sonucu Aç',exact=True).click();dialog=p.get_by_role('dialog',name='Cilt Sağlığı sonucu',exact=True);expect(dialog.locator('[data-skin-snapshot]')).to_be_visible(timeout=15000);return dialog
# Actual separate ASGI server and filesystem store. The shared service is read-only.
def api(port,path,payload=None):
 data=json.dumps(payload).encode() if payload is not None else None
 req=urllib.request.Request(f'http://127.0.0.1:{port}'+path,data=data,headers={'Content-Type':'application/json'} if data else {})
 with urllib.request.urlopen(req,timeout=10) as response:return json.load(response)
shared_before=hashlib.sha256(json.dumps(api(8000,'/api/mental/sessions'),sort_keys=True).encode()).hexdigest()
store=tempfile.TemporaryDirectory(prefix='attune-wipe-store-')
env={**os.environ,'ATTUNE_DATA_DIR':store.name,'ATTUNE_LOAD_LOCAL_ENV':'0','PYTHONPATH':str(ROOT/'.runtime/security-20261008')+os.pathsep+str(ROOT/'services/core-api')}
env.pop('OPENAI_API_KEY',None)
log=(OUT/'isolated-backend.log').open('w',encoding='utf8')
server=subprocess.Popen([sys.executable,'-X','utf8','-m','uvicorn','main:app','--host','127.0.0.1','--port','8001'],cwd=ROOT/'services/core-api',env=env,stdout=log,stderr=log,creationflags=subprocess.CREATE_NO_WINDOW)
def cleanup():
 if server.poll() is None:server.terminate();server.wait(timeout=15)
 log.close();store.cleanup()
atexit.register(cleanup)
for _ in range(45):
 try:
  assert api(8001,'/api/mental/sessions')==[];break
 except urllib.error.URLError:time.sleep(.5)
else:raise RuntimeError('Isolated service did not start')
for n in range(2):api(8001,'/api/mental/sessions',{'summaryText':f'Isolated wipe fixture {n}','recurringThemes':[],'saveMentalSummaries':True})
assert len(api(8001,'/api/mental/sessions'))==2
with tempfile.TemporaryDirectory(prefix='attune-photo-retention-') as profile,sync_playwright() as pw:
 args=['--use-fake-device-for-media-stream','--use-file-for-fake-video-capture='+str(ROOT/'audit-fixtures/three-angle.y4m'),'--enable-unsafe-swiftshader']
 def launch(headed=False):return pw.chromium.launch_persistent_context(profile,channel='chrome',headless=not headed,no_viewport=headed,viewport=None if headed else {'width':1600,'height':1000},permissions=['camera'],args=args+(['--window-size=1600,1000'] if headed else []))
 c=launch();c.route(re.compile(r'http://(?:localhost|127\.0\.0\.1):8000/'),lambda route:route.fulfill(response=route.fetch(url=re.sub(r':8000/',':8001/',route.request.url))));c.add_init_script(constants['INIT']);c.add_init_script(constants['APPEARANCE']);p=c.new_page();errors=[];p.on('pageerror',lambda e:errors.append(str(e)))
 c.request.post('http://127.0.0.1:8001/api/vehicle/speed',data={'speedKmH':0})
 p.goto('http://127.0.0.1:3000/privacy');photo=p.get_by_label('Yeni cilt kayıtlarının fotoğraflarını bu cihazda sakla');assert not photo.is_checked()
 p.get_by_label('Cilt ölçümlerini ve kişisel sayısal referansı bu tarayıcıda sakla').check();photo.click();expect(photo).to_be_checked();p.screenshot(path=str(OUT/'explicit-photo-consent.png'),full_page=True)
 scans=[]
 for n in range(1):
  p.goto('http://127.0.0.1:3000/skin');p.get_by_role('button',name='Analizi Başlat',exact=True).click();start=time.monotonic();trace=[]
  while not p.get_by_text('Cilt Analizi Tamamlandı',exact=True).count() and time.monotonic()-start<300:
   p.wait_for_timeout(2000);trace.append(p.evaluate('({body:document.body.innerText,canvas:{...document.querySelector("canvas")?.dataset}})'));(OUT/f'trace-{n}.json').write_text(json.dumps(trace,ensure_ascii=False),'utf8')
  expect(p.get_by_text('Cilt Analizi Tamamlandı',exact=True)).to_be_visible(timeout=1000)
  assert not p.get_by_text('Cilt fotoğrafı kaydedilemedi. Sayısal sonuçlar korunuyor.',exact=True).count()
  record=p.evaluate('JSON.parse(localStorage.getItem("togg_health_latest_skin"))');stored=rows(p);assert len(stored)==n+1
  entry=next(r for r in stored if r['id']==record['id']);frames=json.loads(entry['payload']);assert set(frames)=={'FRONT','RIGHT','LEFT'}
  assert hashlib.sha256(entry['payload'].encode()).hexdigest()==entry['sha256']
  for pose,snapshot in frames.items():
   assert pose==snapshot['angle'] and snapshot['photoId'] and snapshot['dataUrl'].startswith('data:image/png;base64,')
   assert hashlib.sha256(Image.open(io.BytesIO(base64.b64decode(snapshot['dataUrl'].split(',')[1]))).convert('RGBA').tobytes()).hexdigest()==snapshot['photoId']
   assert all(m['photoId']==snapshot['photoId'] and m['pose']==pose for m in snapshot['localMaps'].values())
  proof=dict(id=record['id'],sourceByRegion={},shaByRegion={},poseByRegion={},storeBytes=entry['bytes'],seconds=time.monotonic()-start)
  expect(p.get_by_role('heading',name='Genel Bakış',exact=True)).to_be_visible()
  assert p.locator('[data-skin-mesh]').count()==0
  assert p.locator('[data-skin-snapshot]').get_attribute('data-snapshot-photoid')==record['general']['captureId']
  p.get_by_role('button',name='Sonraki Bölge',exact=True).click()
  for region in ['forehead','rightCheek','leftCheek','nose','chin','periorbital']:
   svg=p.locator('[data-skin-snapshot]');assert svg.locator('[data-skin-mesh]').get_attribute('data-skin-mesh')==region
   proof['sourceByRegion'][region]=svg.get_attribute('data-snapshot-photoid');proof['shaByRegion'][region]=hashlib.sha256(svg.locator('image').first.get_attribute('href').encode()).hexdigest()
   proof['poseByRegion'][region]='LEFT' if region=='rightCheek' else 'RIGHT' if region=='leftCheek' else 'FRONT'
   p.get_by_role('button',name='Sonraki Bölge',exact=True).click()
  p.screenshot(path=str(OUT/f'scan-{n}.png'),full_page=True);scans.append(proof);print('Actual three-pose scan',n+1,'persisted',entry['bytes'],flush=True)
 # Current-build retained result: desktop, narrow and native Chrome 200%.
 dialog=open_record(p,scans[0]['id']);p.screenshot(path=str(OUT/'result-desktop.png'),full_page=True);p.keyboard.press('Escape')
 p.set_viewport_size({'width':720,'height':900});dialog=open_record(p,scans[0]['id']);assert p.evaluate('document.documentElement.scrollWidth<=innerWidth');p.screenshot(path=str(OUT/'result-narrow.png'),full_page=True);p.keyboard.press('Escape');c.close()
 preferences=Path(profile)/'Default/Preferences';prefs=json.loads(preferences.read_text());prefs.setdefault('partition',{})['default_zoom_level']={'x':math.log(2)/math.log(1.2)};preferences.write_text(json.dumps(prefs),'utf8')
 c=launch(True);c.route(re.compile(r'http://(?:localhost|127\.0\.0\.1):8000/'),lambda route:route.fulfill(response=route.fetch(url=re.sub(r':8000/',':8001/',route.request.url))));p=c.new_page();dialog=open_record(p,scans[0]['id']);geometry=p.evaluate('({innerWidth,outerWidth,dpr:devicePixelRatio,zoom:getComputedStyle(document.documentElement).zoom,scroll:document.documentElement.scrollWidth})');assert geometry['dpr']>=2 and geometry['innerWidth']<geometry['outerWidth']*.65 and geometry['zoom']=='1' and geometry['scroll']<=geometry['innerWidth'],geometry
 capture_owned_window(p,profile,OUT/'result-native200.png');dialog.evaluate('(el)=>el.scrollTop=el.scrollHeight');capture_owned_window(p,profile,OUT/'result-native200-bottom.png');p.keyboard.press('Escape')
 # Browser request is forwarded to the real isolated service, with no fabricated response.
 assert len(api(8001,'/api/mental/sessions'))==2
 p.goto('http://127.0.0.1:3000/privacy');p.get_by_role('button',name='TÜM YEREL VERİLERİ SİL',exact=True).click();p.get_by_role('button',name='Evet, Tüm Verileri Sil',exact=True).click()
 expect(p.get_by_text('Tarayıcıdaki sağlık kayıtları silindi.',exact=True)).to_be_visible(timeout=15000)
 expect(p.get_by_text('Tüm yerel veriler başarıyla temizlendi.',exact=True)).to_be_visible()
 assert api(8001,'/api/mental/sessions')==[]
 assert json.loads((Path(store.name)/'mental_sessions.json').read_text('utf8'))==[]
 assert json.loads((Path(store.name)/'mental_deletions.json').read_text('utf8'))=={}
 assert not rows(p)
 assert p.evaluate('localStorage.getItem("togg_health_skin_history")') is None
 assert p.evaluate('localStorage.getItem("togg_health_latest_skin")') is None
 p.get_by_text('Tüm yerel veriler başarıyla temizlendi.',exact=True).scroll_into_view_if_needed();capture_owned_window(p,profile,OUT/'wipe-local-and-backend-success.png')
 c.close();c=launch();p=c.new_page();p.goto('http://127.0.0.1:3000/profile');assert not p.locator('[data-record-id]').count();assert not rows(p);assert api(8001,'/api/mental/sessions')==[]
 assert hashlib.sha256(json.dumps(api(8000,'/api/mental/sessions'),sort_keys=True).encode()).hexdigest()==shared_before
 assert not errors,errors
 (OUT/'proof.json').write_text(json.dumps(dict(status='PASS',buildId=(ROOT/'apps/vehicle-app/.next/BUILD_ID').read_text().strip(),actualScan=scans[0],localWipeVerified=True,backendForwardedToRealIsolatedService=True,backendWipeAcceptance=True,sharedBackendUnchanged=True,relaunchStillEmpty=True,desktopNarrowVerified=True,native200=geometry,isolatedBackendRecordsBefore=2,isolatedBackendRecordsAfter=0,controlledFixture=True,physicalUserAcceptance=False),ensure_ascii=False,indent=2),'utf8');c.close()
cleanup();atexit.unregister(cleanup)
print('PASS: real scan and actual isolated backend records removed; relaunch empty; shared backend unchanged')

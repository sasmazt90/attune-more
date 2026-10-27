"""Actual consent/IndexedDB wipe plus a task-owned isolated ASGI store. No user data or mocked API responses."""
import hashlib,json,math,os,re,subprocess,sys,tempfile,time,urllib.error,urllib.request
from pathlib import Path
from playwright.sync_api import sync_playwright,expect
sys.path.insert(0,str(Path(__file__).parent))
from current_skin_photo_history import rows,source_receipt
from skin_browser_support import configure,scan,open_selected,capture_native,GPU,BROWSER
ROOT=Path.cwd();OUT=Path(os.getenv('SKIN_PRIVACY_AUDIT_DIR',str(ROOT/'audit-results/skin-findings-privacy')));configure(OUT)

def api(port,path,payload=None):
 data=json.dumps(payload).encode() if payload is not None else None
 request=urllib.request.Request(f'http://127.0.0.1:{port}'+path,data=data,headers={'Content-Type':'application/json'} if data else {})
 with urllib.request.urlopen(request,timeout=10) as response:return json.load(response)

def main():
 # Shared service is observed read-only; only the new isolated store may be wiped.
 shared_before=hashlib.sha256(json.dumps(api(8000,'/api/mental/sessions'),sort_keys=True).encode()).hexdigest()
 with tempfile.TemporaryDirectory(prefix='attune-wipe-store-') as store,tempfile.TemporaryDirectory(prefix='attune-wipe-browser-') as profile:
  env={**os.environ,'ATTUNE_DATA_DIR':store,'ATTUNE_LOAD_LOCAL_ENV':'0'};env.pop('OPENAI_API_KEY',None)
  with (OUT/'isolated-backend.log').open('w') as log:
   server=subprocess.Popen([sys.executable,'-m','uvicorn','main:app','--host','127.0.0.1','--port','8001'],cwd=ROOT/'services/core-api',env=env,stdout=log,stderr=log,creationflags=getattr(subprocess,'CREATE_NO_WINDOW',0))
   try:
    for _ in range(45):
     if server.poll() is not None:raise RuntimeError('Owned isolated backend exited; see log')
     try:
      assert api(8001,'/api/mental/sessions')==[];break
     except urllib.error.URLError:time.sleep(.5)
    else:raise RuntimeError('Owned isolated backend did not become ready')
    for n in range(2):api(8001,'/api/mental/sessions',dict(summaryText=f'Synthetic wipe fixture {n}',recurringThemes=[],saveMentalSummaries=True))
    assert len(api(8001,'/api/mental/sessions'))==2
    with sync_playwright() as pw:
     args=['--use-fake-device-for-media-stream','--use-file-for-fake-video-capture='+str(ROOT/'audit-fixtures/three-angle.y4m'),*GPU]
     def launch(headed=False):
      context=pw.chromium.launch_persistent_context(profile,**BROWSER,headless=not headed,no_viewport=headed,viewport=None if headed else dict(width=1600,height=1000),permissions=['camera'],args=args+(['--window-size=1600,1000'] if headed else []))
      # Forward actual requests to the owned store. No fabricated server response.
      context.route(re.compile(r'http://(?:localhost|127\.0\.0\.1):8000/'),lambda route:route.fulfill(response=route.fetch(url=re.sub(r':8000/',':8001/',route.request.url))))
      return context
     c=launch();p=c.new_page();errors=[];p.on('pageerror',lambda e:errors.append(str(e)))
     assert c.request.post('http://127.0.0.1:8001/api/vehicle/speed',data={'speedKmH':0}).ok
     p.goto('http://127.0.0.1:3000/privacy');photo=p.get_by_label('Yeni cilt kayıtlarının fotoğraflarını bu cihazda sakla');assert not photo.is_checked()
     p.get_by_label('Cilt ölçümlerini ve kişisel sayısal referansı bu tarayıcıda sakla').check();photo.check();expect(photo).to_be_checked()
     record=scan(p,'privacy');stored=rows(p);assert len(stored)==1
     receipt=source_receipt(record,stored[0]);open_selected(p,record);expect(p.locator('[data-skin-snapshot]')).to_have_attribute('data-snapshot-photoid',record['general']['captureId'])
     p.screenshot(path=str(OUT/'result-desktop.png'),full_page=True);p.set_viewport_size(dict(width=720,height=900));assert p.evaluate('document.documentElement.scrollWidth<=innerWidth');p.screenshot(path=str(OUT/'result-narrow.png'),full_page=True);c.close()
     pref=Path(profile)/'Default/Preferences';data=json.loads(pref.read_text());data.setdefault('partition',{})['default_zoom_level']={'x':math.log(2)/math.log(1.2)};pref.write_text(json.dumps(data))
     c=launch(True);p=c.new_page();open_selected(p,record);geometry=p.evaluate('({innerWidth,outerWidth,dpr:devicePixelRatio,cssZoom:getComputedStyle(document.documentElement).zoom,scroll:document.documentElement.scrollWidth})')
     assert geometry['dpr']>=2 and geometry['innerWidth']<geometry['outerWidth']*.65 and geometry['cssZoom']=='1' and geometry['scroll']<=geometry['innerWidth']
     capture=capture_native(p,profile,OUT/'result-native200.png')
     assert len(api(8001,'/api/mental/sessions'))==2
     p.goto('http://127.0.0.1:3000/privacy');p.get_by_role('button',name='TÜM YEREL VERİLERİ SİL',exact=True).click();p.get_by_role('button',name='Evet, Tüm Verileri Sil',exact=True).click()
     expect(p.get_by_text('Tarayıcıdaki sağlık kayıtları silindi.',exact=True)).to_be_visible(timeout=15000)
     expect(p.get_by_text('Tüm yerel veriler başarıyla temizlendi.',exact=True)).to_be_visible()
     assert api(8001,'/api/mental/sessions')==[] and not rows(p)
     assert json.loads((Path(store)/'mental_sessions.json').read_text())==[]
     assert json.loads((Path(store)/'mental_deletions.json').read_text())=={}
     for key in ('togg_health_skin_history','togg_health_latest_skin'):assert p.evaluate('(key)=>localStorage.getItem(key)',key) is None
     capture_native(p,profile,OUT/'wipe-success.png');c.close();c=launch();p=c.new_page();p.goto('http://127.0.0.1:3000/profile')
     expect(p.locator('[data-record-id]')).to_have_count(0);assert not rows(p) and api(8001,'/api/mental/sessions')==[]
     assert hashlib.sha256(json.dumps(api(8000,'/api/mental/sessions'),sort_keys=True).encode()).hexdigest()==shared_before
     assert not errors,errors
     proof=dict(status='PASS',methodVersion='skin-privacy-lifecycle-browser-v1',buildId=(ROOT/'apps/vehicle-app/.next/BUILD_ID').read_text().strip(),realBrowser=True,browserEngine='chromium',controlledFixture=True,physicalUserAcceptance=False,expertGroundTruth=False,accuracyEvidence=False,actualScan=receipt,explicitPhotoConsent=True,consentPassed=True,retentionPassed=True,localWipeVerified=True,deletionPassed=True,backendForwardedToRealIsolatedService=True,backendWipeAcceptance=True,sharedBackendUnchanged=True,relaunchStillEmpty=True,isolatedBackendRecordsBefore=2,isolatedBackendRecordsAfter=0,native200=geometry,native200Capture=capture,pageErrors=errors)
     (OUT/'proof.json').write_text(json.dumps(proof,ensure_ascii=False,indent=2));c.close()
   finally:
    if server.poll() is None:
     server.terminate()
     try:server.wait(timeout=10)
     except subprocess.TimeoutExpired:server.kill();server.wait(timeout=5)
 if api(8000,'/api/health') is None:raise RuntimeError('Shared service no longer available')
 print('PASS: selected real scan, explicit retention and real isolated backend/browser wipe; shared store unchanged')

if __name__=='__main__':main()

"""Three real scans and selected-record replay on the approved React findings UI.

Licensed fake camera; real production MediaPipe/API/model inference. No generated records,
pose/quality overrides, user profile access, or physical-camera/accuracy claim.
"""
import ast,base64,hashlib,io,json,math,os,re,sys,tempfile
from pathlib import Path
from playwright.sync_api import sync_playwright,expect
from PIL import Image
sys.path.insert(0,str(Path(__file__).parent))
from skin_browser_support import configure,scan,check_result,open_selected,capture_native,GPU,REGIONS,BROWSER
ROOT=Path.cwd();OUT=Path(os.getenv('SKIN_HISTORY_AUDIT_DIR',str(ROOT/'audit-results/skin-findings-history')));configure(OUT)

def rows(page):
 return page.evaluate("()=>new Promise((resolve,reject)=>{const q=indexedDB.open('attune-skin-photos');q.onsuccess=()=>{const db=q.result,t=db.transaction('records'),r=t.objectStore('records').getAll();r.onsuccess=()=>resolve(r.result);t.oncomplete=()=>db.close();t.onerror=()=>reject(t.error);};q.onerror=()=>reject(q.error);})")

def source_receipt(record,entry):
 assert hashlib.sha256(entry['payload'].encode()).hexdigest()==entry['sha256']
 frames=json.loads(entry['payload']);assert set(frames)=={'FRONT','LEFT','RIGHT'}
 for pose,snapshot in frames.items():
  assert snapshot['angle']==pose and snapshot['dataUrl'].startswith('data:image/png;base64,')
  rgba=Image.open(io.BytesIO(base64.b64decode(snapshot['dataUrl'].split(',')[1]))).convert('RGBA').tobytes()
  assert hashlib.sha256(rgba).hexdigest()==snapshot['photoId']
  assert all(m['photoId']==snapshot['photoId'] and m['pose']==pose for m in snapshot['localMaps'].values())
 source_by={r:frames['LEFT' if r=='rightCheek' else 'RIGHT' if r=='leftCheek' else 'FRONT'] for r in REGIONS}
 assert record['general']['captureId']==frames['FRONT']['photoId'] and record['general']['analysisId']==record['id']
 return dict(id=record['id'],sourceByRegion={r:f['photoId'] for r,f in source_by.items()},shaByRegion={r:hashlib.sha256(f['dataUrl'].encode()).hexdigest() for r,f in source_by.items()},poseByRegion={r:f['angle'] for r,f in source_by.items()},storeBytes=entry['bytes'])

if __name__=='__main__':
 with tempfile.TemporaryDirectory(prefix='attune-skin-history-') as profile,sync_playwright() as pw:
  args=['--use-fake-device-for-media-stream','--use-file-for-fake-video-capture='+str(ROOT/'audit-fixtures/three-angle.y4m'),*GPU]
  def launch(headed=False):
   return pw.chromium.launch_persistent_context(profile,**BROWSER,headless=not headed,no_viewport=headed,viewport=None if headed else dict(width=1600,height=1000),permissions=['camera'],args=args+(['--window-size=1600,1000'] if headed else []))
  c=launch();p=c.new_page();errors=[];p.on('pageerror',lambda e:errors.append(str(e)))
  assert c.request.post('http://127.0.0.1:8000/api/vehicle/speed',data={'speedKmH':0}).ok
  p.goto('http://127.0.0.1:3000/privacy');photo=p.get_by_label('Yeni cilt kayıtlarının fotoğraflarını bu cihazda sakla');assert not photo.is_checked()
  p.get_by_label('Cilt ölçümlerini ve kişisel sayısal referansı bu tarayıcıda sakla').check();photo.check();expect(photo).to_be_checked()
  scans=[];records=[];shots=[]
  for n in range(3):
   if n:
    c.close();c=launch();p=c.new_page();p.on('pageerror',lambda e:errors.append(str(e)))
   record=scan(p,'scan-'+str(n));stored=rows(p);assert len(stored)==n+1
   entry=next(r for r in stored if r['id']==record['id']);scans.append(source_receipt(record,entry));records.append(record)
   check_result(p,record,shots,'scan-'+str(n));print('Actual scan persisted',n+1,flush=True)
  c.close();c=launch();p=c.new_page();p.goto('http://127.0.0.1:3000/profile');assert len(rows(p))==3
  for n,(record,receipt) in enumerate(zip(records,scans)):
   open_selected(p,record)
   expect(p.locator('[data-skin-snapshot]')).to_have_attribute('data-snapshot-photoid',record['general']['captureId'])
   check_result(p,record,shots,'reopened-'+str(n))
   assert source_receipt(record,next(r for r in rows(p) if r['id']==record['id']))==receipt
  p.set_viewport_size(dict(width=720,height=900));open_selected(p,records[0]);assert p.evaluate('document.documentElement.scrollWidth<=innerWidth');p.screenshot(path=str(OUT/'narrow.png'),full_page=True);c.close()
  pref=Path(profile)/'Default/Preferences';data=json.loads(pref.read_text());data.setdefault('partition',{})['default_zoom_level']={'x':math.log(2)/math.log(1.2)};pref.write_text(json.dumps(data))
  c=launch(True);p=c.new_page();open_selected(p,records[0]);geometry=p.evaluate('({innerWidth,outerWidth,dpr:devicePixelRatio,cssZoom:getComputedStyle(document.documentElement).zoom,scroll:document.documentElement.scrollWidth})')
  assert geometry['dpr']>=2 and geometry['innerWidth']<geometry['outerWidth']*.65 and geometry['cssZoom']=='1' and geometry['scroll']<=geometry['innerWidth']
  captures={'top':capture_native(p,profile,OUT/'native200.png')};p.locator('[data-skin-result]').scroll_into_view_if_needed();captures['result']=capture_native(p,profile,OUT/'native200-result.png')
  p.goto('http://127.0.0.1:3000/profile');row=p.locator('[data-record-table] [data-record-id="'+records[0]['id']+'"]');row.get_by_role('button',name=re.compile('kaydını sil:')).click();p.get_by_role('button',name='Evet, sil',exact=True).click();expect(row).to_have_count(0)
  assert {r['id'] for r in rows(p)}=={r['id'] for r in records[1:]}
  p.goto('http://127.0.0.1:3000/privacy');p.get_by_label('Yeni cilt kayıtlarının fotoğraflarını bu cihazda sakla').uncheck();p.wait_for_function("()=>new Promise(resolve=>{const q=indexedDB.open('attune-skin-photos');q.onsuccess=()=>{const db=q.result,t=db.transaction('records'),r=t.objectStore('records').count();r.onsuccess=()=>resolve(r.result===0);t.oncomplete=()=>db.close();};})")
  assert not rows(p) and len(p.evaluate('JSON.parse(localStorage.getItem("togg_health_skin_history"))'))==2
  open_selected(p,records[1]);expect(p.locator('[data-skin-snapshot]')).to_have_count(0);check_result(p,records[1],shots,'photos-revoked',photo=False)
  assert not errors,errors
  proof=dict(status='PASS',methodVersion='skin-findings-indexeddb-v2',buildId=(ROOT/'apps/vehicle-app/.next/BUILD_ID').read_text().strip(),realBrowser=True,browserEngine='chromium',controlledFixture=True,physicalUserAcceptance=False,expertGroundTruth=False,accuracyEvidence=False,poseMock=False,qualityOverride=False,scans=scans,indexedDbWriteReadPassed=True,relaunchThreeRecords=True,selectedRecordBinding=True,sourceBoundSixRegions=True,approvedFindingsUI=True,deleteOne=True,revokePhotosKeepsNumeric=True,retentionPassed=True,deletionPassed=True,native200=geometry,native200Capture=captures,pageErrors=errors)
  (OUT/'proof.json').write_text(json.dumps(proof,ensure_ascii=False,indent=2));c.close()
 print('PASS: three actual scans, exact selected-record replay and source hashes, delete/revoke, real browser200% zoom')

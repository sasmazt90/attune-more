"""Isolated synthetic browser checks; never opens the user's camera/profile."""
import hashlib,json,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2];sys.path.insert(0,str(ROOT/'scripts/skin-research'))
from heavy_job_lease import HeavyJobLease
OUT=ROOT/'audit-results/acne-classical-comparison-20261015'

def main():
 with HeavyJobLease('CDC-acne-capture-tool-browser-check',peak_mib=1350,minimum_available_mib=1600,include_children=True,memory_metric='private') as lease:
  import cv2,numpy as np,pytest
  from playwright.sync_api import sync_playwright
  html=(ROOT/'scripts/skin-research/acne-appearance-capture.html').read_text('utf8');unit=OUT/'synthetic-tool-input.png';cv2.imwrite(str(unit),np.full((240,320,3),150,np.uint8));checks={}
  with sync_playwright() as pw:
   browser=pw.chromium.launch(channel='chrome',headless=True)
   try:
    context=browser.new_context(accept_downloads=True);page=context.new_page();network=[]
    def route(r):
     network.append(r.request.url)
     if r.request.url=='http://127.0.0.1:6986/audit':r.fulfill(body=html,content_type='text/html')
     else:r.abort()
    context.route('**/*',route);page.goto('http://127.0.0.1:6986/audit')
    page.locator('#file').set_input_files(str(unit));assert page.locator('#canvas').evaluate('(c)=>c.width')==300
    assert 'Eksik' in page.locator('#message').inner_text();checks['unpermittedFileNotDecoded']=True
    for key in ['consent','rights','scope','withdraw','person','group','reviewer','light']:page.locator('#'+key).fill('synthetic-test-only-'+key)
    page.locator('#permission').check();page.locator('#file').set_input_files(str(unit));page.wait_for_function('document.getElementById("canvas").width===320')
    page.locator('#canvas').scroll_into_view_if_needed();box=page.locator('#canvas').bounding_box();page.mouse.move(box['x']+40,box['y']+30);page.mouse.down();page.mouse.move(box['x']+60,box['y']+55);page.mouse.up()
    with page.expect_download() as event:page.locator('#json').click()
    record=json.loads(Path(event.value.path()).read_text('utf8'));assert len(record['labels'])==1 and record['snapshotWidth']==320 and record['snapshotHeight']==240
    assert 'data:image' not in json.dumps(record) and 'base64' not in json.dumps(record);assert not record['persistentPhotoPermission'];checks['numericExportNoPixels']=True
    page.locator('#png').click();assert 'Ayrı' in page.locator('#message').inner_text();checks['persistentPhotoRequiresSeparateConsent']=True
    page.locator('#retain').check()
    with page.expect_download() as event:page.locator('#png').click()
    assert hashlib.sha256(Path(event.value.path()).read_bytes()).hexdigest()==record['photoSHA256'];checks['annotationHashMatchesUnpaintedSourcePNG']=True
    downloads=[];page.on('download',lambda d:downloads.append(d))
    page.evaluate("""()=>{const native=HTMLCanvasElement.prototype.toBlob;HTMLCanvasElement.prototype.toBlob=function(callback,...args){return native.call(this,b=>setTimeout(()=>callback(b),150),...args)};document.getElementById('png').click();document.getElementById('retain').checked=false;}""")
    page.wait_for_function("document.getElementById('message').textContent.includes('iptal')")
    assert not downloads;checks['pendingPhotoExportHonorsRevocation']=True
    page.locator('#permission').uncheck();assert page.locator('#canvas').evaluate('(c)=>c.width')==0;assert page.evaluate('localStorage.length')==0;checks['revocationClearsVolatileFrameWithoutStorage']=True
    checks['noExternalRequests']=network==['http://127.0.0.1:6986/audit'];assert checks['noExternalRequests']
    screenshot=ROOT/'output/playwright/acne-capture-tool.png';screenshot.parent.mkdir(parents=True,exist_ok=True);page.screenshot(path=str(screenshot),full_page=True)
    lease.check()
   finally:browser.close()
  # Existing actual product photo retention/revocation/delete contracts, isolated stores.
  result=pytest.main(['tests/unit/test_skin_photo_history.py','tests/unit/test_skin_atomic_deletion.py','-q'])
  assert result==0
  (OUT/'browser-check.json').write_text(json.dumps(dict(checks=checks,existingPhotoStorageTestsPassed=result==0,physicalCameraOpened=False,syntheticOnly=True,resource=lease.receipt()),indent=2),'utf8')
if __name__=='__main__':main()
"""Natural full portraits through the actual current static-upload UI.
No camera permission, fake landmarks, private-user history or paid service.
"""
import json,hashlib,sys
from pathlib import Path
from playwright.sync_api import sync_playwright,expect
ROOT=Path(__file__).resolve().parents[2];SOURCE=ROOT/'audit-results/followup-closure-20261010/dental-sources';OUT=ROOT/'audit-results/all-health-20261010/dental-natural-ui';OUT.mkdir(parents=True,exist_ok=True)
INIT='''window.uploadResponses=[];window.cameraCalls=0;const gum=navigator.mediaDevices.getUserMedia.bind(navigator.mediaDevices);navigator.mediaDevices.getUserMedia=(...a)=>{cameraCalls++;return gum(...a);};const original=fetch;window.fetch=async(...a)=>{const r=await original(...a);if(String(a[0]).endsWith('/api/local-health/dental-upload'))uploadResponses.push({status:r.status,body:await r.clone().json()});return r;};'''
rows=[];only=int(sys.argv[1]) if len(sys.argv)>1 else None
if only is not None:OUT=OUT/('single-'+str(only));OUT.mkdir(parents=True,exist_ok=True)
with sync_playwright() as pw:
 b=pw.chromium.launch(channel='chrome',headless=True);c=b.new_context(viewport={'width':1600,'height':1000});c.add_init_script(INIT);p=c.new_page();errors=[];p.on('pageerror',lambda e:errors.append(str(e)))
 for item in json.loads((SOURCE/'complete-manifest.json').read_text()):
  if only is not None and item['id']!=only:continue
  path=SOURCE/f"{item['id']}.jpg";assert hashlib.sha256(path.read_bytes()).hexdigest()==item['sourceSHA256']
  p.goto('http://127.0.0.1:3000/dental');p.get_by_label('Fotoğraflarımı yalnız bu cihazda geçici işlemeyi kabul ediyorum.').check();expect(p.get_by_role('button',name='Fotoğraf Yükle',exact=True)).to_be_enabled();expect(p.get_by_label('Diş fotoğrafı seç')).to_be_enabled();p.get_by_label('Diş fotoğrafı seç').set_input_files(str(path))
  try:p.wait_for_function('uploadResponses.length>0||document.querySelector("[data-dental-page] [role=alert]")',timeout=60000)
  except Exception:
   p.screenshot(path=str(OUT/'timeout.png'),full_page=True);(OUT/'timeout.json').write_text(json.dumps(dict(body=p.locator('body').inner_text(),errors=errors,cameraCalls=p.evaluate('cameraCalls'),responses=p.evaluate('uploadResponses')),indent=2),'utf8');raise
  response=p.evaluate('uploadResponses[0]||null');row=dict(id=item['id'],sourceSHA256=item['sourceSHA256'],response=response,cameraCalls=p.evaluate('cameraCalls'),body=p.locator('[data-dental-page]').inner_text(),physicalAcceptance=False)
  assert row['cameraCalls']==0
  if item['id']==6:
   # Actual no-teeth window/brick portrait previously admitted millions of
   # background pixels as enamel. A successful HTTP response is a failure here.
   assert response and response['status']==422,(item['id'],response['status'] if response else 'CLIENT_TIMEOUT')
  if response and response['status']==200:
   expect(p.locator('[data-dental-result]')).to_be_visible();view=response['body']['views'][0];assert view['quality']['geometrySource']=='detected-inner-mouth',view['quality']
   q=view['quality']['roi'];
   for candidate in view['caries']['candidates']:
    bound=candidate['bounds'];assert q['x']<=bound['x']+bound['width']/2<=q['x']+q['width'] and q['y']<=bound['y']+bound['height']/2<=q['y']+q['height']
  rows.append(row);(OUT/'proof-private.json').write_text(json.dumps(dict(buildId=(ROOT/'apps/vehicle-app/.next/BUILD_ID').read_text().strip(),rows=rows,errors=errors,scope='actual MediaPipe + upload + backend; natural appearance labels remain separately reviewed'),indent=2),'utf8');p.screenshot(path=str(OUT/f"{item['id']}-actual-ui.png"),full_page=True);print(json.dumps(dict(id=item['id'],status=response['status'] if response else 'CLIENT_REJECT')),flush=True)
 assert not errors,errors;c.close();b.close()

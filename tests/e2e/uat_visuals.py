"""Read-only production screenshots, isolated empty history, no physical capture."""
import argparse,json,re,os
from pathlib import Path
from playwright.sync_api import sync_playwright,expect
parser=argparse.ArgumentParser();parser.add_argument('--phase',default='after');args=parser.parse_args()
OUT=Path('audit-results/user-acceptance-20261004')/args.phase;OUT.mkdir(parents=True,exist_ok=True)
routes=['/','/vision','/skin','/mental','/care','/profile','/privacy'];proof=[]
with sync_playwright() as p:
 browser=p.chromium.launch(channel='chrome' if os.name=='nt' else 'chromium',headless=True)
 for width in (390,820,1600):
  context=browser.new_context(viewport={'width':width,'height':1000},locale='tr-TR')
  context.add_init_script("navigator.mediaDevices.getUserMedia=()=>Promise.reject(new DOMException('Physical capture forbidden','NotAllowedError'));window.captureForbidden=true;")
  context.request.post('http://localhost:8000/api/vehicle/speed',data={'speedKmH':0})
  page=context.new_page();errors=[];page.on('pageerror',lambda e:errors.append(str(e)))
  for route in routes:
   page.goto('http://localhost:3000'+route);expect(page.locator('[data-vehicle-status]')).to_have_text('PARK');page.wait_for_timeout(500)
   name=('cockpit' if route=='/' else route[1:])+f'-{width}'
   page.screenshot(path=str(OUT/(name+'.png')),full_page=True)
   overflow=page.evaluate('document.documentElement.scrollWidth>innerWidth+1')
   proof.append({'route':route,'width':width,'screenshot':name+'.png','overflow':overflow,'pageErrors':errors.copy()})
   info=page.get_by_role('button',name=re.compile('hakkında bilgi$')).first
   if info.count():
    info.click();page.screenshot(path=str(OUT/(name+'-info.png')),full_page=True);page.keyboard.press('Escape')
  context.close()
 browser.close()
(OUT/'visual-capture.json').write_text(json.dumps(proof,ensure_ascii=False,indent=2),encoding='utf-8')
print(json.dumps({'screens':len(proof),'overflow':sum(x['overflow'] for x in proof),'errors':sum(bool(x['pageErrors']) for x in proof)}))

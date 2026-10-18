"""Read published dataset share using the password published by its authors.
No account login, purchase, captcha bypass, upload or rights inference.
"""
from pathlib import Path
import json
from playwright.sync_api import sync_playwright
ROOT=Path(__file__).resolve().parents[2];OUT=ROOT/'audit-results/all-health-20261010/sources'
with sync_playwright() as pw:
 b=pw.chromium.launch(channel='chrome',headless=True);p=b.new_page();responses=[]
 p.on('response',lambda r:responses.append(dict(url=r.url.split('?')[0],status=r.status)) if '/share/' in r.url else None)
 p.goto('https://pan.baidu.com/s/19fv9itHcpjAQCbBxIzvb2Q',wait_until='domcontentloaded',timeout=45000)
 p.locator('input').first.fill('foa7')
 (OUT/'acne-det-share-before.json').write_text(json.dumps(dict(url=p.url,text=p.locator('body').inner_text(),controls=p.locator('button,a,input').evaluate_all('(els)=>els.map(e=>({tag:e.tagName,text:e.innerText,type:e.type,placeholder:e.placeholder}))')),ensure_ascii=False,indent=2),'utf8')
 submit=p.get_by_text('提取文件',exact=True)
 if submit.count():submit.first.click();p.wait_for_timeout(10000)
 p.screenshot(path=str(OUT/'acne-det-share.png'),full_page=True)
 body=p.locator('body').inner_text();(OUT/'acne-det-share-review.json').write_text(json.dumps(dict(url=p.url,text=body,responses=responses,loginAttempted=False,captchaBypass=False,commercialPermissionInferred=False),ensure_ascii=False,indent=2),'utf8');print(json.dumps(dict(url=p.url,text=body[:2500]),ensure_ascii=True))
 steps=[]
 for label in ['打开压缩包','下载']:
  control=p.get_by_text(label,exact=True)
  if control.count():
   control.first.click();p.wait_for_timeout(3000)
   surfaces=[]
   for view in p.context.pages:
    try:surfaces.append(dict(url=view.url,text=view.locator('body').inner_text(timeout=8000)))
    except Exception as e:surfaces.append(dict(url=view.url,error=type(e).__name__))
   steps.append(dict(action=label,url=p.url,text=p.locator('body').inner_text(),surfaces=surfaces,dialogs=p.get_by_role('dialog').all_text_contents()))
   p.screenshot(path=str(OUT/('acne-det-'+('archive' if label=='打开压缩包' else 'download')+'.png')),full_page=True)
   # Never sign into an account or bypass a login/access requirement.
   if any(view.locator('input[type=password]').count() for view in p.context.pages):break
 (OUT/'acne-det-archive-access.json').write_text(json.dumps(dict(steps=steps,loginAttempted=False,captchaBypass=False,commercialPermissionInferred=False),ensure_ascii=False,indent=2),'utf8')
 print(json.dumps(steps,ensure_ascii=True));b.close()

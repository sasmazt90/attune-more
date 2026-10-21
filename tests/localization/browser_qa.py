"""Real browser screens and events; no simulated assessment or voice success."""
import argparse,json,time,traceback,platform,sys
from pathlib import Path
from urllib.parse import urlsplit
from playwright.sync_api import sync_playwright
parser=argparse.ArgumentParser(description="Finite Cloud-only TR/EN/DE browser acceptance; never starts physical capture")
parser.add_argument('--base-url',default='http://127.0.0.1:3200')
parser.add_argument('--api-url',default='http://127.0.0.1:8100')
parser.add_argument('--output',required=True)
parser.add_argument('--chrome',help='Existing Cloud Chrome executable; no browser download is performed')
args=parser.parse_args()
if platform.system()!='Linux':raise SystemExit('BLOCKED: run this assessment in the published Linux Cloud environment')
BASE=args.base_url.rstrip('/');API=args.api_url.rstrip('/')
allowed={(urlsplit(url).hostname,urlsplit(url).port) for url in (BASE,API)}
if any(host not in ('localhost','127.0.0.1') for host,_ in allowed):raise SystemExit('BLOCKED: use an isolated loopback QA app/API')
OUT=Path(args.output)
if OUT.exists() and any(OUT.iterdir()):raise SystemExit('BLOCKED: evidence output must be new/empty; existing evidence is preserved')
OUT.mkdir(parents=True,exist_ok=True);(OUT/'screenshots').mkdir()
ROUTES=[('dashboard','/'),('vision','/vision'),('skin','/skin'),('dental','/dental'),('mental','/mental'),('hearing','/hearing'),('care','/care'),('history','/profile'),('privacy','/privacy')]
G=r'''()=>{const visible=e=>{const r=e.getBoundingClientRect(),s=getComputedStyle(e);return r.width>0&&r.height>0&&s.visibility!=='hidden'&&s.display!=='none'&&s.opacity!=='0'};const dialog=[...document.querySelectorAll('[role=dialog]')].filter(visible).at(-1);const root=dialog||document.body;const desc=e=>({tag:e.tagName,text:(e.innerText||e.getAttribute('aria-label')||'').trim().slice(0,120),rect:JSON.parse(JSON.stringify(e.getBoundingClientRect()))});const els=[...root.querySelectorAll('*')].filter(visible),controls=els.filter(e=>e.matches('button,a,input,select,textarea'));const onscreen=controls.filter(e=>{const r=e.getBoundingClientRect();return r.right>0&&r.left<innerWidth&&!e.closest('#health-centre-links')});const overlaps=[];for(let i=0;i<onscreen.length;i++)for(let j=i+1;j<onscreen.length;j++){const a=onscreen[i],b=onscreen[j];if(a.contains(b)||b.contains(a))continue;const x=a.getBoundingClientRect(),y=b.getBoundingClientRect(),w=Math.min(x.right,y.right)-Math.max(x.left,y.left),h=Math.min(x.bottom,y.bottom)-Math.max(x.top,y.top);if(w>3&&h>3)overlaps.push({a:desc(a),b:desc(b),width:w,height:h});}return {width:innerWidth,documentWidth:document.documentElement.scrollWidth,lang:document.documentElement.lang,title:document.title,body:root.innerText,headings:[...root.querySelectorAll('h1,h2,h3')].map(e=>e.innerText),overflow:els.filter(e=>{const r=e.getBoundingClientRect();return r.left< -1||r.right>innerWidth+1}).slice(0,15).map(desc),overlappingControls:overlaps,clipped:els.filter(e=>!e.closest('.sr-only')&&e.getBoundingClientRect().width>1&&e.childElementCount===0&&e.textContent.trim()&&e.clientWidth>0&&((e.scrollWidth>e.clientWidth+2&&['hidden','clip'].includes(getComputedStyle(e).overflowX))||(e.scrollHeight>e.clientHeight+2&&['hidden','clip'].includes(getComputedStyle(e).overflowY)))).slice(0,15).map(desc),brokenImages:[...document.images].filter(visible).filter(e=>!e.complete||!e.naturalWidth).map(e=>e.src),captureAttempts:window.__captureAttempts||0,buttons:controls.map(e=>({text:e.innerText,label:e.getAttribute('aria-label'),disabled:!!e.disabled}))}}'''
results=[]
def save(): (OUT/'visual-results.json').write_text(json.dumps(results,ensure_ascii=False,indent=2))
with sync_playwright() as pw:
 browser=pw.chromium.launch(**({'executable_path':args.chrome} if args.chrome else {'channel':'chrome'}),headless=True,args=['--no-sandbox','--disable-dev-shm-usage','--mute-audio'])
 for language in ('tr','en','de'):
  for width in (1440,768,375):
   context=browser.new_context(viewport={'width':width,'height':1000 if width>375 else 844},locale={'tr':'tr-TR','en':'en-US','de':'de-DE'}[language],timezone_id='Europe/Berlin')
   context.add_init_script("window.__captureAttempts=0;if(navigator.mediaDevices)navigator.mediaDevices.getUserMedia=()=>{window.__captureAttempts++;return Promise.reject(new Error('Physical capture outside Cloud QA scope'));};")
   def route(request):
    u=urlsplit(request.request.url)
    if u.scheme in ('data','blob') or ((u.hostname,u.port) in allowed):request.continue_()
    else:request.abort('blockedbyclient')
   context.route('**/*',route)
   p=context.new_page();errors=[];p.on('pageerror',lambda e:errors.append(str(e)));p.on('console',lambda m:errors.append(m.text) if m.type=='error' else None)
   p.goto(BASE+'/',wait_until='domcontentloaded');p.locator('#attune-language').wait_for(state='visible');p.wait_for_function("!document.querySelector('#attune-language').disabled")
   p.locator('#attune-language').select_option(language);p.wait_for_function('(lang)=>document.documentElement.lang===lang',arg=language)
   for name,path in ROUTES:
    row={'language':language,'width':width,'page':name,'route':path,'states':[]};results.append(row);errors.clear()
    try:
     p.goto(BASE+path,wait_until='domcontentloaded');p.wait_for_timeout(350)
     def capture(state):
      p.evaluate('document.fonts.ready');p.evaluate('scrollTo(0,0)');file=f'{language}-{width}-{name}-{state}.png';p.screenshot(path=str(OUT/'screenshots'/file),full_page=True,animations='disabled');g=p.evaluate(G);g.update({'state':state,'screenshot':'screenshots/'+file});row['states'].append(g)
      assert g['lang']==language,g
     dialog=p.get_by_role('dialog').filter(has=p.get_by_role('button',name={'tr':'İzin ver ve devam et','en':'Allow and continue','de':'Erlauben und fortfahren'}[language],exact=True))
     if dialog.count():
      capture('consent');row['consentDisabledBeforeChecks']=dialog.get_by_role('button',name={'tr':'İzin ver ve devam et','en':'Allow and continue','de':'Erlauben und fortfahren'}[language],exact=True).is_disabled();assert row['consentDisabledBeforeChecks']
      for checkbox in dialog.get_by_role('checkbox').all():checkbox.check()
      # Actual UI writes only this isolated browser profile's explicit service permissions.
      dialog.get_by_role('button',name={'tr':'İzin ver ve devam et','en':'Allow and continue','de':'Erlauben und fortfahren'}[language],exact=True).click();p.wait_for_timeout(250)
     assert p.get_by_role('dialog').count()==0, 'A blocking dialog remains'
     assert p.locator('link[rel=manifest]').count()==1, 'Manifest must have a single React owner'
     capture('page')
     if name=='dashboard':
      p.locator('button[aria-controls="health-centre-links"]').click();capture('menu');p.keyboard.press('Escape');row['escapeClosesMenu']=p.locator('#health-centre-links').count()==0;assert row['escapeClosesMenu']
      # Voice preferences use actual platform discovery. Never provide a fake voice list.
      p.locator('[data-language-selector] button').click();p.wait_for_timeout(1200);capture('voices');p.keyboard.press('Escape')
     row['consoleErrors']=list(errors);assert not errors,errors
     assert all(state['documentWidth']<=state['width']+1 and not state['brokenImages'] and not state['overlappingControls'] and not state['clipped'] and state['captureAttempts']==0 for state in row['states']), 'Overflow, clipping, overlapping controls, broken image or unexpected capture attempt'
     row['status']='PASS'
    except Exception as e:row['status']='FAIL';row['error']=str(e);row['trace']=traceback.format_exc()
    save()
   context.close()
 browser.close()
print(json.dumps({'screenshots':len(list((OUT/'screenshots').glob('*.png'))),'checks':len(results),'failed':[(r['language'],r['width'],r['page'],r.get('error')) for r in results if r['status']=='FAIL']},ensure_ascii=False))
sys.exit(1 if any(row.get('status')!='PASS' for row in results) else 0)

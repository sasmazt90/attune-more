"""Production Hearing UI acceptance using explicitly synthetic selected-record data.
No model/physical-device claim. A separate current_hearing_tone run exercises PCM.
"""
import json, math, os, subprocess, tempfile
from pathlib import Path
from playwright.sync_api import sync_playwright, expect
ROOT=Path(__file__).resolve().parents[2]
OUT=Path(os.environ.get('HEARING_UI_EVIDENCE','audit-results/hearing-approved-ui'));OUT.mkdir(parents=True,exist_ok=True)
BROWSER={'executable_path':os.environ['ATTUNE_BROWSER_EXECUTABLE']} if os.getenv('ATTUNE_BROWSER_EXECUTABLE') else {'channel':'chrome'}
code="const {fixture}=require('./tests/unit/hearing_results.cjs'); const a=fixture('synthetic-selected','2026-10-25T12:00:00Z'),b=fixture('synthetic-newest','2026-10-27T12:00:00Z'),c=fixture('synthetic-older-no-timing','2026-10-24T12:00:00Z'); b.presses.forEach(p=>p.at+=200); delete c.presentations;delete c.presses;delete c.presentationVersion; a.thresholds.find(t=>t.ear==='left'&&t.frequency===500).value=null; console.log(JSON.stringify([a,b,c]));"
records=json.loads(subprocess.check_output(['node','-e',code],cwd=ROOT,text=True).splitlines()[-1])
checks=[];errors=[];console_errors=[];shots=[]
def check(name,**data):checks.append({'check':name,'status':'PASS',**data})
def shot(p,name):p.screenshot(path=str(OUT/(name+'.png')),full_page=True);shots.append(name+'.png')
def overflow(p):
 d=p.evaluate('({inner:innerWidth,scroll:document.documentElement.scrollWidth})')
 if d['scroll']>d['inner']:
  p.screenshot(path=str(OUT/'overflow-failure.png'),full_page=True)
  (OUT/'overflow-elements.json').write_text(json.dumps(p.evaluate("[...document.querySelectorAll('body *')].filter(e=>e.getBoundingClientRect().right>innerWidth+1&&getComputedStyle(e).position!=='fixed').map(e=>({tag:e.tagName,cls:e.className,text:e.innerText?.slice(0,80),x:e.getBoundingClientRect().x,w:e.getBoundingClientRect().width})).slice(0,70)"),indent=2))
 assert d['scroll']<=d['inner'],d;return d
def open_record(p,id):
 p.locator('[data-record-id="'+id+'"] td').first.click();expect(p.get_by_role('dialog')).to_be_visible();expect(p.locator('[data-hearing-result-record="'+id+'"]')).to_be_visible()
def close(p):p.get_by_role('dialog').get_by_role('button',name={'tr':'Sonuç penceresini kapat','en':'Close results window','de':'Ergebnisfenster schließen'}.get(p.locator('html').get_attribute('lang'),'Sonuç penceresini kapat')).click()
def swipe(p,node,left=True):
 # Dispatch real React touch handlers with declared synthetic touch coordinates.
 p.locator(node).evaluate("(el,left)=>{const t=(x)=>({identifier:1,target:el,clientX:x,clientY:200});for(const [type,x] of [['touchstart',left?300:100],['touchend',left?100:300]]){const e=new Event(type,{bubbles:true});Object.defineProperty(e,'changedTouches',{value:[t(x)]});el.dispatchEvent(e);}}",left)
with sync_playwright() as pw:
 b=pw.chromium.launch(headless=True,**BROWSER);c=b.new_context(viewport={'width':1440,'height':1000});p=c.new_page();p.on('pageerror',lambda e:errors.append(str(e)));p.on('console',lambda msg:console_errors.append(msg.text) if msg.type=='error' else None)
 p.goto('http://127.0.0.1:3000/hearing');p.get_by_label('Kulaklık sesleri ve yanıtlarımla yerel işitme testinin yapılmasına izin veriyorum.').check();p.get_by_role('button',name='İzin ver ve devam et',exact=True).click()
 p.evaluate("r=>{localStorage.setItem('attune_hearing_history_v1',JSON.stringify(r));localStorage.setItem('attune_hearing_latest_v1',JSON.stringify(r[1]));window.dispatchEvent(new Event('attune-records'));}",records)
 expect(p.locator('[data-record-id]')).to_have_count(3);open_record(p,'synthetic-selected')
 mean=p.locator('[data-hearing-mean-seconds]');assert abs(float(mean.get_attribute('data-hearing-mean-seconds'))-.6)<1e-12
 assert p.locator('[data-hearing-previous-seconds]').count()==0
 expect(p.get_by_text('Önceki kayıtta ölçülen yanıt süresi bulunmuyor.',exact=True)).to_be_visible();check('Selected historical result retains own mean; nearest older timing remains absent')
 swipe(p,'[data-hearing-inner="ear"]');expect(p.locator('[data-hearing-ear-card="right"]')).to_be_visible();expect(p.locator('[data-hearing-main-tab]')).to_have_attribute('data-hearing-main-tab','0');check('Inner ear swipe does not change main tab')
 p.get_by_role('dialog').get_by_role('button',name='Ölçüm tutarlılığı',exact=True).click();swipe(p,'[data-hearing-inner="quality"]');expect(p.get_by_role('heading',name='Sessiz kontroller',exact=True)).to_be_visible();expect(p.locator('[data-hearing-main-tab]')).to_have_attribute('data-hearing-main-tab','2');check('Inner consistency swipe does not change main tab')
 p.get_by_role('dialog').get_by_role('button',name='Frekans analizi',exact=True).click();paths=p.locator('[data-hearing-series="left"] path').evaluate_all('(xs)=>xs.map(x=>x.getAttribute("d"))');assert len(paths)==2,paths
 ys=p.locator('[data-hearing-frequency-analysis] svg text').evaluate_all('(xs)=>xs.filter(x=>["-30","-90"].includes(x.textContent)).map(x=>({text:x.textContent,y:Number(x.getAttribute("y"))}))');assert ys[0]['text']=='-30' and ys[0]['y']<ys[1]['y'];check('Missing thresholds break chart lines; -30 top / -90 bottom',paths=paths)
 shot(p,'selected-frequency-desktop');p.get_by_role('dialog').get_by_role('button',name='Sonuç penceresini kapat').click();open_record(p,'synthetic-newest');assert abs(float(p.locator('[data-hearing-previous-seconds]').get_attribute('data-hearing-previous-seconds'))-.6)<1e-12;assert abs(float(p.locator('[data-hearing-mean-seconds]').get_attribute('data-hearing-mean-seconds'))-.8)<1e-12;check('Current and previous means remain separate')
 p.get_by_role('dialog').get_by_role('button',name='Sonuç penceresini kapat').click();open_record(p,'synthetic-older-no-timing');expect(p.locator('[data-hearing-timing-unavailable]')).to_be_visible();check('Older record without presentation timing has no invented mean');p.get_by_role('dialog').get_by_role('button',name='Sonuç penceresini kapat').click()
 snapshot=p.evaluate("JSON.stringify({records:localStorage.getItem('attune_hearing_history_v1'),consent:localStorage.getItem('attune_health_processing_v1')})")
 labels={'tr':['Genel bakış','Frekans analizi','Ölçüm tutarlılığı'],'en':['Overview','Frequency analysis','Measurement consistency'],'de':['Übersicht','Frequenzanalyse','Konsistenz der Messung']}
 for lang in ('tr','en','de'):
  p.locator('header select').select_option(lang)
  open_record(p,'synthetic-selected')
  for width in (1440,768,375):
   p.set_viewport_size({'width':width,'height':1000})
   for tab,label in enumerate(labels[lang]):
    p.get_by_role('dialog').get_by_role('button',name=label,exact=True).click();d=overflow(p);shot(p,f'{lang}-{width}-tab{tab}');check('Responsive localized selected-record tab',language=lang,width=width,tab=tab,dimensions=d)
  # Close using the actual accessible button, without assuming translated prose.
  p.get_by_role('dialog').locator('button').filter(has_text='✕').click()
 assert p.evaluate("JSON.stringify({records:localStorage.getItem('attune_hearing_history_v1'),consent:localStorage.getItem('attune_health_processing_v1')})")==snapshot;check('TR/EN/DE switching preserves stored records and existing consent bytes')
 p.set_viewport_size({'width':1440,'height':1000});p.locator('header select').select_option('tr');p.goto('http://127.0.0.1:3000/profile');p.locator('[data-hearing-history-open="synthetic-selected"]').click();expect(p.locator('[data-hearing-result-record="synthetic-selected"]')).to_be_visible();assert abs(float(p.locator('[data-hearing-mean-seconds]').get_attribute('data-hearing-mean-seconds'))-.6)<1e-12;shot(p,'overview-selected-popup');check('HealthHistoryOverview carousel opens actual selected record')
 storage=c.storage_state();c.close();b.close()
 # Native Chrome200% preference: CSS zoom stays1 and browser DPR/viewport confirm real zoom.
 with tempfile.TemporaryDirectory(prefix='attune-hearing-zoom-') as profile:
  pref=Path(profile)/'Default';pref.mkdir();(pref/'Preferences').write_text(json.dumps({'partition':{'default_zoom_level':{'x':math.log(2)/math.log(1.2)}}}))
  c=pw.chromium.launch_persistent_context(profile,headless=False,no_viewport=True,args=['--window-size=1600,1000'],**BROWSER)
  c.add_init_script('if(location.origin==="http://127.0.0.1:3000"&&!sessionStorage.getItem("seeded")){for(const v of '+json.dumps(storage['origins'][0]['localStorage'])+')localStorage.setItem(v.name,v.value);sessionStorage.setItem("seeded","1");}')
  p=c.new_page();p.on('pageerror',lambda e:errors.append(str(e)));p.on('console',lambda msg:console_errors.append(msg.text) if msg.type=='error' else None);p.goto('http://127.0.0.1:3000/hearing');open_record(p,'synthetic-selected');d=p.evaluate('({inner:innerWidth,outer:outerWidth,dpr:devicePixelRatio,cssZoom:getComputedStyle(document.documentElement).zoom,scroll:document.documentElement.scrollWidth})');assert d['dpr']>=2 and d['inner']<d['outer']*.65 and d['cssZoom']=='1' and d['scroll']<=d['inner'],d;shot(p,'native-200-overview');check('Actual native browser200% selected-record results',dimensions=d);c.close()
 assert not errors,errors
 assert not console_errors,console_errors
 (OUT/'proof.json').write_text(json.dumps({'status':'PASS','buildId':(ROOT/'apps/vehicle-app/.next/BUILD_ID').read_text().strip(),'syntheticRecords':True,'checks':checks,'screenshots':shots,'pageErrors':errors,'consoleErrors':console_errors,'physicalDeviceAcceptance':False},indent=2))
print('PASS production Hearing UI, selected history, localization, responsive layouts and native zoom')

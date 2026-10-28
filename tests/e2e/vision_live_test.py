"""Voice-first browser regression. Controlled video/model/ASR events only.

API :8000 (ATTUNE_TRUSTED_ORIGINS includes frontend origin), frontend :3306.
CHROME_PATH may point to an installed Chrome executable. Native approved Audio,
DOM/SVG geometry, state transitions, persistence and cleanup are real; these
checks do not establish physical-camera or ASR-provider accuracy.
"""
import json, os, re
from pathlib import Path
from playwright.sync_api import sync_playwright, expect
ROOT=Path(__file__).resolve().parents[2];OUT=ROOT/'docs/vision-evidence';OUT.mkdir(exist_ok=True)
BASE=os.getenv('VISION_TEST_URL','http://127.0.0.1:3306')
BOOT=(ROOT/'tests/e2e/vision_technical_boot.js').read_text().replace("if(fault==='uncertain'){c.left={...open,state:'uncertain'};c.blocker=null}","""
 if(fault==='uncertain'){if(m.eye==='LEFT')c.right={...open,state:'uncertain'};else c.left={...open,state:'uncertain'};c.blocker=null}
 if(fault==='hand'||fault==='object'){const covered={...closed,state:'covered',occlusionKind:fault};if(m.eye==='LEFT')c.right=covered;else c.left=covered;}
 if(fault==='test-covered'){if(m.eye==='LEFT')c.left=closed;else c.right=closed;}
 if(fault==='both-covered'){c.right=closed;c.left=closed;}
 if(fault==='no-face'){c.faceCount=0;c.positionValid=false;c.blocker='face';}
 if(fault==='poor-light'){c.qualityValid=false;c.positionValid=false;c.blocker='light';}
""")
CONSENT="""localStorage.setItem('attune_health_processing_v1',JSON.stringify({version:1,services:{vision:{permissions:['local','speech']}}}));localStorage.setItem('attune_privacy_microphone_allowed','true');"""
PATHS={'M15 90L50 10L85 90M29 60H71':'A','M20 90V10H55C85 10 85 50 55 50H20M55 50C90 50 90 90 55 90H20':'B','M80 10H20V90H80M20 50H70':'E','M80 10H20V90M20 50H70':'F','M20 90V10H55C90 10 90 50 55 50H20':'P'}
# R includes its diagonal, distinct from P.
PATHS['M20 90V10H55C90 10 90 50 55 50H20M55 50L85 90']='R'
checks=[]
def record(name,detail=True):checks.append({'name':name,'status':'PASS','detail':detail});print('PASS',name,flush=True)
def ready(p):p.wait_for_function("()=>document.querySelector('[data-vision-stage]')?.dataset.visionStage==='listening'&&!!document.querySelector('[data-letter-optotype]')&&probe.current&&!probe.current.aborted&&performance.now()-JSON.parse(document.querySelector('canvas').dataset.visionEvidence).conditions.observedAt<600",timeout=45000)
def count(p):return p.evaluate('probe.events.filter(e=>e.combinedCorrect!==undefined).length')
def target(p):
 v=p.locator('[data-letter-optotype]').evaluate("e=>({path:e.querySelector('path').getAttribute('d'),transform:e.querySelector('g').getAttribute('transform')})")
 return {'letter':PATHS[v['path']],'rotation':int(re.search(r'rotate\((\d+)\)',v['transform'])[1]),'mirrored':'scale(-1' in v['transform']}
def emit(p,text,final=True,duplicate=False,confidence=.99):p.evaluate('v=>{probe.current.confidence=v.confidence;probe.current.emit(v.text,v.final,v.duplicate)}',{'text':text,'final':final,'duplicate':duplicate,'confidence':confidence})
def phrase(v,language):
 return v['letter']+' '+{'tr':{0:'düz',90:'saat yönünde doksan derece',180:'baş aşağı',270:'saat yönünün tersinde doksan derece'},'en':{0:'upright',90:'clockwise ninety degrees',180:'upside down',270:'counterclockwise ninety degrees'},'de':{0:'aufrecht',90:'im Uhrzeigersinn neunzig Grad',180:'auf dem Kopf',270:'gegen den Uhrzeigersinn neunzig Grad'}}[language][v['rotation']]+({'tr':' ve aynalı','en':' and mirrored','de':' und gespiegelt'}[language] if v['mirrored'] else '')
def fresh(browser,language='tr',width=1440):
 ctx=browser.new_context(viewport={'width':width,'height':1000 if width>400 else 844});ctx.add_init_script(CONSENT+BOOT+f"localStorage.setItem('attune.language.v1','{language}');")
 p=ctx.new_page();p.goto(BASE+'/vision');p.get_by_role('button',name={'tr':'Başlat','en':'Start','de':'Starten'}[language],exact=True).click();ready(p);return ctx,p
with sync_playwright() as pw:
 browser=pw.chromium.launch(executable_path=os.getenv('CHROME_PATH') or None,channel=None if os.getenv('CHROME_PATH') else 'chrome',headless=True,args=['--autoplay-policy=no-user-gesture-required','--enable-unsafe-swiftshader','--no-sandbox'])
 page=None
 try:
  context,page=fresh(browser);errors=[];page.on('pageerror',lambda e:errors.append(str(e)))
  assert page.locator('[data-vision-answer-controls],[data-vision-coverage-help],[data-vision-coverage-source]').count()==0
  assert page.get_by_role('button',name='Düğmelerle yanıtla',exact=True).count()==0
  page.screenshot(path=str(OUT/'desktop-active.png'),full_page=True)
  # First concise native prompt overlaps the actual recognizer by design.
  page.wait_for_function('()=>probe.audios.some(a=>!a.paused)',timeout=15000)
  v=target(page);emit(page,v['letter'],False);page.wait_for_timeout(100);assert page.evaluate('probe.audios.every(a=>a.paused)');assert count(page)==0
  emit(page,phrase(v,'tr'));emit(page,phrase(v,'tr'),duplicate=True)
  page.wait_for_function('()=>probe.events.filter(e=>e.combinedCorrect!==undefined).length===1');ready(page)
  assert page.evaluate('probe.events.filter(e=>e.combinedCorrect!==undefined)[0].combinedCorrect')
  page.wait_for_timeout(1000);assert page.evaluate('probe.audios.every(a=>a.paused)')
  record('Native approved guidance interrupted by interim speech; duplicate final scores once; obsolete guidance stays stopped')
  v=target(page);wrong='P' if v['letter']!='P' else 'F';emit(page,phrase({**v,'letter':wrong},'tr'));page.wait_for_timeout(250);emit(page,wrong+' değil '+v['letter'])
  page.wait_for_function('()=>probe.events.filter(e=>e.combinedCorrect!==undefined).length===2');ready(page)
  assert page.evaluate('probe.events.filter(e=>e.combinedCorrect!==undefined)[1].combinedCorrect')
  record('Mid-utterance correction changes pending final before scoring')
  # A real final plus transient ASR transport error cannot become a wrong trial.
  before=target(page);page.evaluate("probe.old=probe.current;probe.current.onerror({error:'network'})")
  page.wait_for_function('()=>probe.current!==probe.old&&!probe.current.aborted');ready(page);assert target(page)==before and count(page)==2
  record('Transient ASR transport failure recovers microphone on the same target with no repeated guidance or score')
  for fault in ['test-covered','both-covered','no-face','poor-light','uncertain']:
   page.evaluate('v=>probe.fault=v',fault);page.wait_for_function("()=>!document.querySelector('[data-letter-optotype]')",timeout=6000);assert count(page)==2
   page.evaluate('probe.fault=null');ready(page)
  record('Wrong/both eyes, missing face, poor light and uncertain eyes block presentation/scoring without any manual override')
  # Transport retries are finite; the existing retry action retains the target.
  before=target(page)
  for retry in range(3):
   page.evaluate("probe.old=probe.current;probe.current.onerror({error:'network'})")
   if retry<2:page.wait_for_function('()=>probe.current!==probe.old&&!probe.current.aborted')
  page.wait_for_function("()=>document.querySelector('[data-vision-stage]').dataset.visionStage==='error'");assert count(page)==2
  page.get_by_role('button',name='Tekrar dene',exact=True).click();ready(page);assert target(page)==before
  record('ASR session limit ends after two retries; explicit retry preserves target and does not score a failure')
  # Demonstrate automatic covered states independently in each eye stage.
  for index in range(2,24):
   ready(page)
   if index in [2,12]:page.evaluate("probe.fault='hand'");page.wait_for_timeout(400)
   if index in [3,13]:page.evaluate("probe.fault='object'");page.wait_for_timeout(400)
   if index in [4,14]:page.evaluate('probe.fault=null');page.wait_for_timeout(400)
   ready(page);v=target(page)
   if index==5:
    emit(page,phrase(v,'tr'));page.wait_for_timeout(150);page.get_by_role('button',name='Duraklat',exact=True).click();page.wait_for_timeout(850);assert count(page)==index
    page.get_by_role('button',name='Devam et',exact=True).click();ready(page);assert target(page)==v
   emit(page,phrase(v,'tr'));page.wait_for_function('n=>probe.events.filter(e=>e.combinedCorrect!==undefined).length===n',arg=index+1)
  page.get_by_role('button',name='Tamam',exact=True).click()
  stored=page.evaluate("JSON.parse(localStorage.getItem('togg_health_latest_vision'))");valid=[t for t in stored['trials'] if t['valid']]
  assert len(valid)==24 and sum(t['eye']=='RIGHT' for t in valid)==12 and sum(t['eye']=='LEFT' for t in valid)==12
  assert all(t['combinedCorrect'] for t in valid)
  assert all('coverageConfirmation' not in t['conditions'] and 'coverageVerification' not in t and 'inputMethod' not in t for t in valid)
  assert {'hand','object'}.issubset({t['conditions'][('left' if t['eye']=='RIGHT' else 'right')].get('occlusionKind') for t in valid})
  page.screenshot(path=str(OUT/'desktop-result.png'),full_page=True)
  page.reload();page.get_by_role('button',name='Sonucu Aç',exact=True).click();page.get_by_role('dialog').wait_for();assert page.locator('[data-eye-summary]').count()==2
  assert page.evaluate("JSON.parse(localStorage.getItem('togg_health_latest_vision')).id")==stored['id'];page.screenshot(path=str(OUT/'history.png'),full_page=True)
  record('24 spoken answers, automatic hand/object condition admission in each eye, pause cancellation, deterministic scores and history reload')
  context.close()
  for language in ['tr','en','de']:
   ctx,p=fresh(browser,language,390);assert p.evaluate('document.documentElement.scrollWidth<=innerWidth+1')
   v=target(p);emit(p,phrase(v,language));p.wait_for_function('()=>probe.events.filter(e=>e.combinedCorrect!==undefined).length===1');ready(p)
   assert p.evaluate('probe.events.filter(e=>e.combinedCorrect!==undefined)[0].combinedCorrect')
   p.screenshot(path=str(OUT/f'mobile-{language}.png'),full_page=True)
   p.evaluate("localStorage.setItem('attune_privacy_microphone_allowed','false');window.dispatchEvent(new Event('attune-privacy'))")
   p.wait_for_function("()=>probe.streams.every(s=>s.getTracks().every(t=>t.readyState==='ended'))")
   assert p.evaluate("localStorage.getItem('togg_health_latest_vision')")==None
   record(language+' mobile spoken answer, responsive UI and microphone-consent withdrawal cleanup');ctx.close()
  assert not errors,errors
  (OUT/'browser-results.json').write_text(json.dumps({'kind':'controlled camera/model/ASR events; actual browser UI, Audio, API and history','physicalUserAcceptance':False,'checks':checks,'errors':errors},indent=2)+'\n')
 except Exception:
  if page and not page.is_closed():
   print('Failure state:',page.locator('[data-vision-stage]').get_attribute('data-vision-stage'),flush=True)
   page.screenshot(path=str(OUT/'failure.png'),full_page=True)
  raise
 finally:browser.close()

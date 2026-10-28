"""Production UI/native approved audio, controlled camera/model/ASR events.
No synthetic input is physical-camera or microphone accuracy evidence.
"""
import json,os,re,time
from pathlib import Path
from playwright.sync_api import sync_playwright
ROOT=Path(__file__).resolve().parents[2];OUT=ROOT/'docs/vision-conversation-evidence';OUT.mkdir(exist_ok=True)
BASE=os.getenv('VISION_TEST_URL','http://127.0.0.1:3306')
BOOT=(ROOT/'tests/e2e/vision_technical_boot.js').read_text()
BOOT=BOOT.replace("if(fault==='uncertain'){c.left={...open,state:'uncertain'};c.blocker=null}","""
 if(fault==='uncertain'){if(m.eye==='LEFT')c.right={...open,state:'uncertain'};else c.left={...open,state:'uncertain'};c.blocker=null}
 if(fault==='hand'||fault==='object'){const cover={...closed,state:'covered',occlusionKind:fault};if(m.eye==='LEFT')c.right=cover;else c.left=cover;}
 if(fault==='test-covered'){if(m.eye==='LEFT')c.left=closed;else c.right=closed;}
 if(fault==='no-face'){c.faceCount=0;c.positionValid=false;c.blocker='face'}
""")
SEED="localStorage.setItem('attune_health_processing_v1',JSON.stringify({version:1,services:{vision:{permissions:['local','speech']}}}));localStorage.setItem('attune_privacy_microphone_allowed','true');"
OBSERVE="""
probe.turnEvents=[];probe.overlaps=[];probe.nativeEndedAt=0;
window.addEventListener('attune-vision-speech-timing',e=>probe.turnEvents.push({...e.detail,activeRecognizers:probe.recognitions.filter(r=>!r.aborted&&r.started).length}));
const OriginalStart=SpeechRecognition.prototype.start;SpeechRecognition.prototype.start=function(){this.started=true;const activeAudio=probe.audios.filter(a=>!a.paused).length;if(activeAudio)probe.overlaps.push('mic-during-audio');probe.turnEvents.push({stage:'recognizer-start',afterAudioMs:performance.now()-probe.nativeEndedAt,atMs:performance.now()});return OriginalStart.call(this);};
const ObserveAudio=window.Audio;window.Audio=function(...args){const a=new ObserveAudio(...args);a.addEventListener('playing',()=>{if(probe.recognitions.some(r=>r.started&&!r.aborted))probe.overlaps.push('audio-during-mic');});a.addEventListener('ended',()=>{probe.nativeEndedAt=performance.now();});return a;};window.Audio.prototype=ObserveAudio.prototype;
"""
PATHS={'M15 90L50 10L85 90M29 60H71':'A','M20 90V10H55C85 10 85 50 55 50H20M55 50C90 50 90 90 55 90H20':'B','M80 10H20V90H80M20 50H70':'E','M80 10H20V90M20 50H70':'F','M20 90V10H55C90 10 90 50 55 50H20':'P','M20 90V10H55C90 10 90 50 55 50H20M55 50L85 90':'R'}
WORDS={'tr':{'A':'Adana','B':'Bolu','E':'Edirne','F':'Fatsa','P':'Pırasa','R':'Rize'},'en':{'A':'Alpha','B':'Bravo','E':'Echo','F':'Foxtrot','P':'Papa','R':'Romeo'},'de':{'A':'Anton','B':'Berlin','E':'Emil','F':'Friedrich','P':'Paula','R':'Richard'}}
DIRECTIONS={'tr':{0:'düz',90:'saat yönünde doksan derece',180:'baş aşağı',270:'saat yönünün tersinde doksan derece'},'en':{0:'upright',90:'clockwise ninety degrees',180:'upside down',270:'counterclockwise ninety degrees'},'de':{0:'aufrecht',90:'im Uhrzeigersinn neunzig Grad',180:'auf dem Kopf',270:'gegen den Uhrzeigersinn neunzig Grad'}}
MIRROR={'tr':' ve aynalı','en':' and mirrored','de':' und gespiegelt'}
checks=[];languages={};current=None
CATALOG=json.loads((ROOT/'shared/localization/messages.json').read_text())
def label(text,lang):return next(v[lang] for v in CATALOG.values() if v['tr']==text)

def ready(p):p.wait_for_function("()=>document.querySelector('[data-vision-stage]')?.dataset.visionStage==='listening'&&probe.current&&!probe.current.aborted&&probe.current.started&&probe.audios.every(a=>a.paused)&&!!document.querySelector('[data-letter-optotype]')",timeout=60000)
def count(p):return p.evaluate('probe.events.filter(e=>e.combinedCorrect!==undefined).length')
def target(p):
 v=p.locator('[data-letter-optotype]').evaluate("e=>({path:e.querySelector('path').getAttribute('d'),transform:e.querySelector('g').getAttribute('transform')})")
 return {'letter':PATHS[v['path']],'rotation':int(re.search(r'rotate\((\d+)\)',v['transform'])[1]),'mirrored':'scale(-1' in v['transform']}
def orientation(v,lang):return DIRECTIONS[lang][v['rotation']]+(MIRROR[lang] if v['mirrored'] else '')
def word(v,lang):return WORDS[lang][v['letter']]
def emit(p,text,confidence=.99):
 ready(p);before=count(p);p.evaluate('v=>{probe.current.confidence=v.confidence;probe.current.emit(v.text,true,false)}',{'text':text,'confidence':confidence});return {'fixtureTranscript':text,'confidence':confidence,'scoreCountBefore':before}
def next_prompt(p,code):
 p.wait_for_function('code=>probe.turnEvents.some(e=>e.stage===`prompt:${code}`&&e.atMs>probe.waitAfter)',arg=code,timeout=10000)
 assert p.evaluate('probe.current?.aborted!==false')
def expect_partial(p,text,code,rows,confidence=.99,screenshot=None):
 p.evaluate('probe.waitAfter=performance.now()');row=emit(p,text,confidence);next_prompt(p,code);row.update({'followUp':code,'scored':count(p)-row['scoreCountBefore']});assert row['scored']==0
 if screenshot:p.screenshot(path=str(OUT/screenshot),full_page=False)
 ready(p);rows.append(row)
def finish(p,text,rows,screenshot=None,correct=True):
 row=emit(p,text)
 if screenshot:p.wait_for_timeout(80);snap(p,screenshot)
 p.wait_for_function('n=>probe.events.filter(e=>e.combinedCorrect!==undefined).length===n',arg=row['scoreCountBefore']+1,timeout=10000);row['scored']=1;rows.append(row)
 assert p.evaluate('probe.events.filter(e=>e.combinedCorrect!==undefined).at(-1).combinedCorrect')==correct
def snap(p,name):p.screenshot(path=str(OUT/(name+'.png')),full_page=False)


def exercise_lifecycle(p,lang):
 # Existing retry/pause controls only; no new interaction path.
 ready(p);before=count(p);v=target(p)
 for retry in range(3):
  p.evaluate("probe.old=probe.current;probe.current.onerror({error:'network'})")
  if retry<2:p.wait_for_function('()=>probe.current!==probe.old&&!probe.current.aborted')
 p.wait_for_function("()=>document.querySelector('[data-vision-stage]').dataset.visionStage==='error'");assert count(p)==before
 p.get_by_role('button',name=label('Tekrar dene',lang),exact=True).click();ready(p);assert target(p)==v
 p.evaluate('probe.waitAfter=performance.now()');emit(p,word(v,lang));next_prompt(p,'orientation')
 p.wait_for_function('()=>probe.audios.some(a=>!a.paused)');p.get_by_role('button',name=label('Duraklat',lang),exact=True).click()
 p.wait_for_function("()=>document.querySelector('[data-vision-stage]').dataset.visionStage==='user-paused'&&probe.current&&!probe.current.aborted");assert count(p)==before
 resume={'tr':'devam et','en':'resume','de':'fortsetzen'}[lang]
 p.evaluate("text=>probe.current.emit(text,true,false)",resume);ready(p);assert target(p)==v
 finish(p,orientation(v,lang),[]);checks.append({'stage':lang+' retry / pause during follow-up / spoken resume / retained component','status':'PASS'})

def run_main():
 current=None
 with sync_playwright() as pw:
  browser=pw.chromium.launch(executable_path=os.getenv('CHROME_PATH') or None,channel=None if os.getenv('CHROME_PATH') else 'chrome',headless=True,args=['--autoplay-policy=no-user-gesture-required','--enable-unsafe-swiftshader','--no-sandbox'])
  try:
   for lang in ['tr','en','de']:
    ctx=browser.new_context(viewport={'width':1440,'height':1000});ctx.add_init_script(SEED+BOOT+OBSERVE+f"localStorage.setItem('attune.language.v1','{lang}');")
    p=ctx.new_page();current=p;errors=[];p.on('pageerror',lambda e:errors.append(str(e)));p.goto(BASE+'/vision')
    start={'tr':'Başlat','en':'Start','de':'Starten'}[lang];p.get_by_role('button',name=start,exact=True).wait_for()
    if lang=='tr':snap(p,'desktop-preparation')
    p.get_by_role('button',name=start,exact=True).click()
    p.wait_for_function("()=>document.querySelector('[data-vision-stage]')?.dataset.visionStage==='eye-instruction'",timeout=45000)
    assert p.evaluate('probe.recognitions.length')==0
    if lang=='tr':snap(p,'desktop-eye-closure-instruction')
    ready(p);assert p.locator('[data-vision-answer-controls],[data-vision-coverage-source]').count()==0
    if lang=='tr':snap(p,'desktop-listening')
    scenarios=[]
    for name in ['letter-only','orientation-only','both','neither','ambiguous-letter','ambiguous-orientation','low-letter-confidence','low-orientation-confidence','letter-correction','orientation-correction','silence','stale-event']:
     ready(p)
     if name=='orientation-only':p.evaluate("probe.fault='hand'");p.wait_for_timeout(250)
     elif name=='both':p.evaluate("probe.fault='object'");p.wait_for_timeout(250)
     elif name=='neither':p.evaluate('probe.fault=null');p.wait_for_timeout(250)
     v=target(p);rows=[]
     if name=='letter-only':
      expect_partial(p,word(v,lang),'orientation',rows,screenshot='desktop-recognized-letter.png' if lang=='tr' else None);finish(p,orientation(v,lang),rows)
     elif name=='orientation-only':
      expect_partial(p,orientation(v,lang),'letter',rows);finish(p,word(v,lang),rows)
     elif name=='both':finish(p,word(v,lang)+' '+orientation(v,lang),rows,'desktop-spoken-response' if lang=='tr' else None)
     elif name=='neither':
      expect_partial(p,'blablabla','repeat',rows);finish(p,word(v,lang)+' '+orientation(v,lang),rows)
     elif name=='ambiguous-letter':
      expect_partial(p,({'tr':'E veya F ','en':'E or F ','de':'E oder F '})[lang]+orientation(v,lang),'letter',rows);finish(p,word(v,lang),rows)
     elif name=='ambiguous-orientation':
      expect_partial(p,word(v,lang)+' '+({'tr':'sağa sola','en':'right left','de':'rechts links'})[lang],'orientation',rows);finish(p,orientation(v,lang),rows)
     elif name=='low-letter-confidence':
      expect_partial(p,word(v,lang),'orientation',rows,.3);expect_partial(p,orientation(v,lang),'letter',rows);finish(p,word(v,lang),rows)
     elif name=='low-orientation-confidence':
      expect_partial(p,orientation(v,lang),'letter',rows,.3);expect_partial(p,word(v,lang),'orientation',rows);finish(p,orientation(v,lang),rows)
     elif name=='letter-correction':
      wrong='B' if v['letter']!='B' else 'E';expect_partial(p,wrong,'orientation',rows)
      expect_partial(p,wrong+({'tr':' değil ','en':' no ','de':' nein '})[lang]+v['letter'],'orientation',rows);finish(p,orientation(v,lang),rows)
     elif name=='orientation-correction':
      wrong=DIRECTIONS[lang][(v['rotation']+90)%360]
      expect_partial(p,wrong,'letter',rows)
      expect_partial(p,wrong+({'tr':' değil ','en':' no ','de':' nein '})[lang]+orientation(v,lang),'letter',rows);finish(p,word(v,lang),rows)
     elif name=='silence':
      p.evaluate('probe.waitAfter=performance.now();probe.current.onerror({error:"no-speech"});probe.current.started=false;probe.current.onend()');next_prompt(p,'repeat');ready(p)
      n=p.evaluate('probe.turnEvents.filter(e=>e.stage.startsWith("prompt:")).length');p.evaluate('probe.current.onerror({error:"no-speech"});probe.current.started=false;probe.current.onend()');ready(p)
      assert p.evaluate('probe.turnEvents.filter(e=>e.stage.startsWith("prompt:")).length')==n;finish(p,word(v,lang)+' '+orientation(v,lang),rows)
     elif name=='stale-event':
      p.evaluate('()=>{probe.oldResult=probe.current.onresult;}');expect_partial(p,word(v,lang),'orientation',rows)
      before=count(p);p.evaluate('probe.oldResult({resultIndex:0,results:[Object.assign([{transcript:"F upright",confidence:.99}],{isFinal:true})]})');assert count(p)==before;finish(p,orientation(v,lang),rows)
     scenarios.append({'name':name,'status':'PASS','turns':rows});print('PASS',lang,name,flush=True)
    # Complete both-eye sessions in every locale; screenshots use the current UI.
    if lang=='tr':
     p.wait_for_function("()=>document.querySelector('[data-vision-stage]').dataset.visionStage==='eye-instruction'",timeout=10000);snap(p,'desktop-eye-coverage-instruction')
    ready(p);p.evaluate("probe.fault='hand'");p.wait_for_timeout(250)
    if lang=='tr':snap(p,'desktop-hand-coverage')
    v=target(p);finish(p,word(v,lang)+' '+orientation(v,lang),[])
    ready(p);p.evaluate("probe.fault='object'");p.wait_for_timeout(250)
    if lang=='tr':snap(p,'desktop-object-coverage')
    v=target(p);finish(p,word(v,lang)+' '+orientation(v,lang),[])
    p.evaluate('probe.fault=null')
    for fault in ['test-covered','no-face','uncertain']:
     ready(p);before=count(p);p.evaluate('v=>probe.fault=v',fault);p.wait_for_function("()=>!document.querySelector('[data-letter-optotype]')",timeout=6000);assert count(p)==before;p.evaluate('probe.fault=null');ready(p)
    while count(p)<24:
     ready(p);v=target(p)
    if count(p)==23:
     wrong={**v,'letter':'E' if v['letter']!='E' else 'B'};finish(p,word(wrong,lang)+' '+orientation(v,lang),[],correct=False)
    else:finish(p,word(v,lang)+' '+orientation(v,lang),[])
    p.get_by_role('button',name={'tr':'Tamam','en':'OK','de':'OK'}[lang],exact=True).click()
    if lang=='tr':snap(p,'desktop-results')
    result=p.evaluate("JSON.parse(localStorage.getItem('togg_health_latest_vision'))");valid=[t for t in result['trials'] if t['valid']];assert len(valid)==24 and sum(t['combinedCorrect'] for t in valid)==23;assert sum(t['eye']=='RIGHT' for t in valid)==12
    p.reload();p.get_by_role('button',name={'tr':'Sonucu Aç','en':'Open result','de':'Ergebnis öffnen'}[lang],exact=True).click();p.get_by_role('dialog').wait_for()
    if lang=='tr':snap(p,'desktop-history')
    assert p.locator('[data-eye-summary]').count()==2
    checks.append({'stage':lang+' 24 questions / both eyes / results / history','status':'PASS'})
    assert not errors,errors;assert p.evaluate('probe.overlaps')==[]
    starts=p.evaluate('probe.turnEvents.filter(e=>e.stage==="recognizer-start").map(e=>e.afterAudioMs)');assert all(t>=300 for t in starts)
    languages[lang]={'status':'PASS','camera':'SIMULATED','ASR':'SIMULATED','audio':'native approved recordings','session':{'valid':24,'rightEye':12,'leftEye':12,'intentionallyWrong':1,'combinedCorrect':23},'scenarios':scenarios,'events':p.evaluate('probe.turnEvents'),'overlaps':p.evaluate('probe.overlaps')}
    (OUT/'conversation-browser.json').write_text(json.dumps({'status':'RUNNING','languages':languages,'checks':checks},ensure_ascii=False,indent=2)+'\n')
    ctx.close()
    # Fresh mobile context: same existing responsive UI, real audio then ASR fixture.
    c=browser.new_context(viewport={'width':390,'height':844});c.add_init_script(SEED+BOOT+OBSERVE+f"localStorage.setItem('attune.language.v1','{lang}');");q=c.new_page();current=q;q.goto(BASE+'/vision');q.get_by_role('button',name=start,exact=True).click();ready(q)
    v=target(q);finish(q,word(v,lang)+' '+orientation(v,lang),[]);ready(q);assert q.evaluate('document.documentElement.scrollWidth<=innerWidth+1');q.screenshot(path=str(OUT/f'mobile-{lang}.png'),full_page=True)
    q.evaluate("localStorage.setItem('attune_privacy_microphone_allowed','false');window.dispatchEvent(new Event('attune-privacy'))");q.wait_for_function("()=>probe.streams.every(s=>s.getTracks().every(t=>t.readyState==='ended'))");assert q.evaluate("localStorage.getItem('togg_health_latest_vision')")==None
    checks.append({'stage':lang+' responsive / microphone consent / cleanup','status':'PASS'});c.close()
   (OUT/'conversation-browser.json').write_text(json.dumps({'status':'PASS','kind':'actual production browser/native audio; simulated camera/model/ASR','physicalUserAcceptance':False,'languages':languages,'checks':checks},ensure_ascii=False,indent=2)+'\n')
  except Exception:
   if current and not current.is_closed():current.screenshot(path=str(OUT/'failure.png'),full_page=True)
   raise
  finally:browser.close()

if __name__=='__main__':run_main()

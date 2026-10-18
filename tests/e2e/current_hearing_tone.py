"""Complete native production adaptive plan; automated presses, no human hearing claim."""
import json,time
from pathlib import Path
from playwright.sync_api import sync_playwright,expect
OUT=Path('audit-results/feedback-four-modules-20261009/hearing-tone');OUT.mkdir(exist_ok=True)
INIT='''window.seeds=[];const rand=crypto.getRandomValues.bind(crypto);crypto.getRandomValues=a=>{const out=rand(a);if(a instanceof Uint32Array&&a.length===1)seeds.push(a[0]);return out;};window.guidanceEvents=[];window.addEventListener('attune-guidance-event',e=>guidanceEvents.push({...e.detail,at:performance.now()}));window.pcm=[];const nativeStart=AudioBufferSourceNode.prototype.start;AudioBufferSourceNode.prototype.start=function(...args){if(this.buffer){const channels=[];for(let i=0;i<this.buffer.numberOfChannels;i++){const s=this.buffer.getChannelData(i);let peak=0,sum=0;for(const v of s){peak=Math.max(peak,Math.abs(v));sum+=v*v;}channels.push({peak,rms:Math.sqrt(sum/s.length)});}const row={at:performance.now(),duration:this.buffer.duration,channels,ended:false};pcm.push(row);this.addEventListener('ended',()=>row.ended=true);}return nativeStart.apply(this,args);};'''
with sync_playwright() as pw:
 b=pw.chromium.launch(channel='chrome',headless=True,args=['--autoplay-policy=no-user-gesture-required']);c=b.new_context(viewport={'width':1600,'height':1000});c.add_init_script(INIT);p=c.new_page();errors=[];p.on('pageerror',lambda e:errors.append(str(e)))
 p.goto('http://127.0.0.1:3000/hearing');p.get_by_label('Yerel ses testi işlemini başlatmayı kabul ediyorum.').check();p.get_by_role('button',name='Ses hazırlığını başlat').click();expect(p.get_by_role('button',name='Sol kanalı dinle')).to_be_enabled(timeout=20000)
 for ear in ['sol','sağ']:
  p.get_by_role('button',name=ear.capitalize()+' kanalı dinle').click();check=p.get_by_label('Yalnız '+ear+' kulağımda duydum.');expect(check).to_be_enabled(timeout=10000);check.check()
 p.get_by_role('button',name='Saf ses testi',exact=True).click();expect(p.get_by_role('button',name='Duydum',exact=True)).to_be_visible(timeout=15000)
 # Rapid presses include gap/catch/duplicate events; native timers, PCM and
 # staircase remain untouched. A press never creates a new presentation.
 p.evaluate("window.presses=setInterval(()=>{const b=[...document.querySelectorAll('button')].find(e=>e.innerText==='Duydum');if(b)b.click();},150)")
 transitions=[];last='';deadline=time.monotonic()+540
 while not p.locator('[data-hearing-result]').count() and time.monotonic()<deadline:
  p.wait_for_timeout(1000);row=p.evaluate("(()=>{const e=document.querySelector('[data-tone-progress]');return {at:performance.now(),text:e?.innerText||'',stage:e?.parentElement?.innerText?.slice(0,160)||''}})()");text=row['text']
  if text!=last:transitions.append(row);last=text
  (OUT/'progress.json').write_text(json.dumps(transitions,indent=2),'utf8')
 expect(p.locator('[data-hearing-result]')).to_be_visible(timeout=1000);p.evaluate('clearInterval(window.presses)');p.wait_for_function('localStorage.getItem("attune_hearing_latest_v1")')
 result=p.evaluate('JSON.parse(localStorage.getItem("attune_hearing_latest_v1"))');waves=p.evaluate('window.pcm');events=p.evaluate('window.guidanceEvents');plans=result['presentations']
 (OUT/'raw.json').write_text(json.dumps({'result':result,'waves':waves,'events':events},indent=2),'utf8')
 assert len(result['thresholds'])==14 and result['quality']=='unreliable'
 assert all(t['value'] is None and t['status']=='lower-limit' for t in result['thresholds'])
 assert result['totalPresentations']==len(plans) and all(t['completedAt'] is not None for t in plans)
 assert {'early','silent','late','valid','duplicate'}<=set(p['kind'] for p in result['presses'])
 assert len(result['presses'])>len(plans)*5
 assert sum(t['silent'] for t in plans)==result['catchTrials'] and result['catchFalsePositive']==result['catchTrials']
 assert len(waves)==2+sum(not t['silent'] for t in plans) and all(w['ended'] for w in waves)
 tones=iter(waves[2:])
 for plan in plans:
  gap=(plan['startedAt']-plan['scheduledAt'])/1000;assert 1.0<=gap<=3.1
  if not plan['silent']:
   wave=next(tones);assert abs(wave['at']-plan['startedAt'])<100
   channel=0 if plan['ear']=='left' else 1;assert wave['channels'][1-channel]['rms']==0
   # Discrete 8 kHz samples at 48 kHz do not hit the continuous sine peak.
   import math
   rate=result['captureConditions']['contextSampleRate'];hz=plan['frequency']
   expected=max(abs(math.sin(2*math.pi*hz*i/rate)) for i in range(rate//math.gcd(rate,hz)))*10**(plan['level']/20)
   assert abs(wave['channels'][channel]['peak']-expected)<1e-7,(plan,wave,expected)
 assert len({round(t['startedAt']-t['scheduledAt']) for t in plans})>20
 assert len({round(w['duration'],3) for w in waves[2:]})>20
 ended=next(e for e in events if e['id']=='hearing-tone' and e['event']=='ended');assert waves[2]['at']>=ended['at']
 assert not [e for e in events if e['event']=='playing' and waves[2]['at']<=e['at']<=waves[-1]['at']]
 p.screenshot(path=str(OUT/'result-legend.png'),full_page=True)
 assert len(p.evaluate('JSON.parse(localStorage.getItem("attune_hearing_history_v1"))'))==1
 seeds=p.evaluate('window.seeds');assert result['seed']==seeds[-1]
 p.get_by_role('button',name='Yeni Test',exact=True).click();p.get_by_role('button',name='Ses hazırlığını başlat').click();expect(p.get_by_role('button',name='Sol kanalı dinle')).to_be_enabled(timeout=20000)
 fresh=p.evaluate('window.seeds');assert len(fresh)==len(seeds)+1 and fresh[-1]!=seeds[-1]
 p.get_by_role('button',name='Durdur',exact=True).click();assert len(p.evaluate('JSON.parse(localStorage.getItem("attune_hearing_history_v1"))'))==1
 assert not errors,errors
 (OUT/'proof.json').write_text(json.dumps({'buildId':Path('apps/vehicle-app/.next/BUILD_ID').read_text().strip(),'status':'PASS','fullFourteenStageNativePlan':True,'randomOverride':False,'humanAcceptance':False,'automatedRapidPresses':True,'actualPCM':waves,'result':result,'progress':transitions,'guidanceEvents':events,'freshSeeds':fresh,'pageErrors':errors},indent=2),'utf8');b.close()
print('PASS full 14-stage native plan, all press classes, random gaps/durations/catches, automatic single record')

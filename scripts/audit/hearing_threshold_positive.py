"""Actual production adaptive 14-stage PCM task, controlled audible responses.
Response depends on native PCM peak, not app level/state. No hardware claim.
"""
from pathlib import Path
import json,time
from playwright.sync_api import sync_playwright,expect
ROOT=Path(__file__).resolve().parents[2];OUT=ROOT/'audit-results/all-health-20261010/hearing-threshold';OUT.mkdir(parents=True,exist_ok=True)
INIT='''window.waves=[];window.autoRespond=false;const original=AudioBufferSourceNode.prototype.start;AudioBufferSourceNode.prototype.start=function(...args){if(this.buffer){const channels=[];for(let i=0;i<this.buffer.numberOfChannels;i++){const a=this.buffer.getChannelData(i);let peak=0,e=0;for(const v of a){peak=Math.max(peak,Math.abs(v));e+=v*v;}channels.push({peak,rms:Math.sqrt(e/a.length)});}const row={channels,at:performance.now(),duration:this.buffer.duration,ended:false};waves.push(row);this.addEventListener('ended',()=>row.ended=true);if(autoRespond&&Math.max(...channels.map(c=>c.peak))>=.003162277660168379)setTimeout(()=>{const b=[...document.querySelectorAll('button')].find(e=>e.innerText==='Duydum');b?.click();row.respondedAt=performance.now();},300);}return original.apply(this,args);};'''
with sync_playwright() as pw:
 b=pw.chromium.launch(channel='chrome',headless=True,args=['--autoplay-policy=no-user-gesture-required']);c=b.new_context();c.add_init_script(INIT);p=c.new_page();errors=[];p.on('pageerror',lambda e:errors.append(str(e)))
 c.request.post('http://127.0.0.1:8000/api/vehicle/speed',data={'speedKmH':0})
 network=[];p.on('requestfailed',lambda r:network.append(dict(url=r.url.split('?')[0],failure=r.failure)))
 p.goto('http://127.0.0.1:3000/hearing');p.get_by_label('Yerel ses testi işlemini başlatmayı kabul ediyorum.').check();p.get_by_role('button',name='Ses hazırlığını başlat').click();expect(p.get_by_role('button',name='Sol kanalı dinle')).to_be_enabled(timeout=20000)
 for ear in ['sol','sağ']:
  p.get_by_role('button',name=ear.capitalize()+' kanalı dinle').click();check=p.get_by_label('Yalnız '+ear+' kulağımda duydum.');expect(check).to_be_enabled(timeout=10000);check.check()
 p.evaluate('autoRespond=true');p.get_by_role('button',name='Saf ses testi',exact=True).click();start=time.monotonic()
 while not p.locator('[data-hearing-result]').count() and time.monotonic()-start<800:
  p.wait_for_timeout(2000)
  (OUT/'progress.json').write_text(json.dumps(dict(buildId=(ROOT/'apps/vehicle-app/.next/BUILD_ID').read_text().strip(),seconds=time.monotonic()-start,body=p.locator('main').inner_text(),waveCount=p.evaluate('waves.length'),pageErrors=errors,network=network),ensure_ascii=False,indent=2),'utf8')
 expect(p.locator('[data-hearing-result]')).to_be_visible(timeout=1000);p.wait_for_function('localStorage.getItem("attune_hearing_latest_v1")')
 result=p.evaluate('JSON.parse(localStorage.getItem("attune_hearing_latest_v1"))');waves=p.evaluate('window.waves')
 assert len(result['thresholds'])==14 and all(t['status']=='threshold' and t['value'] in [-50,-45] and t['unit']=='dBFS-peak' for t in result['thresholds']),result
 assert result['catchFalsePositive']==0 and all(p['kind']=='valid' for p in result['presses'])
 assert len(waves)==2+sum(not v['silent'] for v in result['presentations']) and all(v['ended'] for v in waves)
 for ear in ['left','right']:
  t=[t for t in result['thresholds'] if t['ear']==ear and t['frequency']==1000];assert len(t)==2 and t[0]['value']==t[1]['value']
 assert len(p.evaluate('JSON.parse(localStorage.getItem("attune_hearing_history_v1"))'))==1 and not errors
 p.screenshot(path=str(OUT/'fourteen-thresholds.png'),full_page=True)
 (OUT/'proof.json').write_text(json.dumps(dict(status='PASS',buildId=(ROOT/'apps/vehicle-app/.next/BUILD_ID').read_text().strip(),actualPCM=True,controlledResponseFromPCM=True,physicalHearingAcceptance=False,seconds=time.monotonic()-start,result=result,waves=waves,pageErrors=errors),indent=2),'utf8');c.close();b.close()
print('PASS 14 actual adaptive thresholds, zero catch presses, matching repeats and one record')

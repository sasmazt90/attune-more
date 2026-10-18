"""Real 24-trial production DIN convergence with declared engineering replies.
Only the random seed is controlled; no audio, staircase or quality gate is replaced.
"""
import json
from pathlib import Path
from playwright.sync_api import sync_playwright,expect

OUT=Path('audit-results/feedback-four-modules-20261009/hearing-positive');OUT.mkdir(parents=True,exist_ok=True)
SEED=8102026
INIT='''window.counts=[];let lastCount=null;new MutationObserver(()=>{const e=document.querySelector('[data-din-countdown]');const v=e?.innerText;if(v&&v!==lastCount){lastCount=v;counts.push({value:+v,at:performance.now()});}}).observe(document,{childList:true,subtree:true,characterData:true});const originalRandom=crypto.getRandomValues.bind(crypto);crypto.getRandomValues=function(a){if(a instanceof Uint32Array&&a.length===1){a[0]=8102026;return a;}return originalRandom(a);};window.guidanceEvents=[];window.addEventListener('attune-guidance-event',e=>window.guidanceEvents.push({...e.detail,at:performance.now()}));window.playedPCM=[];const start=AudioBufferSourceNode.prototype.start;AudioBufferSourceNode.prototype.start=function(...args){const buffer=this.buffer;if(buffer){const channels=[];for(let i=0;i<buffer.numberOfChannels;i++){const samples=buffer.getChannelData(i);let energy=0,peak=0;for(const x of samples){energy+=x*x;peak=Math.max(peak,Math.abs(x));}channels.push({rms:Math.sqrt(energy/samples.length),peak,first:samples[0],last:samples.at(-1)});}const row={sampleRate:buffer.sampleRate,channels,ended:false,at:performance.now()};window.playedPCM.push(row);this.addEventListener('ended',()=>row.ended=true);}return start.apply(this,args);};'''

with sync_playwright() as pw:
    browser=pw.chromium.launch(channel='chrome',headless=True,args=['--autoplay-policy=no-user-gesture-required'])
    context=browser.new_context();context.add_init_script(INIT);page=context.new_page();errors=[];page.on('pageerror',lambda e:errors.append(str(e)))
    context.request.post('http://127.0.0.1:8000/api/vehicle/speed',data={'speedKmH':0})
    page.goto('http://127.0.0.1:3000/hearing');page.get_by_label('Yerel ses testi işlemini başlatmayı kabul ediyorum.').check();page.get_by_role('button',name='Ses hazırlığını başlat').click()
    expect(page.get_by_role('button',name='Sol kanalı dinle')).to_be_enabled(timeout=20000)
    for ear in ('sol','sağ'):
        check=page.get_by_label('Yalnız '+ear+' kulağımda duydum.');expect(check).to_be_disabled()
        page.get_by_role('button',name=ear.capitalize()+' kanalı dinle').click();expect(check).to_be_enabled(timeout=10000);check.check()
    page.get_by_role('button',name='Gürültüde Türkçe sayılar',exact=True).click();answer=page.get_by_role('textbox',name='Üç sayı yanıtı')
    value=SEED;expected=[]
    def random():
        global value
        value=(1664525*value+1013904223)&0xffffffff
        return value/4294967296
    for index in range(24):
        digits=[int(random()*10) for _ in range(3)];random() # Actual noise-offset draw.
        reply=digits if index%2==0 else [(digit+1)%10 for digit in digits]
        expected.append({'digits':digits,'answer':reply})
        expect(answer).to_be_enabled(timeout=30000);assert page.locator('[data-din-progress]').inner_text()==f'{index}/24';answer.fill(''.join(map(str,reply)));page.get_by_role('button',name='Yanıtı Gönder',exact=True).evaluate('(b)=>{b.click();b.click();}')
    expect(page.locator('[data-hearing-result]')).to_be_visible(timeout=10000)
    page.wait_for_function('JSON.parse(localStorage.getItem("attune_hearing_history_v1")||"[]").length===1')
    result=page.evaluate('JSON.parse(localStorage.getItem("attune_hearing_latest_v1"))')
    assert result['seed']==SEED and result['validTrials']==24 and result['quality']=='valid' and result['value']==-1
    assert result['digitAccuracy']==.5 and result['tripletAccuracy']==.5 and result['repeated']==0
    assert all(row['digits']==reference['digits'] and row['answer']==reference['answer'] for row,reference in zip(result['history'],expected,strict=True))
    assert len(result['reversals'])==23 and result['auditoryAcceptance']=='pending' and result['calibrationProfile'] is None
    signals=page.evaluate('window.playedPCM');assert len(signals)==26 and all(row['ended'] for row in signals)
    countdown=page.evaluate('window.counts');assert [r['value'] for r in countdown]==[5,4,3,2,1],countdown
    assert all(900<=b['at']-a['at']<=1250 for a,b in zip(countdown,countdown[1:]))
    assert signals[2]['at']>=countdown[-1]['at']+900
    page.screenshot(path=str(OUT/'scorecards.png'),full_page=True)
    assert page.get_by_role('link',name='Hizmet seçenekleri').get_attribute('href').startswith('/care?from=hearing')
    assert signals[0]['channels'][1]['rms']==0 and signals[1]['channels'][0]['rms']==0
    for row in signals[2:]:
        assert row['sampleRate']==48000 and row['channels'][0]==row['channels'][1]
        assert 0<row['channels'][0]['peak']<=.080001 and row['channels'][0]['first']==row['channels'][0]['last']==0
    page.evaluate('navigator.mediaDevices.dispatchEvent(new Event("devicechange"))');expect(page.locator('[data-hearing-result]')).to_be_visible()
    page.screenshot(path=str(OUT/'converged-result.png'),full_page=True)
    events=page.evaluate('window.guidanceEvents');ended=next(e for e in events if e['id']=='hearing-digits' and e['event']=='ended');assert signals[2]['at']>=ended['at']
    between=[e for e in events if e['event']=='playing' and signals[2]['at']<=e['at']<=signals[-1]['at']];assert not between,between
    assert not errors,errors
    assert countdown[0]['at']>=ended['at']
    page.get_by_role('button',name='Bu cihazdaki duyulabilirlik hakkında bilgi').click();assert 'dB SNR' in page.get_by_role('dialog').inner_text();page.screenshot(path=str(OUT/'session-snr-info.png'),full_page=True);page.keyboard.press('Escape')
    page.get_by_role('button',name='Yeni Test',exact=True).click();expect(page.get_by_role('button',name='Ses hazırlığını başlat')).to_be_visible();assert len(page.evaluate('JSON.parse(localStorage.getItem("attune_hearing_history_v1"))'))==1
    proof=dict(status='PASS',buildId=Path('apps/vehicle-app/.next/BUILD_ID').read_text().strip(),productionUI=True,
        controlledRandomSeed=SEED,simulatedAlternatingCorrectIncorrectReplies=True,staircaseOverride=False,audioOverride=False,
        humanHearingAcceptance=False,clinicalValidation=False,actualPCM=signals,countdown=countdown,automaticSave=True,doubleSubmitRejected=True,guidanceEvents=events,noScoredTTSOverlap=True,result=result,pageErrors=errors)
    (OUT/'proof.json').write_text(json.dumps(proof,indent=2),'utf8');context.close();browser.close()
print('PASS real 24-trial DIN UI convergence with explicit engineering replies; no human or clinical acceptance')

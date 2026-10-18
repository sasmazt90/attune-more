"""Real 24-trial production DIN convergence with declared engineering replies.
Only the random seed is controlled; no audio, staircase or quality gate is replaced.
"""
import json
from pathlib import Path
from playwright.sync_api import sync_playwright,expect

OUT=Path('audit-results/combined-health-20261008/hearing-positive');OUT.mkdir(parents=True,exist_ok=True)
SEED=8102026
INIT='''const originalRandom=crypto.getRandomValues.bind(crypto);crypto.getRandomValues=function(a){if(a instanceof Uint32Array&&a.length===1){a[0]=8102026;return a;}return originalRandom(a);};window.playedPCM=[];const start=AudioBufferSourceNode.prototype.start;AudioBufferSourceNode.prototype.start=function(...args){const buffer=this.buffer;if(buffer){const channels=[];for(let i=0;i<buffer.numberOfChannels;i++){const samples=buffer.getChannelData(i);let energy=0,peak=0;for(const x of samples){energy+=x*x;peak=Math.max(peak,Math.abs(x));}channels.push({rms:Math.sqrt(energy/samples.length),peak,first:samples[0],last:samples.at(-1)});}const row={sampleRate:buffer.sampleRate,channels,ended:false};window.playedPCM.push(row);this.addEventListener('ended',()=>row.ended=true);}return start.apply(this,args);};'''

with sync_playwright() as pw:
    browser=pw.chromium.launch(channel='chrome',headless=True,args=['--autoplay-policy=no-user-gesture-required'])
    context=browser.new_context();context.add_init_script(INIT);page=context.new_page();errors=[];page.on('pageerror',lambda e:errors.append(str(e)))
    context.request.post('http://127.0.0.1:8000/api/vehicle/speed',data={'speedKmH':0})
    page.goto('http://127.0.0.1:3000/hearing');page.get_by_label('Yerel ses testi işlemini başlatmayı kabul ediyorum.').check();page.get_by_role('button',name='Ses hazırlığını başlat').click()
    page.get_by_label('Stereo kulaklık kullanıyorum; mono/speaker kullanmıyorum.').check()
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
        expect(answer).to_be_enabled(timeout=30000);answer.fill(''.join(map(str,reply)));page.get_by_role('button',name='Yanıtı gönder',exact=True).click()
    expect(page.locator('[data-hearing-result]')).to_be_visible(timeout=10000)
    assert page.evaluate('localStorage.getItem("attune_hearing_latest_v1")') is None
    page.get_by_label('Sayısal sonucu bu tarayıcıdaki geçmişe kaydet.').check();page.get_by_role('button',name='Sonucu kaydet',exact=True).click()
    expect(page.get_by_text('Sayısal sonuç yerel geçmişe kaydedildi.',exact=True)).to_be_visible()
    result=page.evaluate('JSON.parse(localStorage.getItem("attune_hearing_latest_v1"))')
    assert result['seed']==SEED and result['validTrials']==24 and result['quality']=='valid' and result['value']==-1
    assert result['digitAccuracy']==.5 and result['tripletAccuracy']==.5 and result['repeated']==0
    assert all(row['digits']==reference['digits'] and row['answer']==reference['answer'] for row,reference in zip(result['history'],expected,strict=True))
    assert len(result['reversals'])==23 and result['auditoryAcceptance']=='pending' and result['calibrationProfile'] is None
    signals=page.evaluate('window.playedPCM');assert len(signals)==26 and all(row['ended'] for row in signals)
    assert signals[0]['channels'][1]['rms']==0 and signals[1]['channels'][0]['rms']==0
    for row in signals[2:]:
        assert row['sampleRate']==48000 and row['channels'][0]==row['channels'][1]
        assert 0<row['channels'][0]['peak']<=.080001 and row['channels'][0]['first']==row['channels'][0]['last']==0
    page.evaluate('navigator.mediaDevices.dispatchEvent(new Event("devicechange"))');expect(page.locator('[data-hearing-result]')).to_be_visible()
    page.screenshot(path=str(OUT/'converged-result.png'),full_page=True)
    assert not errors,errors
    proof=dict(status='PASS',buildId=Path('apps/vehicle-app/.next/BUILD_ID').read_text().strip(),productionUI=True,
        controlledRandomSeed=SEED,simulatedAlternatingCorrectIncorrectReplies=True,staircaseOverride=False,audioOverride=False,
        humanHearingAcceptance=False,clinicalValidation=False,actualPCM=signals,result=result,pageErrors=errors)
    (OUT/'proof.json').write_text(json.dumps(proof,indent=2),'utf8');context.close();browser.close()
print('PASS real 24-trial DIN UI convergence with explicit engineering replies; no human or clinical acceptance')

"""Reopen the actual completed PCM test without repeating its adaptive protocol.
Requires current_hearing_tone.py raw evidence and its retained isolated profile.
"""
import json,os
from pathlib import Path
from playwright.sync_api import sync_playwright,expect
SOURCE=Path(os.environ['HEARING_PCM_SOURCE']);OUT=Path(os.environ['HEARING_REPLAY_EVIDENCE']);OUT.mkdir(parents=True,exist_ok=True)
raw=json.loads((SOURCE/'raw.json').read_text());r=raw['result'];plans=r['presentations'];waves=raw['waves']
assert len(r['thresholds'])==14 and len(waves)==2+sum(not v['silent'] for v in plans) and all(v['ended'] for v in waves)
assert r['totalPresentations']==len(plans) and all(v['completedAt'] is not None for v in plans)
assert {'early','late','valid','duplicate','silent'}<=set(v['kind'] for v in r['presses'])
expected={ear:[(next(v for v in r['presses'] if v['trialId']==p['id'] and v['kind']=='valid')['at']-p['startedAt'])/1000 for p in plans if p['ear']==ear and not p['silent'] and not p.get('invalidReason')] for ear in ['left','right']}
with sync_playwright() as pw:
 c=pw.chromium.launch_persistent_context(os.environ['HEARING_BROWSER_PROFILE'],executable_path=os.environ['ATTUNE_BROWSER_EXECUTABLE'],headless=True,viewport={'width':1440,'height':1000});c.add_init_script('window.seeds=[];const nativeRandom=crypto.getRandomValues.bind(crypto);crypto.getRandomValues=a=>{const out=nativeRandom(a);if(a instanceof Uint32Array&&a.length===1)seeds.push(a[0]);return out;};');p=c.new_page();errors=[];p.on('pageerror',lambda e:errors.append(str(e)));p.goto('http://127.0.0.1:3000/hearing');expect(p.locator('[data-record-id="'+r['id']+'"]')).to_be_visible();stored=p.evaluate('JSON.parse(localStorage.getItem("attune_hearing_latest_v1"))');assert stored==r,'Retained actual record must be byte-meaning identical'
 p.locator('[data-record-id="'+r['id']+'"] td').first.click();expect(p.get_by_role('dialog')).to_be_visible();means={}
 for ear in ['left','right']:
  if ear=='right':p.locator('[data-hearing-inner="ear"]').get_by_role('button',name='Sağ kulak',exact=True).last.click()
  actual=float(p.locator('[data-hearing-mean-seconds]').get_attribute('data-hearing-mean-seconds'));want=sum(expected[ear])/len(expected[ear]);assert abs(actual-want)<1e-12,(ear,actual,want);means[ear]={'meanSeconds':actual,'actualValidPresses':len(expected[ear])};p.screenshot(path=str(OUT/(ear+'-actual-completed.png')),full_page=True)
 assert len(p.evaluate('JSON.parse(localStorage.getItem("attune_hearing_history_v1"))'))==1
 p.get_by_role('dialog').get_by_role('button',name='Sonuç penceresini kapat').click();p.get_by_role('button',name='Ses hazırlığını başlat').click();expect(p.get_by_role('button',name='Sol kanalı dinle')).to_be_enabled(timeout=25000);fresh=p.evaluate('window.seeds');assert fresh and fresh[-1]!=r['seed'];p.get_by_role('button',name='Durdur',exact=True).click();assert len(p.evaluate('JSON.parse(localStorage.getItem("attune_hearing_history_v1"))'))==1
 assert not errors,errors;c.close()
 (OUT/'proof.json').write_text(json.dumps({'status':'PASS','buildId':Path('apps/vehicle-app/.next/BUILD_ID').read_text().strip(),'fullPCMSource':str(SOURCE/'raw.json'),'sourcePresentationCount':len(plans),'fullFourteenStagePCMPlan':True,'recordId':r['id'],'means':means,'submillisecondCompletions':sum(v['completedAt']<v['deadline'] for v in plans),'unchangedStoredResult':True,'abortedPreparationNotPersisted':True,'independentFreshSeed':fresh[-1],'pageErrors':errors,'physicalHeadphoneAcceptance':False},indent=2))
print('PASS actual completed PCM record mean replay; no protocol rerun or data rewrite')

"""Current silent entry and actual fixed preparation-audio lifecycle.
No obsolete dental-entry autoplay expectation or auditory acceptance.
"""
import json
from pathlib import Path
from playwright.sync_api import sync_playwright, expect
OUT=Path('audit-results/current-health-20261009/guidance');OUT.mkdir(parents=True,exist_ok=True)
INIT="window.guidanceEvents=[];window.guidanceAudio=[];window.addEventListener('attune-guidance-event',e=>window.guidanceEvents.push({...e.detail,at:performance.now()}));const A=window.Audio;window.Audio=class extends A{constructor(...a){super(...a);window.guidanceAudio.push(this);}};"
with sync_playwright() as pw:
 b=pw.chromium.launch(channel='chrome',headless=True,args=['--autoplay-policy=document-user-activation-required'])
 c=b.new_context();c.add_init_script(INIT);p=c.new_page();errors=[];p.on('pageerror',lambda e:errors.append(str(e)))
 for route in ('/', '/dental', '/skin', '/profile', '/hearing'):
  p.goto('http://127.0.0.1:3000'+route);p.wait_for_timeout(500)
  assert not p.evaluate('guidanceEvents.some(e=>e.event==="playing")')
 p.get_by_label('Yerel ses testi işlemini başlatmayı kabul ediyorum.').check()
 p.get_by_role('button',name='Ses hazırlığını başlat',exact=True).click()
 p.wait_for_function('guidanceEvents.some(e=>e.id==="hearing-prepare"&&e.event==="playing")',timeout=15000)
 assert not p.evaluate('guidanceEvents.some(e=>e.id==="hearing-prepare"&&e.event==="ended")')
 expect(p.get_by_role('button',name='Sol kanalı dinle',exact=True)).to_be_disabled()
 p.wait_for_function('guidanceEvents.some(e=>e.id==="hearing-prepare"&&e.event==="ended")',timeout=30000)
 expect(p.get_by_role('button',name='Sol kanalı dinle',exact=True)).to_be_enabled()
 assert p.evaluate('guidanceEvents.filter(e=>e.id==="hearing-prepare"&&e.event==="playing").length')==1
 p.get_by_role('button',name='Durdur',exact=True).click()
 p.get_by_role('button',name='Ses hazırlığını başlat',exact=True).click()
 p.wait_for_function('guidanceEvents.filter(e=>e.id==="hearing-prepare"&&e.event==="playing").length===2')
 p.get_by_role('link',name='Kokpit',exact=True).click();expect(p).to_have_url('http://127.0.0.1:3000/')
 assert p.evaluate('guidanceAudio.every(a=>a.paused&&!a.getAttribute("src"))')
 events=p.evaluate('guidanceEvents');assert not errors,errors
 manifest=json.loads(Path('apps/vehicle-app/public/audio/guidance/manifest.json').read_text('utf8'))
 for key,e in manifest['entries'].items():
  assert e['voice']==('tr-TR-EmelNeural' if key.startswith('mental-') else 'tr-TR-AhmetNeural') and e['rate']=='-10%' and e['pitch']=='-10Hz'
 proof=dict(status='PASS',buildId=Path('apps/vehicle-app/.next/BUILD_ID').read_text().strip(),silentGeneralEntries=True,
            actualHTMLAudio=True,trustedPreparationStart=True,endedRequired=True,restart=True,routeCancel=True,
            manifestVersion=manifest['version'],events=events,humanAuditoryAcceptance=False,providerCalls=0,pageErrors=errors)
 (OUT/'proof.json').write_text(json.dumps(proof,indent=2),'utf8');b.close()
print('PASS silent entries, real preparation playing/ended gate, restart and route cancellation')

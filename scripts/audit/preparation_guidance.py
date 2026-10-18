"""Approved preparation-only fixed-cache HTML audio and cancellation.
Photographic camera fixture, actual guidance audio. No physical/auditory claim.
"""
import json
from pathlib import Path
from playwright.sync_api import sync_playwright,expect
ROOT=Path(__file__).resolve().parents[2];OUT=ROOT/'audit-results/all-health-20261010/preparation-guidance';OUT.mkdir(parents=True,exist_ok=True)
INIT="window.guidanceEvents=[];window.guidanceAudio=[];window.addEventListener('attune-guidance-event',e=>window.guidanceEvents.push({...e.detail,at:performance.now()}));const A=window.Audio;window.Audio=class extends A{constructor(...a){super(...a);window.guidanceAudio.push(this);}};"
fixture=ROOT/'audit-results/followup-closure-20261010/dental-four-poses.y4m'
with sync_playwright() as pw:
 b=pw.chromium.launch(channel='chrome',headless=True,args=['--autoplay-policy=document-user-activation-required','--use-fake-device-for-media-stream','--use-file-for-fake-video-capture='+str(fixture),'--enable-unsafe-swiftshader']);c=b.new_context(permissions=['camera']);c.add_init_script(INIT);p=c.new_page();errors=[];p.on('pageerror',lambda e:errors.append(str(e)))
 for route in ('','profile','care','privacy','dental','skin','hearing'):
  p.goto('http://127.0.0.1:3000/'+route);p.wait_for_timeout(1200);assert not p.evaluate('guidanceEvents.some(e=>e.event==="playing")'),route
 p.goto('http://127.0.0.1:3000/dental');p.get_by_label('Fotoğraflarımı yalnız bu cihazda geçici işlemeyi kabul ediyorum.').check();p.get_by_role('button',name='Diş Taramasını Başlat',exact=True).click()
 p.wait_for_function('guidanceEvents.some(e=>e.id==="dental-front"&&e.event==="playing")',timeout=20000)
 assert p.evaluate('guidanceEvents.filter(e=>e.id==="dental-front"&&e.event==="playing").length')==1
 p.wait_for_timeout(1000);assert p.evaluate('guidanceEvents.filter(e=>e.id==="dental-front"&&e.event==="playing").length')==1
 p.get_by_role('button',name='Yönerge sesini kapat',exact=True).click();assert p.evaluate('guidanceAudio.every(a=>a.paused&&!a.getAttribute("src"))')
 total=p.evaluate('guidanceEvents.filter(e=>e.event==="playing").length');p.wait_for_timeout(1200);assert p.evaluate('guidanceEvents.filter(e=>e.event==="playing").length')==total
 p.get_by_role('button',name='Yönerge sesini aç',exact=True).click();p.get_by_role('link',name='Kokpit',exact=True).click();expect(p).to_have_url('http://127.0.0.1:3000/');assert p.evaluate('guidanceAudio.every(a=>a.paused&&!a.getAttribute("src"))');p.wait_for_timeout(1200);assert p.evaluate('guidanceEvents.filter(e=>e.event==="playing").length')==total
 manifest=json.loads((ROOT/'apps/vehicle-app/public/audio/guidance/manifest.json').read_text('utf8'))
 for id,e in manifest['entries'].items():assert e['voice']==('tr-TR-EmelNeural' if id.startswith('mental-') else 'tr-TR-AhmetNeural') and e['rate']=='-10%' and e['pitch']=='-10Hz'
 assert not errors,errors;p.screenshot(path=str(OUT/'silent-cockpit.png'),full_page=True)
 (OUT/'proof.json').write_text(json.dumps(dict(status='PASS',buildId=(ROOT/'apps/vehicle-app/.next/BUILD_ID').read_text().strip(),actualHTMLAudio=True,preparationOnly=True,readyAndGeneralPagesSilent=True,rerenderDedup=True,muteCancel=True,routeCancel=True,cameraFixture=True,manifestVersion=manifest['version'],entries=len(manifest['entries']),events=p.evaluate('guidanceEvents'),humanAuditoryAcceptance=False,pageErrors=errors),indent=2),'utf8');c.close();b.close()
print('PASS preparation-only actual guidance, silent general pages, dedup/mute/route cleanup')

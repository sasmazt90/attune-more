"""Production algorithm with measured browser geometry; explicit UI fixtures.
No simulated camera/STT accepted session, no real clinical-result claim.
"""
import json,subprocess
from pathlib import Path
from playwright.sync_api import sync_playwright,expect
OUT=Path('audit-results/product-decisions-20261005/letter-render');OUT.mkdir(parents=True,exist_ok=True)
code=subprocess.check_output(['node','-e',"const fs=require('fs'),ts=require('typescript');process.stdout.write(ts.transpileModule(fs.readFileSync('apps/vehicle-app/src/utils/spokenVision.ts','utf8'),{compilerOptions:{module:ts.ModuleKind.CommonJS,target:ts.ScriptTarget.ES2022}}).outputText)"],text=True)
with sync_playwright() as pw:
 b=pw.chromium.launch(channel='chromium',headless=True);proof=[]
 for width in (390,1600):
  c=b.new_context(viewport={'width':width,'height':1000});c.add_init_script("navigator.mediaDevices.getUserMedia=()=>{throw Error('Physical capture forbidden')}");p=c.new_page();c.request.post('http://localhost:8000/api/vehicle/speed',data={'speedKmH':0});p.goto('http://localhost:3000/vision');p.add_script_tag(content='var exports={};'+code+';window.letterAlgorithm=exports')
  observations=p.evaluate("""()=>{
   const V=window.letterAlgorithm,s=new V.SpokenLetterSession(),open={state:'open',ear:.3,darkFraction:.1,contrast:20,method:'lid-geometry-and-current-pixels'},closed={...open,state:'closed',ear:.1};
   const svg=document.createElementNS('http://www.w3.org/2000/svg','svg');svg.setAttribute('viewBox','0 0 100 100');const path=document.createElementNS(svg.namespaceURI,'path');path.setAttribute('d',V.LETTER_PATHS.P);path.setAttribute('stroke','white');path.setAttribute('stroke-width','10');path.setAttribute('fill','none');svg.append(path);document.querySelector('main').append(svg);
   const observations=[];
   for(let i=0;i<4;i++){
    s.present();s.letter='P';s.orientation='right';svg.style.width=s.sizePx+'px';svg.style.height=s.sizePx+'px';const r=svg.getBoundingClientRect(),g=path.getBoundingClientRect(),measuredAt=performance.now();const geometry={viewportWidthCssPx:r.width,viewportHeightCssPx:r.height,pathWidthCssPx:g.width,pathHeightCssPx:g.height,strokeWidthCssPx:s.sizePx*.1,measuredAt,method:'dom-svg-css-pixels'};
    const conditions={observedAt:performance.now(),cameraLive:true,modelActive:true,faceCount:1,qualityValid:true,positionValid:true,relativeScaleChange:0,right:open,left:closed};
    const answer=i===3?{command:'not-visible'}:{letter:i===2?'F':'P',orientation:i===0?'left':'right'};
    if(!s.respond(answer,conditions,performance.now(),s.presentationId,geometry))throw Error('Algorithm rejected explicit fixture');observations.push({geometry,nominal:s.trials.at(-1).sizePx,score:V.scoreLetterTrial(s.trials.at(-1))});
   }
   svg.remove();const record={id:s.id,date:new Date().toISOString(),protocolVersion:V.LETTER_PROTOCOL,trials:s.ledger,deviceContext:{width:screen.width,height:screen.height,dpr:devicePixelRatio},profileVerification:'unverified',distanceMethod:'relative-face-scale-only',physicalScale:null,completed:false,controlledVisualFixture:true};
   localStorage.setItem('togg_health_vision_history',JSON.stringify([record]));return observations;
  }""")
  assert observations[2]['geometry']['viewportWidthCssPx']<observations[0]['geometry']['viewportWidthCssPx']
  assert all(abs(x['nominal']-x['geometry']['viewportWidthCssPx'])<.1 for x in observations)
  p.reload();panel=p.locator('[data-record-history=vision]');expect(panel.locator('[data-record-id]')).to_have_count(1);panel.get_by_role('button',name='Sonucu Aç',exact=True).click();d=p.get_by_role('dialog',name='Harf tanıma sonucu',exact=True);expect(d).to_contain_text('Yeterli yanıt yok');expect(d).to_contain_text('Birleşik');assert 'en küçük' not in d.inner_text();p.screenshot(path=str(OUT/f'algorithm-fixture-result-{width}.png'),full_page=True);p.keyboard.press('Escape')
  panel.get_by_role('button',name='kaydını sil:').click();p.screenshot(path=str(OUT/f'fixture-delete-{width}.png'),full_page=True);p.get_by_role('button',name='Hayır, vazgeç',exact=True).click();expect(panel.locator('[data-record-id]')).to_have_count(1)
  panel.get_by_role('button',name='kaydını sil:').click();p.get_by_role('button',name='Evet, sil',exact=True).click();expect(panel.locator('[data-record-id]')).to_have_count(0);expect(p.get_by_role('dialog')).to_have_count(0);p.reload();expect(panel.locator('[data-record-id]')).to_have_count(0)
  proof.append({'width':width,'observations':observations,'nativeSTT':False,'cameraAcceptance':False,'controlledAlgorithmFixture':True,'actualDOMGeometry':True,'durableDelete':True});c.close()
 b.close()
(OUT/'proof.json').write_text(json.dumps(proof,indent=2));print(json.dumps(proof))

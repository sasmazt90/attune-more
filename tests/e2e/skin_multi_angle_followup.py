"""Actual three-pose video frames, production MediaPipe and persisted metric references."""
import json
from pathlib import Path
from playwright.sync_api import sync_playwright, expect

OUT=Path('audit-results/skin-multi-angle');OUT.mkdir(parents=True,exist_ok=True)
with sync_playwright() as pw:
    browser=pw.chromium.launch(channel="chromium",headless=True,args=['--use-fake-device-for-media-stream','--use-file-for-fake-video-capture='+str(Path('audit-fixtures/three-angle.y4m').resolve()),'--use-gl=angle','--use-angle=swiftshader','--enable-unsafe-swiftshader'])
    context=browser.new_context(permissions=['camera'],viewport={'width':1600,'height':1000})
    context.add_init_script("window.cameraStreams=[];const original=navigator.mediaDevices.getUserMedia.bind(navigator.mediaDevices);navigator.mediaDevices.getUserMedia=async(...args)=>{const stream=await original(...args);window.cameraStreams.push(stream);return stream;};")
    context.request.post('http://localhost:8000/api/vehicle/speed',data={'speedKmH':0})
    page=context.new_page();errors=[];page.on('pageerror',lambda e:errors.append(str(e)))
    captures=[]
    page.goto('http://localhost:3000/skin');page.screenshot(path=str(OUT/'start.png'),full_page=True)
    for repetition in range(2):
        page.goto('http://localhost:3000/skin')
        page.get_by_role('button',name='Cilt taraması hakkında bilgi',exact=True).click();expect(page.get_by_role('checkbox',name='Üç açılı tarama',exact=True)).to_be_checked();page.keyboard.press('Escape')
        page.get_by_role('button',name='Analizi Başlat',exact=True).click()
        page.screenshot(path=str(OUT/f'prepare-{repetition}.png'),full_page=True)
        page.wait_for_function('document.querySelector("canvas")?.dataset.completedAngles==="FRONT"',timeout=65000)
        assert page.evaluate('localStorage.getItem("togg_health_latest_skin")') is None if repetition==0 else True
        page.screenshot(path=str(OUT/f'right-stage-{repetition}.png'),full_page=True)
        expect(page.get_by_text('Cilt Analizi Tamamlandı',exact=True)).to_be_visible(timeout=125000)
        result=page.evaluate('JSON.parse(localStorage.getItem("togg_health_latest_skin"))')
        reference=page.evaluate('JSON.parse(localStorage.getItem("togg_health_skin_multi_baseline_v2"))')
        assert result['comparisonScope']=='three-angle-v2' and result['usedMediaPipe'] is True
        page.get_by_role('button',name='Referans ve görüntü hakkında bilgi',exact=True).click()
        scope=page.locator('[data-skin-comparison-scope]');expect(scope).to_have_attribute('data-skin-comparison-scope','three-angle-v2');expect(scope).to_contain_text('Kapsam: ön, anatomik sağ ve anatomik sol açı');assert 'tek karşı açı' not in scope.inner_text();page.keyboard.press('Escape')
        assert len(result['regions'])==6 and result['isBaseline'] == (repetition==0)
        assert set(reference['captures'])=={'FRONT','RIGHT','LEFT'}
        assert len({c['frameToken'] for c in reference['captures'].values()})==3
        assert set(reference['captures']['RIGHT']['regions'])=={'leftCheek'}
        assert set(reference['captures']['LEFT']['regions'])=={'rightCheek'}
        if repetition:
            assert result['baselineId']==captures[0]['reference']['id'] and result['comparisonUnavailable'] is False
            assert all(r['changeFromBaselinePct']==0 for r in result['regions'].values())
        else:
            assert all('changeFromBaselinePct' not in r for r in result['regions'].values())
            assert page.evaluate('localStorage.getItem("togg_health_skin_baseline")') is None
        assert page.evaluate('window.cameraStreams.every(s=>s.getTracks().every(t=>t.readyState==="ended"))')
        assert page.locator('[data-skin-snapshot]').count()==1 and page.locator('[data-skin-photo-empty]').count()==0
        assert page.locator('[data-skin-roi="rightCheek"]').count()==1 and page.locator('[data-skin-roi="leftCheek"]').count()==0
        assert 'data:image' not in page.evaluate('JSON.stringify(Object.fromEntries(Object.entries(localStorage)))')
        meshes=[]
        for _ in range(6):
            svg=page.locator('[data-skin-snapshot]');mesh=page.locator('[data-skin-mesh]')
            assert mesh.count()==1,'Only the selected regional graph may render'
            region=mesh.get_attribute('data-skin-mesh');assert region not in meshes;meshes.append(region)
            assert mesh.locator('path[data-mesh-edge]').count()>=20
            assert svg.locator('clipPath').count()==0,'Numerical ROI boxes must not clip the visual graph'
            assert page.locator('[data-face-panel] button').count()==0,'Navigation must be outside the photo'
            assert page.locator('[data-skin-navigation]').bounding_box()['y']>=page.locator('[data-face-panel]').bounding_box()['y']+page.locator('[data-face-panel]').bounding_box()['height']-1
            assert 'Doku Değişimi' not in page.locator('main').inner_text()
            page.screenshot(path=str(OUT/f'{region}-{repetition}.png'),full_page=True)
            page.get_by_role('button',name='Sonraki Bölge',exact=True).click()
        assert len(meshes)==6
        captures.append({'result':result,'reference':reference})
        page.screenshot(path=str(OUT/f'completed-{repetition}.png'),full_page=True)
    assert not errors,errors
    previous=page.evaluate('({reference:localStorage.getItem("togg_health_skin_multi_baseline_v2"),latest:localStorage.getItem("togg_health_latest_skin"),history:localStorage.getItem("togg_health_skin_history")})')
    page.goto('http://localhost:3000/skin');page.get_by_role('button',name='Analizi Başlat',exact=True).click()
    page.wait_for_function('document.querySelector("canvas")?.dataset.completedAngles==="FRONT"',timeout=65000)
    page.get_by_role('button',name='Taramayı İptal Et',exact=True).click()
    page.wait_for_function('window.cameraStreams.every(s=>s.getTracks().every(t=>t.readyState==="ended"))')
    assert page.evaluate('({reference:localStorage.getItem("togg_health_skin_multi_baseline_v2"),latest:localStorage.getItem("togg_health_latest_skin"),history:localStorage.getItem("togg_health_skin_history")})')==previous
    page.evaluate('localStorage.setItem("togg_health_skin_multi_baseline_v2","invalid-reference-json")')
    page.get_by_role('button',name='Analizi Başlat',exact=True).click()
    expect(page.get_by_text('Üç açılı ölçüm veya referans kaydı doğrulanamadı.',exact=False)).to_be_visible(timeout=125000)
    assert page.evaluate('localStorage.getItem("togg_health_skin_multi_baseline_v2")')=='invalid-reference-json'
    assert page.evaluate('localStorage.getItem("togg_health_latest_skin")')==previous['latest']
    assert page.evaluate('localStorage.getItem("togg_health_skin_history")')==previous['history']
    assert not errors,errors
    context.close();browser.close()
(OUT/'results.json').write_text(json.dumps({'status':'PASS','captures':captures,'poseMock':False,'reusedFrameForAngles':False,'clinicalClaim':False,'cancellationPreservedRecords':True,'invalidReferencePreservedRecords':True},ensure_ascii=False,indent=2),encoding='utf-8')
print('PASS: three actual distinct MediaPipe poses, exposed regions, compatible v2 reference comparison')

"""Actual MediaPipe/UI baseline, anatomy, reminder and repeat comparison."""
import json,re
from datetime import datetime,timedelta
from pathlib import Path
from playwright.sync_api import sync_playwright, expect

OUT=Path('audit-results/live-followup'); OUT.mkdir(parents=True,exist_ok=True)
with sync_playwright() as pw:
    browser=pw.chromium.launch(channel='chromium',headless=True,args=[
      '--use-fake-device-for-media-stream','--use-file-for-fake-video-capture='+str(Path('audit-fixtures/valid-face.y4m').resolve()),
      '--use-gl=angle','--use-angle=swiftshader','--enable-unsafe-swiftshader'])
    context=browser.new_context(permissions=['camera'],accept_downloads=True)
    context.add_init_script("window.actualStreams=[];const original=navigator.mediaDevices.getUserMedia.bind(navigator.mediaDevices);navigator.mediaDevices.getUserMedia=async(...args)=>{const stream=await original(...args);window.actualStreams.push(stream);return stream;};")
    assert context.request.post('http://localhost:8000/api/vehicle/speed',data={'speedKmH':0}).ok
    page=context.new_page();errors=[];page.on('pageerror',lambda error:errors.append(str(error)))
    page.goto('http://localhost:3000/skin')
    page.get_by_role('button',name='Cilt taraması hakkında bilgi',exact=True).click()
    expect(page.get_by_role('dialog',name='Cilt taraması',exact=True)).to_be_visible()
    page.get_by_role('checkbox',name='Üç açılı tarama',exact=True).uncheck()
    page.get_by_role('button',name='Bilgi penceresini kapat',exact=True).click()
    expect(page.get_by_role('dialog')).to_have_count(0)
    page.get_by_role('button',name='Analizi Başlat',exact=True).click()
    page.wait_for_function('''()=>{const video=document.querySelector('video');return video && video.videoWidth>0 && video.videoHeight>0;}''')
    geometry=page.locator('video').evaluate('''video=>{
      const box=video.getBoundingClientRect();const panel=video.closest('[data-face-panel]').getBoundingClientRect();
      return {source:video.videoWidth/video.videoHeight,display:box.width/box.height,panel:panel.width/panel.height};
    }''')
    assert abs(geometry['source']-geometry['display'])<.02,geometry
    expect(page.get_by_text('Cilt Analizi Tamamlandı',exact=True)).to_be_visible(timeout=45000)
    first=page.evaluate('JSON.parse(localStorage.getItem("togg_health_latest_skin"))')
    assert first['isBaseline'] is True and first['usedMediaPipe'] is True
    page.get_by_role('button',name='Referans ve görüntü hakkında bilgi',exact=True).click()
    scope=page.locator('[data-skin-comparison-scope]');expect(scope).to_have_attribute('data-skin-comparison-scope','single-front-v1');expect(scope).to_contain_text('Kapsam: tek karşı açı');page.keyboard.press('Escape')
    assert first['quality']['blurScore']>=4 and 40<=first['quality']['avgLuminance']<=220
    expect(page.get_by_text('Referans oluşturuldu; sonraki uygun taramalar bununla karşılaştırılacak.',exact=True)).to_be_visible()
    assert page.locator('video').count()==0
    page.wait_for_function('window.actualStreams.length>0 && window.actualStreams.every(s=>s.getTracks().every(t=>t.readyState==="ended"))')
    assert '%0' not in page.locator('body').inner_text()
    for _ in range(6):
        graphic=page.locator('[data-skin-snapshot]')
        label=graphic.get_attribute('aria-label')
        assert graphic.locator('[data-skin-roi]').count()==1  # compatibility attribute on the selected graph, no ROI clip
        selected_mesh=graphic.locator('[data-skin-mesh]')
        assert selected_mesh.count()==1
        assert selected_mesh.locator('[data-mesh-edge]').count()>=15
        assert graphic.locator('clipPath').count()==0
        page.get_by_role('button',name='Gözlem Notu',exact=True).click()
        selected=label.replace(' kabul edilmiş tarama görüntüsü','')
        note=page.get_by_text(selected+' — İlk tarama',exact=True)
        expect(note).to_be_visible()
        page.keyboard.press('Escape')
        page.get_by_role('button',name='Sonraki Bölge',exact=True).click()
    visual=OUT/'uat-skin';visual.mkdir(exist_ok=True)
    for width,height in [(1280,900),(390,844),(820,900)]:
        page.set_viewport_size({'width':width,'height':height});page.evaluate('scrollTo(0,0)')
        assert page.evaluate('document.documentElement.scrollWidth<=innerWidth')
        page.screenshot(path=str(visual/f'actual-first-reference-{width}.png'),full_page=True)
    page.set_viewport_size({'width':1280,'height':900})
    for region_index in range(6):
        graphic=page.locator('[data-skin-snapshot]');selected=graphic.get_attribute('aria-label').replace(' kabul edilmiş tarama görüntüsü','')
        page.evaluate('scrollTo(0,0)');page.screenshot(path=str(visual/f'actual-region-{region_index}.png'),full_page=True)
        page.get_by_role('button',name='Gözlem Notu',exact=True).click();expect(page.get_by_text(selected+' — İlk tarama',exact=True)).to_be_visible()
        page.screenshot(path=str(visual/f'actual-region-note-{region_index}.png'));page.keyboard.press('Escape');page.get_by_role('button',name='Sonraki Bölge',exact=True).click()
    page.screenshot(path=str(OUT/'skin-baseline-snapshot.png'))
    page.get_by_role('button',name='Önerilen Aksiyonlar',exact=True).click()
    page.get_by_role('button',name='Hatırlat',exact=True).click()
    date_input=page.get_by_role('textbox',name='Hatırlatma tarihi ve saati')
    date_input=page.locator('input[type=datetime-local]')
    expect(date_input).to_have_value(re.compile(r'\d{4}-\d{2}-\d{2}T\d{2}:\d{2}'))
    default_date=datetime.fromisoformat(date_input.input_value());today=page.evaluate('new Date().toLocaleDateString("sv-SE")')
    assert (default_date.date()-datetime.fromisoformat(today).date()).days==28
    page.set_viewport_size({'width':390,'height':500});page.screenshot(path=str(visual/'actual-reminder-expanded-short.png'))
    date_input.fill('2000-01-01T10:00');page.get_by_role('button',name='Hatırlatmayı kaydet',exact=True).click();expect(page.get_by_role('status')).to_contain_text('Plan kaydedilemedi')
    assert page.evaluate('localStorage.getItem("togg_health_skin_reminder")') is None
    date_input.fill(default_date.isoformat(timespec='minutes'))
    page.get_by_role('button',name='Hatırlatmayı kaydet',exact=True).click()
    expect(page.get_by_text('Uygulama içi plan kaydedildi. İşletim sistemi bildirimi kurulmadı.',exact=True)).to_be_visible()
    page.screenshot(path=str(OUT/'reminder-plan.png'),full_page=True)
    reminder=page.evaluate('JSON.parse(localStorage.getItem("togg_health_skin_reminder"))')
    page.get_by_role('button',name='Hatırlatmayı kaydet',exact=True).click()
    assert page.evaluate('JSON.parse(localStorage.getItem("togg_health_skin_reminder")).id')==reminder['id']
    updated_date=default_date+timedelta(days=2,hours=1);date_input.fill(updated_date.isoformat(timespec='minutes'));page.get_by_role('button',name='Hatırlatmayı kaydet',exact=True).click()
    updated=page.evaluate('JSON.parse(localStorage.getItem("togg_health_skin_reminder"))');assert updated['id']==reminder['id'] and updated['dueAt']!=reminder['dueAt']
    reminder=updated
    close_box=page.get_by_role('button',name='Pencereyi kapat',exact=True).bounding_box();assert 15<=close_box['y'] and close_box['y']+close_box['height']<=485
    page.screenshot(path=str(visual/'actual-reminder-edited-short.png'))
    with page.expect_download() as pending: page.get_by_role('button',name='Takvim dosyasını indir (.ics)',exact=True).click()
    download=pending.value;download.save_as(str(OUT/'planlanan-takip.ics'))
    calendar=(OUT/'planlanan-takip.ics').read_text(encoding='utf-8')
    assert 'BEGIN:VEVENT' in calendar and 'BEGIN:VALARM' in calendar and 'SUMMARY:Planlanan takip' in calendar
    assert 'cilt' not in calendar.lower() and 'mental' not in calendar.lower()
    page.get_by_role('button',name='Hatırlatmayı iptal et',exact=True).click()
    assert not page.evaluate('localStorage.getItem("togg_health_skin_reminder")')
    expect(page.get_by_role('status')).to_contain_text('takvim kaydını ayrıca silin')
    page.screenshot(path=str(visual/'actual-reminder-cancelled-short.png'))
    page.keyboard.press('Escape')
    page.set_viewport_size({'width':1280,'height':900})
    page.goto('http://localhost:3000/skin')
    page.get_by_role('button',name='Cilt taraması hakkında bilgi',exact=True).click()
    expect(page.get_by_role('dialog',name='Cilt taraması',exact=True)).to_be_visible()
    page.get_by_role('checkbox',name='Üç açılı tarama',exact=True).uncheck()
    page.get_by_role('button',name='Bilgi penceresini kapat',exact=True).click()
    expect(page.get_by_role('dialog')).to_have_count(0)
    page.get_by_role('button',name='Analizi Başlat',exact=True).click()
    expect(page.get_by_text('Cilt Analizi Tamamlandı',exact=True)).to_be_visible(timeout=45000)
    second=page.evaluate('JSON.parse(localStorage.getItem("togg_health_latest_skin"))')
    assert second['id']!=first['id'] and second['isBaseline'] is False
    assert second['baselineId']==first['id'] and not second['comparisonUnavailable']
    assert len(second['regions'])==6
    assert all('changeFromBaselinePct' in r for r in second['regions'].values())
    assert not errors,errors
    page.screenshot(path=str(OUT/'skin-repeat-snapshot.png'))
    page.get_by_role('button',name='Zaman İçinde Değişim',exact=True).click();page.screenshot(path=str(visual/'actual-compatible-trend.png'));page.keyboard.press('Escape')
    (OUT/'skin.json').write_text(json.dumps({'first':first,'second':second,'calendarUid':reminder['id'],'cameraStoppedInResult':True,'allSixRegionsVisible':True,'reminderDefaultCalendarDays':28,'reminderEditDedupErrorCancel':True,'visualScreenshots':'uat-skin (actual production MediaPipe/UI scans, not injected baseline)'},ensure_ascii=False,indent=2),encoding='utf-8')
    # Migration fixture starts from the two actual UI scans above, never injected metrics.
    original_baseline=page.evaluate('localStorage.getItem("togg_health_skin_baseline")')
    page.evaluate('localStorage.removeItem("togg_health_skin_baseline_meta")')
    page.goto('http://localhost:3000/skin')
    page.get_by_role('button',name='Cilt taraması hakkında bilgi',exact=True).click()
    expect(page.get_by_role('dialog',name='Cilt taraması',exact=True)).to_be_visible()
    page.get_by_role('checkbox',name='Üç açılı tarama',exact=True).uncheck()
    page.get_by_role('button',name='Bilgi penceresini kapat',exact=True).click()
    expect(page.get_by_role('dialog')).to_have_count(0)
    page.get_by_role('button',name='Analizi Başlat',exact=True).click()
    expect(page.get_by_text('Cilt Analizi Tamamlandı',exact=True)).to_be_visible(timeout=45000)
    legacy=page.evaluate('JSON.parse(localStorage.getItem("togg_health_latest_skin"))')
    assert legacy['isBaseline'] is False and legacy['comparisonUnavailable'] is True
    assert all('changeFromBaselinePct' not in r for r in legacy['regions'].values())
    assert page.evaluate('localStorage.getItem("togg_health_skin_baseline")')==original_baseline
    expect(page.get_by_text('Karşılaştırılamadı. Referansınız korundu.',exact=True)).to_have_count(1)
    page.get_by_role('button',name='Referans ve görüntü hakkında bilgi',exact=True).click()
    expect(page.locator('[data-comparison-reason]')).to_contain_text('Eski referansın kalite veya poz bilgisi eksik')
    page.keyboard.press('Escape')
    # Controlled corrupt-storage fault: prove existing data is preserved, not overwritten.
    page.evaluate('localStorage.setItem("togg_health_skin_baseline","invalid-reference-json")')
    latest_before=page.evaluate('localStorage.getItem("togg_health_latest_skin")')
    page.goto('http://localhost:3000/skin')
    page.get_by_role('button',name='Cilt taraması hakkında bilgi',exact=True).click()
    expect(page.get_by_role('dialog',name='Cilt taraması',exact=True)).to_be_visible()
    page.get_by_role('checkbox',name='Üç açılı tarama',exact=True).uncheck()
    page.get_by_role('button',name='Bilgi penceresini kapat',exact=True).click()
    expect(page.get_by_role('dialog')).to_have_count(0)
    page.get_by_role('button',name='Analizi Başlat',exact=True).click()
    expect(page.get_by_text('Mevcut referans okunamadı. Referansınız değiştirilmedi; bu tarama kaydedilmedi.',exact=True)).to_be_visible(timeout=45000)
    assert page.evaluate('localStorage.getItem("togg_health_skin_baseline")')=='invalid-reference-json'
    assert page.evaluate('localStorage.getItem("togg_health_latest_skin")')==latest_before
    assert not errors,errors
    page.goto('http://localhost:3000/profile')
    page.get_by_role('button',name='Hekimle Paylaşılabilir Özet',exact=True).click()
    choices=page.get_by_role('checkbox')
    assert choices.evaluate_all('(items)=>items.every(i=>!i.checked)')
    page.get_by_label('Cilt',exact=True).check()
    preview=page.locator('[data-share-preview]').inner_text()
    assert 'Cilt' in preview and 'Ruhsal iyi oluş' not in preview and 'Görme' not in preview
    page.screenshot(path=str(OUT/'selected-share-preview.png'),full_page=True)
    # Observe the native print event and the actual print document; do not replace print().
    page.evaluate('''()=>{
      window.printReports=[];
      const original=Node.prototype.appendChild;
      Node.prototype.appendChild=function(node){
        const result=original.call(this,node);
        if(node instanceof HTMLIFrameElement){
          const doc=node.contentDocument, close=doc.close.bind(doc);
          // document.open removes window listeners: attach after the real document closes.
          doc.close=function(){
            const closed=close();
            node.contentWindow.addEventListener('beforeprint',()=>{
              window.printReports.push({html:doc.documentElement.outerHTML,title:doc.title,text:doc.body.innerText});
            });
            return closed;
          };
        }
        return result;
      };
    }''')
    page.get_by_role('button',name='Yazdır / PDF olarak kaydet',exact=True).click()
    page.wait_for_function('window.printReports.length===1')
    report=page.evaluate('window.printReports[0]')
    assert 'Cilt' in report['text'] and 'Ruhsal iyi oluş' not in report['html'] and 'Görme' not in report['html']
    assert 'klinik tanı' in report['text'] and 'Ahmet Yılmaz' not in report['html']
    assert 'http://localhost:8000' not in report['html']
    (OUT/'selected-print.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
    context.close();browser.close()
print('PASS: actual MediaPipe baseline/repeat; six anatomy regions; real calendar file; cancellation')

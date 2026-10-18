"""Opt-in transcript and actual stored-session UI; keyless fixture, zero device capture."""
import json
from pathlib import Path
from playwright.sync_api import sync_playwright,expect
OUT=Path('audit-results/mental-sessions');OUT.mkdir(parents=True,exist_ok=True)
with sync_playwright() as pw:
    browser=pw.chromium.launch(headless=True)
    context=browser.new_context(locale='tr-TR');context.add_init_script("window.captureAttempts=0;navigator.mediaDevices.getUserMedia=()=>{window.captureAttempts++;throw Error('No capture allowed')};")
    context.request.post('http://localhost:8000/api/vehicle/speed',data={'speedKmH':0})
    page=context.new_page();posts=[];page.on('request',lambda r:posts.append(r.url) if r.method=='POST' and '/mental/' in r.url else None)
    page.goto('http://localhost:3000/privacy');preference=page.get_by_role('checkbox',name='Tam konuşma dökümünü bu cihazda sakla',exact=True);expect(preference).not_to_be_checked()
    for enabled in [False,True]:
        if enabled:page.goto('http://localhost:3000/privacy');preference.check()
        page.goto('http://localhost:3000/mental');page.get_by_role('checkbox',name='TOGG Attune hizmet onayı',exact=True).check();page.get_by_role('button',name='İsterseniz yazabilirsiniz',exact=True).click();page.get_by_role('button',name='Sesli yanıtı kapat',exact=True).click()
        for text in ['Bugün yeni bir kitap okudum.','Bugün yeni bir film izledim.']:
            page.get_by_role('textbox',name='Görüşme mesajı').fill(text);page.get_by_role('button',name='Gönder',exact=True).click();expect(page.locator('[data-conversation-phase]')).to_have_attribute('data-conversation-phase','ready')
        page.get_by_role('button',name='Görüşmeyi Bitir',exact=True).click();expect(page.locator('[data-conversation-phase]')).to_have_attribute('data-conversation-phase','completed')
        page.get_by_role('dialog',name='Görüşme tamamlandı',exact=True).get_by_role('button',name='Tamam',exact=True).click()
        stored=page.evaluate('JSON.parse(localStorage.getItem("togg_health_mental_history"))');record=stored[-1];assert record['schemaVersion']==3 and record['startedAt']<record['completedAt']
        assert ('transcript' in record)==enabled
        if enabled:
            assert record['transcriptConsented'] and len(record['transcript'])==4
            assert [m['sender'] for m in record['transcript']]==['USER','AI','USER','AI']
            assert all(record['startedAt']<=m['timestamp']<=record['completedAt'] for m in record['transcript'])
        panel=page.locator('[data-session-rows]');assert panel.evaluate('e=>getComputedStyle(e).overflowY')=='auto'
        count=len(posts);panel.locator(f'[data-record-id="{record["id"]}"] [aria-haspopup=dialog]').click();dialog=page.get_by_role('dialog',name='Görüşme kaydı',exact=True)
        expect(dialog).to_contain_text('Başlangıç:');expect(dialog).to_contain_text('Bitiş:')
        if enabled:expect(page.locator('[data-session-author]')).to_have_count(4)
        else:expect(dialog).to_contain_text('Bu kayıtta konuşma dökümü bulunmuyor.')
        page.screenshot(path=str(OUT/f'transcript-{enabled}.png'));page.wait_for_timeout(300);assert len(posts)==count
        page.keyboard.press('Escape')
    before=len(posts);page.locator('[data-session-rows] [aria-haspopup=dialog]').first.click();page.get_by_role('button',name='Bu kaydı sil',exact=True).click();page.get_by_role('button',name='Evet, sil',exact=True).click();expect(page.locator('[data-session-rows] [data-record-id]')).to_have_count(1);page.reload();expect(page.locator('[data-session-rows] [data-record-id]')).to_have_count(1);assert len(posts)==before
    remaining=page.evaluate('JSON.parse(localStorage.getItem("togg_health_mental_history"))');assert len(remaining)==1 and 'transcript' not in remaining[0]
    other=browser.new_context();p=other.new_page();p.goto('http://localhost:3000/profile');expect(p.locator('[data-record-history=mental] [data-record-id]')).to_have_count(0);other.close()
    assert page.evaluate('window.captureAttempts')==0
    proof={'status':'PASS','transcriptDefaultOff':True,'explicitOptInFourOrderedTimestampedMessages':True,'dialogNoProviderRequests':True,'storedTranscriptDeletedDurably':True,'otherUserIsolated':True,'physicalCapture':0,'liveAcceptance':False}
    (OUT/'proof.json').write_text(json.dumps(proof,indent=2),encoding='utf-8');context.close();browser.close()
print(json.dumps(proof))

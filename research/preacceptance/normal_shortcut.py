"""Actual normal shortcut launch; content-free local GETs and owned WM_CLOSE only."""
import ctypes, datetime, hashlib, json, socket, struct, subprocess, time, urllib.request
from contextlib import ExitStack
from ctypes import wintypes
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2];PRODUCT=ROOT.parent/'attune-live-test';OUT=ROOT/'research/preacceptance'
folder=list(Path('C:/Users/PC/Desktop').glob('*/Applications/7. TOGG'))[0]
shortcut=list(folder.glob('*.lnk'))[0];home=folder/'.launcher';session=home/'session.json'
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def port(p):
    with socket.socket() as s:return s.connect_ex(('127.0.0.1',p))==0
def fetch(url):
    with urllib.request.urlopen(url,timeout=3) as r:return r.read()
def state():
    try:return json.loads(session.read_text())
    except (OSError,ValueError):return {}
def wait(fn,seconds=60):
    end=time.monotonic()+seconds
    while time.monotonic()<end:
        if fn():return
        time.sleep(.25)
    raise TimeoutError('Owned launch condition not met')
def chrome_pids():
    p=subprocess.run(['powershell','-NoProfile','-Command','Get-Process chrome -ErrorAction SilentlyContinue | Select-Object -ExpandProperty Id'],stdout=subprocess.PIPE,stderr=subprocess.DEVNULL)
    return {int(x) for x in p.stdout.decode().split() if x.isdigit()}
def permissions():
    p=home/'chrome-profile/Default/Preferences'
    if not p.is_file():return None
    d=json.loads(p.read_text(encoding='utf-8'))
    profile=d.get('profile',{})
    exceptions=profile.get('content_settings',{}).get('exceptions',{})
    # Compare actual permission settings, not Chrome's site/media engagement counters.
    settings={kind:{origin:entry['setting'] for origin,entry in values.items() if isinstance(entry,dict) and 'setting' in entry}
        for kind,values in exceptions.items() if isinstance(values,dict) and kind not in ['site_engagement','media_engagement']}
    return {'defaults':profile.get('default_content_setting_values',{}),'settings':{k:v for k,v in settings.items() if v}}
def link_strings():
    b=shortcut.read_bytes();flags=struct.unpack_from('<I',b,20)[0];offset=76
    if flags&1:offset+=2+struct.unpack_from('<H',b,offset)[0]
    if flags&2:offset+=struct.unpack_from('<I',b,offset)[0]
    d={}
    for bit,name in [(2,'description'),(3,'relativePath'),(4,'workingDirectory'),(5,'arguments'),(6,'icon')]:
        if flags&(1<<bit):
            n=struct.unpack_from('<H',b,offset)[0];offset+=2;size=n*(2 if flags&128 else 1)
            d[name]=b[offset:offset+size].decode('utf-16-le' if flags&128 else 'cp1252');offset+=size
    return d
proof={'checkedAt':datetime.datetime.now(datetime.timezone.utc).isoformat(),'sourceHead':'f8f08d98cf23eb23c5a171b5b50411364d79adf6','shortcut':str(shortcut),'shortcutHashBefore':sha(shortcut),'safeLinkMetadata':link_strings(),'buildId':(PRODUCT/'apps/vehicle-app/.next/BUILD_ID').read_text().strip(),'paidProviderRequests':0,'physicalMicrophoneCapture':0,'profileDeleted':False,'normalDebuggingEnabled':False}
assert not port(3000) and not port(8000),'Existing services were not adopted or stopped'
user32=ctypes.WinDLL('user32',use_last_error=True)
callback=ctypes.WINFUNCTYPE(wintypes.BOOL,wintypes.HWND,wintypes.LPARAM)
def chrome_windows():
    pids=chrome_pids();windows=[]
    def each(hwnd,_):
        pid=wintypes.DWORD();user32.GetWindowThreadProcessId(hwnd,ctypes.byref(pid))
        if pid.value in pids and user32.IsWindowVisible(hwnd):windows.append((int(hwnd),pid.value))
        return True
    user32.EnumWindows(callback(each),0)
    return set(windows)
before=chrome_windows();permission_before=permissions();old=state();owned=None
def close_owned(pid):
    def each(hwnd,_):
        window_pid=wintypes.DWORD();user32.GetWindowThreadProcessId(hwnd,ctypes.byref(window_pid))
        if window_pid.value==pid:user32.PostMessageW(hwnd,0x0010,0,0)
        return True
    user32.EnumWindows(callback(each),0)
try:
    shell=ctypes.WinDLL('shell32',use_last_error=True);shell.ShellExecuteW.argtypes=[wintypes.HWND,wintypes.LPCWSTR,wintypes.LPCWSTR,wintypes.LPCWSTR,wintypes.LPCWSTR,ctypes.c_int];shell.ShellExecuteW.restype=ctypes.c_void_p
    result=shell.ShellExecuteW(None,'open',str(shortcut),None,None,1)
    proof['shellExecuteCode']=result
    assert result and result>32,'Normal shortcut failed to open'
    wait(lambda:state().get('status')=='running' and state().get('started_at')!=old.get('started_at'))
    owned=state();proof['ownedSession']=owned
    proof['freshProcess']=owned['launcher_pid']!=old.get('launcher_pid') and owned['backend_pid']!=old.get('backend_pid')
    proof['health']=json.loads(fetch('http://127.0.0.1:8000/api/health'))
    proof['providerStatus']=json.loads(fetch('http://127.0.0.1:8000/api/mental/provider-status'))
    page=fetch('http://localhost:3000/mental').decode()
    proof['servedConsentUI']=all(t in page for t in ['OpenAI bulut aktarımı onayı','Ses aktarımı onayı','tarayıcının konuşma tanıma'])
    proof['servedBuildManifest']=len(fetch('http://localhost:3000/_next/static/'+proof['buildId']+'/_buildManifest.js'))>0
    assert proof['freshProcess'] and proof['providerStatus']['apiKeyConfigured'] and proof['servedConsentUI'] and proof['servedBuildManifest']
    from playwright.sync_api import sync_playwright,expect
    ui={'captureAttempts':0,'generationRequests':[],'blockedUnauthorizedRequests':0,'providerStatusMocked':False,'responseMocked':False}
    with sync_playwright() as pw, ExitStack() as browser_cleanup:
        browser=pw.chromium.launch(channel='chrome',headless=False)
        browser_cleanup.callback(browser.close)
        context=browser.new_context(locale='tr-TR',permissions=[],viewport={'width':1280,'height':900})
        browser_cleanup.callback(context.close)
        context.add_init_script('''window.captureAttempts=0;const SR=window.SpeechRecognition||window.webkitSpeechRecognition;if(SR)SR.prototype.start=function(){window.captureAttempts++;throw new Error('Physical capture prohibited by read-only verification')};navigator.mediaDevices.getUserMedia=()=>{window.captureAttempts++;return Promise.reject(new Error('Physical capture prohibited by read-only verification'))};''')
        page=context.new_page();cdp=browser.new_browser_cdp_session()
        ids=cdp.send('Target.getBrowserContexts')['browserContextIds'];assert len(ids)==1, f'Expected one owned context; count={len(ids)}'
        cdp.send('Browser.setPermission',{'permission':{'name':'microphone'},'setting':'denied','origin':'http://localhost:3000','browserContextId':ids[0]})
        def admission(route):
            data=route.request.post_data_json
            if data.get('cloudConsent') is not False:
                ui['blockedUnauthorizedRequests']+=1;route.abort();return
            ui['generationRequests'].append({'path':route.request.url.split('/api/')[-1],'cloudConsent':False})
            route.continue_()
        context.route('**/api/mental/converse',admission)
        context.route('**/api/mental/analyze-session',admission)
        context.route('**/api/mental/speech',admission)
        page.goto('http://localhost:3000/mental')
        cloud=page.get_by_role('checkbox',name='OpenAI bulut aktarımı onayı',exact=True)
        speech=page.get_by_role('checkbox',name='Ses aktarımı onayı',exact=True)
        expect(cloud).not_to_be_checked();expect(speech).not_to_be_checked()
        source=page.get_by_role('combobox',name='Yanıt sesi',exact=True)
        option=source.locator('option[value="openai"]')
        expect(option).to_have_attribute('disabled','');assert option.evaluate('(el)=>el.disabled') is True
        ui['defaultCloudAndSpeechOff']=True
        cloud.check();expect(option).not_to_have_attribute('disabled','');assert option.evaluate('(el)=>el.disabled') is False
        source.select_option('openai')
        cloud.uncheck();expect(source).to_have_value('openai');expect(option).to_have_attribute('disabled','');assert option.evaluate('(el)=>el.disabled') is True
        ui['revocationRetainsLastVoiceChoiceButDisablesOption']=True
        ui['cloudTTSRequiresConsentAndConfiguredKey']=True
        page.get_by_role('button',name='Görüşmeyi Başlat',exact=True).click()
        expect(page.get_by_text('Ses aktarım izni kapalı. Yazarak devam edebilirsiniz.',exact=True)).to_be_visible()
        ui['speechOffPreventsNativeCapture']=True
        box=page.get_by_role('textbox',name='Görüşme mesajı');box.fill('Bugün yeni bir kitap okudum.');box.press('Enter')
        expect(page.locator('[data-chat-author="AI"]')).to_have_count(1)
        expect(page.get_by_text('LOCAL_DEMO — Yerel Model',exact=True)).to_be_visible()
        expect(page.locator('[data-voice-state]')).to_have_attribute('data-voice-state','failed')
        expect(page.get_by_text('Sesli yanıt başarısız. Yanıtı metin olarak okuyabilirsiniz.',exact=True)).to_be_visible()
        assert not any(r['path']=='mental/speech' for r in ui['generationRequests'])
        ui['revokedCloudTTSCannotDispatchAndActualTextRemains']=True
        page.screenshot(path=str(OUT/'ui-consent-local-only.png'),full_page=True)
        ui['configuredKeyWithCloudOffUsesActualLocalDemo']=True
        cloud.check();cloud.uncheck()
        expect(page.get_by_role('button',name='Görüşmeyi Başlat',exact=True)).to_be_visible()
        ui['cloudRevocationCancelsSession']=True
        privacy=context.new_page();privacy.goto('http://localhost:3000/privacy')
        card=privacy.get_by_role('heading',name='Kabin Mikrofonu',exact=True).locator('..').locator('..').locator('..')
        card.get_by_role('button',name='Erişimi Kapat',exact=True).click()
        assert privacy.evaluate('localStorage.getItem("attune_privacy_microphone_allowed")')=='false'
        page.reload();speech=page.get_by_role('checkbox',name='Ses aktarımı onayı',exact=True);speech.check()
        page.get_by_role('button',name='Görüşmeyi Başlat',exact=True).click()
        expect(page.get_by_text('Mikrofon kullanım izni Gizlilik ayarlarında kapalıdır. Yazarak devam edebilirsiniz.',exact=True)).to_be_visible()
        ui['appMicrophoneOffBlocksCaptureDespiteSpeechConsent']=True
        page.screenshot(path=str(OUT/'ui-microphone-off.png'),full_page=True)
        ui['captureAttempts']=page.evaluate('window.captureAttempts')
        assert ui['captureAttempts']==0 and ui['blockedUnauthorizedRequests']==0 and len(ui['generationRequests'])==1
        context.close();browser.close()
    proof['actualProductionUI']=ui
    proof['status']='PASS'
except Exception as e:
    proof['status']='UNVERIFIED';proof['errorCategory']=type(e).__name__
    # This block only contains local UI/launcher errors, never a credential-bearing HTTP response.
    message=str(e)
    if 'sk-' not in message and 'Authorization' not in message:proof['localDiagnostic']=message[:1500]
    tb=e.__traceback__
    while tb.tb_next:tb=tb.tb_next
    proof['failedCheckLine']=tb.tb_lineno
    if 'ui' in locals():proof['actualProductionUI']=ui
finally:
    if owned:
        close_owned(owned['browser_pid'])
        try:wait(lambda:state().get('status')=='stopped' and not port(3000) and not port(8000),30)
        except TimeoutError:proof['cleanup']='UNVERIFIED'
    proof['listeningPortsAfter']=[p for p in [3000,8000] if port(p)]
    proof['unrelatedChromeWindowsPreserved']=before.issubset(chrome_windows())
    proof['unrelatedChromeWindowsBefore']=len(before)
    proof['permissionSettingsPreserved']=permission_before==permissions()
    after_permissions=permissions()
    proof['changedPermissionTypes']=[k for k in set(permission_before['settings'])|set(after_permissions['settings']) if permission_before['settings'].get(k)!=after_permissions['settings'].get(k)]
    proof['shortcutHashAfter']=sha(shortcut)
    (OUT/'normal-shortcut-proof.json').write_text(json.dumps(proof,indent=2,ensure_ascii=False),encoding='utf-8')
print(json.dumps(proof,ensure_ascii=False))

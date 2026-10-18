"""Actual Chrome capture of controlled PulseAudio PCM, with no fake media flags."""
import json
import os
import pathlib
import platform
import signal
import subprocess


def play_fixture(out):
    log = open(out / 'pulse-playback.log', 'ab')
    player = subprocess.Popen(['bash', '-c',
        'while true; do paplay --device=audit_mic audit-fixtures/speech.wav || exit; sleep 1; done'],
        stdout=log, stderr=log, start_new_session=True)
    return player, log


def stop_fixture(player, log):
    if player.poll() is None:
        os.killpg(player.pid, signal.SIGTERM)
    player.wait(timeout=5)
    log.close()


def native_speech(pw, base, out, init, snapshot, require):
    require(platform.system() == 'Linux',
            'Native speech prerequisite requires controlled Linux PulseAudio; no personal microphone is used')
    fixture = pathlib.Path('audit-fixtures/speech.wav')
    require(fixture.is_file(), 'Spoken WAV prerequisite is missing')
    browser = pw.chromium.launch(channel='chrome', headless=True, args=[
        '--autoplay-policy=no-user-gesture-required', '--enable-speech-dispatcher'])
    context = browser.new_context(permissions=['microphone'], locale='tr-TR',
                                  viewport={'width': 1600, 'height': 1000})
    page = context.new_page()
    context.add_init_script(init)
    page._audit_errors=[];page._audit_console=[];page._audit_requests=[]
    page.on('pageerror', lambda e:page._audit_errors.append(str(e)))
    page.goto(base+'/mental?demo=1')
    page.get_by_role('button', name='Görüşmeyi Başlat', exact=True).wait_for()
    player = log = None
    try:
        player, log = play_fixture(out)
        amplitude = page.evaluate('''async()=>{const s=await navigator.mediaDevices.getUserMedia({audio:{echoCancellation:false,noiseSuppression:false,autoGainControl:false}});const a=new AudioContext();try{await a.resume();const an=a.createAnalyser();a.createMediaStreamSource(s).connect(an);const buf=new Float32Array(an.fftSize);let peak=0;for(let i=0;i<35;i++){an.getFloatTimeDomainData(buf);peak=Math.max(peak,...buf.map(Math.abs));await new Promise(r=>setTimeout(r,100));}return {peak,tracks:s.getTracks().map(t=>({kind:t.kind,settings:t.getSettings()}))};}finally{s.getTracks().forEach(t=>t.stop());await a.close();}}''')
        (out/'native-spoken-pcm.json').write_text(json.dumps(amplitude, indent=2))
        require(amplitude['peak']>.001, 'No non-zero spoken PCM reached native microphone')
        stop_fixture(player, log);player=log=None
        page.get_by_role('checkbox',name='TOGG Attune hizmet onayı',exact=True).check();page.get_by_role('button',name='Görüşmeyi Başlat',exact=True).click()
        page.wait_for_function('window.__audit.speech.some(e=>e.type==="audiostart" || e.type==="error")',timeout=10000)
        require(page.evaluate('window.__audit.speech.some(e=>e.type==="audiostart")'),
                'Native speech capture did not start: '+str(page.evaluate('window.__audit.speech')))
        player,log=play_fixture(out)
        page.wait_for_function('window.__audit.speech.some(e=>e.type==="result" && e.transcript) || window.__audit.speech.some(e=>e.type==="error")',timeout=18000)
        snapshot(page,'mental-speech')
        events=page.evaluate('window.__audit.speech')
        # Preserve the original transcript assertion; add proof it reached the real UI.
        require(any(e['type']=='result' and e['transcript'] for e in events),'Actual SpeechRecognition produced no transcript: '+json.dumps(events))
        require(any(e.get('transcript') and e['transcript'] in page.locator('body').inner_text()
                    for e in events if e['type']=='result'), 'Native transcript did not reach the conversation')
        return events
    finally:
        if player is not None:stop_fixture(player,log)
        context.close();browser.close()

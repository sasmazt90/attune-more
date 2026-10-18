"""Actual MSE voice playback and hearing focus exclusion, provider-free.

Only the frozen, nonpersonal digit-zero bank file is transcoded for this test.
No browser audio/STT/provider implementation is replaced.
"""
import hashlib,json,shutil,subprocess
from pathlib import Path
from playwright.sync_api import sync_playwright

ROOT=Path(__file__).resolve().parents[2]
OUT=ROOT/'audit-results/current-health-20261009/audio-focus';OUT.mkdir(parents=True,exist_ok=True)
bank=json.loads((ROOT/'apps/vehicle-app/public/audio/hearing-bank/manifest.json').read_text('utf8'))
entry=bank['digits'][0];source=ROOT/'apps/vehicle-app/public'/entry['url'].lstrip('/')
assert hashlib.sha256(source.read_bytes()).hexdigest()==entry['sha256']
destination=OUT/'fixed-digit-zero.mp3';ffmpeg=shutil.which('ffmpeg')
if not ffmpeg:
    import imageio_ffmpeg
    ffmpeg=imageio_ffmpeg.get_ffmpeg_exe() # Same existing bank-build tool.
subprocess.run([ffmpeg,'-hide_banner','-loglevel','error','-y','-i',str(source),'-codec:a','libmp3lame','-b:a','128k',str(destination)],check=True)
compiled=subprocess.check_output(['node','-e',"const fs=require('fs'),ts=require('typescript');process.stdout.write(ts.transpileModule(fs.readFileSync(process.argv[1],'utf8'),{compilerOptions:{module:ts.ModuleKind.CommonJS,target:ts.ScriptTarget.ES2022}}).outputText)",str(ROOT/'apps/vehicle-app/src/utils/streamSpeech.ts')],text=True,encoding='utf8')
with sync_playwright() as pw:
    browser=pw.chromium.launch(channel='chrome',headless=True,args=['--autoplay-policy=no-user-gesture-required'])
    page=browser.new_page();page.goto('http://127.0.0.1:3000/hearing')
    result=page.evaluate('''async ({compiled,bytes})=>{
      const helper={};new Function('exports',compiled)(helper);
      const pcm=new Uint8Array(bytes);let cancelled=false;
      // Keep the transport open until focus cancellation. Under concurrent
      // inference, native playback may legitimately start after 1.8 seconds.
      let delayed;const response=()=>new Response(new ReadableStream({start(controller){controller.enqueue(pcm);delayed=setTimeout(()=>{if(!cancelled)controller.close();},60000);},cancel(){cancelled=true;clearTimeout(delayed);}}),{headers:{'Content-Type':'audio/mpeg'}});
      localStorage.removeItem('attune_hearing_audio_focus');
      const audio=new Audio();audio.volume=.05;let played=false;
      const playing=new Promise((resolve,reject)=>{audio.addEventListener('playing',()=>{played=true;resolve();},{once:true});setTimeout(()=>reject(Error('Actual voice did not play')),5000);});
      const stream=helper.streamSpeech(audio,response(),new AbortController().signal,()=>true);
      const finished=stream.finished.then(()=>null,error=>error.name);
      await playing;localStorage.setItem('attune_hearing_audio_focus',String(Date.now()+5000));window.dispatchEvent(new Event('attune-audio-focus'));
      await new Promise(resolve=>setTimeout(resolve,80));
      const pausedByHearing=audio.paused,readingCancelled=cancelled,error=await finished;
      let rejected=null;const forbidden=new Audio();try{helper.streamSpeech(forbidden,new Response(pcm,{headers:{'Content-Type':'audio/mpeg'}}),new AbortController().signal,()=>true);}catch(e){rejected=e.message;}
      localStorage.setItem('attune_hearing_audio_focus',String(Date.now()-1));
      const allowed=new Audio();allowed.volume=.05;let playedAfterExpired=false;
      const done=new Promise((resolve,reject)=>{allowed.addEventListener('playing',()=>playedAfterExpired=true);allowed.addEventListener('ended',resolve,{once:true});allowed.addEventListener('error',()=>reject(Error('Expired lease voice error')),{once:true});setTimeout(()=>reject(Error('Expired lease playback timeout')),5000);});
      const resumed=helper.streamSpeech(allowed,new Response(pcm,{headers:{'Content-Type':'audio/mpeg'}}),new AbortController().signal,()=>true);await resumed.finished;await done;
      stream.cancel();resumed.cancel();audio.removeAttribute('src');allowed.removeAttribute('src');URL.revokeObjectURL(stream.url);URL.revokeObjectURL(resumed.url);localStorage.removeItem('attune_hearing_audio_focus');
      return {played,pausedByHearing,readingCancelled,error,rejected,playedAfterExpired};
    }''',{'compiled':compiled,'bytes':list(destination.read_bytes())})
    print(json.dumps(result),flush=True)
    assert result['played'] and result['pausedByHearing'] and result['readingCancelled']
    assert result['error']=='AbortError' and result['rejected']=='İşitme testi ses çıkışını kullanıyor.'
    assert result['playedAfterExpired']
    proof=dict(status='PASS',buildId=(ROOT/'apps/vehicle-app/.next/BUILD_ID').read_text().strip(),
      actualMSEPlayback=True,focusStopsVoice=True,focusBlocksNewVoice=True,expiredLeaseAllowsVoice=True,
      sourceFixedDigit=0,sourceSHA256=entry['sha256'],testMP3SHA256=hashlib.sha256(destination.read_bytes()).hexdigest(),
      providerCalls=0,humanAuditoryAcceptance=False,results=result)
    (OUT/'proof.json').write_text(json.dumps(proof,indent=2),'utf8');browser.close()
print('PASS actual provider-free MSE voice, hearing focus stop/block and expired lease recovery')

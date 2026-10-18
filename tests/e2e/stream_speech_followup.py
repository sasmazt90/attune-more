"""Actual Chromium MPEG MediaSource with synthetic tone; no provider or physical input."""
import json,subprocess,base64,os
from pathlib import Path
from playwright.sync_api import sync_playwright
code=subprocess.check_output(['node','-e',"const fs=require('fs'),ts=require('typescript');process.stdout.write(ts.transpileModule(fs.readFileSync('apps/vehicle-app/src/utils/streamSpeech.ts','utf8'),{compilerOptions:{target:ts.ScriptTarget.ES2022,module:ts.ModuleKind.ESNext}}).outputText)"],text=True).replace('export function streamSpeech','function streamSpeech')
audio=base64.b64encode(Path('tests/fixtures/synthetic-tone.mp3').read_bytes()).decode()
with sync_playwright() as pw:
    browser=pw.chromium.launch(channel='chrome' if os.name=='nt' else 'chromium',headless=True,args=['--autoplay-policy=no-user-gesture-required']);page=browser.new_page();page.goto('http://localhost:3000/mental')
    page.add_script_tag(content=code+';window.actualStreamSpeech=streamSpeech')
    result=page.evaluate("""async encoded=>{
        const bytes=Uint8Array.from(atob(encoded),c=>c.charCodeAt(0));
        async function run(abort,delay=180,direct=false){
            const events=[],chunks=[];let completedAt=null,index=0,valid=true,cancelled=0;
            const response=new Response(new ReadableStream({async pull(controller){if(delay)await new Promise(r=>setTimeout(r,delay));if(index<bytes.length){const next=bytes.slice(index,index+(delay?1024:bytes.length));index+=next.length;chunks.push(performance.now());controller.enqueue(next);}else{completedAt=performance.now();controller.close();}},cancel(){cancelled++;}}),{headers:{'content-type':'audio/mpeg'}});
            const audio=new Audio(),signal=new AbortController();
            for(const type of ['playing','ended','error'])audio.addEventListener(type,()=>events.push({type,at:performance.now()}));
            const output=window.actualStreamSpeech(audio,response,signal.signal,()=>valid);
            if(abort){await new Promise(r=>setTimeout(r,240));valid=false;if(direct)output.cancel();else signal.abort();audio.pause();audio.removeAttribute('src');audio.load();}
            let failure=null;try{await output.finished;}catch(e){failure=e.name;}
            if(!abort)await new Promise((resolve,reject)=>{audio.addEventListener('ended',resolve,{once:true});audio.addEventListener('error',reject,{once:true});setTimeout(()=>reject(Error('ended missing')),8000);});
            URL.revokeObjectURL(output.url);return {events,chunks,completedAt,cancelled,failure};
        }
        return {success:await run(false),fast:await run(false,0),abort:await run(true),directCancel:await run(true,180,true)};
    }""",audio)
    success=result['success'];playing=next(e for e in success['events'] if e['type']=='playing');assert playing['at']<success['completedAt'];assert any(e['type']=='ended' for e in success['events']);assert not any(e['type']=='error' for e in success['events']);assert result['abort']['failure']=='AbortError' and result['abort']['cancelled']==1
    result.update(status='PASS',browser=browser.version,syntheticTone=True,liveAcceptance=False);out=Path('audit-results/stream-speech');out.mkdir(parents=True,exist_ok=True);(out/'proof.json').write_text(json.dumps(result,indent=2),encoding='utf-8');browser.close()
assert [e['type'] for e in result['fast']['events']].count('playing')==1
assert [e['type'] for e in result['fast']['events']].count('ended')==1
assert result['fast']['failure'] is None and not any(e['type']=='error' for e in result['fast']['events'])
assert result['directCancel']['failure']=='AbortError' and result['directCancel']['cancelled']==1
assert not any(e['type']=='ended' for e in result['directCancel']['events'])
print('PASS: incremental production MPEG starts before controlled body end; fast whole body, native ended, abort and direct cancellation')

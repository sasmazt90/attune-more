"""Actual browser decode/render of project signals and fixed bank; no human claim."""
import json,subprocess
from pathlib import Path
from playwright.sync_api import sync_playwright
ROOT=Path(__file__).resolve().parents[2];OUT=ROOT/'audit-results/combined-health-20261008/audio-render';OUT.mkdir(parents=True,exist_ok=True)
def compiled(name):
 return subprocess.check_output(['node','-e',"const fs=require('fs'),ts=require('typescript');process.stdout.write(ts.transpileModule(fs.readFileSync(process.argv[1],'utf8'),{compilerOptions:{module:ts.ModuleKind.CommonJS,target:ts.ScriptTarget.ES2022}}).outputText)",str(ROOT/('apps/vehicle-app/src/utils/'+name+'.ts'))],text=True,encoding='utf8')
with sync_playwright() as pw:
 b=pw.chromium.launch(channel='chrome',headless=True,args=['--autoplay-policy=no-user-gesture-required']);p=b.new_page();p.goto('http://127.0.0.1:3000/hearing')
 result=p.evaluate(r'''async ({protocol,audio})=>{
 const H={},A={};new Function('exports',protocol)(H);new Function('exports','require',audio)(A,()=>H);
 const fftPeak=v=>{const n=16384,re=new Float64Array(n),im=new Float64Array(n);let j=0;
  for(let i=0;i<n;i++)re[i]=v[i+3000]*.5*(1-Math.cos(2*Math.PI*i/(n-1)));
  for(let i=1;i<n;i++){let bit=n>>1;for(;j&bit;bit>>=1)j^=bit;j^=bit;if(i<j){let x=re[i];re[i]=re[j];re[j]=x;}}
  for(let size=2;size<=n;size<<=1){const half=size>>1;for(let base=0;base<n;base+=size)for(let k=0;k<half;k++){const angle=-2*Math.PI*k/size,c=Math.cos(angle),s=Math.sin(angle),a=base+k,z=a+half,tr=re[z]*c-im[z]*s,ti=re[z]*s+im[z]*c;re[z]=re[a]-tr;im[z]=im[a]-ti;re[a]+=tr;im[a]+=ti;}}
  let peak=0,bin=0;for(let i=1;i<n/2;i++){const power=re[i]**2+im[i]**2;if(power>peak){peak=power;bin=i;}}return bin*48000/n;
 };
 const tones=[];
 for(const hz of H.HEARING_CONFIG.frequencies.slice(0,6)){
  const pcm=H.tonePCM(hz,-40,1,48000),ctx=new OfflineAudioContext(2,pcm.length,48000),buf=ctx.createBuffer(2,pcm.length,48000);buf.copyToChannel(pcm,0);const node=ctx.createBufferSource();node.buffer=buf;node.connect(ctx.destination);node.start();const rendered=await ctx.startRendering(),left=rendered.getChannelData(0),right=rendered.getChannelData(1);
  tones.push({hz,FFT:fftPeak(left),leftRMS:H.rms(left),rightRMS:H.rms(right),peak:H.peak(left),first:left[0],last:left.at(-1),maxDifference:Math.max(...Array.from(left,(v,i)=>Math.abs(v-pcm[i])))});
 }
 const invalidations=[],engine=new A.HearingAudio(s=>invalidations.push(s));await engine.loadBank(new AbortController().signal);
 const bank=engine.bank.map((pcm,digit)=>({digit,duration:pcm.length/48000,rms:H.rms(pcm),peak:H.peak(pcm),clipped:Array.from(pcm).filter(v=>Math.abs(v)>=1).length}));
 const mixes=[];for(const snr of [-15,0,15]){const m=engine.triplet([0,5,9],snr,H.seeded(123));mixes.push({target:snr,actualSNR:m.actualSNR,fromRMS:20*Math.log10(m.speechRMS/m.noiseRMS),peak:m.peak,duration:m.pcm.length/48000,first:m.pcm[0],last:m.pcm.at(-1)});}
 for(let i=0;i<10;i++){const speech=engine.bank[i],noise=engine.noise.slice(0,speech.length),m=H.mixDigits(speech,noise,0);await engine.play(m.pcm,'both');}
 // Controlled asynchronous resume delay: cancellation must create no node.
 const originalResume=engine.resume.bind(engine),originalCreate=engine.context.createBufferSource.bind(engine.context);let unblock,createdAfterCancel=0;
 const pendingResume=new Promise(resolve=>{unblock=resolve;});engine.resume=async()=>{await pendingResume;await originalResume();};
 engine.context.createBufferSource=()=>{createdAfterCancel++;return originalCreate();};
 const pendingTone=engine.tone(1000,-40,1,'left').then(()=>null,error=>error.message);engine.stop();unblock();const cancelledPendingResume=await pendingTone;
 engine.resume=originalResume;engine.context.createBufferSource=originalCreate;
 await engine.context.suspend();await new Promise(r=>setTimeout(r,50));engine.close();
 return {tones,bank,mixes,actualTenDigitsPlayed:true,invalidations,cancelledPendingResume,createdAfterCancel,closedBankReleased:engine.bank.length===0&&!engine.noise&&!engine.manifest,humanAuditoryAcceptance:false,clinicalValidation:false};
}''',{'protocol':compiled('hearingProtocol'),'audio':compiled('hearingAudio')})
 for tone in result['tones']:
  assert abs(tone['FFT']-tone['hz'])<3 and tone['rightRMS']==0 and tone['maxDifference']<1e-8
  assert tone['first']==tone['last']==0 and tone['peak']<=.010001
 assert len(result['bank'])==10 and all(abs(d['rms']-10**(-24/20))<1e-6 and d['clipped']==0 for d in result['bank'])
 assert all(abs(m['target']-m['fromRMS'])<1e-8 and m['peak']<=.080001 and m['first']==m['last']==0 for m in result['mixes'])
 assert result['invalidations']
 assert result['cancelledPendingResume']=='AUDIO_CANCELLED' and result['createdAfterCancel']==0 and result['closedBankReleased']
 result['buildId']=Path('apps/vehicle-app/.next/BUILD_ID').read_text().strip()
 (OUT/'proof.json').write_text(json.dumps(result,indent=2),'utf8');b.close()
print('PASS actual browser OfflineAudioContext FFT/stereo and all ten frozen digits playback; auditory acceptance pending')

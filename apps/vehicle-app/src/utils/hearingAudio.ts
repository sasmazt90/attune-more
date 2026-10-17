import {observeOutputNode} from './playbackMeter';
import { Ear, HEARING_CONFIG, tonePCM, mixDigits, rms } from './hearingProtocol';
export type DigitBankManifest={version:string;voice:string;rate:string;pitch:string;digits:{digit:number;url:string;sha256:string;duration:number}[];noise:{url:string;sha256:string};auditoryAcceptance:'pending'|'accepted'};
export class HearingAudio {
 context:AudioContext;private nodes=new Set<AudioBufferSourceNode>();private disposed=false;private epoch=0;
 bank:Float32Array[]=[];noise?:Float32Array;manifest?:DigitBankManifest;
 constructor(private invalidated:(reason:string)=>void){
  this.context=new AudioContext({sampleRate:48000});
  this.context.addEventListener('statechange',this.state);document.addEventListener('visibilitychange',this.visibility);navigator.mediaDevices?.addEventListener('devicechange',this.device);
 }
 private state=()=>{if(this.context.state==='suspended'&&!this.disposed){this.stop();this.invalidated('Ses motoru durakladı; hazırlığı yeniden doğrulayın.');}};
 private visibility=()=>{if(document.hidden){this.stop();this.invalidated('Pencere arka plana geçti; hazırlığı yeniden doğrulayın.');}};
 private device=()=>{this.stop();this.invalidated('Ses aygıtı değişti; sol/sağ kanalı yeniden doğrulayın.');};
 async resume(){if(this.disposed)throw Error('AUDIO_CLOSED');await this.context.resume();}
 async play(data:Float32Array,ear:Ear|'both',onStarted?:()=>void){
  const epoch=this.epoch;await this.resume();if(this.disposed||epoch!==this.epoch)throw Error('AUDIO_CANCELLED');const buffer=this.context.createBuffer(2,data.length,this.context.sampleRate);
  if(ear==='left'||ear==='both')buffer.copyToChannel(data as Float32Array<ArrayBuffer>,0);
  if(ear==='right'||ear==='both')buffer.copyToChannel(data as Float32Array<ArrayBuffer>,1);
  const node=this.context.createBufferSource();node.buffer=buffer;node.channelCount=2;node.channelCountMode='explicit';const unmeter=observeOutputNode(this.context,node);this.nodes.add(node);
  return new Promise<void>((resolve,reject)=>{node.onended=()=>{unmeter();node.disconnect();this.nodes.delete(node);epoch===this.epoch?resolve():reject(Error('AUDIO_CANCELLED'));};node.start();onStarted?.();});
 }
 tone(frequency:number,db:number,duration:number,ear:Ear,onStarted?:()=>void){return this.play(tonePCM(frequency,db,duration,this.context.sampleRate),ear,onStarted);}
 stop(){this.epoch++;for(const node of this.nodes){try{node.stop();}catch{}node.disconnect();}this.nodes.clear();}
 close(){this.disposed=true;this.stop();this.bank=[];this.noise=undefined;this.manifest=undefined;this.context.removeEventListener('statechange',this.state);document.removeEventListener('visibilitychange',this.visibility);navigator.mediaDevices?.removeEventListener('devicechange',this.device);void this.context.close();}
 async loadBank(signal:AbortSignal){
  const response=await fetch('/audio/hearing-bank/manifest.json',{signal});if(!response.ok)throw Error('Sayı bankası bulunamadı.');const manifest:DigitBankManifest=await response.json();
  if(manifest.voice!=='tr-TR-AhmetNeural'||manifest.rate!=='-10%'||manifest.pitch!=='-10Hz'||manifest.digits.length!==10||manifest.digits.some((d,i)=>d.digit!==i))throw Error('Sayı bankası profili doğrulanamadı.');
  const decode=async(item:{url:string;sha256:string})=>{const r=await fetch(item.url,{signal});if(!r.ok)throw Error('Sayı dosyası açılamadı.');const bytes=await r.arrayBuffer();const hash=Array.from(new Uint8Array(await crypto.subtle.digest('SHA-256',bytes))).map(x=>x.toString(16).padStart(2,'0')).join('');if(hash!==item.sha256)throw Error('Sayı bankası hash uyuşmazlığı.');const decoded=await this.context.decodeAudioData(bytes);if(decoded.numberOfChannels!==1||decoded.sampleRate!==48000||decoded.duration>30)throw Error('Sayı bankası biçimi doğrulanamadı.');const pcm=decoded.getChannelData(0).slice();if(!pcm.every(Number.isFinite)||rms(pcm)<=.001)throw Error('Geçersiz veya sessiz sayı dosyası.');return pcm;};
  const digits=await Promise.all(manifest.digits.map(decode));const noise=await decode(manifest.noise);if(this.disposed||signal.aborted)throw Error('AUDIO_CANCELLED');this.noise=noise;this.bank=digits;this.manifest=manifest;
 }
 triplet(digits:number[],snr:number,random:()=>number){
  if(digits.length!==3||digits.some(d=>!Number.isInteger(d)||d<0||d>9))throw Error('THREE_DIGITS_REQUIRED');
  if(this.bank.length!==10||!this.noise)throw Error('BANK_NOT_READY');
  const gap=Math.round(this.context.sampleRate*.18),length=digits.reduce((sum,d)=>sum+this.bank[d].length,0)+2*gap;
  const speech=new Float32Array(length),noise=new Float32Array(length);let at=0;
  for(const digit of digits){speech.set(this.bank[digit],at);at+=this.bank[digit].length+gap;}
  const offset=Math.floor(random()*this.noise.length);for(let i=0;i<length;i++)noise[i]=this.noise[(offset+i)%this.noise.length];
  // Fade the entire mixture edges without changing the SNR of speech/noise.
  const ramp=Math.floor(.03*this.context.sampleRate);for(let i=0;i<length;i++){const envelope=Math.min(1,i/ramp,(length-1-i)/ramp);speech[i]*=envelope;noise[i]*=envelope;}
  return mixDigits(speech,noise,snr);
 }
}

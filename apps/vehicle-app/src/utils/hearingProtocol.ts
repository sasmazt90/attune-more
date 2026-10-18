/** Experimental, uncalibrated digital protocol. No clinical dB HL/SPL. */
export const HEARING_CONFIG={version:'digital-hearing-v1',startDbFS:-60,minDbFS:-90,maxDbFS:-30,heardStepDb:-10,missStepDb:5,maxTrials:30,frequencies:[1000,2000,4000,8000,500,250,1000],rampSeconds:.035,catchProbability:.12,durationMin:.8,durationMax:1.35,gapMin:1.1,gapMax:2.7,responseSeconds:1.2,dinStart:0,dinMin:-15,dinMax:15,dinTrials:24,dinInitialStep:4,dinStableStep:2,dinMinimumReversals:6,dinSpeechRMS:'whole-presentation-window',mixturePeak:.08} as const;
export type Ear='left'|'right';
export const amplitude=(db:number)=>10**(db/20);
export function rms(values:ArrayLike<number>){let sum=0;for(let i=0;i<values.length;i++)sum+=values[i]**2;return Math.sqrt(sum/Math.max(1,values.length));}
export function peak(values:ArrayLike<number>){let max=0;for(let i=0;i<values.length;i++)max=Math.max(max,Math.abs(values[i]));return max;}
export function tonePCM(frequency:number,db:number,duration:number,rate:number){
 if(![frequency,db,duration,rate].every(Number.isFinite)||frequency<250||frequency>8000||frequency>=rate/2||db>HEARING_CONFIG.maxDbFS||db<HEARING_CONFIG.minDbFS||duration<=0||duration>2||!Number.isInteger(rate)||rate<16000||rate>192000)throw Error('SIGNAL_LIMIT');
 const data=new Float32Array(Math.floor(duration*rate)),ramp=Math.floor(HEARING_CONFIG.rampSeconds*rate);
 for(let i=0;i<data.length;i++){const edge=Math.min(1,i/ramp,(data.length-1-i)/ramp);data[i]=amplitude(db)*.5*(1-Math.cos(Math.PI*Math.max(0,edge)))*Math.sin(2*Math.PI*frequency*i/rate);}return data;
}
export type ToneThreshold={ear:Ear;frequency:number;value:number|null;unit:'dBFS-peak';status:'threshold'|'upper-limit'|'lower-limit'|'max-trials';trials:number;repeat?:boolean};
export class FrequencyStaircase {
 level:number=HEARING_CONFIG.startDbFS;trials=0;ascending=false;finished=false;
 readonly asc=new Map<number,{presentations:number;heard:number}>();
 history:{level:number;heard:boolean;ascending:boolean}[]=[];
 response(heard:boolean):{value:number|null;status:ToneThreshold['status']}|null {
  if(this.finished)throw Error('STAIRCASE_FINISHED');this.trials++;this.history.push({level:this.level,heard,ascending:this.ascending});
  if(this.ascending){const votes=this.asc.get(this.level)||{presentations:0,heard:0};votes.presentations++;votes.heard+=Number(heard);this.asc.set(this.level,votes);
   if(votes.heard>=2&&votes.heard/votes.presentations>=.5){this.finished=true;return {value:this.level,status:'threshold'};}}
  if(!heard&&this.level===HEARING_CONFIG.maxDbFS){this.finished=true;return {value:null,status:'upper-limit'};}
  if(heard&&this.level===HEARING_CONFIG.minDbFS){this.finished=true;return {value:null,status:'lower-limit'};}
  if(this.trials>=HEARING_CONFIG.maxTrials){this.finished=true;return {value:null,status:'max-trials'};}
  this.level=Math.min(HEARING_CONFIG.maxDbFS,Math.max(HEARING_CONFIG.minDbFS,this.level+(heard?HEARING_CONFIG.heardStepDb:HEARING_CONFIG.missStepDb)));
  this.ascending=!heard;return null;
 }
}
/** Seeded only for reproducible engineering tests; products seed crypto randomly. */
export function seeded(seed:number){let value=seed>>>0;return()=>{value=(1664525*value+1013904223)>>>0;return value/4294967296;};}
export type DigitTrial={digits:number[];answer:number[];snr:number;correct:boolean;repeated:boolean};
export class DigitStaircase {
 snr:number=HEARING_CONFIG.dinStart;history:DigitTrial[]=[];reversals:number[]=[];lastDirection=0;
 respond(digits:number[],answer:number[],repeated=false){
  if(digits.length!==3||answer.length!==3||answer.some(v=>!Number.isInteger(v)||v<0||v>9))throw Error('THREE_DIGITS_REQUIRED');
  const correct=digits.every((v,i)=>v===answer[i]);this.history.push({digits:[...digits],answer:[...answer],snr:this.snr,correct,repeated});
  if(repeated)return;
  const direction=correct?-1:1;
  if(this.lastDirection&&direction!==this.lastDirection&&this.snr>HEARING_CONFIG.dinMin&&this.snr<HEARING_CONFIG.dinMax)this.reversals.push(this.snr);
  const step=this.reversals.length>=2?HEARING_CONFIG.dinStableStep:HEARING_CONFIG.dinInitialStep;
  this.snr=Math.min(HEARING_CONFIG.dinMax,Math.max(HEARING_CONFIG.dinMin,this.snr+direction*step));this.lastDirection=direction;
 }
 get scored(){return this.history.filter(t=>!t.repeated);}
 result(){const scored=this.scored,tail=this.reversals.slice(-6),bounded=scored.filter(t=>Math.abs(t.snr)===15).length;
  const threshold=tail.length>=HEARING_CONFIG.dinMinimumReversals&&bounded<scored.length/3?tail.reduce((a,b)=>a+b,0)/tail.length:null;
  return {type:'longitudinal_measurement',methodVersion:HEARING_CONFIG.version,unit:'dB-SNR',value:threshold,quality:threshold===null?'insufficient':'valid',limitationCode:threshold===null?'INSUFFICIENT_REVERSALS_OR_BOUNDARY':null,validTrials:scored.length,digitAccuracy:scored.length?scored.reduce((a,t)=>a+t.digits.filter((v,i)=>v===t.answer[i]).length,0)/(scored.length*3):null,tripletAccuracy:scored.length?scored.filter(t=>t.correct).length/scored.length:null,repeated:this.history.length-scored.length,reversals:[...this.reversals]};}
}
/** Actual PCM mixing; RMS uses the entire common triplet presentation window. */
export function mixDigits(speech:Float32Array,noise:Float32Array,snr:number){
 if(!Number.isFinite(snr)||speech.length!==noise.length||speech.length>480000||snr<HEARING_CONFIG.dinMin||snr>HEARING_CONFIG.dinMax)throw Error('MIX_LIMIT');
 const sr=rms(speech),nr=rms(noise);if(!Number.isFinite(sr)||!Number.isFinite(nr)||sr<=0||nr<=0)throw Error('EMPTY_SIGNAL');
 const gain=sr/nr/amplitude(snr),mixture=new Float32Array(speech.length);
 for(let i=0;i<mixture.length;i++)mixture[i]=speech[i]+noise[i]*gain;
 const common=Math.min(.015/Math.max(rms(mixture),.0001),HEARING_CONFIG.mixturePeak/Math.max(peak(mixture),.0001));
 for(let i=0;i<mixture.length;i++)mixture[i]*=common;
 return {pcm:mixture,actualSNR:20*Math.log10(sr/(nr*gain)),speechRMS:sr*common,noiseRMS:nr*gain*common,peak:peak(mixture),gain:common};
}

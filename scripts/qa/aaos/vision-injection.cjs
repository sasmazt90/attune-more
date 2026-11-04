'use strict';
// Page scripts for Vision on the AVD, which has no camera and no recognizer. The camera honours
// the app's 640-wide request the way a real sensor would, and paints only as fast as the app reads:
// a sensor costs the page nothing, while canvas capture shares the guest's GPU path with inference
// (measured: 15 fps 499 ms per frame, 5 fps 237 ms). Diagnostics watch from outside the app:
// worker round trips, frame ages and gate states per frame, never pixels or answers' audio.
const CAMERA = (width, fps) => `(()=>{window.__qaVision={target:'Front',images:{},recognitions:0,answers:[]};
 const canvas=document.createElement('canvas');const g=canvas.getContext('2d');let last=null;canvas.width=${width};canvas.height=${Math.round(width * 9 / 16)};
 setInterval(()=>{const image=window.__qaVision.images[window.__qaVision.target];if(!(image&&image.complete&&image.naturalWidth)){if(!last){g.fillStyle='#111';g.fillRect(0,0,canvas.width,canvas.height);}return;}g.drawImage(image,0,0,canvas.width,canvas.height);last=image;},${Math.round(1000 / fps)});
 const stream=canvas.captureStream(${fps});
 const real=navigator.mediaDevices.getUserMedia.bind(navigator.mediaDevices);
 navigator.mediaDevices.getUserMedia=c=>c&&c.video?Promise.resolve(new MediaStream(stream.getVideoTracks().map(t=>t.clone()))):real(c);})();`;

// A recognizer that answers from what is on screen, with the words a person would use.
const WORDS = {
  tr: {notVisible: 'göremiyorum', rotation: {0: 'düz', 90: 'sağa', 180: 'baş aşağı', 270: 'sola'}, mirrored: 'aynalı'},
  en: {notVisible: 'i cannot see it', rotation: {0: 'upright', 90: 'right', 180: 'upside down', 270: 'left'}, mirrored: 'mirrored'},
  de: {notVisible: 'ich sehe es nicht', rotation: {0: 'aufrecht', 90: 'nach rechts', 180: 'auf dem kopf', 270: 'nach links'}, mirrored: 'gespiegelt'},
};
const RECOGNIZER = (words, paths, plan) => `(()=>{const WORDS=${JSON.stringify(words)},PATHS=${JSON.stringify(paths)},PLAN=${JSON.stringify(plan)};
 function read(){const svg=document.querySelector('[data-letter-optotype]');if(!svg)return null;const d=svg.querySelector('path')?.getAttribute('d'),t=svg.querySelector('g')?.getAttribute('transform')||'',letter=Object.keys(PATHS).find(k=>PATHS[k]===d),rotation=Number((t.match(/rotate\\((\\d+)\\)/)||[])[1]||0),mirrored=/scale\\(-1/.test(t);return letter?{letter,rotation,mirrored}:null;}
 function answer(){const done=Number(document.querySelector('[role=progressbar]')?.getAttribute('aria-valuenow')||0),kind=PLAN[done%PLAN.length],shown=read();if(kind==='not-visible'||!shown)return {kind:'not-visible',text:WORDS.notVisible};const letter=kind==='wrong-letter'?Object.keys(PATHS).find(k=>k!==shown.letter):shown.letter;return {kind,shown,text:[letter,WORDS.rotation[shown.rotation],shown.mirrored?WORDS.mirrored:''].filter(Boolean).join(' ').toLowerCase()};}
 class QaRecognition{constructor(){this.lang='';this.continuous=false;this.interimResults=false;this.maxAlternatives=1;}
  start(){window.__qaVision.recognitions++;this.timer=setTimeout(()=>{this.onstart&&this.onstart();this.timer=setTimeout(()=>{const a=answer();window.__qaVision.answers.push({...a,at:performance.now()});const item=Object.assign([{transcript:a.text,confidence:.95}],{isFinal:true});this.onresult&&this.onresult({resultIndex:0,results:[item]});this.onend&&this.onend();},700);},40);}
  abort(){clearTimeout(this.timer);}stop(){clearTimeout(this.timer);}}
 window.SpeechRecognition=QaRecognition;window.webkitSpeechRecognition=QaRecognition;})();`;

const DIAGNOSTICS = delegate => `(()=>{const D=window.__qaDiag={frames:[],samples:[],long:[],pending:new Map(),initialized:null};const Real=window.Worker;
 window.Worker=class extends Real{constructor(...a){super(...a);this.addEventListener('message',e=>{const m=e.data||{};if(m.ready)D.initialized=performance.now();const sent=D.pending.get(m.id);if(sent===undefined)return;D.pending.delete(m.id);const c=m.evidence&&m.evidence.conditions,eye=s=>s&&{state:s.state,candidate:s.candidateState,held:Math.round(s.heldMs||0)};D.frames.push({sent:Math.round(sent),received:Math.round(performance.now()),inference:m.evidence&&Math.round(m.evidence.inferenceMs),delegate:m.evidence&&m.evidence.delegate,error:m.error,blocker:c&&c.blocker,distance:c&&c.distanceState,right:c&&eye(c.right),left:c&&eye(c.left)});});}
  postMessage(m,t){if(m&&m.type==='frame')D.pending.set(m.id,performance.now());${delegate ? `if(m&&m.type==='initialize')m={...m,delegate:'${delegate}'};` : ''}return super.postMessage(m,t);}};
 try{new PerformanceObserver(l=>{for(const e of l.getEntries())D.long.push({at:Math.round(e.startTime),ms:Math.round(e.duration)});}).observe({entryTypes:['longtask']});}catch{}
 setInterval(()=>{const v=document.querySelector('video'),s=document.querySelector('[data-vision-stage]'),c=document.querySelector('canvas[hidden]');let age=null;try{const e=c&&c.dataset.visionEvidence&&JSON.parse(c.dataset.visionEvidence);if(e)age=Math.round(performance.now()-e.conditions.observedAt);}catch{}
  D.samples.push({at:Math.round(performance.now()),stage:s&&s.dataset.visionStage,voice:s&&s.querySelector('[data-vision-voice]')?.getAttribute('data-vision-voice'),done:Number(document.querySelector('[role=progressbar]')?.getAttribute('aria-valuenow')||0),age,video:v&&{t:+v.currentTime.toFixed(2),ready:v.readyState,paused:v.paused},inFlight:D.pending.size,hidden:document.hidden});},500);
 D.drain=()=>{const out={frames:D.frames,samples:D.samples,long:D.long};D.frames=[];D.samples=[];D.long=[];return out;};})();`;

module.exports = {CAMERA, DIAGNOSTICS, RECOGNIZER, WORDS};

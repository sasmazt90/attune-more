window.mentalProbe={recognitions:[],audios:[],events:[],requests:[],cameraAttempts:0};
navigator.mediaDevices.getUserMedia=()=>{mentalProbe.cameraAttempts++;throw Error('Physical hardware forbidden in controlled test')};
class ControlledRecognition{constructor(){mentalProbe.recognitions.push(this)}start(){mentalProbe.current=this;if(!mentalProbe.suppressStart)this.onstart?.()}abort(){this.aborted=true;this.onend?.()}emit(text,final=true){this.onresult?.({resultIndex:0,results:[Object.assign([{transcript:text,confidence:.98}],{isFinal:final})]})}}
window.SpeechRecognition=window.webkitSpeechRecognition=ControlledRecognition;
const NativeAudio=window.Audio;window.Audio=function(...a){const audio=new NativeAudio(...a);mentalProbe.audios.push(audio);for(const type of ['playing','ended','error'])audio.addEventListener(type,()=>mentalProbe.events.push({kind:'native-audio',type,at:performance.now()}));return audio};window.Audio.prototype=NativeAudio.prototype;
window.addEventListener('attune-speech-timing',e=>mentalProbe.events.push(e.detail));window.addEventListener('attune-guidance-event',e=>mentalProbe.events.push({kind:'guidance',...e.detail}));
const nativeFetch=window.fetch.bind(window);window.fetch=(url,options)=>{if(String(url).includes('/api/mental/'))mentalProbe.requests.push({path:new URL(url).pathname,at:performance.now()});return nativeFetch(url,options)};

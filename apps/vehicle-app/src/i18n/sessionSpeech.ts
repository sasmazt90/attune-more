/** A queued free-text reply belongs to its original language. Never replay it
 * with a newly selected language/voice; keep transcript and assessment data. */
export function cancelQueuedSessionSpeech(
 runtime:{active:boolean;paused:boolean;pendingSpeech:{crisis:boolean}|null},
 actions:{pause:()=>void;crisis:()=>void;notice:()=>void},
){
 if(!runtime.active)return;
 if(runtime.pendingSpeech?.crisis){actions.crisis();return;}
 if(!runtime.paused)actions.pause();
 runtime.pendingSpeech=null;
 actions.notice();
}

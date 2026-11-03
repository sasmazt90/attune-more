/** Ending while a reply is pending drops only that unanswered turn: its exchange never
 * completed, while the exchanges before it did. Any other unfinished message means a
 * failed turn, and a failed session stays out of history. */
export function closingTranscript<T extends {id:string;completed:boolean}>(transcript:T[],pendingUserId:string|undefined,sessionFailed:boolean){
 const unfinished=transcript.filter(m=>!m.completed);
 return {
  completed:transcript.filter(m=>m.completed),
  discardedPending:unfinished.some(m=>m.id===pendingUserId),
  failed:sessionFailed||unfinished.some(m=>m.id!==pendingUserId),
 };
}

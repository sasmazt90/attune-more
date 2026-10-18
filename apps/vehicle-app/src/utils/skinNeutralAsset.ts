/** Fixed, decoded local guidance only. Admission never substitutes another voice. */
export const SKIN_NEUTRAL_TEXT='Ağzınızı kapatın. Gülümsemeden yüzünüzü rahat bırakın; başınızı istenen pozda sabit tutun.';
export const SKIN_NEUTRAL_CONTRACT='574b1c2f1fcd0bf4f7c597476875ac563a91959bb2fc144f1bce948156a0adaf';
export function admittedSkinNeutral(entry:unknown,version:string):boolean {
 if(!entry||typeof entry!=='object')return false;
 const e=entry as Record<string,unknown>,a=e.admission as Record<string,unknown>|undefined;
 return version==='guidance-20261009-v1'&&e.textVersion===version&&e.text===SKIN_NEUTRAL_TEXT&&
  e.voice==='tr-TR-AhmetNeural'&&e.rate==='-10%'&&e.pitch==='-10Hz'&&
  e.contractHash===SKIN_NEUTRAL_CONTRACT&&e.url===`/audio/guidance/${SKIN_NEUTRAL_CONTRACT}.mp3`&&
  typeof e.sha256==='string'&&/^[a-f0-9]{64}$/.test(e.sha256)&&
  a?.version==='fixed-neutral-decoded-v1'&&a.codec==='mp3'&&a.sampleRate===24000&&a.channels===1&&
  typeof a.durationSeconds==='number'&&Number.isFinite(a.durationSeconds)&&a.durationSeconds>1&&a.durationSeconds<30&&
  typeof a.decodedSamples==='number'&&Number.isInteger(a.decodedSamples)&&a.decodedSamples===Math.round(a.durationSeconds*24000)&&
  typeof a.decodeReceiptSHA256==='string'&&/^[a-f0-9]{64}$/.test(a.decodeReceiptSHA256);
}

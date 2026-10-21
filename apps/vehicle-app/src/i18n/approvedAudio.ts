import raw from '../../public/audio/user-approved/tr-en-de-20261020-v1/manifest.json';
import type {Language} from './core';
import type {HealthModule} from '../utils/healthModules';
import type {FixedClip} from './fixedAudio';

export type ApprovedRecording=FixedClip & {
 recordingId:string;eventId:string;language:Language;applicationLocale:string;voiceLocale:string;
 voice:string;voiceProfile:string;provider:string;providerVoiceId:string|null;gender:'male'|'female';
 exactScript:string;integrationDisposition:string;activeModules:string[];
};
const MODULE_NAMES:Record<HealthModule,string>={skin:'Skin Health',dental:'Dental Health',vision:'Vision Health',mental:'Mental Health',hearing:'Hearing Health'};
export const approvedAudio=raw;
const recordings=new Map(raw.recordings.map(r=>[r.recordingId,{...r,text:r.exactScript,sourceTextSha256:r.scriptSHA256} as ApprovedRecording]));
/** Only the owner's selected module/language/event tuples may dispatch. */
export function approvedClip(language:Language,module:HealthModule,eventId:string):ApprovedRecording|undefined {
 const mapping=raw.activeGuidanceMappings.find(m=>m.language===language&&m.module===MODULE_NAMES[module]&&m.eventId===eventId);
 const clip=mapping&&recordings.get(mapping.recordingId);
 return clip?.integrationDisposition==='FIXED_GUIDANCE_OR_EXACT_TEMPLATE_INTEGRATION_CANDIDATE'&&clip.language===language&&clip.eventId===eventId?clip:undefined;
}
export function approvedMentalTemplate(language:Language,text:string){
 // Literal full-text equality: no substring, nearest match, or demo substitution.
 return raw.activeGuidanceMappings.filter(m=>m.language===language&&m.module==='Mental Health'&&m.eventId.startsWith('mental-template:'))
  .map(m=>recordings.get(m.recordingId)).find(clip=>clip?.exactScript===text);
}
export function mentalVoiceContract(language:Language){return approvedClip(language,'mental','guidance:mental-entry');}

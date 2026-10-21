import catalog from '../../../../shared/localization/messages.json';
import vocabulary from '../../../../shared/localization/mental-themes.json';
import {t} from './core';
const normalize=(value:string)=>value.normalize('NFC').trim().toLocaleLowerCase('tr-TR');
const aliases=new Map<string,string>();
for(const raw of [...vocabulary.session,...vocabulary.conversation]){
 const message=Object.values(catalog).find(row=>row.tr===raw);
 for(const label of [raw,...(message?[message.en,message.de]:[])])aliases.set(normalize(label),raw);
}
/** Only the controlled vocabulary is canonicalized; private/custom text stays raw. */
export const canonicalMentalTheme=(value:string)=>aliases.get(normalize(value))||value;
export const displayMentalTheme=(value:string)=>t(canonicalMentalTheme(value));

import type {Letter, ParsedAnswer, Rotation} from './spokenVision';
type Language='tr'|'en'|'de';
/** Target-independent vocabulary. No unrestricted fuzzy matching or first-letter scoring.
 * Other words require explicit spelling syntax ("E as in elephant"). */
const words:Record<Language,Record<Letter,string[]>>={
 tr:{A:['a','adana','ankara','ali'],B:['b','be','bolu','bursa'],E:['e','elma','edirne'],F:['f','fe','ef','efe','fatsa','fatma'],P:['p','pe','pırasa','polatlı'],R:['r','re','er','rize']},
 en:{A:['a','ay','alpha','alfa','apple'],B:['b','bee','be','bravo','banana'],E:['e','ee','echo','elephant'],F:['f','eff','ef','foxtrot','fox','finish'],P:['p','pee','pea','papa','pear','pause'],R:['r','are','ar','romeo','rabbit','repeat','resume']},
 de:{A:['a','ah','anton','aachen','anna','apfel'],B:['b','be','beh','berta','berlin','bären','beenden'],E:['e','eh','emil','essen','elefant'],F:['f','ef','eff','friedrich','frankfurt','fuchs','fertig','fortsetzen'],P:['p','pe','peh','paula','potsdam','papier','pausieren'],R:['r','er','richard','rostock','rose']}
};
const controls:Record<Language,Record<string,NonNullable<ParsedAnswer['command']>>>={
 tr:{'göremiyorum':'not-visible','harfi göremiyorum':'not-visible','ayırt edemiyorum':'not-visible','bitir':'finish','sonlandır':'finish','testi bitir':'finish','devam et':'resume','sürdür':'resume','duraklat':'pause','bekle':'pause','tekrar':'repeat','yeniden söyle':'repeat'},
 en:{'i can t see it':'not-visible','i cannot see it':'not-visible','not visible':'not-visible','repeat':'repeat','pause':'pause','resume':'resume','continue':'resume','finish the test':'finish','stop the test':'finish'},
 de:{'ich sehe es nicht':'not-visible','nicht erkennbar':'not-visible','wiederholen':'repeat','pausieren':'pause','pause':'pause','fortsetzen':'resume','weiter':'resume','test beenden':'finish','den test beenden':'finish'}
};
function normalize(text:string,language:Language){
 let value=text.normalize('NFKC').toLocaleLowerCase(language==='tr'?'tr-TR':language==='de'?'de-DE':'en-US').replace(/[’‘`']/g,' ').replace(/[^\p{L}\d° ]/gu,' ').replace(/\s+/g,' ').trim();
 if(language==='tr')value=value.replace(/\başaa\b/gu,'aşağı').replace(/\bdoksan\b/gu,'90').replace(/\byüz seksen\b/gu,'180');
 if(language==='en')value=value.replace(/\bone hundred (?:and )?eighty\b/gu,'180').replace(/\bninety\b/gu,'90');
 if(language==='de')value=value.replace(/\bhundertachtzig\b/gu,'180').replace(/\bneunzig\b/gu,'90');
 return value;
}
const patterns:Record<Language,{normal:RegExp;cw:RegExp;ccw:RegExp;half:RegExp;mirror:RegExp;vertical:RegExp;reverse:RegExp;negativeMirror:RegExp;point:RegExp;filler:RegExp}>={
 tr:{normal:/\b(?:normal|standart)\b|düz|dik|doğru yönde/gu,cw:/saat yönünde(?: 90(?: derece)?)?|90(?: derece)? sağa|sağa(?: doğru)?(?: 90(?: derece)?)?|sağ yana|sağ yat/gu,ccw:/saat yönünün tersin(?:d)?e(?: 90(?: derece)?)?|90(?: derece)? sola|sola(?: doğru)?(?: 90(?: derece)?)?|sol yana|sol yat/gu,half:/baş aşağı|başaşağı|tepetaklak|180(?: derece)?(?: dönmüş)?/gu,mirror:/aynalı|ayna (?:görüntüsü|yansıması)|yansıtılmış|yansıma|simetrik|yatay(?: olarak)? (?:ayna|çevir|yansıt)\p{L}*/gu,vertical:/dikey(?: olarak)? (?:ayna|çevir|yansıt)\p{L}*/gu,reverse:/\bters\b/gu,negativeMirror:/aynasız|aynalı değil|ayna görüntüsü değil/gu,point:/(yukarı|aşağı)(?:ya)?(?: doğru)? (?:bakıyor|dönük)/gu,filler:/(?<!\p{L})(?:bence|harf|harfi|harfin|bu|şu|bir|kelime|kelimesi|söylüyorum|söylediğim|olan|ve|ama|hem|si|sı|s|i|ı|nin|nın|nun|nün)(?!\p{L})|(?:dönmüş|dönük|devrik|devrilmiş|yatmış|derece|yönde|yönünde|bakıyor)/gu},
 en:{normal:/\b(?:upright|normal|standard|straight|right way up)\b/gu,cw:/\b(?:clockwise(?: 90(?: degrees)?)?|90(?: degrees)? clockwise|90(?: degrees)? (?:to the )?right|(?:turned |rotated |tilted |leaning )?(?:to the )?right(?: 90(?: degrees)?)?)\b/gu,ccw:/\b(?:(?:counterclockwise|counter clockwise|anticlockwise|anti clockwise)(?: 90(?: degrees)?)?|90(?: degrees)? (?:counterclockwise|counter clockwise|anticlockwise)|90(?: degrees)? (?:to the )?left|(?:turned |rotated |tilted |leaning )?(?:to the )?left(?: 90(?: degrees)?)?)\b/gu,half:/\b(?:upside down|180(?: degrees)?(?: (?:rotation|rotated))?|half (?:a )?turn)\b/gu,mirror:/\b(?:(?:horizontally |horizontal )?(?:mirrored|mirror image|mirror reflection|reflected)(?: horizontally)?|flipped horizontally|horizontal mirror|back to front)\b/gu,vertical:/\b(?:vertically (?:mirrored|reflected)|vertical (?:mirror|reflection)|flipped vertically)\b/gu,reverse:/\b(?:reverse|reversed|backwards|symmetric)\b/gu,negativeMirror:/\b(?:unmirrored|not (?:mirrored|a mirror image))\b/gu,point:/\b(?:points?|pointing|faces?|facing) (up|down)\b/gu,filler:/\b(?:please|the|letter|is|it|i|think|see|and|but|both|looks|like|turned|rotated|rotation|degrees|to)\b/gu},
 de:{normal:/\b(?:aufrecht|normal|gerade|richtig herum|unverdreht)\b/gu,cw:/\b(?:im uhrzeigersinn(?: (?:um )?90(?: grad)?)?|90(?: grad)? im uhrzeigersinn|90(?: grad)? (?:nach )?rechts|(?:nach )?rechts(?: (?:um )?90(?: grad)?)?)\b/gu,ccw:/\b(?:gegen den uhrzeigersinn(?: (?:um )?90(?: grad)?)?|90(?: grad)? gegen den uhrzeigersinn|90(?: grad)? (?:nach )?links|(?:nach )?links(?: (?:um )?90(?: grad)?)?)\b/gu,half:/\b(?:auf dem kopf|kopfüber|180(?: grad)?(?: gedreht)?|halbe drehung)\b/gu,mirror:/\b(?:(?:horizontal |waagerecht )?(?:gespiegelt|spiegelverkehrt)|spiegelbild)\b/gu,vertical:/\b(?:vertikal|senkrecht) (?:gespiegelt|spiegelverkehrt)\b/gu,reverse:/\b(?:umgekehrt|verkehrt herum|symmetrisch)\b/gu,negativeMirror:/\bnicht (?:gespiegelt|spiegelverkehrt)\b/gu,point:/\b(?:zeigt|schaut|blickt)(?: nach)? (oben|unten)\b/gu,filler:/\b(?:bitte|der|die|das|buchstabe|ist|ich|denke|sehe|und|aber|sowohl|als auch|um|grad|gedreht|gekippt|geneigt|liegend|drehung)\b/gu}
};
/** No expected answer is consulted. Context only resolves a pointing direction
 * against the base E geometry: its arms point right before transformation. */
export function interpretVisionAnswer(text:string,language:Language='tr',context?:{letter:Letter}):ParsedAnswer{
 let value=normalize(text,language);
 const command=controls[language][value];if(command)return {command};
 if(language==='tr')value=value.replace(/aynalı değil|ayna görüntüsü değil/gu,'aynasız');
 if(language==='en')value=value.replace(/\bnot (?:mirrored|a mirror image)\b/gu,'unmirrored').replace(/^not ([abefpr]) but /u,'');
 const bareNegative=language==='tr'?/(?:^değil|değil$)/u:language==='en'?/^(?:not|no)\b/u:/^(?:nicht|kein)\b/u;
 if(bareNegative.test(value)&&!(language==='de'&&/\bsondern\b/u.test(value))&&!(language==='en'&&/^not (?:mirrored|a mirror image)/u.test(value))&&!(language==='de'&&/^nicht (?:gespiegelt|spiegelverkehrt)/u.test(value)))return {clarify:'letter',ambiguous:'letter'};
 const correction=language==='tr'?/\s+değil\s+|\s+(?:hayır|pardon|düzeltiyorum)\s+/u:language==='en'?/\s+(?:no|sorry|i mean|rather)\s+/u:/\s+(?:nein|sondern|ich meine|korrektur)\s+/u;
 // Negating a component alone cannot affirm it. A replacement must supply it.
 const corrected=value.split(correction);
 if(corrected.length>1){
  const before=interpretVisionAnswer(corrected.slice(0,-1).join(' '),language,context),after=interpretVisionAnswer(corrected.at(-1)!,language,context);
  const result:ParsedAnswer={...before,...after};delete result.command;
  if(after.ambiguous)return finish(result);
  if(!after.letter&&after.rotation===undefined&&after.mirrored===undefined)return {...before,ambiguous:before.letter?'letter':'rotation',clarify:before.letter?'letter':'orientation'};
  delete result.ambiguous;delete result.clarify;
  return finish(result);
 }
 // Keep digit forms and word forms equivalent without losing angle evidence.
 const p=patterns[language],result:ParsedAnswer={},rotations:Rotation[]=[];
 // An explicitly named letter with a possessive code word identifies that
 // letter only when the word has the same initial (Paris'in P'si).
 if(language==='tr')value=value.replace(/(?<!\p{L})(\p{L}+?)(?:nın|nin|nun|nün|ın|in|un|ün)? (?:nın |nin |nun |nün |ın |in |un |ün )?([abefpr]) (?:si|sı|s|i|ı)(?!\p{L})/gu,(all:string,word:string,letter:string)=>word[0].toLocaleUpperCase('tr-TR')===letter.toUpperCase()?letter:all);
 const take=(pattern:RegExp)=>{pattern.lastIndex=0;const found=pattern.test(value);pattern.lastIndex=0;if(found)value=value.replace(pattern,' ');return found;};
 // Explicit spelling syntax is bounded by a letter, not the displayed target.
 const explicit=language==='tr'?/\b([abefpr])(?: harfi)? (?:ile başlayan|yani) \p{L}+/gu:language==='en'?/\b([abefpr]) (?:as in|for) \p{L}+/gu:/\b([abefpr]) (?:wie) \p{L}+/gu;
 value=value.replace(explicit,(all:string,letter:string)=>{const word=all.split(' ').at(-1)!;return word[0].toLocaleUpperCase(language==='tr'?'tr-TR':language)===letter.toUpperCase()?letter:letter+' '+word;});
 if(take(p.negativeMirror))result.mirrored=false;
 const vertical=take(p.vertical);if(vertical){rotations.push(180);result.mirrored=true;}
 if(take(p.ccw))rotations.push(270); // Consume counterclockwise before clockwise.
 const half=take(p.half);
 const cw=take(p.cw);if(cw)rotations.push(90);
 if(half){if(cw&&rotations.includes(270))result.ambiguous='rotation';rotations.splice(0,rotations.length,180);}
 if(take(p.normal))rotations.push(0);
 if(take(p.mirror))result.mirrored=true;
 p.point.lastIndex=0;const pointing=[...value.matchAll(p.point)];value=value.replace(p.point,' ');
 if(pointing.length){
  if(context?.letter==='E')for(const m of pointing)rotations.push(/up|oben|yukarı/u.test(m[1])?270:90);
  else if(!context&&language==='tr'&&pointing.every(m=>m[0].includes('dönük')&&m[1]==='aşağı'))rotations.push(180); // Legacy standalone description.
  else result.ambiguous='rotation';
 }
 const reverse=take(p.reverse);
 if(reverse&&!half)result.clarify='reverse';
 // A bare negative never supplies an affirmative answer.
 const negative=language==='tr'?/değil|hayır/u:language==='en'?/\b(?:not|no|don t)\b/u:/\b(?:nicht|kein|nein)\b/u;
 if(negative.test(value))return {clarify:'orientation',ambiguous:'rotation'};
 value=value.replace(/°/g,' ').replace(p.filler,' ').replace(/\s+/g,' ').trim();
 const tokens=value.split(' ').filter(Boolean),letters=new Set<Letter>();
 for(const token of tokens)for(const letter of Object.keys(words[language]) as Letter[])if(words[language][letter].includes(token))letters.add(letter);
 // An explicit letter can accompany possessive spelling words; unrelated words
 // alongside it remain uncertain instead of being silently thrown away.
 const known=new Set(Object.values(words[language]).flat());
 const suffix=language==='tr'?/^(?:nin|nın|nun|nün|si|sı|s|i|ı)$/u:/^$/u;
 const unknown=tokens.filter(token=>!known.has(token)&&!suffix.test(token));
 // TR conventional "Pırasanın P'si" has an explicit letter plus possessive code word.
 const possessive=language==='tr'&&letters.size===1&&unknown.every(token=>/\p{L}+(?:nın|nin|nun|nün)$/u.test(token)&&token[0].toLocaleUpperCase('tr-TR')===[...letters][0]);
 if(letters.size===1&&(!unknown.length||possessive))result.letter=[...letters][0];
 else if(letters.size>1||tokens.length)result.ambiguous='letter';
 const unique=[...new Set(rotations)];
 if(unique.length===1)result.rotation=unique[0];else if(unique.length>1)result.ambiguous='rotation';
 return finish(result);
}
function finish(result:ParsedAnswer):ParsedAnswer{
 if(result.ambiguous)return {...result,clarify:result.ambiguous==='letter'?'letter':'orientation'};
 if(result.clarify==='reverse')return result;
 if(!result.letter)return {...result,clarify:'letter'};
 if(result.rotation===undefined&&result.mirrored!==true)return {...result,clarify:'orientation'};
 delete result.clarify;return result;
}

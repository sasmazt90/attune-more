// Actual share adapter/catalog; synthetic storage only, no health profile IO.
require('./ts_loader.js');
const assert=require('node:assert/strict');
const language=process.argv[2];assert(['tr','en','de'].includes(language));
global.window=new EventTarget();
const values=new Map();global.localStorage={getItem:k=>values.get(k)??null,setItem:(k,v)=>values.set(k,String(v)),removeItem:k=>values.delete(k)};
const core=require('../../apps/vehicle-app/src/i18n/core.ts');
const translate=core.t,inputs=[];
// Observe the real translation boundary, keeping the production catalog active.
core.t=(value,...args)=>{inputs.push(value);return translate(value,...args);};
const {measuredShareSection}=require('../../apps/vehicle-app/src/utils/healthShare.ts');
core.setLanguage(language);
const ISO='2026-10-20T12:34:56.000Z';
localStorage.setItem('attune_health_processing_v1',JSON.stringify({version:1,services:{hearing:{permissions:['audio'],at:ISO}}}));
localStorage.setItem('togg_health_vision_history','[{"id":"untouched-vision","value":1.25}]');
const snapshot=()=>JSON.stringify([...values].filter(([k])=>k!=='attune.language.v1'));
const dental={id:'synthetic-dental-composition',timestamp:ISO,sourceType:'upload',measurements:[
 {pose:'FRONT',caries:{value:2,quality:'valid'},accumulation:{value:15.6,quality:'valid'}},
 {pose:'RIGHT',caries:{value:0,quality:'valid'},accumulation:{value:0,quality:'valid'}},
 {pose:'LEFT',caries:{value:99,quality:'invalid'},accumulation:{value:null,quality:'insufficient'}}]};
localStorage.setItem('attune_dental_history_v1',JSON.stringify([dental]));
let before=snapshot();
const section=measuredShareSection('dental');
assert.equal(snapshot(),before);
assert(inputs.includes('Ön: 2 görünür aday; birikim 16% görünür sınır alanı'),'Translate the complete raw template before its fields');
assert(inputs.includes('Anatomik sağ: 0 görünür aday; birikim 0% görünür sınır alanı'));
const dentalExpected={
 tr:'Yüklenen tek fotoğraf · Ön: 2 görünür aday; birikim 16% görünür sınır alanı. Anatomik sağ: 0 görünür aday; birikim 0% görünür sınır alanı. Anatomik sol: Çürük adayı değerlendirilemiyor; birikim değerlendirilemiyor',
 en:'Single uploaded photo · Front: 2 visible candidates; accumulation 16% of the visible boundary area. Anatomical right: 0 visible candidates; accumulation 0% of the visible boundary area. Anatomical left: Caries candidate cannot be assessed; accumulation cannot be assessed',
 de:'Einzelnes hochgeladenes Foto · Vorne: 2 sichtbare Kandidaten; Ansammlung 16% der sichtbaren Randfläche. Anatomisch rechts: 0 sichtbare Kandidaten; Ansammlung 0% der sichtbaren Randfläche. Anatomisch links: Karieskandidat nicht beurteilbar; Ansammlung nicht beurteilbar'};
assert.equal(section.text,dentalExpected[language]);
const fallback={tr:'kararlı eşik bulunamadı',en:'no stable threshold found',de:'keine stabile Schwelle gefunden'};
for(const [quality,value,validTrials] of [['valid',-1,24],['invalid',0,24],['valid',null,undefined]]){
 const hearing={id:'synthetic-hearing-composition',timestamp:ISO,quality,value,validTrials,unit:'dB SNR'};
 localStorage.setItem('attune_hearing_history_v1',JSON.stringify([hearing]));before=snapshot();inputs.length=0;
 const result=measuredShareSection('hearing');
 assert.equal(snapshot(),before);
 const count=validTrials===undefined?'Kaydedilmemiş sayıda':String(validTrials);
 const threshold=quality==='valid'&&value!==null?'-1 dB SNR':'kararlı eşik bulunamadı';
 assert(inputs.includes(count+' geçerli üçlü · '+threshold),'DIN template must reach translation with raw fields');
 const expectedCount=validTrials===undefined?{tr:'Kaydedilmemiş sayıda',en:'Unrecorded number of',de:'Nicht erfasste Anzahl'}[language]:String(validTrials);
 const triplets={tr:'geçerli üçlü',en:'valid triplets',de:'gültige Zahlentripel'}[language];
 assert.equal(result.text,expectedCount+' '+triplets+' · '+(quality==='valid'&&value!==null?'-1 dB SNR':fallback[language]));
 if(language!=='tr')assert(!/geçerli üçlü|kararlı eşik|birikim/.test(result.text));
 assert.equal(result.dateTr,new Date(ISO).toLocaleString(core.LOCALES[language]));
}
console.log('PASS '+language+': complete Dental/DIN templates, numeric zero/rounding, unavailable results and byte-identical records/consents');

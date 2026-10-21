// Actual storage/selectors with synthetic in-memory records. No user profile IO.
require('./ts_loader.js');
const assert=require('node:assert/strict');
const values=new Map();global.localStorage={getItem:k=>values.get(k)??null,setItem:(k,v)=>values.set(k,String(v)),removeItem:k=>values.delete(k)};
global.window=new EventTarget();global.document=new EventTarget();
Object.defineProperty(global,'navigator',{value:{locks:{request:async(_name,fn)=>fn()}},configurable:true});
const {setLanguage,LOCALES}=require('../../apps/vehicle-app/src/i18n/core.ts');
const {appendHealthRecord}=require('../../apps/vehicle-app/src/utils/healthRecords.ts');
const {getMentalSummary}=require('../../apps/vehicle-app/src/utils/healthSelectors.ts');
const ISO='2026-10-20T12:34:56.000Z',latestKey='togg_health_latest_mental',historyKey='togg_health_mental_history';
localStorage.setItem('attune_health_processing_v1',JSON.stringify({version:1,services:{mental:{at:ISO,permissions:['recognition','conversation','speech']}}}));
(async()=>{
 setLanguage('de');const record={id:'synthetic-mental-locale-fixture',timestamp:ISO,themes:['Synthetic theme'],summaryText:'Synthetic nonpersonal summary'};
 await appendHealthRecord('mental',record);
 const saved=JSON.parse(localStorage.getItem(latestKey));assert.equal(saved.timestamp,ISO);assert(!Object.hasOwn(saved,'dateTr'));
 assert.deepEqual(JSON.parse(localStorage.getItem(historyKey)),[record]);
 // A pre-existing locale string must not win over its raw timestamp, and
 // display reads/switches must not rewrite any record/consent bytes.
 localStorage.setItem(latestKey,JSON.stringify({...saved,dateTr:'STALE GERMAN SNAPSHOT'}));
 const snapshot=()=>JSON.stringify([...values].filter(([k])=>k!=='attune.language.v1'));
 const before=snapshot();
 for(const language of ['tr','en','de']){setLanguage(language);assert.equal(getMentalSummary(false).dateTr,new Date(ISO).toLocaleString(LOCALES[language]));assert.equal(snapshot(),before);}
 const {measuredShareSection}=require('../../apps/vehicle-app/src/utils/healthShare.ts');
 const dental={id:'synthetic-dental',timestamp:ISO,sourceType:'upload',measurements:[
   {pose:'FRONT',caries:{value:2,quality:'valid'},accumulation:{value:null,quality:'insufficient'}},
   {pose:'LEFT',caries:{value:null,quality:'insufficient'},accumulation:{value:5,quality:'valid'}}]};
 localStorage.setItem('attune_dental_history_v1',JSON.stringify([dental]));
 localStorage.setItem('attune_hearing_history_v1',JSON.stringify([{id:'synthetic-hearing',timestamp:ISO,quality:'valid',thresholds:[{ear:'left',frequency:1000,status:'threshold',value:-30},{ear:'right',frequency:2000,status:'upper-limit',value:null}]}]));
 const stored=snapshot();
 for(const [language,terms] of Object.entries({en:['Single uploaded photo','2 visible candidates','accumulation','cannot be assessed','Left','no threshold found'],de:['Einzelnes hochgeladenes Foto','2 sichtbare Kandidaten','Ansammlung','nicht beurteilbar','Links','keine Schwelle gefunden']})){
   setLanguage(language);const text=measuredShareSection('dental').text+' '+measuredShareSection('hearing').text;
   for(const term of terms)assert(text.includes(term),text);
   for(const term of ['Yüklenen tek fotoğraf','birikim','görünür aday','değerlendirilemiyor','eşik bulunamadı'])assert(!text.includes(term),text);
   assert.equal(snapshot(),stored);
 }
 setLanguage('tr');assert(measuredShareSection('dental').text.includes('2 görünür aday'));
 localStorage.setItem(latestKey,JSON.stringify({id:'legacy-fixture',dateTr:'Original legacy date without raw timestamp',summaryText:'Synthetic'}));
 assert.equal(getMentalSummary(false).dateTr,'Original legacy date without raw timestamp');
 console.log('PASS: new writes retain raw timestamp; live locale formatting ignores stale snapshot; old undated records preserved; no read-time record/consent rewrites');
})().catch(error=>{console.error(error);process.exitCode=1;});

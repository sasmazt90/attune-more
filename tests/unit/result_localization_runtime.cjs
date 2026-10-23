/* Controlled result labels, optional dynamic fields and readonly history. */
require('./ts_loader.js');
const assert=require('assert/strict');
const stored=new Map();global.localStorage={getItem:k=>stored.get(k)??null,setItem:(k,v)=>stored.set(k,String(v))};
global.window=new EventTarget();global.CustomEvent=class extends Event{constructor(type,options){super(type);this.detail=options?.detail;}};
const C=require('../../apps/vehicle-app/src/i18n/core.ts');
const {SKIN_TYPE_LABELS}=require('../../apps/vehicle-app/src/utils/skinOverview.ts');
const {SIGN_LABELS}=require('../../apps/vehicle-app/src/utils/skinIndicators.ts');
const {buildSkinRegionViewModel}=require('../../apps/vehicle-app/src/data/skinDemoFixture.ts');
const {translateMood}=require('../../apps/vehicle-app/src/utils/mentalHistory.ts');
const {moduleOverview,formatHistoryValue}=require('../../apps/vehicle-app/src/utils/healthHistorySeries.ts');
const current={id:'readonly-source',timestamp:'2026-10-23T10:00:00Z',schemaVersion:3,completed:true,consented:true,themes:['uyku düzeni','iş stresi']};
const original=JSON.stringify(current);
for(const language of ['en','de']){
 C.setLanguage(language);
 const expected=language==='en'?{dry:'Dry',combination:'Combination',sag:'Sagging',mood:'Stressed Tired Relaxed Neutral'}:{dry:'Trocken',combination:'Mischhaut',sag:'Hauterschlaffung',mood:'Angespannt Müde Entspannt Neutral'};
 assert.equal(C.t(SKIN_TYPE_LABELS.dry),expected.dry);
 assert.equal(C.t(SKIN_TYPE_LABELS.combination),expected.combination);
 assert.equal(C.t(SIGN_LABELS.sag),expected.sag);
 for(const label of ['Parlaklık','parlaklık','Cilt parlaklığı','Cilt Parlaklığı','cilt parlaklığı','Cilt Parlaklık Skoru','Ton / Parlaklık','Ton / parlaklık','Ton/Parlaklık','Yüksek parlaklık','Dengeli']){
  const translated=C.t(label);assert(!/parlak|cilt|dengeli/i.test(translated),`${label}: ${translated}`);
 }
 assert.equal(translateMood('STRESSED TIRED RELAXED NEUTRAL'),expected.mood);
 assert.equal(C.t('PRIVATE Öztürk Straße İı'), 'PRIVATE Öztürk Straße İı');
 const overview=C.t(moduleOverview('mental',[current]).text);
 for(const tr of ['görüşme','uyku düzeni','iş stresi'])assert(!overview.includes(tr),overview);
 assert(!formatHistoryValue(2,'aday').includes('aday'));
 for(const value of [0,5,-5,12.5]){
  const region=buildSkinRegionViewModel('forehead',{isBaseline:false,regions:{forehead:{rednessScore:10,luminanceScore:50,textureVariance:0,changeFromBaselinePct:value}}});
  const translated=C.t(region.observation.details);
  assert(!translated.includes('bölgesinin'),translated);
  assert(!translated.includes('ölçüldü'),translated);
  assert(translated.includes(String(value)),translated);
 }
 assert.equal(JSON.stringify(current),original);
}
// Render the actual result components with the locale supplied by the hook.
// Effects/capture do not run in server rendering; source records remain raw.
const Module=require('module'),originalLoad=Module._load;
const {localizedNode}=require('../../apps/vehicle-app/src/i18n/render.ts');
Module._load=function(id,parent,...rest){
 if(id.endsWith('/i18n/LanguageProvider'))return {useTranslations:()=>({language:C.getLanguage(),text:C.t,node:localizedNode})};
 return originalLoad.call(this,id,parent,...rest);
};
try{
 const React=require('react'),{renderToStaticMarkup}=require('react-dom/server');
 global.React=React; // The shared test loader uses classic JSX; Next uses the automatic runtime.
 const {SkinRegionSummary}=require('../../apps/vehicle-app/src/components/skin/SkinRegionSummary.tsx');
 const {DentalRecordDetail}=require('../../apps/vehicle-app/src/components/DentalRecordDetail.tsx');
 const {LetterVisionResult}=require('../../apps/vehicle-app/src/components/LetterVisionResult.tsx');
 const {ContinuousVisionResult}=require('../../apps/vehicle-app/src/components/ContinuousVisionResult.tsx');
 for(const language of ['en','de']){
  C.setLanguage(language);
  const region=buildSkinRegionViewModel('forehead',{regions:{forehead:{rednessScore:10,luminanceScore:75,textureVariance:0,changeFromBaselinePct:0}}});
  const components=[
   React.createElement(SkinRegionSummary,{currentRegion:region,onOpenModal:()=>{},onNavigateToCare:()=>{}}),
   React.createElement(DentalRecordDetail,{record:{id:'dental-readonly',measurements:[{pose:'FRONT',caries:{value:2},accumulation:{value:4},alignment:{rows:{upper:{value:0}}}}]}}),
   React.createElement(LetterVisionResult,{result:{trials:[]}}),
   React.createElement(ContinuousVisionResult,{result:{trials:[],validTrials:0,notVisible:0,invalidPresentations:0}}),
  ];
  for(const component of components){
   const text=renderToStaticMarkup(component).replace(/<[^>]*>/g,' ');
   assert(!/(Parlaklık|parlaklık|Dengeli|görünür aday|yön dağılımı|Yeterli yanıt|Göremedi|Çürük|Kızarıklık|Önerilen|Sonraki|Önceki)/.test(text),text);
  }
 }
}finally{Module._load=originalLoad;delete global.React;}
console.log('PASS: EN/DE skin types, sagging, mood/history, units, zero/positive/negative dynamic results; source records unchanged');

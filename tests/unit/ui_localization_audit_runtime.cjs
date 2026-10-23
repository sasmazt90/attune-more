/* Render production UI text with deterministic state; no effects, devices or services. */
require('./ts_loader.js');
const assert=require('assert/strict'),Module=require('module'),path=require('path'),fs=require('fs');
const React=require('react'),{renderToStaticMarkup}=require('react-dom/server');
global.React=React;
const storage=new Map();global.localStorage={getItem:k=>storage.get(k)??null,setItem:(k,v)=>storage.set(k,String(v)),removeItem:k=>storage.delete(k)};
global.window=new EventTarget();global.CustomEvent=class extends Event{constructor(type,options){super(type);this.detail=options?.detail;}};
const C=require('../../apps/vehicle-app/src/i18n/core.ts'),{localizedNode}=require('../../apps/vehicle-app/src/i18n/render.ts');
const root=path.resolve('apps/vehicle-app/src'),originalLoad=Module._load;
let states={},counts={},current='',pathname='/profile';
const noOp=()=>{},guidance={cancel:noOp,phase:noOp,issue:noOp,say:()=>{throw Error('No speech call permitted in text audit');}};
const mentalRecord={id:'mental-fixture',timestamp:'2026-10-23T10:00:00Z',schemaVersion:3,completed:true,consented:true,themes:['uyku düzeni','iş stresi'],summaryText:'STRESSED TIRED RELAXED NEUTRAL'};
Module._load=function(id,parent,...rest){
 const file=parent?.filename?.replace(root+'/','');
 if(id==='react'&&parent?.filename?.startsWith(root))return {...React,useState:initial=>{
  const index=counts[file]||0;counts[file]=index+1;
  const override=states[file]?.[index];
  return React.useState(override===undefined?(file==='components/InformationButton.tsx'&&index===0?true:initial):override);
 }};
 if(id.endsWith('/i18n/LanguageProvider'))return {useTranslations:()=>({language:C.getLanguage(),locale:C.getLocale(),text:C.t,node:localizedNode})};
 if(id.endsWith('/i18n/useLocaleSwitchLock'))return {useLocaleSwitchLock:noOp,useLanguageSwitchLocked:()=>false};
 if(id.endsWith('/context/VehicleContext'))return {useVehicle:()=>({isParked:true,vehicleState:'PARK'})};
 if(id.endsWith('/utils/audioGuidance'))return {useGuidance:()=>guidance};
 if(id.endsWith('/utils/skinInference'))return {SkinInference:class{}};
 if(id.endsWith('/utils/visionInference'))return {VisionInference:class{}};
 if(id.endsWith('/utils/skinLocalMaps'))return {SkinLocalAnalysis:class{}};
 if(id.endsWith('/utils/useMentalConversation'))return {useMentalConversation:()=>({phase:'completed',active:false,voiceEnabled:false,messages:[],history:[mentalRecord],serviceConsent:true,notice:'Tamamlanan görüşmenin tek özeti kaydedildi.',...new Proxy({},{get:()=>noOp})})};
 if(id==='next/navigation')return {useRouter:()=>({push:noOp}),usePathname:()=>pathname,useSearchParams:()=>new URLSearchParams()};
 if(id==='next/link')return {__esModule:true,default:({children,...props})=>React.createElement('a',props,children)};
 if(id==='next/image')return {__esModule:true,default:({priority,fill,unoptimized,...props})=>React.createElement('img',props)};
 if(id.endsWith('/AccessibleDialog')||id==='./AccessibleDialog')return {AccessibleDialog:({title,children})=>React.createElement('section',{'role':'dialog','aria-label':title},children)};
 if(id==='@packages/health-profile/mockData')return originalLoad.call(this,path.resolve('packages/health-profile/mockData.ts'),parent,...rest);
 return originalLoad.call(this,id,parent,...rest);
};
const load=file=>require(path.join(root,file));
let rendered=0;
function render(name,Component,props={},overrides={}){
 current=name;states=overrides;counts={};
 const html=renderToStaticMarkup(React.createElement(Component,props));
 const chunks=[...html.matchAll(/>([^<>]+)</g),...html.matchAll(/(?:aria-label|title|placeholder|alt)="([^"]*)"/g)].map(m=>m[1].replace(/&amp;/g,'&').replace(/&quot;/g,'"').replace(/&#x27;/g,"'").replace(/&lt;/g,'<').replace(/&gt;/g,'>').replace(/\s+/g,' ').trim()).filter(Boolean);
 for(const text of chunks){
  assert(!/[çğıİŞĞ]/.test(text),`${C.getLanguage()} ${name}: ${text}`);
  assert.equal(C.t(text).replace(/\s/g,''),text.replace(/\s/g,''),`${C.getLanguage()} ${name}: untranslated controlled text: ${text}`);
 }
 rendered++;return html;
}
try{
 const {SKIN_REGIONS}=load('data/skinDemoFixture.ts');
 const {HealthModuleIcon}=load('components/HealthModuleIcon.tsx');
 const {CameraPreparation}=load('components/CameraPreparation.tsx');
 const {RecordHistory}=load('components/RecordHistory.tsx');
 const {MentalSessionRows}=load('components/MentalSessionRows.tsx');
 const {HealthHistoryOverview}=load('components/HealthHistoryOverview.tsx');
 const {SkinActionsModal}=load('components/skin/SkinActionsModal.tsx');
 const {SkinObservationModal}=load('components/skin/SkinObservationModal.tsx');
 const {SkinTrendModal}=load('components/skin/SkinTrendModal.tsx');
 const {LetterVisionResult}=load('components/LetterVisionResult.tsx');
 const {HealthStartCard}=load('components/HealthStartCard.tsx');
 const {HealthConsentGate}=load('components/HealthConsentGate.tsx');
 const {buildSkinRoutine}=load('utils/skinRoutine.ts');
 const {LanguageSelector}=load('components/LanguageSelector.tsx');
 const Hearing=load('app/hearing/page.tsx').default,Mental=load('app/mental/page.tsx').default;
 const timestamp='2026-10-23T10:00:00Z';
 const letterTrial={id:'letter-trial',eye:'RIGHT',valid:true,letter:'E',transform:{rotation:0,mirrored:false,mirrorAxis:'x',order:'mirror-then-rotate'},answer:{letter:'E',transform:{rotation:0,mirrored:false,mirrorAxis:'x',order:'mirror-then-rotate'}},renderedGeometry:{viewportWidthCssPx:40,viewportHeightCssPx:40,pathWidthCssPx:20,pathHeightCssPx:20,strokeWidthCssPx:4}};
 const {LETTER_PROTOCOL}=load('utils/spokenVision.ts');
 const records={vision:[{id:'v',timestamp,protocolVersion:LETTER_PROTOCOL,trials:[letterTrial]}],skin:[{id:'s',timestamp,analysisMode:'instant-appearance-v2',indicators:{forehead:[{id:'redness',score:12,unit:'Renk indeksi / 100',method:'fixture-v1'}]}}],dental:[{id:'d',timestamp,sourceType:'camera',measurements:[{pose:'FRONT',caries:{value:2,quality:'valid'},accumulation:{value:4,quality:'valid'},alignment:{quality:'valid',rows:{upper:{value:0}}}}]}],hearing:[{id:'h',timestamp,value:-4,validTrials:3,digitAccuracy:.5,tripletAccuracy:.3}],mental:[mentalRecord]};
 for(const language of ['en','de']){
  C.setLanguage(language);
  for(const id of Object.keys(records))render('start-'+id,HealthStartCard,{module:id});
  for(const id of Object.keys(records)){pathname='/'+id;render('consent-'+id,HealthConsentGate,{children:null});}pathname='/profile';
  const icon=render('mental-icon',HealthModuleIcon,{module:'mental'});assert(icon.includes('lucide-brain')&&!icon.includes('heart-pulse'));
  render('camera-empty',CameraPreparation,{position:'Konum hazır',fresh:false});
  render('language-dialog',LanguageSelector,{}, {'components/LanguageSelector.tsx':{0:true,1:'Dil tercihi kaydedilemedi.'}});
  render('mental-completion',Mental,{}, {'app/mental/page.tsx':{0:true}});
  render('record-read-error',RecordHistory,{parked:true},{'components/RecordHistory.tsx':{4:'Göz Sağlığı, Cilt Sağlığı: kayıtlar okunamadı; veriler korunuyor.',6:false}});
  render('mental-record-dialog',MentalSessionRows,{records:[mentalRecord],parked:true,busy:false,onDelete:noOp},{'components/MentalSessionRows.tsx':{0:mentalRecord.id}});
  const tones=[{ear:'left',frequency:250,value:null,status:'upper-limit'},{ear:'right',frequency:1000,repeat:true,value:-30,status:'threshold'}];
  render('hearing-tones',Hearing,{}, {'app/hearing/page.tsx':{0:'result',5:tones,7:{thresholds:tones,totalPresentations:12,catchFalsePositive:0,catchTrials:2,quality:'unreliable'}}});
  render('hearing-digits',Hearing,{}, {'app/hearing/page.tsx':{0:'result',7:{value:null,history:[{digits:[1,2,3],answer:[1,2,3],correct:true}],validTrials:1}}});
  for(const id of Object.keys(records)){
   const record=id==='mental'?mentalRecord:id==='hearing'?{id:'h',value:null,validTrials:2,digitAccuracy:.5}:id==='dental'?{id:'d',measurements:[{pose:'FRONT',caries:{value:2},accumulation:{value:4},alignment:{rows:{upper:{value:0}}}}]}:id==='vision'?{id:'v',protocolVersion:'landolt-orientation-guided-v2',trials:[],validTrials:0,notVisible:0,invalidPresentations:0}:{id:'s',clinicalNoteTr:'Bu kayıtta bölge ölçümü yok.'};
   const row={category:id,record};
   render('record-'+id,RecordHistory,{parked:true},{'components/RecordHistory.tsx':{0:[row],2:row,3:row,6:false}});
   render('history-analysis-'+id,HealthHistoryOverview,{parked:true},{'components/HealthHistoryOverview.tsx':{0:records,1:id}});
  }
  render('letter-scores',LetterVisionResult,{result:{trials:[letterTrial]}});
  for(const type of ['normal','dry','oily','combination'])render('skin-routine-'+type,SkinActionsModal,{region:{...SKIN_REGIONS.forehead,routine:buildSkinRoutine([{id:type==='normal'?'acne':'redness',score:12,measurement:{quality:'valid'}}],{value:type,quality:'valid'})},onClose:noOp,onNavigateToCare:noOp});
  for(const region of Object.values(SKIN_REGIONS)){
   render('skin-actions-'+region.id,SkinActionsModal,{region,onClose:noOp,onNavigateToCare:noOp});
   render('skin-observation-'+region.id,SkinObservationModal,{region,onClose:noOp});
   render('skin-trend-'+region.id,SkinTrendModal,{region,onClose:noOp});
  }
  storage.set('attune_demo_mode','true');
  for(const region of Object.values(SKIN_REGIONS))render('skin-demo-trend-'+region.id,SkinTrendModal,{region,onClose:noOp});
  storage.delete('attune_demo_mode');
  for(const file of ['app/page.tsx','app/profile/page.tsx','app/privacy/page.tsx','app/care/page.tsx','app/skin/page.tsx','app/dental/page.tsx','app/vision/page.tsx'])render(file,load(file).default);
  render('profile-share-dialog',load('app/profile/page.tsx').default,{}, {'app/profile/page.tsx':{0:true}});
  const slot={id:'slot',providerName:'Fixture Specialist',clinicName:'Fixture Clinic',specialty:'Dermatoloji',locationLabel:'Çevrimiçi',displayTime:'Saati sağlayıcıda doğrulayın',dateTime:'2026-10-24T10:00:00Z',isOnline:true,travelTimeMin:null,calendarConflict:null,sourceBadge:'Demo Randevu Verisi',matchScore:null};
  for(const mode of ['CONFIRM_MODAL','BOOKED'])render('care-'+mode,load('app/care/page.tsx').default,{}, {'app/care/page.tsx':{5:[slot],6:false,9:slot,10:mode}});
  for(const status of ['CONFIRM','PARTIAL','FAILED'])render('privacy-'+status,load('app/privacy/page.tsx').default,{}, {'app/privacy/page.tsx':{16:status,17:{local:true,backend:false}}});
  const {CockpitHeader}=load('components/CockpitHeader.tsx');render('navigation',CockpitHeader,{}, {'components/CockpitHeader.tsx':{0:true}});
 }
 console.log(JSON.stringify({status:'PASS',renderedStates:rendered,languages:['en','de'],scope:'All routes/navigation/settings plus five health modules, result/history dialogs, criteria, information popups, skin action/observation/trend modals. SSR state fixtures; no browser/device/service calls.'}));
}finally{Module._load=originalLoad;delete global.React;}

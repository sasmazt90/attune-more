/** Presentation contracts: actual components; no audio, health inference or data writes. */
require('./ts_loader.js');
const assert=require('node:assert/strict'),Module=require('node:module');
global.React=require('react');const {renderToStaticMarkup}=require('react-dom/server'),h=React.createElement;
global.window=new EventTarget();const store=new Map();global.localStorage={getItem:k=>store.get(k)??null,setItem:(k,v)=>store.set(k,String(v))};
const core=require('../../apps/vehicle-app/src/i18n/core.ts');
const {informationContent}=require('../../apps/vehicle-app/src/components/InformationButton.tsx');
for(const lang of ['tr','en','de']){
 core.setLanguage(lang);
 const link=h('a',{href:'/privacy'},'Existing privacy link');const control=h('label',null,h('input',{type:'checkbox'}),'Existing consent control');
 const content=informationContent([h('p',{key:'sentences'},'First point. Second point.'),h('p',{key:'decimal'},'The result is 3.5 dB.'),link,control]);
 const html=renderToStaticMarkup(h('div',null,content));assert.equal((html.match(/<li/g)||[]).length,3);assert(html.includes('3.5 dB.'));assert(html.includes('href="/privacy"'));assert(html.includes('type="checkbox"'));
 assert(!renderToStaticMarkup(h('div',null,informationContent(h('p',null,'The result is 3.5 dB.')))).includes('<li'));
}
let parked=true,locked=false,language='tr';const original=Module._load;
Module._load=function(request,parent,...args){
 if(parent?.filename.endsWith('LanguageSelector.tsx')){
  if(request==='../context/VehicleContext')return {useVehicle:()=>({isParked:parked})};
  if(request==='../i18n/useLocaleSwitchLock')return {useLanguageSwitchLocked:()=>locked};
  if(request==='../i18n/LanguageProvider')return {useTranslations:()=>({language,text:x=>x})};
 }
 return original.call(this,request,parent,...args);
};
const {LanguageSelector}=require('../../apps/vehicle-app/src/components/LanguageSelector.tsx');
for(language of ['tr','en','de'])for(const [p,l] of [[true,false],[false,false],[true,true]]){
 parked=p;locked=l;const html=renderToStaticMarkup(h(LanguageSelector));const select=html.match(/<select[^>]*>/)[0];assert.equal(/\sdisabled(?:=|\s|>)/.test(select),!parked||locked);assert.equal((html.match(/<option/g)||[]).length,3);assert(!html.includes('<button'));assert(!html.includes('role="dialog"'));assert(html.includes('attune-language'));
}
Module._load=original;
console.log('PASS actual language-only header component, PARK/assessment-lock gates, three locales, semantic information bullets and preservation of decimal text/links/consent controls; no synthesis.');


/** Actual locale consumer and subscription source; storage writes represent another tab. */
require('./ts_loader.js');const assert=require('assert/strict'),fs=require('fs'),ts=require('typescript');
global.window=new EventTarget();const values=new Map([['attune.language.v1','en'],['health','unchanged'],['consent','unchanged']]);global.localStorage={getItem:k=>values.get(k)??null,setItem:(k,v)=>values.set(k,String(v))};
const C=require('../../apps/vehicle-app/src/i18n/core.ts'),L=require('../../apps/vehicle-app/src/i18n/locks.ts');
const text=fs.readFileSync('apps/vehicle-app/src/i18n/LanguageProvider.tsx','utf8'),ast=ts.createSourceFile('provider.tsx',text,ts.ScriptTarget.Latest,true,ts.ScriptKind.TSX);let subscribe;
function visit(n){if(ts.isFunctionDeclaration(n)&&n.name?.text==='subscribe')subscribe=n.getText(ast);ts.forEachChild(n,visit);}visit(ast);
const js=ts.transpileModule(subscribe,{compilerOptions:{target:ts.ScriptTarget.ES2022,module:ts.ModuleKind.None}}).outputText;
const deps={...C,...L,window};const connect=new Function(...Object.keys(deps),js+';return subscribe;')(...Object.values(deps));let renders=0,cancels=0;
const dispose=connect(()=>renders++);window.addEventListener('attune-locale-media-cancel',()=>cancels++);
const remote=lang=>{values.set(C.LANGUAGE_KEY,lang);const event=new Event('storage');event.key=C.LANGUAGE_KEY;window.dispatchEvent(event);};
L.setLanguageSwitchLock('hearing',true);L.setLanguageSwitchLock('vision',true);remote('de');assert.equal(C.getLanguage(),'en');assert.equal(C.getLocale(),'en-US');assert(C.languageURL('/api/test').includes('language=en'));assert.equal(renders,0);assert.equal(cancels,0);assert.throws(()=>C.setLanguage('tr'),/ASSESSMENT_IN_PROGRESS/);
L.setLanguageSwitchLock('hearing',false);assert.equal(C.getLanguage(),'en');L.setLanguageSwitchLock('vision',false);assert.equal(C.getLanguage(),'de');assert.equal(renders,1);assert.equal(cancels,1);remote('tr');assert.equal(C.getLanguage(),'tr');assert.equal(renders,2);assert.equal(cancels,2);assert.equal(values.get('health'),'unchanged');assert.equal(values.get('consent'),'unchanged');dispose();console.log('PASS actual core/API locale remains frozen under multi-owner local lock; foreign tab changes defer until final unlock, without storage rewrites or in-flight cancellation');

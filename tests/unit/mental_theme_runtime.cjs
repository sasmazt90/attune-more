require('./ts_loader.js');const assert=require('assert/strict');
global.window=new EventTarget();const store=new Map();global.localStorage={getItem:k=>store.get(k)??null,setItem:(k,v)=>store.set(k,String(v))};
const C=require('../../apps/vehicle-app/src/i18n/core.ts'),M=require('../../apps/vehicle-app/src/i18n/mentalThemes.ts'),H=require('../../apps/vehicle-app/src/utils/mentalHistory.ts'),S=require('../../apps/vehicle-app/src/utils/healthSelectors.ts');
const record=(id,theme)=>({id,date:'2026-10-21T00:00:00Z',summaryText:'Synthetic private text unchanged',themes:[theme],schemaVersion:3,completed:true,consented:true});const rows=[record('tr','iş yaşamı'),record('en','working life'),record('de','Arbeitsleben')];
store.set('togg_health_mental_history',JSON.stringify(rows));store.set('togg_health_latest_mental',JSON.stringify({...rows[1],themes:['working life','sleep pattern'],primaryTheme:'old localized snapshot'}));store.set('consent','unchanged');
const snapshot=()=>JSON.stringify([...store].filter(([k])=>k!==C.LANGUAGE_KEY));const before=snapshot();
for(const language of C.LANGUAGES){C.setLanguage(language);const stats=H.mentalThemeStats(rows);assert.equal(stats.rows.length,1);assert.equal(stats.rows[0].theme,'iş yaşamı');assert.equal(stats.rows[0].count,3);assert.equal(stats.rows[0].percent,100);assert.equal(rows.filter(h=>h.themes.some(t=>M.canonicalMentalTheme(t)===stats.rows[0].theme)).length,3);assert.equal(M.displayMentalTheme('working life'),C.t('iş yaşamı'));assert.equal(S.getMentalSummary(false).primaryTheme,[C.t('iş yaşamı'),C.t('uyku düzeni')].join(' • '));assert.equal(snapshot(),before);}
assert.equal(M.canonicalMentalTheme('PRIVATE Straße İı'),'PRIVATE Straße İı');assert.equal(M.displayMentalTheme('PRIVATE Straße İı'),'PRIVATE Straße İı');assert.equal(snapshot(),before);console.log('PASS TR/EN/DE stable theme identity, mixed legacy grouping and drill-down, per-theme localized sharing, original stored bytes/custom text/consents unchanged');
const vocabulary=require('../../shared/localization/mental-themes.json'),catalog=require('../../shared/localization/messages.json');
for(const raw of [...vocabulary.session,...vocabulary.conversation]){
 const row=Object.values(catalog).find(m=>m.tr===raw);assert(row,raw);
 for(const language of C.LANGUAGES){C.setLanguage(language);for(const alias of [row.tr,row.en,row.de])assert.equal(M.displayMentalTheme(alias),row[language]);}
}assert.equal(snapshot(),before);console.log('PASS all controlled session/conversation aliases render in all three languages without storage changes');

// Actual catalog/template engine and actual Vision text producers. No media capture.
require('./ts_loader.js');
const assert=require('assert/strict'),fs=require('fs'),ts=require('typescript');
const C=require('../../apps/vehicle-app/src/i18n/core.ts');
const V=require('../../apps/vehicle-app/src/utils/spokenVision.ts');
const F=require('../../apps/vehicle-app/src/utils/visionFlow.ts');
const source=fs.readFileSync('apps/vehicle-app/src/app/vision/SpokenLetterPage.tsx','utf8');
const ast=ts.createSourceFile('vision.tsx',source,ts.ScriptTarget.Latest,true,ts.ScriptKind.TSX);
const constants={};
for(const statement of ast.statements)if(ts.isVariableStatement(statement))for(const d of statement.declarationList.declarations){
 if(['TEXT','EYE_TEXT'].includes(d.name.getText(ast)))constants[d.name.getText(ast)]=new Function('return '+d.initializer.getText(ast))();
}
const directions={tr:['düz','sağa yatmış','baş aşağı','sola yatmış'],en:['upright','tilted right','upside down','tilted left'],de:['aufrecht','nach rechts geneigt','auf dem Kopf','nach links geneigt']};
const missing={tr:'harf anlaşılmadı',en:'letter not understood',de:'Buchstabe nicht verstanden'};
const noDirection={tr:'yön anlaşılmadı',en:'orientation not understood',de:'Ausrichtung nicht verstanden'};
const mirrored={tr:' ve aynalı',en:' and mirrored',de:' und gespiegelt'};
const prefix={tr:'Algılanan: ',en:'Detected: ',de:'Erkannt: '};
const suffixes=[
 ['Yalnız harf bekleniyor.','Waiting only for the letter.','Es wird nur der Buchstabe erwartet.'],
 ['Yalnız yön bekleniyor.','Waiting only for orientation.','Es wird nur die Ausrichtung erwartet.'],
 ['Baş aşağı mı, aynalı mı?','Upside down or mirrored?','Auf dem Kopf oder gespiegelt?'],
 ['Yanıtı yeniden söyleyin.','Say your response again.','Sagen Sie Ihre Antwort erneut.'],
 ['Koşullar düzelince bu harf için yeniden yanıt verin.','Answer this letter again once conditions improve.','Antworten Sie erneut auf diesen Buchstaben, sobald die Bedingungen besser sind.'],
];
const evidence={};
for(const [language,index] of [['tr',0],['en',1],['de',2]]){
 let dynamic=0;
 for(const letter of [undefined,...'ABEFPR'])for(const rotation of [undefined,0,90,180,270])for(const mirror of [false,true])for(const suffix of suffixes){
  const answer={letter,rotation,mirrored:mirror},source=`Algılanan: ${V.describeAnswer(answer)}. ${suffix[0]}`;
  const effective=rotation??(mirror?0:undefined);
  const direction=effective===undefined?noDirection[language]:directions[language][effective/90]+(mirror?mirrored[language]:'');
  assert.equal(C.t(source,language),prefix[language]+(letter||missing[language])+' · '+direction+'. '+suffix[index],source+' / '+language);
  dynamic++;
 }
 for(const [eye,base] of [['RIGHT',{en:'We are testing your right eye. Close or cover your left eye. Look at the letter area with your open eye.',de:'Wir testen Ihr rechtes Auge. Schließen Sie Ihr linkes Auge oder decken Sie es ab. Schauen Sie mit dem offenen Auge auf den Buchstabenbereich.'}],['LEFT',{en:'We are testing your left eye. Close or cover your right eye. Look at the letter area with your open eye.',de:'Wir testen Ihr linkes Auge. Schließen Sie Ihr rechtes Auge oder decken Sie es ab. Schauen Sie mit dem offenen Auge auf den Buchstabenbereich.'}]]){
  const expected=language==='tr'?F.eyeInstruction(eye):base[language];
  assert.equal(C.t(F.eyeInstruction(eye),language),expected);dynamic++;
  for(const condition of Object.values(constants.TEXT)){
   assert.equal(C.t(F.eyeInstruction(eye)+' '+condition,language),expected+' '+C.t(condition,language));dynamic++;
  }
 }
 for(const a of Object.values(constants.EYE_TEXT))for(const b of Object.values(constants.EYE_TEXT)){
  const expected=language==='tr'?`Sol göz: ${a} · Sağ göz: ${b}`:language==='en'?`Left eye: ${C.t(a,language)} · Right eye: ${C.t(b,language)}`:`Linkes Auge: ${C.t(a,language)} · Rechtes Auge: ${C.t(b,language)}`;
  assert.equal(C.t(`Sol göz: ${a} · Sağ göz: ${b}`,language),expected);dynamic++;
 }
 for(const [side,native] of [['Sağ',{tr:'Sağ göz',en:'Right eye',de:'Rechtes Auge'}],['Sol',{tr:'Sol göz',en:'Left eye',de:'Linkes Auge'}]])for(let i=1;i<=12;i++){
  assert.equal(C.t(`${side} göz · ${i}/12`,language),`${native[language]} · ${i}/12`);dynamic++;
 }
 for(const [tr,en,de] of [
  ['Kamera karesi bekleniyor','Waiting for a camera frame','Warten auf ein Kamerabild'],
  ['Toplam ortalama skor','Overall average score','Mittlerer Gesamtwert'],
  ['Harf boyutu','Letter size','Buchstabengröße'],
  ['Kaydırılabilir kartlar','carousel','Karussell'],
  ['Göz Sağlığı: kayıtlar okunamadı; veriler korunuyor.','Vision Health: records could not be read; data is preserved.','Augengesundheit: Einträge konnten nicht gelesen werden; die Daten bleiben erhalten.'],
  ['Seslendirme kapalı. Üst çubuktaki hoparlörü açıp devam edin.','Speech output is muted. Enable the speaker in the top bar and resume.','Die Sprachausgabe ist stummgeschaltet. Aktivieren Sie den Lautsprecher in der oberen Leiste und setzen Sie die Aufgabe fort.'],
 ]){assert.equal(C.t(tr,language),[tr,en,de][index]);dynamic++;}
 // Source-derived strings from status/error/notice/dialog setters must have an
 // actual translation; inventory exemptions cannot hide a displayed fallback.
 const display=new Set([...Object.values(constants.TEXT),...Object.values(constants.EYE_TEXT)]);
 const walk=n=>{
  if(ts.isCallExpression(n)&&['setError','setDialog','setAnswerNotice','stage'].includes(n.expression.getText(ast))){
   const collect=x=>{if(ts.isStringLiteralLike(x)&&x.text.includes(' '))display.add(x.text);else ts.forEachChild(x,collect);};
   for(const argument of n.arguments)collect(argument);
  }
  ts.forEachChild(n,walk);
 };walk(ast);
 for(const text of display)if(language!=='tr')assert.notEqual(C.t(text,language),text,language+' missing display translation: '+text);
 // Never translate raw/private transcripts or infer an answer from display text.
 assert.equal(C.t('PRIVATE: Straße, İı, user utterance',language),'PRIVATE: Straße, İı, user utterance');
 evidence[language]={status:'PASS',dynamicAssertions:dynamic,displayStatuses:display.size};
}
assert(!source.includes('Header hoparlör'));
assert(fs.readFileSync('apps/vehicle-app/src/components/CardCarousel.tsx','utf8').includes('aria-roledescription={i18nText("Kaydırılabilir kartlar")}'));
// Check selected recordings and their declared scripts/locales, without changing
// the approved files or claiming physical microphone testing.
const A=require('../../apps/vehicle-app/src/i18n/approvedAudio.ts');
for(const language of C.LANGUAGES)for(const event of ['prepare','right','left','letter','orientation','reverse','repeat','first','next1','next2','next3']){
 const clip=A.approvedClip(language,'vision','vision:'+event);assert(clip,event);assert.equal(clip.language,language);assert.equal(clip.applicationLocale,C.LOCALES[language]);
 const tr=A.approvedClip('tr','vision','vision:'+event).exactScript;
 assert.equal(clip.exactScript,C.t(tr,language),event+' approved script '+language);
}
console.log(JSON.stringify(evidence));

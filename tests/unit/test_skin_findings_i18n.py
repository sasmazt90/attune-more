"""Skin findings UI in English and German: every catalog-backed text of the result screen (cards, overview, dialogs,
recommendations, units, reasons, acne types, date range, history chart labels) is translated; Turkish stays unchanged."""
import subprocess
from pathlib import Path
import pytest
ROOT = Path(__file__).resolve().parents[2]

# Renders the real components with renderToStaticMarkup. The language comes from the app's own core translator;
# useTranslations is pointed at the language under test, AccessibleDialog renders its content inline (no portal).
HARNESS = r'''
const assert=require('assert/strict');
const LANG=process.env.SKIN_I18N_LANGUAGE;
const store={'attune.language.v1':LANG};
global.localStorage={getItem:k=>store[k]??null,setItem:(k,v)=>{store[k]=String(v);},removeItem:k=>{delete store[k];}};
const React=require('react'),{renderToStaticMarkup}=require('react-dom/server');
const core=require('./apps/vehicle-app/src/i18n/core.ts'),render=require('./apps/vehicle-app/src/i18n/render.ts');
const LP=require('./apps/vehicle-app/src/i18n/LanguageProvider.tsx');
LP.useTranslations=()=>({language:LANG,locale:core.LOCALES[LANG],text:v=>core.t(v,LANG),node:v=>render.localizedNode(v,LANG)});
LP.useLanguage=()=>LANG;
const AD=require('./apps/vehicle-app/src/components/AccessibleDialog.tsx');
AD.AccessibleDialog=({title,children})=>React.createElement('div',{role:'dialog','aria-label':core.t(title,LANG)},render.localizedNode(children,LANG));
const F=require('./apps/vehicle-app/src/utils/skinFindings.ts'),Rec=require('./apps/vehicle-app/src/utils/skinRecommendations.ts');
const O=require('./apps/vehicle-app/src/utils/skinOverview.ts');
const {SkinFindingsPanel}=require('./apps/vehicle-app/src/components/skin/SkinFindingsPanel.tsx');
const {SkinFindingCard}=require('./apps/vehicle-app/src/components/skin/SkinFindingCard.tsx');
const {SkinRecommendationsDialog}=require('./apps/vehicle-app/src/components/skin/SkinRecommendationsDialog.tsx');
const {SkinUnmeasuredFindingsDialog}=require('./apps/vehicle-app/src/components/skin/SkinUnmeasuredFindingsDialog.tsx');
const {SkinInconclusiveFindingsDialog}=require('./apps/vehicle-app/src/components/skin/SkinInconclusiveFindingsDialog.tsx');
const {SkinDateRangeDialog}=require('./apps/vehicle-app/src/components/skin/SkinDateRangeDialog.tsx');
const {SkinFindingCallouts}=require('./apps/vehicle-app/src/components/skin/SkinFindingCallouts.tsx');
const {SkinResultView}=require('./apps/vehicle-app/src/components/skin/SkinResultView.tsx');
const h=React.createElement,out=[],add=(name,el)=>out.push([name,renderToStaticMarkup(el)]);
const ids=Object.keys(F.FINDING_DEFS),reasons=[...Object.keys(F.UNAVAILABLE_REASON_TEXT),'SOME_NEW_REASON'];
const regionOf={forehead:'forehead',periorbital:'periorbital',rightCheek:'rightCheek',leftCheek:'leftCheek',chin:'chin'};
const finding=(id,region,extra={})=>({id,region,status:'seen',pose:'FRONT',...(F.FINDING_DEFS[id].unit?{count:3}:{severity:55}),...extra});
const all=F.FINDING_VIEWS.flatMap(v=>ids.filter(id=>F.viewFindings([finding(id,regionOf[v])],v).length).map(id=>finding(id,regionOf[v],
  id==='acne'?{subtypes:{blackhead:1,papule:2},toneDiff:2.5}:id==='redness'?{severity:undefined,areaPct:12,toneDiff:3.1}:{})));
const result={version:'v',status:'measured',findings:all,unavailable:reasons.map((reason,i)=>({id:ids[i],reason}))};
// history entries carry their method version and status: only comparable values are charted (skinHistorySummary)
const history=[{at:'2026-09-01T10:00:00Z',findings:all,version:'v',status:'measured'},{at:'2026-10-01T10:00:00Z',findings:all,version:'v',status:'measured'}];
const props={scanAt:'2026-10-26T10:00:00Z',index:0,onIndex:()=>{},onGoToView:()=>{},onNavigateToCare:()=>{},onRescan:()=>{},onOverviewSel:()=>{}};
add('overview',h(SkinFindingsPanel,{...props,view:'overview',overviewSel:null,findings:all,findingsResult:result}));
for(const value of Object.keys(O.SKIN_TYPE_LABELS))for(const sensitive of [false,true])
  add('skin-type',h(SkinFindingsPanel,{...props,view:'overview',overviewSel:null,findings:all,findingsResult:result,skinType:{value,quality:'valid',sensitive}}));
for(const id of ids)add('overview-'+id,h(SkinFindingsPanel,{...props,view:'overview',overviewSel:id,findings:all,findingsResult:result}));
for(const reason of reasons)add('unavailable-'+reason,h(SkinFindingsPanel,{...props,view:'overview',overviewSel:null,findings:[],findingsResult:{version:'v',status:'unavailable',reason,findings:[],unavailable:[{id:'acne',reason}]}}));
for(const v of F.FINDING_VIEWS){
  add('missing-'+v,h(SkinFindingsPanel,{...props,view:v,overviewSel:null}));
  add('none-'+v,h(SkinFindingsPanel,{...props,view:v,overviewSel:null,findings:[],findingsResult:{version:'v',status:'measured',findings:[],unavailable:[]}}));
  add('page-'+v,h(SkinFindingsPanel,{...props,view:v,overviewSel:null,findings:[...all,{id:'mole',region:regionOf[v],status:'inconclusive',causes:['LIGHTING']}],findingsResult:result,history}));
  const items=F.viewFindings(all,v);
  items.forEach((f,i)=>add('card-'+v+'-'+f.id,h(SkinFindingCard,{view:v,items,index:i,onIndex:()=>{},history,scanAt:props.scanAt,current:result})));
}
for(const id of ['overview',...F.FINDING_VIEWS])
  add('result-'+id,h(SkinResultView,{currentRegion:{id,nameTr:'Genel Bakış',indicators:[],skinType:{value:'combination',quality:'valid'}},findings:all,findingsResult:result,findingsHistory:history,scanAt:props.scanAt,onPrev:()=>{},onNext:()=>{},onNavigateToCare:()=>{}}));
// every finding with every count/score shape, as card and as recommendations dialog
const shapes=[{count:1},{count:1,countAtLeast:true},{count:3},{count:8},{count:15},{count:30},{countRange:'1-3',count:undefined},{severity:undefined,count:undefined},
  ...[5,30,50,70,90].map(severity=>({severity,count:undefined})),{severity:undefined,count:undefined,areaPct:35}];
for(const id of ids)for(const s of shapes){
  const v=F.FINDING_VIEWS.find(x=>F.viewFindings([finding(id,regionOf[x])],x).length),f=finding(id,regionOf[v],s);
  add('rec-'+id,h(SkinRecommendationsDialog,{finding:f,onClose:()=>{},onExpert:()=>{}}));
  add('card-'+id,h(SkinFindingCard,{view:v,items:[f],index:0,onIndex:()=>{},scanAt:props.scanAt}));
}
add('unmeasured',h(SkinUnmeasuredFindingsDialog,{items:reasons.map((reason,i)=>({id:ids[i],reason})),onClose:()=>{}}));
add('unmeasured-1',h(SkinUnmeasuredFindingsDialog,{items:[{id:'acne',reason:'NOT_VALIDATED'}],onClose:()=>{}}));
add('inconclusive',h(SkinInconclusiveFindingsDialog,{items:ids.map((id,i)=>({...finding(id,'forehead'),status:'inconclusive',view:'forehead',causes:[['LIGHTING'],['ANGLE'],['COVER'],['LIGHTING','ANGLE'],null][i%5]})),onClose:()=>{},onRescan:()=>{}}));
add('date-range',h(SkinDateRangeDialog,{scans:['2026-09-01T10:00:00Z'],value:{from:new Date(2026,8,1),to:new Date(2026,9,26)},onApply:()=>{},onClose:()=>{}}));
add('callouts',h(SkinFindingCallouts,{callouts:[...ids.map(id=>({key:id,id,label:F.FINDING_DEFS[id].label,color:'#fff',anchor:{x:1,y:1}})),
  ...F.FINDING_VIEWS.map(v=>({key:v,id:'acne',label:F.FINDING_VIEW_NAMES[v],sub:'%42',color:'#fff',anchor:{x:1,y:1},active:true}))],photoRef:{current:null},active:null},h('div')));
'''


@pytest.mark.parametrize('language', ['en', 'de'])
def test_skin_findings_ui_has_no_turkish_in_english_and_german(language):
    script = HARNESS + r'''
// Turkish-only letters (German keeps its own ö/ü) and Turkish words of the skin UI, matched as whole words.
const letters=LANG==='de'?/[çğışÇĞİŞ]/u:/[çğıöşüÇĞİÖŞÜ]/u;
const words=/(?<![\p{L}])(sivilce|leke|uçuk|ben|bulgu|bulgular|Sabah|Akşam|Kapat|Geçmiş|Belirginlik|Hafif|Orta|Uygula|Tümü|Ayrıntılar|Öneriler|eğilimi|profil|ve|veya|için|bu|Bu|taramada|ölçülemedi|türleri|Akne türleri|Uzman|Cilt|tonunuza|Tarih|aralığı|gün|ay|Son|nokta|komedon|Papül|Püstül|Nodül|Melazma|Kızarıklık|kremi|serumu|asit|güneş|koruyucu)(?![\p{L}])/u;
const bad=[];
for(const [name,html] of out){
  // visible text and accessibility labels; class/style/data-* values are code, not copy
  const copy=html.replace(/ (class|style|data-[\w-]+|key)="[^"]*"/g,'').split(/<[^>]*?(?:aria-label|aria-description|title|alt)="([^"]*)"[^>]*>|<[^>]*>/).filter(Boolean);
  for(const s of copy)if(letters.test(s)||words.test(s))bad.push(name+': '+s);
}
assert.deepEqual([...new Set(bad)],[]);
assert(out.length>400,'rendered '+out.length);
// the acne type rows are collapsed in static markup: check their labels and the section title directly
for(const s of [...F.ACNE_SUBTYPES.map(x=>x.label),'Akne türleri','Cilt tonunuza göre kırmızılık farkı'])assert(!letters.test(core.t(s,LANG))&&core.t(s,LANG)!==s,s);
'''
    run(script, language)


@pytest.mark.parametrize('language', ['en', 'de'])
def test_every_finding_text_band_and_reason_has_a_translation(language):
    script = HARNESS + r'''
const same=new Set(['Normal','Retinol','Cica','Adapalen','Melasma']);
const texts=new Set();
for(const d of Object.values(F.FINDING_DEFS)){texts.add(d.label);texts.add(d.info);if(d.unit){texts.add(d.unit);texts.add('1 '+d.unit);}}
F.ACNE_SUBTYPES.forEach(x=>texts.add(x.label));Object.values(F.UNAVAILABLE_REASON_TEXT).forEach(x=>texts.add(x));
Object.values(F.FINDING_VIEW_NAMES).forEach(x=>texts.add(x));Object.values(Rec.REC_NOTES).forEach(x=>texts.add(x));
Object.values(O.SKIN_TYPE_LABELS).forEach(x=>{texts.add(x);texts.add(x+' ve hassas');});
// every band of every finding: all score / count positions reach each band once
for(const id of Object.keys(F.FINDING_DEFS)){
  const seen=new Map();let total=0;
  for(const severity of [0,10,20,25,30,40,45,50,60,65,70,75,80,85,90,100])for(const count of [1,2,3,4,5,8,10,12,15,20,25]){
    const b=Rec.recommendationBand({id,region:'chin',status:'seen',severity,count});
    if(b){seen.set(b.index,b.band);total=b.total;}
  }
  assert.equal(seen.size,total,id);
  for(const b of seen.values())[b.range,...b.ingredients,b.morning,b.evening,b.usage,b.habit].filter(Boolean).forEach(x=>texts.add(x));
}
const missing=[...texts].filter(x=>/\p{L}/u.test(x)&&!same.has(x)&&core.t(x,LANG)===x);
assert.deepEqual(missing,[]);
// counts: singular for exactly one, plural otherwise; Turkish unchanged
assert.equal(F.countUnit('1','ben',x=>core.t(x,LANG)),LANG==='en'?'mole':'Muttermal');
assert.equal(F.countUnit('3','ben',x=>core.t(x,LANG)),LANG==='en'?'moles':'Muttermale');
assert.equal(F.countUnit('1+','uçuk',x=>core.t(x,LANG)),LANG==='en'?'cold sores':'Lippenherpes');
for(const unit of ['sivilce','ben','leke','uçuk'])for(const n of ['1','1+','3'])assert.equal(F.countUnit(n,unit,x=>core.t(x,'tr')),unit);
'''
    run(script, language)


def test_turkish_output_is_unchanged():
    script = HARNESS + r'''
const html=out.map(x=>x[1]).join('\n');
for(const s of ['text-slate-400">uçuk<','>1+<','Akne türleri','Cilt tonunuza göre kırmızılık farkı','Öneriler','Uzman seçenekleri','Sol profil','Sağ profil','Tarama yapılan günler','Uygula','Belirginlik geçmişi: '])
  assert(html.includes(s),s);
assert(html.includes('>1</span><span class="text-base text-slate-400">ben<'));
assert(html.includes('>+2.5</strong>'));
'''
    run(script, 'tr')


def run(script, language):
    r = subprocess.run(['node', '-e', "require('./tests/unit/ts_loader.js');\n" + script], cwd=ROOT, text=True, capture_output=True,
                       encoding='utf8', timeout=120, env={**__import__('os').environ, 'SKIN_I18N_LANGUAGE': language})
    assert r.returncode == 0, r.stdout + r.stderr

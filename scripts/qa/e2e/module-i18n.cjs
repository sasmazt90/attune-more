const {open,tr,language}=require('./harness.cjs');
// TR/EN/DE entry surfaces at the 1280x720 viewport. A leftover source-language sentence on an
// EN or DE page is reported with its text; proper nouns and approved names are excluded.
const MODULES=['vision','hearing','mental'];
// ö and ü are also German; only letters German does not use mark a Turkish leftover there.
const TURKISH=language==='de'?/[çğıİşÇĞŞ]|\b(ve|bir|için|görüşme|kayıt|kaydet)\b/iu:/[çğıİöşÇĞÖŞ]|\b(ve|bir|için|görüşme|kayıt|kaydet)\b/iu;
const ALLOWED=/TR|Türkçe|Attune|Kadıköy|Levent|İstanbul/;
(async()=>{const h=await open('hearing'),{p,r,save}=h;let error;r.checks=[];const check=(what,pass,observed)=>{r.checks.push({what,pass:!!pass,observed});save();console.log((pass?'PASS ':'FAIL ')+what);};
 try{
  for(const module of MODULES){
   await p.goto(new URL('/',p.url()).href);await p.locator('#attune-language').waitFor();await p.getByRole('button',{name:tr('Sağlık Merkezi'),exact:true}).click();await p.locator(`#health-centre-links a[href="/${module}"]`).click();await p.waitForURL('**/'+module);
   const d=p.getByRole('dialog');if(await d.waitFor({timeout:4000}).then(()=>true,()=>false)){
    if(language!=='tr'){const text=await d.innerText();const left=text.split('\n').filter(l=>TURKISH.test(l)&&!ALLOWED.test(l));check(`${module}: consent dialog has no source-language text`,left.length===0,left.slice(0,6));}
    for(const box of await d.getByRole('checkbox').all())await box.check();await d.getByRole('button',{name:tr('İzin ver ve devam et'),exact:true}).click();await d.waitFor({state:'hidden'});
   }
   await p.locator('[data-health-start]').waitFor();
   const shape=await p.evaluate(()=>{const small=[];for(const e of document.querySelectorAll('main button,main a[href],main select')){const b=e.getBoundingClientRect();if(b.width&&b.height&&(b.height<40||b.width<40))small.push({text:(e.innerText||e.getAttribute('aria-label')||'').trim().slice(0,40),w:Math.round(b.width),h:Math.round(b.height)});}return {lang:document.documentElement.lang,overflow:document.documentElement.scrollWidth>innerWidth+1,small};});
   check(`${module}: document language`,shape.lang===language,shape.lang);check(`${module}: no sideways scroll at 1280x720`,!shape.overflow);check(`${module}: controls are touch-sized`,shape.small.length===0,shape.small);
   if(language!=='tr'){const text=await p.locator('main').innerText();const left=text.split('\n').filter(l=>TURKISH.test(l)&&!ALLOWED.test(l));check(`${module}: page has no source-language text`,left.length===0,left.slice(0,6));}
   await p.screenshot({path:`${h.out}/${module}-${language}.png`});
  }
  r.result=true;r.fullResultCoverage=r.checks.every(x=>x.pass);if(!r.fullResultCoverage)process.exitCode=1;
 }catch(e){error=e;console.error(String(e));process.exitCode=1;}finally{await h.close(error);}
})().catch(e=>{console.error(String(e));process.exitCode=1;});

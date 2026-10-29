/** Rendered UI acceptance. Requires Playwright and a running local build. Temporary contexts never use owner health records. */
const fs=require('node:fs'),path=require('node:path');
const {chromium}=require('playwright');
const out=path.resolve(process.env.ATTUNE_UI_OUTPUT||'output/approved-ui-layout'),mode='corrected';
const baseURL=process.env.ATTUNE_UI_BASE_URL||'http://127.0.0.1:3000';
fs.mkdirSync(out,{recursive:true});
let browser;
(async()=>{
 browser=await chromium.launch({headless:true,...(process.env.ATTUNE_CHROME_EXECUTABLE?{executablePath:process.env.ATTUNE_CHROME_EXECUTABLE}:{})});
 const result={mode,rows:[],dialogChecks:[],errors:[]};
 const widths=mode==='corrected'?[{width:1440,height:1000},{width:1024,height:600},{width:800,height:480},{width:390,height:844}]:[{width:1440,height:1000},{width:800,height:480}];
 const langs=mode==='corrected'?['tr','en','de']:['tr'];
 const routes=['','skin','dental','hearing','mental','vision','care','profile','privacy'];
 const shots=path.join(out,'screenshots',mode);fs.mkdirSync(shots,{recursive:true});
 for(const lang of langs)for(const viewport of widths){
  const context=await browser.newContext({viewport});await context.addInitScript(lang=>localStorage.setItem('attune.language.v1',lang),lang);
  const page=await context.newPage();page.on('pageerror',e=>result.errors.push(String(e)));
  for(const route of routes){
   const response=await page.goto(baseURL+'/'+route,{waitUntil:'networkidle'});if(response.status()!==200)throw Error('Unexpected route status');
   const consent=page.getByRole('dialog');
   if(await consent.count()&&await consent.locator('input[type=checkbox]').count()){
    const checks=await consent.locator('input[type=checkbox]').all();for(const check of checks)await check.check();await consent.locator('button').first().click();
   }
   if(['skin','dental','hearing','mental','vision'].includes(route)){
    await page.locator('[data-health-portrait] img').waitFor();
    await page.waitForFunction(()=>[...document.querySelectorAll('[data-health-portrait] img')].every(i=>i.complete&&i.naturalWidth>0));
   }
   await page.evaluate(async()=>{await document.fonts.ready;await Promise.all([...document.images].map(i=>i.decode().catch(()=>{})));});
   const row=await page.evaluate(()=>{const visible=e=>{const r=e.getBoundingClientRect();return r.width&&r.height};const infos=[...document.querySelectorAll('button[aria-haspopup="dialog"]')].filter(e=>e.textContent.trim()==='ⓘ'&&visible(e));return {headings:[...document.querySelectorAll('main h1,main h2')].map(e=>e.textContent),language:document.querySelector('#attune-language')?.value,headerVoiceButtons:document.querySelectorAll('header [data-language-selector] button').length,overflow:document.documentElement.scrollWidth-innerWidth,infos:infos.map(e=>{const r=e.getBoundingClientRect(),prev=e.previousElementSibling;const t=prev?.getBoundingClientRect();return {label:e.getAttribute('aria-label'),previousTag:prev?.tagName,previousText:prev?.textContent?.slice(0,70),gap:t?Math.round(r.left-t.right):null,verticalDifference:t?Math.round((r.top+r.height/2)-(t.top+t.height/2)):null,insideViewport:r.left>=0&&r.right<=innerWidth+1}}),heroInformationCount:document.querySelector('main section')?[...document.querySelector('main section').querySelectorAll('button')].filter(e=>e.textContent.trim()==='ⓘ').length:null};});
   const shot=path.join(shots,`${lang}-${viewport.width}-${route||'dashboard'}.png`);await page.screenshot({path:shot,fullPage:true,animations:'disabled'});
   result.rows.push({lang,viewport,route:route||'dashboard',status:response.status(),screenshot:shot,...row});
   if(mode==='corrected'){
    if(row.language!==lang||row.headerVoiceButtons||row.overflow>1)throw Error('Locale/header/overflow acceptance failed '+JSON.stringify(result.rows.at(-1)));
    if(!route&&row.heroInformationCount!==1)throw Error('Expected one dashboard introduction information button');
    for(const i of row.infos)if(!i.insideViewport||i.gap===null||i.gap<0||i.gap>20||Math.abs(i.verticalDifference)>22)throw Error('Detached information control '+JSON.stringify(i));
   }
   if(mode==='corrected'&&viewport.width===1440){
    const infos=page.locator('button[aria-haspopup="dialog"]').filter({hasText:'ⓘ'});const count=await infos.count();
    for(let index=0;index<count;index++){
     const control=infos.nth(index);if(!await control.isVisible())continue;await control.click();const dialog=page.getByRole('dialog');await dialog.waitFor({state:'visible'});const title=(await dialog.getAttribute('aria-label'))||(await dialog.getAttribute('aria-labelledby'));if(!title)throw Error('Dialog lacks accessible name');
     await page.keyboard.press('Escape');await dialog.waitFor({state:'hidden'});if(!await control.evaluate(e=>document.activeElement===e))throw Error('Information dialog focus was not restored');result.dialogChecks.push({lang,route:route||'dashboard',index,passed:true});
    }
   }
   fs.writeFileSync(path.join(out,`render-${mode}.json`),JSON.stringify(result,null,2));
  }
  await context.close();
 }
 result.complete=true;fs.writeFileSync(path.join(out,`render-${mode}.json`),JSON.stringify(result,null,2));console.log(JSON.stringify({mode,rows:result.rows.length,dialogs:result.dialogChecks.length,errors:result.errors}));
 await browser.close();
})().catch(async e=>{await browser?.close();console.error(e);process.exitCode=1});

/** Focused UI regressions. Run against a fresh production frontend and isolated API.
 * Camera failures are browser fixtures only; the exported checks also accept a real AAOS page. */
const assert=require('node:assert/strict'),fs=require('node:fs'),path=require('node:path');
const routes=['/skin','/dental','/vision','/hearing','/mental'];
const missing={tr:'Bu cihazda kullanılabilir kamera bulunamadı. Kamera bağlayıp yeniden deneyin veya fotoğraf yükleyin.',en:'No available camera was found on this device. Connect a camera and try again, or upload a photo.',de:'Auf diesem Gerät wurde keine verfügbare Kamera gefunden. Schließen Sie eine Kamera an und versuchen Sie es erneut oder laden Sie ein Foto hoch.'};
async function consent(page){
 await page.waitForTimeout(500);
 const dialog=page.getByRole('dialog');
 if(await dialog.count()&&await dialog.locator('input[type=checkbox]').count()){
  for(const box of await dialog.locator('input[type=checkbox]').all())await box.check();
  await dialog.locator('button').first().click();await dialog.waitFor({state:'hidden'});
 }
}
async function locale(page,lang){await page.locator('#attune-language').selectOption(lang);await page.waitForFunction(lang=>document.documentElement.lang===lang,lang);}
async function geometry(page){return page.locator('#health-centre-links').evaluate(e=>{const r=e.getBoundingClientRect(),v=visualViewport;return {top:r.top,bottom:r.bottom,height:r.height,viewportHeight:v?.height||innerHeight,viewportBottom:(v?.offsetTop||0)+(v?.height||innerHeight),scrollHeight:e.scrollHeight,clientHeight:e.clientHeight,scrollTop:e.scrollTop,links:[...e.querySelectorAll('a')].map(a=>({route:a.getAttribute('href'),height:a.getBoundingClientRect().height,top:a.getBoundingClientRect().top}))};});}
async function wheelIntoView(page,link){
 const panel=page.locator('#health-centre-links');
 for(let attempt=0;attempt<5;attempt++){
  const item=await link.boundingBox(),box=await panel.boundingBox();
  if(item.y>=box.y+2&&item.y+item.height<=box.y+box.height-2)return;
  const previous=await panel.evaluate(e=>e.scrollTop);await panel.hover();await page.mouse.wheel(0,item.y<box.y?-96:96);
  await page.waitForFunction(previous=>document.querySelector('#health-centre-links').scrollTop!==previous,previous);
 }
 throw Error('Menu link is not fully reachable by normal wheel scrolling');
}
async function menu(page,{scroll,activate=link=>link.click({timeout:10000}),shot=async()=>{}}={}){
 const trigger=page.locator('[aria-controls="health-centre-links"]'),panel=page.locator('#health-centre-links');const rows=[];
 for(let i=0;i<routes.length;i++){
  await page.evaluate(()=>window.scrollTo(0,0));await trigger.click();await panel.waitFor();
  const before=await geometry(page);assert.deepEqual(before.links.map(x=>x.route),routes);assert(before.bottom<=before.viewportBottom-7,'dropdown exceeds visible viewport');assert(before.links.every(x=>x.height>=48),'touch targets shrank');
  const link=panel.locator('a').nth(i);
  await (scroll||wheelIntoView)(page,link);
  await activate(link);await page.waitForURL(url=>url.pathname===routes[i]);await consent(page);assert.equal(await panel.count(),0);rows.push({route:routes[i],before});
 }
 await page.evaluate(()=>window.scrollTo(0,0));await trigger.click();await panel.waitFor();
 await (scroll||wheelIntoView)(page,panel.locator('a').last());
 const after=await geometry(page);await shot('menu-last-link');
 await page.keyboard.press('Escape');assert.equal(await panel.count(),0);assert(await trigger.evaluate(e=>e===document.activeElement));
 await trigger.press('ArrowDown');await panel.locator('a').first().waitFor();
 await page.waitForFunction(()=>document.activeElement===document.querySelector('#health-centre-links a'));
 for(const [key,index] of [['End',4],['ArrowDown',0],['ArrowUp',4],['Home',0],['ArrowDown',1],['ArrowUp',0]]){
  await page.keyboard.press(key);assert(await panel.locator('a').nth(index).evaluate(e=>e===document.activeElement));
 }
 await page.keyboard.press('Tab');assert(await panel.locator('a').nth(1).evaluate(e=>e===document.activeElement));
 await page.keyboard.press('Escape');await trigger.press('ArrowUp');await page.waitForFunction(()=>document.activeElement===[...document.querySelectorAll('#health-centre-links a')].at(-1));
 await page.keyboard.press('Escape');await trigger.click();await page.locator('[data-vehicle-status]').click();await panel.waitFor({state:'hidden'});
 return {rows,after,keyboard:true,outsideSelection:true};
}
async function dental(page,{lang,expected=missing[lang],shot=async()=>{}}){
 await page.goto(new URL('/dental',page.url()).href,{waitUntil:'networkidle'});await consent(page);await locale(page,lang);
 const scope=page.locator('[data-dental-page]');const start=scope.locator('section button').filter({hasText:/Diş Taramasını Başlat|Start dental scan|Zahnscan starten/});
 await start.waitFor();await page.waitForFunction(()=>{const e=document.querySelector('[data-vehicle-status]');return e&&/PARK/.test(e.textContent);});await start.click();
 const alert=scope.getByRole('alert');await alert.waitFor();assert.equal(await alert.textContent(),expected);assert.equal(await scope.getByRole('status').count(),0);assert.equal(await alert.count(),1);assert(!await scope.textContent().then(x=>/Requested device not found|RAW_DEVICE_DETAILS/.test(x)));
 const actions=alert.locator('..').locator('button');assert.equal(await actions.count(),3);for(const b of await actions.all())assert(await b.isEnabled());
 await actions.nth(0).click();await alert.waitFor();assert.equal(await alert.textContent(),expected);
 const chooser=page.waitForEvent('filechooser');await actions.nth(1).click();const upload=await chooser;assert.equal(upload.isMultiple(),false);
 await shot('dental-no-camera');await actions.nth(2).click();await start.waitFor();assert.equal(await scope.getByRole('alert').count(),0);
 return {lang,error:expected,alerts:1,statusDuplicates:0,retry:true,uploadChooser:true,close:true};
}
module.exports={menu,dental,consent,locale,geometry,missing};
if(require.main===module)(async()=>{
 const {chromium}=require('playwright');const output=path.resolve(process.env.ATTUNE_UI_OUTPUT||'output/aaos-ui-regressions');fs.mkdirSync(output,{recursive:true});
 const browser=await chromium.launch({headless:true,...(process.env.ATTUNE_CHROME_EXECUTABLE?{executablePath:process.env.ATTUNE_CHROME_EXECUTABLE}:{})});const result={menus:[],dental:[]};
 try{
  for(const viewport of [{width:1024,height:317},{width:1440,height:1000},{width:390,height:844}])for(const lang of ['tr','en','de']){
   const context=await browser.newContext({viewport});await context.addInitScript(lang=>localStorage.setItem('attune.language.v1',lang),lang);const page=await context.newPage();
   await page.goto(process.env.ATTUNE_UI_BASE_URL||'http://localhost:3000',{waitUntil:'networkidle'});
   if(viewport.height===317)await page.addStyleTag({path:path.resolve(__dirname,'../../apps/automotive/app/src/main/assets/automotive.css')});
   result.menus.push({lang,viewport,...await menu(page,{shot:name=>page.screenshot({path:path.join(output,`${lang}-${viewport.width}-${name}.png`)})})});await context.close();
  }
  for(const lang of ['tr','en','de'])for(const name of ['NotFoundError','NotAllowedError','NotReadableError','UnknownError']){
   const context=await browser.newContext({viewport:{width:1024,height:600}});await context.addInitScript(({lang,name})=>{localStorage.setItem('attune.language.v1',lang);navigator.mediaDevices.getUserMedia=async()=>{throw new DOMException('RAW_DEVICE_DETAILS_Requested device not found',name);};},{lang,name});
   const page=await context.newPage();const diagnostics=[];page.on('console',m=>{if(m.type()==='warning')diagnostics.push(m.text());});await page.goto(process.env.ATTUNE_UI_BASE_URL||'http://localhost:3000',{waitUntil:'networkidle'});
   const catalog=require('../../shared/localization/messages.json');const source=name==='NotAllowedError'?'Kamera erişimi sağlanamadı. Lütfen kamera izinlerinizi kontrol edip tekrar deneyin.':name==='NotReadableError'?'Kamera açılamadı; başka kamera kullanımını bitirip yeniden deneyin.':name==='UnknownError'?'Kamera açılamadı.':missing.tr;
   const expected=Object.values(catalog).find(x=>x.tr===source)[lang];
   result.dental.push({name,...await dental(page,{lang,expected,shot:label=>page.screenshot({path:path.join(output,`${lang}-${name}-${label}.png`),fullPage:true})})});assert(diagnostics.some(x=>x.includes('Dental camera startup failed:')&&x.includes('RAW_DEVICE_DETAILS')),'technical diagnostic missing');await context.close();
  }
  result.passed=true;
 }finally{fs.writeFileSync(path.join(output,'results.json'),JSON.stringify(result,null,2));await browser.close();}
 console.log(JSON.stringify({menus:result.menus.length,activatedRoutes:result.menus.length*5,dental:result.dental.length,passed:result.passed}));
})().catch(e=>{console.error(e);process.exitCode=1;});

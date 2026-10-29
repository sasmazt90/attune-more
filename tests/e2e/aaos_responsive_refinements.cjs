/** Real rendered geometry and ordinary document scrolling; no camera/model fixtures. */
const assert=require('node:assert/strict'),fs=require('node:fs'),path=require('node:path');
const {consent,locale}=require('./aaos_ui_regressions.cjs');
const modules=['skin','dental','vision','hearing','mental'];
async function measure(page){return page.evaluate(()=>{
 const rect=e=>{const r=e.getBoundingClientRect();return {x:r.x,y:r.y,width:r.width,height:r.height,bottom:r.bottom,right:r.right};};
 const root=document.scrollingElement,card=document.querySelector('[data-health-start]'),portrait=card?.querySelector('[data-health-portrait]'),image=portrait?.querySelector('img');
 const header=document.querySelector('header'),contentTop=['sticky','fixed'].includes(getComputedStyle(header).position)?Math.max(0,header.getBoundingClientRect().bottom):0;
 const actions=card?[...card.querySelectorAll('[data-health-start-actions] button')]:[...document.querySelectorAll('main a,main button')].filter(e=>{const r=e.getBoundingClientRect();return r.width>0&&r.left>=0&&r.right<=innerWidth;});
 return {contentTop,url:location.pathname,language:document.documentElement.lang,viewport:{width:innerWidth,height:innerHeight},scroll:{top:root.scrollTop,height:root.scrollHeight,clientHeight:root.clientHeight,width:root.scrollWidth,overflowY:getComputedStyle(root).overflowY,scrollbarWidth:getComputedStyle(root,'::-webkit-scrollbar').width},header:{...rect(document.querySelector('header')),position:getComputedStyle(document.querySelector('header')).position},footer:rect(document.querySelector('footer')),footerLink:rect(document.querySelector('footer a')),card:card?{...rect(card),paddingTop:parseFloat(getComputedStyle(card).paddingTop),paddingBottom:parseFloat(getComputedStyle(card).paddingBottom),borderTop:parseFloat(getComputedStyle(card).borderTopWidth),borderBottom:parseFloat(getComputedStyle(card).borderBottomWidth),text:rect(card.firstElementChild.lastElementChild)}:null,portrait:portrait?{...rect(portrait),image:rect(image),naturalWidth:image.naturalWidth,naturalHeight:image.naturalHeight,objectFit:getComputedStyle(image).objectFit,src:image.getAttribute('src')}:null,actions:actions.map((e,index)=>{const r=rect(e),visibleTop=Math.max(contentTop,r.y),visibleBottom=Math.min(innerHeight,r.bottom),hit=document.elementFromPoint(r.x+r.width/2,card?r.y+r.height/2:(visibleTop+visibleBottom)/2);return {index,text:e.textContent.trim(),...r,disabled:e.disabled||false,visible:(card?r.y>=contentTop&&r.bottom<=innerHeight:visibleBottom-visibleTop>=Math.min(48,r.height))&&r.x>=0&&r.right<=innerWidth,hit:hit===e||e.contains(hit)};})};
 });}
async function initialMenu(page,{approved=true,shot=async()=>{}}={}){
 const button=page.locator('[aria-controls="health-centre-links"]');await button.click();await page.locator('#health-centre-links').waitFor();
 const value=await page.locator('#health-centre-links').evaluate(e=>{const r=e.getBoundingClientRect(),b=document.querySelector('[aria-controls="health-centre-links"]').getBoundingClientRect();return {x:r.x,y:r.y,width:r.width,height:r.height,bottom:r.bottom,button:{x:b.x,bottom:b.bottom},scrollTop:e.scrollTop,scrollHeight:e.scrollHeight,clientHeight:e.clientHeight,viewport:{width:innerWidth,height:innerHeight},links:[...e.querySelectorAll('a')].map(a=>{const v=a.getBoundingClientRect();return {href:a.getAttribute('href'),text:a.textContent,x:v.x,y:v.y,width:v.width,height:v.height,right:v.right,bottom:v.bottom};})};});
 if(approved){
  assert.deepEqual(value.links.map(x=>x.href),modules.map(x=>'/'+x));assert.equal(value.scrollTop,0);assert(value.scrollHeight<=value.clientHeight+1,'initial menu requires internal scrolling');
  assert(Math.abs(value.x-value.button.x)<1&&value.y>=value.button.bottom&&value.y-value.button.bottom<=9,'menu lost its below-button anchor');
  for(const a of value.links)assert(a.height>=48&&a.y>=value.y&&a.bottom<=value.bottom+1&&a.bottom<=value.viewport.height&&a.x>=0&&a.right<=value.viewport.width,'initial target clipped: '+JSON.stringify(a));
  assert(value.links[0].x===value.links[2].x&&value.links[2].x===value.links[4].x);assert(value.links[1].x===value.links[3].x&&value.links[1].x>value.links[0].x);assert.equal(value.links[0].y,value.links[1].y);assert.equal(value.links[2].y,value.links[3].y);assert(value.links[4].y>value.links[2].y);
 }
 await shot('menu-initial');await page.keyboard.press('Escape');
 if(approved){
  assert(await button.evaluate(e=>e===document.activeElement));await button.press('ArrowDown');await page.waitForFunction(()=>document.activeElement===document.querySelector('#health-centre-links a'));
  for(const [key,index] of [['End',4],['ArrowDown',0],['ArrowUp',4],['Home',0],['ArrowDown',1]]){await page.keyboard.press(key);assert(await page.locator('#health-centre-links a').nth(index).evaluate(e=>e===document.activeElement));}
  await page.keyboard.press('Escape');assert(await button.evaluate(e=>e===document.activeElement));
 }
 return value;
}
async function prepare(page,base,route,lang){
 await page.goto(base+'/'+route,{waitUntil:'networkidle'});await consent(page);await locale(page,lang);await page.waitForFunction(()=>document.querySelector('[data-vehicle-status]')?.textContent==='PARK');
 if(route){await page.waitForFunction(()=>{const i=document.querySelector('[data-health-portrait] img');return i?.complete&&i.naturalWidth>0;});}
 await page.evaluate(()=>document.fonts.ready);await page.evaluate(()=>new Promise(resolve=>requestAnimationFrame(()=>requestAnimationFrame(resolve))));
}
async function documentScroll(page,{gesture,shot=async()=>{}}={}){
 const initial=await measure(page),seen=new Set(),positions=[];let value=initial;
 const observe=()=>{assert(value.scroll.width<=value.viewport.width+1,'horizontal document overflow');for(const a of value.actions)if(a.visible&&a.hit)seen.add(a.index);positions.push(value.scroll.top);};observe();
 for(let n=0;value.scroll.top+value.viewport.height<value.scroll.height-2;n++){
  assert(n<100,'document did not reach its end');const previous=value.scroll.top;
  const step=Math.round((value.viewport.height-(['sticky','fixed'].includes(value.header.position)?value.header.height:0))*.5);
  if(gesture)await gesture(step);else{await page.mouse.move(value.viewport.width-24,value.viewport.height-24);await page.mouse.wheel(0,step);}
  await page.waitForFunction(top=>document.scrollingElement.scrollTop>top,previous,{timeout:7000});value=await measure(page);observe();
  if(n===0)await shot('scrollbar');
 }
 const last=value;assert(last.footer.bottom<=last.viewport.height+2,'footer cannot be reached');assert(last.footerLink.y>=last.contentTop&&last.footerLink.bottom<=last.viewport.height&&last.footerLink.height>=48,'last footer control is covered');
 for(const a of initial.actions)assert(seen.has(a.index),'primary/content action not reached by ordinary scrolling: '+a.text);
 await shot('page-end');return {initial,end:last,positions,reachableActions:[...seen]};
}
function portraitCheck(value,{approved=true}={}){
 const p=value.portrait;assert(p&&p.naturalWidth&&p.naturalHeight);assert.equal(p.objectFit,'contain');assert(Math.abs(p.width/p.height-p.naturalWidth/p.naturalHeight)<.005,'portrait aspect ratio changed');
 if(approved){assert(p.height<=value.viewport.height-(['sticky','fixed'].includes(value.header.position)?value.header.height:0)-value.card.paddingTop-value.card.paddingBottom-value.card.borderTop-value.card.borderBottom+1,'portrait exceeds available card viewport');assert(p.height<480,'oversized portrait unchanged');}
 for(const a of value.actions){assert(a.height>=48,'preparation target shrank');assert(!a.disabled,'preparation action unexpectedly disabled: '+a.text);}
 return {rendered:{width:p.width,height:p.height},natural:{width:p.naturalWidth,height:p.naturalHeight},cardHeight:value.card.height,textHeight:value.card.text.height,minimumActionBottom:Math.max(...value.actions.map(a=>a.bottom-value.card.y)),availableViewport:value.viewport.height};
}
module.exports={modules,measure,initialMenu,prepare,documentScroll,portraitCheck};
if(require.main===module)(async()=>{
 const {chromium}=require('playwright'),base=process.env.ATTUNE_UI_BASE_URL||'http://localhost:3000',out=path.resolve(process.env.ATTUNE_UI_OUTPUT||'output/aaos-responsive-refinements');fs.mkdirSync(out,{recursive:true});
 const browser=await chromium.launch({headless:true,...(process.env.ATTUNE_CHROME_EXECUTABLE?{executablePath:process.env.ATTUNE_CHROME_EXECUTABLE}:{})});const result={menus:[],pages:[],normal:[]};
 try{
  for(const viewport of [{width:1024,height:317},{width:1280,height:437}])for(const lang of ['tr','en','de']){
   const context=await browser.newContext({viewport});await context.addInitScript(lang=>localStorage.setItem('attune.language.v1',lang),lang);const page=await context.newPage();
   // Native-only CSS marker: mirrors the existing shell's unchanged onPageFinished injection.
   await page.addInitScript(()=>addEventListener('DOMContentLoaded',()=>{const s=document.createElement('style');s.id='attune-automotive-style';s.textContent='button,select,nav a,footer a{min-height:48px}nav button,nav a{font-size:14px}';document.head.append(s);}));
   await prepare(page,base,'',lang);result.menus.push({lang,viewport,...await initialMenu(page,{shot:label=>page.screenshot({path:path.join(out,`${lang}-${viewport.width}-${label}.png`)})})});
   for(const route of ['',...modules]){await prepare(page,base,route,lang);const before=await measure(page);const portrait=route?portraitCheck(before):null;const scroll=await documentScroll(page);result.pages.push({lang,viewport,route:route||'dashboard',portrait,scroll});}
   await context.close();
  }
  for(const viewport of [{width:1440,height:1000},{width:1024,height:600},{width:800,height:480},{width:390,height:844}])for(const lang of ['tr','en','de']){
   const context=await browser.newContext({viewport});await context.addInitScript(lang=>localStorage.setItem('attune.language.v1',lang),lang);const page=await context.newPage();
   for(const route of modules){await prepare(page,base,route,lang);const value=await measure(page);assert(Math.abs(value.portrait.width-(viewport.width===390?308:360))<1,'approved normal portrait size changed');assert(Math.abs(value.portrait.width/value.portrait.height-.75)<.005);result.normal.push({lang,viewport,route,geometry:value});}
   await page.evaluate(()=>window.scrollTo(0,0));await page.locator('[aria-controls="health-centre-links"]').click();const xs=await page.locator('#health-centre-links a').evaluateAll(es=>es.map(e=>e.getBoundingClientRect().x));assert(xs.every(x=>x===xs[0]),'normal menu changed to multiple columns');await context.close();
  }
  result.passed=true;
 }finally{fs.writeFileSync(path.join(out,'results.json'),JSON.stringify(result,null,2));await browser.close();}
 console.log(JSON.stringify({menus:result.menus.length,pages:result.pages.length,normal:result.normal.length,passed:result.passed}));
})().catch(e=>{console.error(e);process.exitCode=1;});

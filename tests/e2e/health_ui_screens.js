async page=>{
 const assert=(x,m)=>{if(!x)throw Error(m)},proof={screens:[],checked:[]};
 await page.route('**/api/mental/speech',r=>r.fulfill({status:503,json:{detail:'NO_EXTRA_LIVE_REQUESTS'}}));
 for(const module of ['dental','hearing','skin','mental']){
  await page.goto('http://127.0.0.1:3308/'+module);await page.waitForSelector('main button,[role=dialog]');const modal=page.getByRole('dialog');if(await modal.count()){for(const box of await modal.getByRole('checkbox').all())await box.check();await modal.getByRole('button',{name:'İzin ver ve devam et'}).click();await modal.waitFor({state:'detached'});}
  await page.waitForFunction(()=>document.querySelector('main').innerText.length>100);
  if(module==='mental'){assert(await page.getByRole('textbox').count()===0,'Text entry remains');assert(!/konuşabilir veya yaz|yazarak devam|İsterseniz yaz/i.test(await page.locator('main').innerText()),'Writing prompt remains');assert(await page.getByRole('button',{name:/Sesli yanıtı/}).count()===0,'Duplicate mute');}
  if(module==='skin')assert(!(await page.locator('main').innerText()).includes('Ön ve iki yan pozda kısa bir tarama'),'Skin caption remains');
  for(const [size,width] of [['desktop',1440],['narrow',390]]){
   await page.setViewportSize({width,height:1000});await page.waitForTimeout(180);const layout=await page.evaluate(()=>({width:innerWidth,scroll:document.documentElement.scrollWidth,header:document.querySelector('header').getBoundingClientRect().height,brokenImages:Array.from(document.querySelectorAll('main img')).filter(i=>!i.complete||!i.naturalWidth).map(i=>i.getAttribute('src'))}));assert(layout.scroll<=layout.width,'Horizontal overflow');await page.locator('main img').first().waitFor({state:'attached',timeout:1000}).catch(()=>{});await page.waitForTimeout(300);
   await page.screenshot({path:`output/playwright/health-ui/${module}-${size}.png`,fullPage:true});proof.screens.push({module,size,...layout});
  }
  proof.checked.push(module);
 }
 const d=page.waitForEvent('download');await page.evaluate(v=>{const a=document.createElement('a');a.href=URL.createObjectURL(new Blob([JSON.stringify(v)],{type:'application/json'}));a.download='screen-proof.json';a.click()},proof);await(await d).saveAs('../cdc-progress/health-ui-consent-audio-followup-20261017/screen-proof.json');return proof;
}

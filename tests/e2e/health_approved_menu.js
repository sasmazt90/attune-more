async page => {
 const assert=(v,m)=>{if(!v)throw Error(m)},base='http://127.0.0.1:3311';
 const ids=['skin','dental','vision','hearing','mental'],names=['Cilt Sağlığı','Diş Sağlığı','Göz Sağlığı','İşitme Sağlığı','Ruh Sağlığı'];
 const globalIds=['vision','skin','dental','hearing','mental'];
 const proof={menu:[],keyboard:[],unchangedOrders:[],physicalUserAcceptance:false};
 await page.setViewportSize({width:1440,height:1000});
 await page.addInitScript(()=>{navigator.mediaDevices.getUserMedia=()=>{throw Error('No physical capture in UI checks')};});
 await page.route('**/api/mental/speech',r=>r.fulfill({status:503,json:{detail:'CONTROLLED_UNAVAILABLE'}}));
 const trigger=()=>page.getByRole('button',{name:'Sağlık Merkezi',exact:true});
 const links=()=>page.locator('#health-centre-links a');
 const focus=()=>page.evaluate(()=>document.activeElement?.getAttribute('href'));
 for (let i=0;i<ids.length;i++) {
  await page.goto(base+'/');await trigger().focus();await page.keyboard.press('ArrowDown');await links().first().waitFor();
  assert(JSON.stringify(await links().allTextContents())===JSON.stringify(names),'Exact menu text/order');
  const rows=await links().evaluateAll(es=>es.map(e=>({text:e.textContent,href:e.getAttribute('href'),svg:e.querySelector('svg')?.outerHTML})));
  assert(rows.every((r,j)=>r.href==='/'+ids[j]&&r.svg?.includes('aria-hidden="true"')),'Route/icon mismatch');
  assert(new Set(rows.map(r=>r.svg)).size===5,'Icons no longer distinct');
  if(!i){
   assert(await focus()==='/skin','ArrowDown must enter first');
   for(const [key,id] of [['ArrowDown','dental'],['ArrowUp','skin'],['End','mental'],['ArrowDown','skin'],['ArrowUp','mental'],['Home','skin']]){
    await page.keyboard.press(key);assert(await focus()==='/'+id,'Keyboard order: '+key);proof.keyboard.push({key,id});
   }
   await page.keyboard.press('Escape');assert(await trigger().evaluate(e=>e===document.activeElement),'Escape focus return');
   assert(await links().count()===0,'Escape close');await page.keyboard.press('ArrowUp');await links().first().waitFor();assert(await focus()==='/mental','Trigger ArrowUp must enter last');
   await page.screenshot({path:'../cdc-progress/health-approved-assets-menu-20261017/menu-desktop.png'});
   proof.menu=rows;
  }
  await links().nth(i).focus();await page.keyboard.press('Enter');await page.waitForURL(base+'/'+ids[i]);
  const d=page.getByRole('dialog');if(await d.count()){for(const c of await d.getByRole('checkbox').all())await c.check();await d.getByRole('button',{name:'İzin ver ve devam et'}).click();}
  await page.locator('[data-health-start]').waitFor();assert(await page.locator('[data-health-portrait]').getAttribute('data-health-portrait')===ids[i],'Route preparation mismatch');
 }
 for(const route of ['/','/profile']) {
  await page.goto(base+route);await page.locator('[data-health-module]').first().waitFor();
  const actual=await page.locator('[data-health-module]').evaluateAll(es=>es.map(e=>e.getAttribute('data-health-module')));
  assert(JSON.stringify(actual)===JSON.stringify(globalIds),'Carousel/history order changed');proof.unchangedOrders.push({route,actual});
 }
 await page.setViewportSize({width:390,height:1000});await trigger().click();await links().first().waitFor();
 assert(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth),'Narrow menu overflow');
 await page.screenshot({path:'../cdc-progress/health-approved-assets-menu-20261017/menu-narrow.png',fullPage:true});
 const d=page.waitForEvent('download');await page.evaluate(v=>{const a=document.createElement('a');a.href=URL.createObjectURL(new Blob([JSON.stringify(v)],{type:'application/json'}));a.download='menu.json';a.click()},proof);await(await d).saveAs('../cdc-progress/health-approved-assets-menu-20261017/menu-proof.json');
 return {routes:5,exactOrder:names,keyboard:proof.keyboard.length,unchangedOrders:proof.unchangedOrders};
}

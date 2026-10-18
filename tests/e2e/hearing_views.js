async page=>{
 const rows=[],assert=(x,m)=>{if(!x)throw Error(m)};
 for(const viewport of [{width:1440,height:1000},{width:390,height:844}]){
  await page.setViewportSize(viewport);await page.evaluate(()=>scrollTo(0,0));await page.waitForTimeout(150);
  if(!await page.getByRole('dialog').count())await page.locator('[data-record-history=hearing] article').first().getByRole('button',{name:'Sonucu Aç',exact:true}).click();
  const rect=await page.getByRole('dialog').boundingBox(),layout=await page.evaluate(()=>({width:innerWidth,scrollWidth:document.documentElement.scrollWidth}));assert(layout.scrollWidth<=layout.width+1&&rect.x>=0&&rect.x+rect.width<=viewport.width+1,'Dialog overflow');
  await page.screenshot({path:`../cdc-progress/hearing-technical-closeout-20261017/history-${viewport.width}.png`});
  await page.getByRole('button',{name:'Sonuç penceresini kapat'}).click();await page.evaluate(()=>scrollTo(0,0));await page.screenshot({path:`../cdc-progress/hearing-technical-closeout-20261017/preparation-${viewport.width}.png`});
  const checks=await page.evaluate(()=>({muteControls:document.querySelectorAll('[aria-label="Seslendirmeyi kapat"],[aria-label="Seslendirmeyi aç"]').length,photo:document.querySelector('[data-hearing-page] img')?.getAttribute('src'),inlineCheckboxes:document.querySelectorAll('[data-hearing-page] input[type=checkbox]').length,overflow:document.documentElement.scrollWidth>innerWidth+1}));assert(checks.muteControls===1&&checks.photo?.includes('hearing-preparation')&&checks.inlineCheckboxes===0&&!checks.overflow,'Preserved preparation/header layout');rows.push({viewport,dialog:rect,checks});
 }
 await page.setViewportSize({width:1440,height:1000});const proof={rows,physicalHeadphoneAcceptance:false};const d=page.waitForEvent('download');await page.evaluate(v=>{const a=document.createElement('a');a.href=URL.createObjectURL(new Blob([JSON.stringify(v)],{type:'application/json'}));a.download='views.json';a.click()},proof);await(await d).saveAs('../cdc-progress/hearing-technical-closeout-20261017/views.json');return proof;
}

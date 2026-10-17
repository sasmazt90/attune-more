/** Native Chrome 200%, profile preference log(2)/log(1.2), viewport:null.
 * Capture the visible compositor surface: Playwright's default full-page
 * capture applies an incorrect clip under native zoom on this installation. */
async page=>{
 const value=await page.locator('[data-letter-optotype]').evaluate(e=>{
  const rect=e.getBoundingClientRect(),path=e.querySelector('path'),matrix=path.getScreenCTM(),length=path.getTotalLength();
  const hitChecks=Array.from({length:9},(_,i)=>{const p=path.getPointAtLength(length*i/8),q=new DOMPoint(p.x,p.y).matrixTransform(matrix);return e.contains(document.elementFromPoint(q.x,q.y))});
  return {kind:'native browser zoom, no CSS zoom or page scale override',rect:rect.toJSON(),dpr:devicePixelRatio,innerWidth,innerHeight,outerWidth,outerHeight,cssZoom:getComputedStyle(document.body).zoom,visualScale:visualViewport.scale,hitChecks,sourceVideo:{width:document.querySelector('video').videoWidth,height:document.querySelector('video').videoHeight},physicalUserAcceptance:false};
 });
 if(value.cssZoom!=='1'||value.visualScale!==1||!value.hitChecks.every(Boolean)||value.rect.right>value.innerWidth+1||value.rect.bottom>value.innerHeight+1)throw Error('Native zoom target not fully visible');
 const cdp=await page.context().newCDPSession(page),shot=await cdp.send('Page.captureScreenshot',{format:'png',captureBeyondViewport:false,fromSurface:false});
 let d=page.waitForEvent('download');await page.evaluate(raw=>{const a=document.createElement('a');a.href='data:image/png;base64,'+raw;a.download='native200-surface.png';a.click()},shot.data);await(await d).saveAs('output/playwright/vision/native200-surface.png');
 d=page.waitForEvent('download');await page.evaluate(v=>{const a=document.createElement('a');a.href=URL.createObjectURL(new Blob([JSON.stringify(v)],{type:'application/json'}));a.download='native200-surface.json';a.click()},value);await(await d).saveAs('output/playwright/vision/native200-surface.json');return value;
}

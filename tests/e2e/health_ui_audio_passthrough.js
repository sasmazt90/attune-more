async page=>{
 const result=await page.evaluate(async()=>{
  const render=async(meter)=>{const c=new OfflineAudioContext(2,2048,48000),buffer=c.createBuffer(2,2048,48000);for(let i=0;i<2048;i++){buffer.getChannelData(0)[i]=.17*Math.sin(i/13);buffer.getChannelData(1)[i]=.09*Math.cos(i/7);}const source=c.createBufferSource();source.buffer=buffer;if(meter){const analyser=c.createAnalyser();analyser.fftSize=512;source.connect(analyser);analyser.connect(c.destination);}else source.connect(c.destination);source.start();const rendered=await c.startRendering();return [rendered.getChannelData(0),rendered.getChannelData(1)];};
  const a=await render(false),b=await render(true);let diff=0;for(let ch=0;ch<2;ch++)for(let i=0;i<2048;i++)diff=Math.max(diff,Math.abs(a[ch][i]-b[ch][i]));return {channels:2,samplesPerChannel:2048,maxAbsoluteSampleDifference:diff,bitExact:diff===0};
 });if(!result.bitExact)throw Error('Analyser altered output');
 const d=page.waitForEvent('download');await page.evaluate(v=>{const a=document.createElement('a');a.href=URL.createObjectURL(new Blob([JSON.stringify(v)],{type:'application/json'}));a.download='audio-passthrough-proof.json';a.click()},result);await(await d).saveAs('../cdc-progress/health-ui-consent-audio-followup-20261017/audio-passthrough-proof.json');return result;
}

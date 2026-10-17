async page=>{
 const fault=await page.evaluate(()=>({waves,unownedPauses,progress:document.querySelector('[data-tone-progress]')?.textContent,contexts:contexts.map(c=>c.state)}));
 await page.getByRole('button',{name:'Durdur',exact:true}).click();await page.waitForTimeout(200);
 const after=await page.evaluate(()=>({contexts:contexts.map(c=>c.state),records:JSON.parse(localStorage.getItem('attune_hearing_history_v1')||'[]').length}));
 if(!fault.unownedPauses||!fault.waves.some(w=>w.suppressed&&!w.ended)||!after.contexts.includes('running'))throw Error('Baseline regression not reproduced');
 const proof={sourceCommit:'7fe773c1f87e0e45dd3386c6e08d13fda6f2cba7',fault,after,bugs:['claim calls pause on unrelated DOM media','unstarted source advances completed presentation/adaptation','pause leaves hearing AudioContext running'],faultInjection:'AudioBufferSource.start withheld; native timers and protocol untouched',testCorrection:'Original waiter used nonexistent text: 1 sunum; corrected to actual ses denemesi. App was not changed.',physicalHeadphoneAcceptance:false};
 const d=page.waitForEvent('download');await page.evaluate(v=>{const a=document.createElement('a');a.href=URL.createObjectURL(new Blob([JSON.stringify(v)],{type:'application/json'}));a.download='baseline.json';a.click()},proof);await(await d).saveAs('../cdc-progress/hearing-technical-closeout-20261017/baseline.json');return proof;
}

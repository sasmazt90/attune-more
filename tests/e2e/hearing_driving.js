async page=>{
 await page.goto('http://127.0.0.1:3309/hearing');await page.getByRole('button',{name:'Ses hazırlığını başlat'}).click();await page.getByRole('button',{name:'Sol kanalı dinle'}).click({timeout:25000});
 const started=await page.evaluate(()=>({states:contexts.map(c=>c.state),waves:waves.length}));
 try{await page.request.post('http://127.0.0.1:8309/api/vehicle/speed',{data:{speedKmH:10}});await page.waitForFunction(()=>document.querySelector('[data-hearing-page] [role=status]')?.textContent.includes('Araç PARK'),{},{timeout:5000});await page.waitForFunction(()=>contexts.every(c=>c.state!=='running'),{},{timeout:3000});
 const after=await page.evaluate(()=>({states:contexts.map(c=>c.state),records:JSON.parse(localStorage.getItem('attune_hearing_history_v1')||'[]').length,owner:localStorage.getItem('attune_hearing_audio_owner'),notice:document.querySelector('[data-hearing-page] [role=status]')?.textContent}));if(after.records||after.owner)throw Error('Driving produced record or retained lease');const proof={started,after,realIsolatedVehicleAPI:true,physicalVehicleEvent:false,physicalHeadphoneAcceptance:false};
 const d=page.waitForEvent('download');await page.evaluate(v=>{const a=document.createElement('a');a.href=URL.createObjectURL(new Blob([JSON.stringify(v)],{type:'application/json'}));a.download='driving.json';a.click()},proof);await(await d).saveAs('../cdc-progress/hearing-technical-closeout-20261017/driving.json');return proof;
 }finally{await page.request.post('http://127.0.0.1:8309/api/vehicle/speed',{data:{speedKmH:0}});}
}

const assert=require('assert/strict');
// Only IDs returned by the real completed synthetic workflow are eligible.
async function deleteSynthetic(h,id,module){
 const {p,r,tr,act,observe,save}=h;assert(id&&typeof id==='string');
 const eligible=[r.recordId,...(r.generated||[]).map(x=>x.id),...(r.assessments||[]).filter(x=>x.record&&Array.isArray(x.beforeIds)&&!x.beforeIds.includes(x.record.id)).map(x=>x.record.id)].filter(Boolean);
 assert(eligible.includes(id),'Deletion must target a proven generated record from this exact run');
 assert(!(r.beforeIds||[]).includes(id)&&!(Array.isArray(r.before)?r.before:[]).includes(id),'Pre-existing record must be preserved');
 await p.getByRole('link',{name:tr('Sağlık Geçmişim'),exact:true}).click();
 const row=p.locator('[data-record-category="'+module+'"][data-record-id="'+id+'"]');await row.waitFor();
 await act('Open deletion confirmation for this synthetic record',row.getByRole('button',{name:/Delete .*record:|kaydını sil|löschen/i}),()=>p.getByRole('dialog').waitFor());
 await observe('Deletion scope and irreversible warning',p.getByRole('dialog'));
 await act('Cancel deletion',p.getByRole('button',{name:tr('Hayır, vazgeç'),exact:true}),()=>p.getByRole('dialog').waitFor({state:'hidden'}));assert.equal(await row.count(),1);
 await row.getByRole('button',{name:/Delete .*record:|kaydını sil|löschen/i}).click();
 await act('Confirm deletion of this synthetic record',p.getByRole('button',{name:tr('Evet, sil'),exact:true}),()=>row.waitFor({state:'detached'}));
 await p.locator('nav a[href="/"]').click();await p.getByRole('link',{name:tr('Sağlık Geçmişim'),exact:true}).click();await p.locator('[data-record-table]').waitFor().catch(()=>{});assert.equal(await row.count(),0);
 r.syntheticDeletions??=[];r.syntheticDeletions.push({id,module,cancelPreserved:true,confirmedRemoved:true,absenceAfterNavigation:true});save();
}
async function referral(h,link,module,label){
 const {p,r,act,observe,save}=h;const href=await link.getAttribute('href');assert(href?.startsWith('/care?'));assert.equal(new URL(href,'http://localhost').searchParams.get('from'),module);
 await act(label,link,()=>p.waitForURL('**/care?**'));assert.equal(new URL(p.url()).searchParams.get('from'),module);await observe(label+' destination',p.locator('main'));r.referrals??=[];r.referrals.push({label,url:p.url(),status:'PASS',seconds:h.stamp()});save();
}
module.exports={deleteSynthetic,referral};

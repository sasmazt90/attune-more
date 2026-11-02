const assert=require('node:assert/strict');
require('./ts_loader');
const React=require('react'),{renderToStaticMarkup:render}=require('react-dom/server');
const {sourceBoundCallouts,findingSnapshot}=require('../../apps/vehicle-app/src/utils/skinCalloutModel.ts');
const {dentalCrop}=require('../../apps/vehicle-app/src/components/dental/DentalPhotoView.tsx');
const {SkinFindingsPanel}=require('../../apps/vehicle-app/src/components/skin/SkinFindingsPanel.tsx');
const {SkinResultView}=require('../../apps/vehicle-app/src/components/skin/SkinResultView.tsx');
const lm=Array.from({length:478},()=>({x:.5,y:.5}));lm[234].x=.2;lm[454].x=.8;
const snapshot={photoId:'a'.repeat(64),angle:'FRONT',width:1000,height:800,landmarks:lm};
const captures={FRONT:{captureId:snapshot.photoId,pose:'FRONT',sourceWidth:1000,sourceHeight:800}};
const eye={id:'downturnedCorners',region:'periorbital',pose:'FRONT',status:'seen',severity:64};
const side={...snapshot,angle:'RIGHT',photoId:'b'.repeat(64)},sources={...captures,RIGHT:{captureId:side.photoId,pose:'RIGHT',sourceWidth:1000,sourceHeight:800}};
assert.equal(findingSnapshot([{...eye,id:'crowsFeet',pose:'RIGHT'}],'periorbital','crowsFeet',{FRONT:snapshot,RIGHT:side},sources,snapshot),side,'show the photo that actually decided the selected finding');
assert.equal(findingSnapshot([{...eye,id:'crowsFeet',pose:'RIGHT'}],'periorbital','crowsFeet',{RIGHT:{...side,photoId:'c'.repeat(64)}},sources,snapshot),snapshot,'another session cannot replace the photo');
assert.equal(sourceBoundCallouts([eye],snapshot,captures,'overview',null).length,1);
assert.equal(sourceBoundCallouts([eye],snapshot,{FRONT:{...captures.FRONT,captureId:'b'.repeat(64)}},'overview',null).length,0,'another session is never drawn');
assert.equal(sourceBoundCallouts([{...eye,pose:'LEFT'}],snapshot,captures,'overview',null).length,0,'another pose is never anchored to front landmarks');
assert.equal(sourceBoundCallouts([{...eye,status:'inconclusive'}],snapshot,captures,'overview',null).length,0);
assert.equal(sourceBoundCallouts([{id:'acne',region:'forehead',pose:'FRONT',status:'seen',count:1}],snapshot,captures,'forehead',null).length,0,'no invented lesion point');
const marker={id:'acne',region:'forehead',pose:'LEFT',status:'seen',markers:[{x:300,y:200,pose:'FRONT'}]};
assert.deepEqual(sourceBoundCallouts([marker],snapshot,captures,'forehead','acne')[0].anchor,{x:300,y:200});
const props={scanAt:'2026-11-02T10:00:00Z',index:0,onIndex:()=>{},onGoToView:()=>{},onNavigateToCare:()=>{},overviewSel:null,onOverviewSel:()=>{}};
const result=rows=>({version:'skin-findings-v2',status:'measured',findings:rows});
const html=rows=>render(React.createElement(SkinFindingsPanel,{...props,view:'chin',findings:rows,findingsResult:result(rows)}));
assert.match(html([eye]),/data-skin-findings-empty="not-measured"/);
assert.match(html([{id:'redness',region:'chin',status:'inconclusive'}]),/data-skin-findings-empty="inconclusive"/);
assert.match(html([{id:'redness',region:'chin',status:'notSeen'}]),/data-skin-findings-empty="measured"/);
for(const id of ['overview','forehead','periorbital','rightCheek','leftCheek','chin']){
 const h=render(React.createElement(SkinResultView,{currentRegion:{id},findings:[],findingsResult:result([]),onPrev:()=>{},onNext:()=>{},onNavigateToCare:()=>{}}));
 assert.match(h,/data-health-result-navigation/);assert.match(h,/Önceki bölge/);assert.match(h,/Sonraki bölge/);
}
for(const size of [[1920,1080],[320,240]]){
 const [w,h]=size,c=dentalCrop({quality:{roi:{x:w/2-40,y:h/2-20,width:80,height:40}}},w,h);
 assert(c.width>=Math.min(w,480));assert(c.x>=0&&c.y>=0&&c.x+c.width<=w&&c.y+c.height<=h);
}
console.log('PASS: source/session/pose-bound callouts, regional measurement states, all six always-available controls, bounded dental crops');

// Render real staged outputs with the unchanged production photo/map/value components.
require('../../tests/unit/ts_loader.js');
const fs=require('fs'),path=require('path'),React=require('react');global.React=React;
const {renderToStaticMarkup}=require('react-dom/server');
const {SkinFacePanel}=require('../../apps/vehicle-app/src/components/skin/SkinFacePanel.tsx');
const {SkinIndicatorValue}=require('../../apps/vehicle-app/src/components/skin/SkinIndicatorValue.tsx');
const {SKIN_REGIONS}=require('../../apps/vehicle-app/src/data/skinDemoFixture.ts');
const root=path.resolve(__dirname,'../..'),detector=process.argv.includes('--detector'),folder=path.join(root,'audit-results/skin-expanded-20261011/interim-diagnosis',detector?'selected-detector-product-staging':'mask-product-staging');
const css=fs.readdirSync(path.join(root,'apps/vehicle-app/.next/static/css')).filter(x=>x.endsWith('.css')).map(x=>fs.readFileSync(path.join(root,'apps/vehicle-app/.next/static/css',x),'utf8')).join('\n');
const receipt=[];
for(const file of fs.readdirSync(folder).filter(x=>detector?/^[a-f0-9]{12}\.json$/.test(x):/^(oil|redness|tone)-(True|False)\.json$/.test(x))){
 const stage=JSON.parse(fs.readFileSync(path.join(folder,file),'utf8'));const criterion=stage.rows.overview.id;
 const snapshot={...stage,localMaps:stage.maps,crop:{x:0,y:0,width:stage.width,height:stage.height},acneCandidates:Object.fromEntries(Object.entries(stage.rows).map(([n,r])=>[n,r.components?.bounds||[]]))};
 const panels=Object.entries(stage.rows).map(([name,row])=>{
  const region=name==='overview'?{id:name,index:1,viewTotal:7,nameTr:'Genel Bakış'}:{...SKIN_REGIONS[name],viewTotal:7};
  const indicator={id:criterion,label:criterion,score:row.value,unit:row.unit,method:'appearance-cv-6',appearance:{...row,type:'appearance_proxy',methodVersion:'appearance-cv-6'}};
  return React.createElement('section',{'data-staging-region':name,key:name},React.createElement('h2',{},region.nameTr),React.createElement(SkinFacePanel,{currentRegion:region,snapshot,selectedCriterion:criterion}),React.createElement(SkinIndicatorValue,{indicator}),detector?React.createElement('div',{'data-final-candidate-count':row.components.candidateCount},row.components.candidateCount):null);
 });
 const html='<!doctype html><meta charset="utf-8"><style>'+css+' body{background:#020617;color:#cbd5e1;padding:24px}main{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:24px}h2{margin-bottom:10px}</style><main>'+renderToStaticMarkup(React.createElement(React.Fragment,{},...panels))+'</main>';
 const output=path.join(folder,file.replace('.json','.html'));fs.writeFileSync(output,html);receipt.push({file:output,sourcePhoto:stage.photoId,criterion,regions:panels.length,realProductionComponents:true,normalUIChanged:false});
}
fs.writeFileSync(path.join(folder,'render-receipt.json'),JSON.stringify(receipt,null,2));console.log('ACTUAL STAGING COMPONENTS',receipt.length);

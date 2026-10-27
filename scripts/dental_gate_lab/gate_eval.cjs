// Runs the app's real client gate (assessDentalCapture, transpiled TS) in Chromium
// on composed frames + MediaPipe landmarks. Usage: node gate_eval.cjs <dentalCapture.ts> <lm.json> <out.json>
const {chromium}=require('playwright');const fs=require('fs');const ts=require(process.env.TS_MODULE||'typescript');
const [,,src,lmPath,outPath]=process.argv;
const js=ts.transpileModule(fs.readFileSync(src,'utf8'),{compilerOptions:{module:ts.ModuleKind.CommonJS,target:ts.ScriptTarget.ES2020}}).outputText;
(async()=>{
 const b=await chromium.launch();const page=await b.newPage();
 await page.setContent('<canvas id=c></canvas>');
 await page.evaluate(code=>{const module={exports:{}};const exports=module.exports;new Function('module','exports','require',code)(module,exports,()=>({}));window.DC=module.exports;},js);
 const items=JSON.parse(fs.readFileSync(lmPath,'utf8')),out=[];
 for(const it of items){
  if(!it.face){out.push({id:it.id,face:false});continue;}
  const data='data:image/png;base64,'+fs.readFileSync(it.frame).toString('base64');
  const r=await page.evaluate(async({data,it})=>{const img=new Image();img.src=data;await img.decode();const c=document.getElementById('c');c.width=img.naturalWidth;c.height=img.naturalHeight;const ctx=c.getContext('2d',{willReadFrequently:true});ctx.drawImage(img,0,0);
   const a={faceDetected:true,isMediaPipeActive:true,landmarks:it.landmarks,faceTransform:it.faceTransform,scaleRatio:.25,faceCount:it.faceCount};
   const res={};for(const pose of ['FRONT','RIGHT','LEFT','BITE']){const q=DC.assessDentalCapture(ctx,a,pose);res[pose]={valid:q.valid,reasons:q.reasons,opening:q.opening,visibleFraction:q.visibleFraction,toothPixels:q.toothPixels,mouthWidth:q.mouthWidth,light:q.light,sharp:q.sharp,glare:q.glareFraction,tongue:q.tongueFraction,contact:q.contact,rotation:q.rotation,extra:q.extra};}
   return res;},{data,it});
  out.push({id:it.id,src:it.src,faceFrac:it.faceFrac,gates:r});
 }
 fs.writeFileSync(outPath,JSON.stringify(out,null,1));await b.close();
 for(const o of out){if(!o.face&&o.face!==undefined){console.log(o.id,'noface');continue;}const g=o.gates,rot=g.FRONT.rotation;console.log(o.id.padEnd(22),'yaw',rot?rot.yawDeg.toFixed(1):'-','pitch',rot?rot.pitchDeg.toFixed(1):'-','roll',rot?rot.rollDeg.toFixed(1):'-','mw',g.FRONT.mouthWidth.toFixed(0),'open',g.FRONT.opening.toFixed(2),'vis',g.FRONT.visibleFraction.toFixed(2),'|',['FRONT','RIGHT','LEFT','BITE'].map(p=>p[0]+':'+(g[p].valid?'OK':g[p].reasons.map(x=>x.slice(0,28)).join('/'))).join(' | '));}
})().catch(e=>{console.error(e);process.exit(1);});

// Verification-only CommonJS bundle of the actual frontend utility sources.
const fs=require('fs'),path=require('path'),ts=require('typescript'),crypto=require('crypto');
const root=path.resolve(__dirname,'../..'),modules={},hashes={};
const entries=['skinSnapshot','skinAnalyzer','skinIndicators','appearanceMeasurements','skinOverview','skinPhotoHistory','healthRecords','healthHistorySeries','skinSurfaceAnalysis','skinMultiAngle','skinEyewear'].map(n=>'apps/vehicle-app/src/utils/'+n+'.ts');
function visit(id){
 if(modules[id])return;const file=path.join(root,id),source=fs.readFileSync(file,'utf8');hashes[id]=crypto.createHash('sha256').update(source).digest('hex');
 if(id.endsWith('.json')){modules[id]={code:'module.exports='+source,dependencies:{}};return;}
 const code=ts.transpileModule(source,{compilerOptions:{module:ts.ModuleKind.CommonJS,target:ts.ScriptTarget.ES2022,esModuleInterop:true}}).outputText,dependencies={};modules[id]={code,dependencies};
 for(const match of code.matchAll(/require\(["']([^"']+)["']\)/g)){
  const request=match[1];if(request==='@mediapipe/tasks-vision'){dependencies[request]='@mediapipe/tasks-vision';continue;}
  if(!request.startsWith('.'))throw Error('Unexpected external dependency '+request);
  let actual=path.resolve(path.dirname(file),request);if(!fs.existsSync(actual))actual+='.ts';if(!fs.existsSync(actual))throw Error(actual);
  const child=path.relative(root,actual).replaceAll('\\','/');if(child.startsWith('../'))throw Error('Scope escape');dependencies[request]=child;visit(child);
 }
}
entries.forEach(visit);
const directory=path.join(root,'.runtime/periorbital-v5-browser-support');fs.mkdirSync(directory,{recursive:true});
const bundle='window.__auditModules='+JSON.stringify(modules)+';window.__auditCache={};window.__auditRequire=function(id){if(id==="@mediapipe/tasks-vision")return window.__auditMediaPipe;let prior=window.__auditCache[id];if(prior)return prior.exports;const module={exports:{}};window.__auditCache[id]=module;const spec=window.__auditModules[id];new Function("module","exports","require",spec.code)(module,module.exports,(name)=>window.__auditRequire(spec.dependencies[name]));return module.exports;};';
fs.writeFileSync(path.join(directory,'utilities.js'),bundle);fs.writeFileSync(path.join(directory,'source-hashes.json'),JSON.stringify(hashes,null,2));console.log(JSON.stringify({modules:Object.keys(modules).length,bytes:bundle.length}));

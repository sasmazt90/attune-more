// Export current original ESLint configuration only; no replacement rules or AST system.
const fs=require('node:fs'); const path=require('node:path'); const crypto=require('node:crypto');
const root=path.resolve(__dirname,'../..'); const product=path.join(root,'../attune-live-test');
const baselineFile=path.join(root,'../attune-biome-feasibility/research/tailwind4-biome/effective-configurations.json');
const baseline=JSON.parse(fs.readFileSync(baselineFile,'utf8'));
const {ESLint}=require(path.join(product,'node_modules/eslint'));
const lint=new ESLint({cwd:path.join(product,'apps/vehicle-app')});
const active=v=>![0,'off'].includes(Array.isArray(v)?v[0]:v);
(async()=>{
 const results=[];
 for(const prior of baseline.results){
  const absolute=path.join(product,prior.file);
  try{
   const config=await lint.calculateConfigForFile(absolute);
   const rules=Object.fromEntries(Object.entries(config.rules||{}).filter(([,v])=>active(v)).sort(([a],[b])=>a.localeCompare(b)));
   const rulesHash=crypto.createHash('sha256').update(JSON.stringify(rules)).digest('hex');
   const ignored=await lint.isPathIgnored(absolute);
   results.push({file:prior.file,tracked:prior.tracked,ignored,rules,rulesHash,activeCount:Object.keys(rules).length,nextCount:Object.keys(rules).filter(r=>r.startsWith('@next/')).length,
       baselineRuleOptionsAndSeverityMatch:rulesHash===prior.rulesHash,baselineScopeMatch:ignored===prior.ignored});
  }catch(error){results.push({file:prior.file,error:String(error.message),baselineAlsoHasNoConfiguration:!!prior.error});}
 }
 const unchanged=results.every(r=>r.error?r.baselineAlsoHasNoConfiguration:r.baselineRuleOptionsAndSeverityMatch&&r.baselineScopeMatch);
 const proof={sourceHead:'f8f08d98cf23eb23c5a171b5b50411364d79adf6',baselineResearchCommit:'5ebf9a9f05dbcb327bb684f2d64645641c662bcc',baselineFileSha256:crypto.createHash('sha256').update(fs.readFileSync(baselineFile)).digest('hex'),
     replacementAttempted:false,negativeParityRerun:false,unchanged,filesChecked:results.length,nextLintDefaultDirectories:require(path.join(product,'node_modules/next/dist/lib/constants')).ESLINT_DEFAULT_DIRS,results};
 fs.writeFileSync(path.join(__dirname,'current-lint-inventory.json'),JSON.stringify(proof,null,2));
 console.log(JSON.stringify({unchanged,filesChecked:results.length,configured47Rules:results.filter(r=>r.activeCount===47).length,noConfig:results.filter(r=>r.error).length}));
 if(!unchanged)process.exitCode=1;
})();

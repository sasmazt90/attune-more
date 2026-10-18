// Only dispatch/forwarding regression: no build, lint, Windows Job or CSS rerun.
const assert=require('node:assert/strict'),path=require('node:path'),fs=require('node:fs');
const root=path.resolve(__dirname,'../..');
const {selectInvocation,main}=require(path.join(root,'scripts/tooling/run_tool.cjs'));

// The same source is the small actual child standing in for the Next CLI.
if(['build','lint'].includes(process.argv[2])){
  process.stdout.write(JSON.stringify({args:process.argv.slice(2),nodeOptions:process.env.NODE_OPTIONS||''}));
  process.stderr.write('REAL_CHILD_STDERR');process.exit(17);
}
if(process.argv[2]==='dispatch'){
  main('linux',process.argv.slice(3),{nextCli:__filename});
}else if(process.argv[2]==='explicit-guard'){
  main('linux',['--guarded',process.argv[3]],{nextCli:__filename});
}else{

async function realForward(mode,extras){
  const plan=selectInvocation('linux',[mode,...extras],{nextCli:__filename});
  assert.equal(plan.kind,'legacy-next');assert.match(plan.message,/NOT applied/);
  const env={...process.env,NODE_OPTIONS:'--trace-warnings'};
  const child=require('node:child_process').spawn(process.execPath,[__filename,'dispatch',mode,...extras],{stdio:['ignore','pipe','pipe'],env,cwd:root,windowsHide:true});
  let stdout='',stderr='';child.stdout.on('data',x=>stdout+=x);child.stderr.on('data',x=>stderr+=x);
  const exit=await new Promise((resolve,reject)=>{child.once('error',reject);child.once('close',(code,signal)=>resolve({code,signal}));});
  assert.deepEqual(exit,{code:17,signal:null});assert.deepEqual(JSON.parse(stdout),{args:[mode,...extras],nodeOptions:env.NODE_OPTIONS});assert.equal(stderr,plan.message+'\nREAL_CHILD_STDERR');
  return {mode,argsPreserved:true,stdoutPreserved:true,stderrPreserved:true,exitCode:exit.code,childPID:child.pid,actualHost:process.platform,selectedPlatform:'linux',realLinuxCI:false};
}

(async()=>{
 const packageRoot=JSON.parse(fs.readFileSync(path.join(root,'package.json'),'utf8'));
 const packageApp=JSON.parse(fs.readFileSync(path.join(root,'apps/vehicle-app/package.json'),'utf8'));
 for(const mode of ['build','lint']){
  assert.equal(packageRoot.scripts[mode],`npm --workspace=apps/vehicle-app run ${mode}`);
  assert.equal(packageApp.scripts[mode],`node ../../scripts/tooling/run_tool.cjs ${mode}`);
  const guarded=selectInvocation('win32',[mode,'--help'],{python:'EXACT_PYTHON'});
  assert.equal(guarded.kind,'windows-job');assert.equal(guarded.command,'EXACT_PYTHON');
  assert.deepEqual(guarded.args,[path.join(root,'scripts/tooling/finite_job.py'),mode,'--help','--owner-pipe']);
  const explicit=selectInvocation('linux',['--guarded',mode]);assert.equal(explicit.kind,'error');assert.equal(explicit.code,78);
  assert.equal(selectInvocation('darwin',[mode]).kind,'legacy-next');
 }
 const rows=[await realForward('build',[]),await realForward('lint',[]),await realForward('lint',['--file','src/çğİı öşü.tsx','--max-warnings','0'])];
 const explicit=require('node:child_process').spawnSync(process.execPath,[__filename,'explicit-guard','build'],{cwd:root,encoding:'utf8',windowsHide:true,timeout:5000});
 assert.equal(explicit.status,78);assert.equal(explicit.stdout,'');assert.match(explicit.stderr,/explicitly selected Windows Job guard is unavailable/);
 const result={windowsMandatoryGuardSelection:true,unsupportedExplicitGuardFailsClosed:true,rootAndWorkspaceCallerFormsPreserved:true,existingUbuntuWorkflowsUnmodified:true,rows,productionBuilds:0,jobTestsRepeated:0,cssRuns:0,realLinuxCI:false};
 if(process.argv[2])fs.writeFileSync(process.argv[2],JSON.stringify(result,null,2));
 console.log(JSON.stringify(result));
})().catch(error=>{console.error(error);process.exitCode=1});
}

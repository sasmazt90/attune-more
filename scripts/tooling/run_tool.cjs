// Platform dispatch, not a cross-platform sandbox. Root npm delegates workspace.
// Windows always selects the Job guard. Other platforms retain original Next.
const {spawn}=require('node:child_process');
const path=require('node:path');
const root=path.resolve(__dirname,'../..');

// Explicit function argument is a test seam, never an environment/CLI override
// of the running host's platform. main() always reads process.platform.
function selectInvocation(platform,argv,options={}){
  const args=[...argv],explicit=args[0]==='--guarded';
  if(explicit)args.shift();
  if(!['build','lint'].includes(args[0]))return {kind:'error',code:64,message:'Usage: run_tool.cjs [--guarded] build|lint [Next options]'};
  if(platform!=='win32'&&explicit)return {kind:'error',code:78,message:'FINITE_TOOL_UNSUPPORTED_OS: explicitly selected Windows Job guard is unavailable; no command started.'};
  if(platform==='win32')return {kind:'windows-job',command:options.python||process.env.ATTUNE_TOOL_PYTHON||'python',args:[path.join(__dirname,'finite_job.py'),...args,'--owner-pipe']};
  return {kind:'legacy-next',command:options.node||process.execPath,args:[options.nextCli||path.join(root,'node_modules/next/dist/bin/next'),...args],message:'[tooling] Non-Windows Next pass-through; Windows Job protection is NOT applied.'};
}

function startLegacy(plan,options={}){
  if(plan.kind!=='legacy-next')throw Error('Expected explicit legacy Next plan');
  return spawn(plan.command,plan.args,{stdio:options.stdio||'inherit',windowsHide:true,env:options.env||process.env,cwd:options.cwd||process.cwd()});
}

function main(platform=process.platform,argv=process.argv.slice(2),options={}){
 const plan=selectInvocation(platform,argv,options);
 if(plan.kind==='error'){console.error(plan.message);process.exitCode=plan.code;return;}
 if(plan.kind==='legacy-next'){
  console.error(plan.message);
  const child=startLegacy(plan);
  const interrupt=()=>child.kill('SIGINT'),terminate=()=>child.kill('SIGTERM');
  process.on('SIGINT',interrupt);process.on('SIGTERM',terminate);
  const release=()=>{process.off('SIGINT',interrupt);process.off('SIGTERM',terminate);};
  child.on('error',error=>{release();console.error('NEXT_NOT_STARTED: '+error.message);process.exitCode=1;});
  child.on('exit',(code,signal)=>{release();process.exitCode=code===null?128+(require('node:os').constants.signals[signal]||2):code;});
  return;
 }
// A Windows Node bridge can otherwise tear down Python before its lease finally
// runs. Keep the supervisor independent, but tethered by the private pipe below.
const child=spawn(plan.command,plan.args,{stdio:['pipe','inherit','inherit'],detached:true,windowsHide:true,env:process.env});
// A private lifetime pipe: bridge death/cancellation closes it. The Next child
// receives NUL stdin, so descendants cannot retain the supervisor's read end.
const cancel=()=>{child.stdin.destroy();};
process.on('SIGINT',cancel);process.on('SIGTERM',cancel);
child.stdin.on('error',()=>{});
child.on('error',error=>{console.error('FINITE_TOOL_NOT_STARTED: '+error.message);process.exitCode=78;});
child.on('exit',(code,signal)=>{child.stdin.destroy();process.exitCode=code===null?130:code;});
}

module.exports={selectInvocation,startLegacy,main};
if(require.main===module)main();

// Single leaf guard. Root npm delegates workspace; never call npm from here.
const {spawn}=require('node:child_process');
const path=require('node:path');
if(process.platform!=='win32'){
  console.error('FINITE_TOOL_UNSUPPORTED_OS: Windows 10+ atomic Job-list support required. This build/lint was not started; dev/watch unchanged.');
  process.exit(78);
}
const python=process.env.ATTUNE_TOOL_PYTHON||'python';
// A Windows Node bridge can otherwise tear down Python before its lease finally
// runs. Keep the supervisor independent, but tethered by the private pipe below.
const child=spawn(python,[path.join(__dirname,'finite_job.py'),...process.argv.slice(2),'--owner-pipe'],{stdio:['pipe','inherit','inherit'],detached:true,windowsHide:true,env:process.env});
// A private lifetime pipe: bridge death/cancellation closes it. The Next child
// receives NUL stdin, so descendants cannot retain the supervisor's read end.
const cancel=()=>{child.stdin.destroy();};
process.on('SIGINT',cancel);process.on('SIGTERM',cancel);
child.stdin.on('error',()=>{});
child.on('error',error=>{console.error('FINITE_TOOL_NOT_STARTED: '+error.message);process.exitCode=78;});
child.on('exit',(code,signal)=>{child.stdin.destroy();process.exitCode=code===null?130:code;});

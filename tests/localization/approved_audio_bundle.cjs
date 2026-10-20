/* Bundle actual production modules for Cloud-only browser evidence; no test
 * hooks are added to the product. React's own production export is retained. */
const fs=require('fs'),path=require('path'),ts=require('typescript');
const root=path.resolve(__dirname,'../..'),modules={};
function collect(file){
 file=path.resolve(file);const id=path.relative(root,file);if(modules[id])return id;
 modules[id]='';
 if(file.endsWith('.json'))modules[id]='module.exports='+fs.readFileSync(file,'utf8')+';';
 else{
  let code=file.endsWith('.ts')?ts.transpileModule(fs.readFileSync(file,'utf8'),{compilerOptions:{module:ts.ModuleKind.CommonJS,target:ts.ScriptTarget.ES2022,esModuleInterop:true}}).outputText:fs.readFileSync(file,'utf8');
  code=code.replace(/require\(["']([^"']+)["']\)/g,(_match,spec)=>{
   let dependency;
   if(spec==='react')dependency=path.join(path.dirname(require.resolve('react')),'cjs/react.production.js');
   else if(spec.startsWith('.')){const base=path.resolve(path.dirname(file),spec);dependency=[base,base+'.ts',base+'.json'].find(p=>fs.existsSync(p)&&fs.statSync(p).isFile());}
   if(!dependency)throw Error('Unresolved browser evidence dependency: '+spec);
   return 'require('+JSON.stringify(collect(dependency))+')';
  });modules[id]=code;
 }return id;
}
const entries={};for(const [key,name] of Object.entries({audio:'i18n/approvedAudio.ts',guidance:'utils/audioGuidance.ts',playback:'utils/fixedFileSpeech.ts',core:'i18n/core.ts',hearing:'utils/hearingAudio.ts'}))entries[key]=collect(path.join(root,'apps/vehicle-app/src',name));
const factories=Object.entries(modules).map(([id,code])=>JSON.stringify(id)+':function(module,exports,require){\n'+code+'\n}').join(',\n');
process.stdout.write('(function(){const factories={'+factories+'},cache={};function require(id){if(cache[id])return cache[id].exports;const module=cache[id]={exports:{}};factories[id](module,module.exports,require);return module.exports;}window.ApprovedAudioQA=Object.fromEntries(Object.entries('+JSON.stringify(entries)+').map(([k,id])=>[k,require(id)]));})();');

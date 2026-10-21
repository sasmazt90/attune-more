/** Compile actual TS dependencies used by small Node-based behavior tests. */
const fs=require('fs'),path=require('path'),Module=require('module'),ts=require('typescript');
for(const ext of ['.ts','.tsx'])require.extensions[ext]=(m,f)=>m._compile(ts.transpileModule(fs.readFileSync(f,'utf8'),{compilerOptions:{module:ts.ModuleKind.CommonJS,target:ts.ScriptTarget.ES2022,jsx:ts.JsxEmit.React,esModuleInterop:true}}).outputText,f);
const resolve=Module._resolveFilename;
Module._resolveFilename=function(request,parent,...rest){
 for(const prefix of ['../i18n/','../../i18n/'])if(request.startsWith(prefix))return path.resolve('apps/vehicle-app/src/i18n',request.slice(prefix.length)+'.ts'+(request.endsWith('LanguageProvider')?'x':''));
 for(const prefix of ['../../utils/','../utils/'])if(request.startsWith(prefix))return path.resolve('apps/vehicle-app/src/utils',request.slice(prefix.length)+'.ts');
 if(request==='./healthModules')return path.resolve('apps/vehicle-app/src/utils/healthModules.ts');
 if(request==='../ResultValue')return path.resolve('apps/vehicle-app/src/components/ResultValue.tsx');
 if(request==='./SkinIndicatorValue')return path.resolve('apps/vehicle-app/src/components/skin/SkinIndicatorValue.tsx');
 try{return resolve.call(this,request,parent,...rest);}catch(error){
  if(error.code==='MODULE_NOT_FOUND'&&request.startsWith('./')){
   const actual=path.resolve('apps/vehicle-app/src/utils',request+'.ts');if(fs.existsSync(actual))return actual;
  }
  throw error;
 }
};

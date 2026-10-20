// Compile the actual transitive TS graph into a disposable directory. No mocks.
const fs=require('fs'),path=require('path'),ts=require('typescript');
module.exports=directory=>{
 const sourceRoot=path.resolve('apps/vehicle-app/src'),compiled=new Set();
 function compile(source){
  const relative=path.relative(sourceRoot,source),target=path.join(directory,relative.replace(/\.tsx?$/,'.js'));
  if(compiled.has(source))return target;compiled.add(source);
  let output=ts.transpileModule(fs.readFileSync(source,'utf8'),{compilerOptions:{module:ts.ModuleKind.CommonJS,target:ts.ScriptTarget.ES2022,jsx:ts.JsxEmit.React,esModuleInterop:true}}).outputText;
  output=output.replace(/require\(["']([^"']+)["']\)/g,(match,spec)=>{
   if(spec.startsWith('.')){
    const actual=path.resolve(path.dirname(source),spec);
    if(spec.endsWith('.json'))return 'require('+JSON.stringify(actual)+')';
    const dependency=['.ts','.tsx'].map(ext=>actual+ext).find(p=>fs.existsSync(p));
    if(dependency)return 'require('+JSON.stringify(compile(dependency))+')';
   }else{try{return 'require('+JSON.stringify(require.resolve(spec,{paths:[process.cwd()]}))+')';}catch{}}
   return match;
  });
  fs.mkdirSync(path.dirname(target),{recursive:true});fs.writeFileSync(target,output);return target;
 }
 return name=>{
  const target=compile(path.resolve(sourceRoot,'utils',name+'.ts'));
  // Keep the historical public test-loader path and module identity for tests
  // that inspect a loaded constructor directly; transitive graph stays intact.
  const alias=path.join(directory,name+'.js');fs.mkdirSync(path.dirname(alias),{recursive:true});
  if(!fs.existsSync(alias))fs.writeFileSync(alias,'module.exports=require('+JSON.stringify(target)+');\n');
  return require(target);
 };
};

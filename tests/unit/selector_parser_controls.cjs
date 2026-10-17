// Bounded security/compatibility controls; no request-path exposure is asserted.
const fs=require('fs'),path=require('path'),assert=require('assert'),crypto=require('crypto'),{spawnSync}=require('child_process');
const root=process.cwd(),out=process.argv[2],label=process.argv[3];
const parser=require('postcss-selector-parser'),postcss=require('postcss'),tailwind=require('tailwindcss'),nested=require('postcss-nested');
const controls=['.a:hover > #b::before','[data-x="a b"]:not(.c)','& .x\\:y','a:is(.a,#b)','a, b, c'];
for(const s of controls)assert.equal(parser().processSync(s),s);
const config={content:[{raw:'sm:hover:bg-red-500 group-hover:text-blue-500 peer-checked:block [&>span]:underline before:content-["x"] hover:!m-2'}],corePlugins:{preflight:false}};
(async()=>{
 const normal=await postcss([tailwind(config),nested]).process('@tailwind utilities; .parent { & > span { color: red; } &:hover { @apply block; } }',{from:undefined});
 const prefixed=await postcss([tailwind({...config,prefix:'tw-',important:'#app',content:[{raw:'tw-block hover:tw-text-red-500 [&>span]:tw-underline'}]})]).process('@tailwind utilities; .button { @apply tw-block; }',{from:undefined});
 const corpus=normal.css+'\n'+prefixed.css;
 const resolutions=['tailwindcss','postcss-nested'].map(name=>{const p=require.resolve('postcss-selector-parser/package.json',{paths:[path.dirname(require.resolve(name))]});return {consumer:name,path:p,version:require(p).version}});
 require(require.resolve('postcss-selector-parser/dist/util/unesc',{paths:[path.dirname(require.resolve('tailwindcss'))]}));
 const timings=[];
 for(const kind of ['class','id','mixed','numeric-prefix'])for(const n of [2000,4000,8000]){
  const script=`const p=require('postcss-selector-parser');const kind=${JSON.stringify(kind)},n=${n};const s=kind==='class'?'.a'.repeat(n):kind==='id'?'#a'.repeat(n):kind==='numeric-prefix'?'1'.repeat(n)+'.a'.repeat(n):'.a#b'.repeat(n);const start=performance.now();const out=p().processSync(s);if(out!==s)throw Error('roundtrip');process.stdout.write(String(performance.now()-start));`;
  const r=spawnSync(process.execPath,['-e',script],{cwd:root,encoding:'utf8',timeout:5000});assert.equal(r.status,0,String(r.error||r.stderr));timings.push({kind,n,ms:Number(r.stdout)});
 }
 const receipt={label,version:require('postcss-selector-parser/package.json').version,resolutions,controls:controls.length,cssSHA256:crypto.createHash('sha256').update(corpus).digest('hex'),timings,privateImport:true,linearComplexityEstablished:false};
 fs.writeFileSync(path.join(out,`selector-${label}.css`),corpus);fs.writeFileSync(path.join(out,`selector-${label}.json`),JSON.stringify(receipt,null,2));
 if(label==='patched'){const prior=JSON.parse(fs.readFileSync(path.join(out,'selector-baseline.json')));assert.equal(receipt.cssSHA256,prior.cssSHA256);assert(resolutions.every(r=>r.version==='7.1.6'));}
 console.log(JSON.stringify(receipt));
})().catch(e=>{console.error(e);process.exit(1)});

import assert from 'node:assert/strict';
import fs from 'node:fs';
import vm from 'node:vm';
import ts from 'typescript';
const filename='apps/vehicle-app/src/utils/localBackend.ts';
const source=ts.transpileModule(fs.readFileSync(filename,'utf8'),{compilerOptions:{module:ts.ModuleKind.CommonJS}}).outputText;
let requested;
function build(env){const context={exports:{},require:()=>({getLanguage:()=> 'de'}),process:{env},location:{origin:'https://attunemore.sasmaz.digital'},URL,globalThis:{fetch:(url)=>{requested=url;return Promise.resolve({});}}};vm.runInNewContext(source,context);return context.exports;}
const local=build({});assert.equal(local.localBackend('/api/health'),'http://localhost:8000/api/health');
assert.equal(build({NEXT_PUBLIC_ATTUNE_LOCAL_API_PORT:'8020'}).localBackend('/api/health'),'http://127.0.0.1:8020/api/health');
const cloud=build({NEXT_PUBLIC_ATTUNE_SAME_ORIGIN_API:'1'});assert.equal(cloud.localBackend('/api/health'),'/api/health');
await cloud.apiFetch('/api/health');assert.equal(requested,'https://attunemore.sasmaz.digital/api/health?language=de');
await cloud.apiFetch('https://outside.example/api/health');assert.equal(requested,'https://outside.example/api/health');
process.env.NEXT_PUBLIC_ATTUNE_SAME_ORIGIN_API='1';const config=(await import('../../apps/vehicle-app/next.config.mjs')).default;
const headers=await config.headers();assert.ok(!JSON.stringify(headers).includes('localhost'));assert.ok(JSON.stringify(headers).includes("connect-src 'self'"));
console.log('Cloud routing and locale checks passed; no AWS execution claimed.');

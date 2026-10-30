require('./ts_loader.js');
const assert=require('node:assert/strict');
const {localAnalysisError}=require('../../apps/vehicle-app/src/utils/localAnalysisError.ts');
const codes=new Map([[429,'LOCAL_ANALYSIS_BUSY'],[504,'LOCAL_ANALYSIS_TIMEOUT'],[409,'CANCELLED'],[503,'LOCAL_MODEL_FAILURE'],[422,'INVALID_LOCAL_GEOMETRY_OR_PHOTO']]);
const messages=[];
for(const [status,code] of codes){const e=localAnalysisError(status,code);assert.equal(e.name,'LocalAnalysisError');assert.equal(e.status,status);assert.equal(e.code,code);messages.push(e.message);}
assert.equal(new Set(messages).size,codes.size);
assert.equal(localAnalysisError(408,'LOCAL_ANALYSIS_TIMEOUT').message,localAnalysisError(504,'LOCAL_ANALYSIS_TIMEOUT').message);
assert.ok(!localAnalysisError(503,'PRIVATE_PROVIDER_TRACE').message.includes('PRIVATE_PROVIDER_TRACE'));
assert.equal(localAnalysisError(500,{}).code,'LOCAL_ANALYSIS_FAILED');
console.log('PASS distinct recovery messages, timeout compatibility, stable codes and private detail exclusion');

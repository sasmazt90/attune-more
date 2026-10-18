import subprocess
from pathlib import Path

def test_isolated_port_preserves_both_ordinary_api_origins():
    script=r"""
require('./tests/unit/ts_loader.js');const assert=require('assert/strict'),{localBackend}=require('./apps/vehicle-app/src/utils/localBackend.ts');
delete process.env.NEXT_PUBLIC_ATTUNE_LOCAL_API_PORT;assert.equal(localBackend('/api/vehicle/state'),'http://localhost:8000/api/vehicle/state');assert.equal(localBackend('/api/vision/speech','http://127.0.0.1:8000'),'http://127.0.0.1:8000/api/vision/speech');
process.env.NEXT_PUBLIC_ATTUNE_LOCAL_API_PORT='8306';assert.equal(localBackend('/api/vision/speech'),'http://127.0.0.1:8306/api/vision/speech');
for(const bad of ['0','65536','8306/evil','https://external.example',' 8306']){process.env.NEXT_PUBLIC_ATTUNE_LOCAL_API_PORT=bad;assert.equal(localBackend('/x'),'http://localhost:8000/x');}
"""
    result=subprocess.run(['node','-e',script],cwd=Path(__file__).resolve().parents[2],capture_output=True,text=True,encoding='utf8')
    assert result.returncode==0,result.stdout+result.stderr

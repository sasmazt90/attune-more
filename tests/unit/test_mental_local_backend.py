"""The isolated history/privacy route must not reach the ordinary backend."""
import subprocess
from pathlib import Path
def test_isolated_api_port_and_ordinary_defaults():
 script="""require('./tests/unit/ts_loader.js');const assert=require('assert/strict'),{localBackend}=require('./apps/vehicle-app/src/utils/localBackend.ts');
 delete process.env.NEXT_PUBLIC_ATTUNE_LOCAL_API_PORT;assert.equal(localBackend('/api/mental/sessions/x'),'http://localhost:8000/api/mental/sessions/x');
 process.env.NEXT_PUBLIC_ATTUNE_LOCAL_API_PORT='8307';assert.equal(localBackend('/api/privacy/wipe'),'http://127.0.0.1:8307/api/privacy/wipe');
 for(const v of ['0','65536','8307/evil','https://external.example']){process.env.NEXT_PUBLIC_ATTUNE_LOCAL_API_PORT=v;assert.equal(localBackend('/api/mental'),'http://localhost:8000/api/mental')}
 """
 result=subprocess.run(['node','-e',script],cwd=Path(__file__).resolve().parents[2],capture_output=True,text=True,encoding='utf8');assert result.returncode==0,result.stdout+result.stderr

"""Real IndexedDB + localStorage rollback/reopen; isolated browser and unit photos."""
import json,subprocess
from pathlib import Path
from playwright.sync_api import sync_playwright
ROOT=Path(__file__).resolve().parents[2]

def test_numeric_failure_preserves_photo_and_crash_recovery(tmp_path):
    modules=['utils/attuneMode','utils/healthModules','utils/serviceConsent','utils/dentalPhotoHistory','utils/skinPhotoHistory','utils/healthRecords']
    node="const fs=require('fs'),ts=require('typescript'),out={};for(const p of "+json.dumps(modules)+"){out[p.split('/').at(-1)]=ts.transpileModule(fs.readFileSync('apps/vehicle-app/src/'+p+'.ts','utf8'),{compilerOptions:{module:ts.ModuleKind.CommonJS}}).outputText;}process.stdout.write(JSON.stringify(out));"
    sources=json.loads(subprocess.check_output(['node','-e',node],cwd=ROOT,text=True,encoding='utf8'))
    sources['healthModules']=sources['healthModules'].replace('require("../../../../shared/healthModules.json")',json.dumps({'default':json.loads((ROOT/'shared/healthModules.json').read_text('utf8'))}))
    with sync_playwright() as pw:
        def launch():
            c=pw.chromium.launch_persistent_context(str(tmp_path/'browser'),channel='chrome',headless=True)
            c.route('**/*',lambda r:r.fulfill(body='<html>Isolated atomic deletion</html>',content_type='text/html'))
            p=c.new_page();p.goto('http://localhost:6983/unit')
            p.evaluate("sources=>{window.M={};for(const [key,source] of Object.entries(sources)){const exports={};new Function('exports','require',source)(exports,id=>M[id.replace('./','')]);M[key]=exports;}window.H=M.healthRecords;window.P=M.skinPhotoHistory;}",sources)
            return c,p
        c,p=launch()
        p.evaluate("""async()=>{
          localStorage.setItem('togg_health_skin_history',JSON.stringify([{id:'a'},{id:'b'}]));localStorage.setItem('togg_health_latest_skin',JSON.stringify({id:'a'}));
          localStorage.setItem(P.SKIN_PHOTO_PERMISSION,'true');const canvas=document.createElement('canvas');canvas.width=canvas.height=32;
          const frames={FRONT:{angle:'FRONT',photoId:'a'.repeat(64),dataUrl:canvas.toDataURL(),width:32,height:32}};
          await P.saveSkinPhotos('a',frames);await P.saveSkinPhotos('b',frames);
        }""")
        before=p.evaluate("async()=>JSON.stringify(await P.loadSkinPhotos('a'))")
        failed=p.evaluate("""async()=>{const set=Storage.prototype.setItem;let once=true;Storage.prototype.setItem=function(k,v){if(k==='togg_health_skin_history'&&once){once=false;throw new DOMException('controlled quota','QuotaExceededError');}return set.call(this,k,v);};try{await H.deleteHealthRecord('skin','a');return false;}catch{return true;}finally{Storage.prototype.setItem=set;}}""")
        assert failed and p.evaluate("async()=>JSON.stringify(await P.loadSkinPhotos('a'))")==before
        assert len(p.evaluate("()=>H.readHealthRecords('skin')"))==2
        assert p.evaluate("localStorage.getItem(H.RECORD_JOURNAL)") is None
        # Simulate a process interruption after IDB completed, before numeric
        # journal finalization. The durable undo photo must survive a restart.
        p.evaluate("""async()=>{
          localStorage.setItem(H.RECORD_JOURNAL,JSON.stringify({'togg_health_skin_history':localStorage.getItem('togg_health_skin_history'),'togg_health_latest_skin':localStorage.getItem('togg_health_latest_skin')}));
          localStorage.setItem(P.SKIN_PHOTO_DELETE_PENDING,JSON.stringify({id:'a',phase:'prepared'}));
          await new Promise((resolve,reject)=>{const q=indexedDB.open('attune-skin-photos');q.onsuccess=()=>{const db=q.result,t=db.transaction('records','readwrite'),s=t.objectStore('records'),r=s.get('a');r.onsuccess=()=>{s.put({...r.result,id:'delete-backup:a',deleteRecoveryFor:'a'});s.delete('a');};t.oncomplete=()=>{db.close();resolve();};t.onabort=()=>reject(t.error);};});
          localStorage.setItem('togg_health_skin_history',JSON.stringify([{id:'b'}]));localStorage.setItem('togg_health_latest_skin',JSON.stringify({id:'b'}));
        }""")
        c.close();c,p=launch()
        assert len(p.evaluate("()=>H.prepareHealthRecords('skin')"))==2
        assert p.evaluate("async()=>JSON.stringify(await P.loadSkinPhotos('a'))")==before
        p.evaluate("()=>H.deleteHealthRecord('skin','a')")
        assert len(p.evaluate("()=>H.readHealthRecords('skin')"))==1
        assert p.evaluate("()=>P.loadSkinPhotos('a')") is None
        assert p.evaluate("()=>P.loadSkinPhotos('b')") is not None
        assert p.evaluate("localStorage.getItem(P.SKIN_PHOTO_DELETE_PENDING)") is None
        c.close()

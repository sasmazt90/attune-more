"""Isolated real-browser IndexedDB contracts; synthetic unit data, no user profile."""
import json,subprocess
from pathlib import Path
from playwright.sync_api import sync_playwright

ROOT=Path(__file__).resolve().parents[2]

def test_explicit_consent_atomic_storage_relaunch_and_revocation(tmp_path):
    js=subprocess.check_output(['node','-e',"const fs=require('fs'),ts=require('typescript');process.stdout.write(ts.transpileModule(fs.readFileSync('apps/vehicle-app/src/utils/skinPhotoHistory.ts','utf8'),{compilerOptions:{module:ts.ModuleKind.CommonJS}}).outputText);"],cwd=ROOT,text=True)
    with sync_playwright() as pw:
        def launch():
            c=pw.chromium.launch_persistent_context(str(tmp_path/'browser'),channel='chrome',headless=True)
            c.route('**/*',lambda r:r.fulfill(body='<html>Isolated photo-store unit test</html>',content_type='text/html'))
            p=c.new_page();p.goto('http://localhost:6982/unit')
            p.evaluate('(js)=>{window.photos={};new Function("exports",js)(photos);}',js)
            return c,p
        c,p=launch()
        p.evaluate('''()=>{
          localStorage.setItem('togg_health_skin_history',JSON.stringify(['a','b','c','d'].map(id=>({id}))));
          const canvas=document.createElement('canvas');canvas.width=32;canvas.height=32;canvas.getContext('2d').fillRect(0,0,32,32);
          window.frames={FRONT:{angle:'FRONT',photoId:'a'.repeat(64),dataUrl:canvas.toDataURL(),width:32,height:32,localMaps:{test:{photoId:'a'.repeat(64),pose:'FRONT',sourceWidth:32,sourceHeight:32,values:new Float32Array([.25,.5]),valid:new Uint8Array([1,0])}}}};
        }''')
        assert not p.evaluate("()=>photos.saveSkinPhotos('a',frames)")
        p.evaluate("localStorage.setItem(photos.SKIN_PHOTO_PERMISSION,'true')")
        assert not p.evaluate("()=>photos.saveSkinPhotos('a',frames,()=>false)")
        for ident in ('a','b','c','d'):assert p.evaluate('(id)=>photos.saveSkinPhotos(id,frames)',ident)
        expected=p.evaluate("async()=>{const f=await photos.loadSkinPhotos('a');return JSON.stringify(f,(_k,v)=>ArrayBuffer.isView(v)?Array.from(v):v);}")
        # A failed replacement aborts its entire transaction; previous data survives.
        failed=p.evaluate('''async()=>{const original=IDBObjectStore.prototype.put;IDBObjectStore.prototype.put=()=>{throw new DOMException('unit quota failure','QuotaExceededError');};try{await photos.saveSkinPhotos('a',frames);return false;}catch{return true;}finally{IDBObjectStore.prototype.put=original;}}''')
        assert failed
        assert p.evaluate("async()=>JSON.stringify(await photos.loadSkinPhotos('a'),(_k,v)=>ArrayBuffer.isView(v)?Array.from(v):v)")==expected
        assert p.evaluate("async()=>{const limit=photos.SKIN_PHOTO_LIMITS.totalBytes;photos.SKIN_PHOTO_LIMITS.totalBytes=1;try{await photos.saveSkinPhotos('a',frames);return false;}catch{return true;}finally{photos.SKIN_PHOTO_LIMITS.totalBytes=limit;}}")
        assert p.evaluate("async()=>JSON.stringify(await photos.loadSkinPhotos('a'),(_k,v)=>ArrayBuffer.isView(v)?Array.from(v):v)")==expected
        assert p.evaluate("async()=>{try{await photos.saveSkinPhotos('a',{FRONT:{...frames.FRONT,padding:'x'.repeat(photos.SKIN_PHOTO_LIMITS.recordBytes)}});return false;}catch{return true;}}")
        c.close();c,p=launch()
        for ident in ('a','b','c','d'):
            assert p.evaluate("async(id)=>JSON.stringify(await photos.loadSkinPhotos(id),(_k,v)=>ArrayBuffer.isView(v)?Array.from(v):v)",ident)==expected
        assert p.evaluate("async()=>{const f=await photos.loadSkinPhotos('a');return f.FRONT.localMaps.test.values instanceof Float32Array&&f.FRONT.localMaps.test.valid instanceof Uint8Array;}")
        p.evaluate("()=>new Promise((resolve,reject)=>{const q=indexedDB.open('attune-skin-photos');q.onsuccess=()=>{const db=q.result,t=db.transaction('records','readwrite'),s=t.objectStore('records'),r=s.get('d');r.onsuccess=()=>s.put({...r.result,sha256:'0'.repeat(64)});t.oncomplete=()=>{db.close();resolve();};t.onerror=()=>reject(t.error);};})")
        assert p.evaluate("async()=>{try{await photos.loadSkinPhotos('d');return false;}catch{return true;}}")
        assert p.evaluate("()=>photos.loadSkinPhotos('d')") is None
        p.evaluate("()=>photos.deleteSkinPhotos('b')");assert p.evaluate("()=>photos.loadSkinPhotos('b')") is None
        # Broken numeric association cannot display another record's pixels.
        p.evaluate("localStorage.setItem('togg_health_skin_history',JSON.stringify([{id:'c'},{id:'d'}]))")
        assert p.evaluate("()=>photos.loadSkinPhotos('a')") is None
        p.evaluate("localStorage.setItem(photos.SKIN_PHOTO_PERMISSION,'false')")
        assert p.evaluate("()=>photos.loadSkinPhotos('c')") is None
        p.evaluate('()=>photos.clearSkinPhotos()')
        assert p.evaluate("JSON.parse(localStorage.getItem('togg_health_skin_history')).length")==2
        p.evaluate("localStorage.setItem(photos.SKIN_PHOTO_PERMISSION,'true')")
        assert p.evaluate("()=>photos.loadSkinPhotos('c')") is None
        c.close()

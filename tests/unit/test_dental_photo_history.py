"""Real IndexedDB in a disposable profile; synthetic source pixels only."""
import subprocess
from pathlib import Path
from playwright.sync_api import sync_playwright
ROOT=Path(__file__).resolve().parents[2]
def test_dental_photo_permission_association_reopen_and_deletion(tmp_path):
 js=subprocess.check_output(['node','-e',"const fs=require('fs'),ts=require('typescript');process.stdout.write(ts.transpileModule(fs.readFileSync('apps/vehicle-app/src/utils/dentalPhotoHistory.ts','utf8'),{compilerOptions:{module:ts.ModuleKind.CommonJS}}).outputText)"],cwd=ROOT,text=True)
 with sync_playwright() as pw:
  def launch():
   c=pw.chromium.launch_persistent_context(str(tmp_path/'profile'),channel='chrome',headless=True,args=['--mute-audio']);c.route('http://localhost:6983/**',lambda r:r.fulfill(body='<html>Isolated dental store unit fixture</html>',content_type='text/html',headers={'Content-Security-Policy':"default-src 'self'; script-src 'self' 'unsafe-eval'; connect-src 'self'; img-src 'self' data: blob:"}));p=c.new_page();p.goto('http://localhost:6983/unit');p.evaluate('(js)=>{window.photos={};new Function("exports",js)(photos)}',js);return c,p
  c,p=launch()
  p.evaluate('''async()=>{const canvas=document.createElement('canvas');canvas.width=32;canvas.height=32;const ctx=canvas.getContext('2d');ctx.fillStyle='#789abc';ctx.fillRect(0,0,32,32);const digest=Array.from(new Uint8Array(await crypto.subtle.digest('SHA-256',ctx.getImageData(0,0,32,32).data))).map(x=>x.toString(16).padStart(2,'0')).join('');window.frames=[{photo:canvas.toDataURL('image/png'),photoId:digest,width:32,height:32,pose:'FRONT',landmarks:[],conditions:{},sourceType:'upload'}];localStorage.setItem('attune_dental_history_v1',JSON.stringify(['a','b'].map(id=>({id,measurements:[{photoId:digest,sourceWidth:32,sourceHeight:32,pose:'FRONT'}]}))));}''')
  assert not p.evaluate("()=>photos.saveDentalPhotos('a',frames)")
  p.evaluate("localStorage.setItem(photos.DENTAL_PHOTO_PERMISSION,'true')")
  assert not p.evaluate("()=>photos.saveDentalPhotos('a',frames,()=>false)")
  assert p.evaluate("()=>photos.saveDentalPhotos('a',frames)")
  expected=p.evaluate("async()=>JSON.stringify(await photos.loadDentalPhotos('a'))")
  assert p.evaluate("async()=>{try{await photos.saveDentalPhotos('a',[{...frames[0],photoId:'a'.repeat(64)}]);return false}catch{return true}}")
  assert p.evaluate("async()=>{const original=IDBObjectStore.prototype.put;IDBObjectStore.prototype.put=()=>{throw Error('controlled quota')};try{await photos.saveDentalPhotos('a',frames);return false}catch{return true}finally{IDBObjectStore.prototype.put=original}}")
  assert p.evaluate("async()=>JSON.stringify(await photos.loadDentalPhotos('a'))")==expected
  assert p.evaluate("async()=>{const old=photos.DENTAL_PHOTO_LIMITS.totalBytes;photos.DENTAL_PHOTO_LIMITS.totalBytes=1;try{await photos.saveDentalPhotos('b',frames);return false}catch{return true}finally{photos.DENTAL_PHOTO_LIMITS.totalBytes=old}}")
  c.close();c,p=launch()
  assert p.evaluate("async()=>JSON.stringify(await photos.loadDentalPhotos('a'))")==expected
  assert p.evaluate("async()=>{await photos.deleteDentalPhotosWithRecords('a',()=>localStorage.setItem('delete-callback','applied'),()=>localStorage.setItem('delete-callback','rolled-back'),()=>localStorage.setItem('delete-finalized','true'));return !(await photos.loadDentalPhotos('a'))&&localStorage.getItem('delete-finalized')==='true'&&!localStorage.getItem(photos.DENTAL_PHOTO_DELETE_PENDING)}")
  p.evaluate("localStorage.setItem(photos.DENTAL_PHOTO_PERMISSION,'false')")
  assert p.evaluate("()=>photos.loadDentalPhotos('b')") is None
  p.evaluate("()=>photos.clearDentalPhotos()")
  c.close()

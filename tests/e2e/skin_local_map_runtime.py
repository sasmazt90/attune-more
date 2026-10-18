"""Real production map worker: cold/warm timing, owned Chrome RSS, cancellation.
Deadline case delays the real worker asset; it is fault injection, not latency.
No camera/model output override and no physical/clinical acceptance claim.
"""
import base64,hashlib,json,subprocess,time
from pathlib import Path
import psutil
from playwright.sync_api import sync_playwright
ROOT=Path(__file__).resolve().parents[2];OUT=ROOT/'audit-results/skin-capabilities-20261008/runtime';OUT.mkdir(parents=True,exist_ok=True)
def main():
 chunks=[p for p in (ROOT/'apps/vehicle-app/.next/static/chunks').glob('*.js') if 'cyan-fixed-100-v1' in p.read_text('utf8')];assert len(chunks)==1;chunk=chunks[0];url='http://127.0.0.1:3000/_next/static/chunks/'+chunk.name
 source=(ROOT/'apps/vehicle-app/src/utils/skinLocalMaps.ts').read_text().replace("new URL('./skinLocalMaps.worker.ts',import.meta.url)",json.dumps(url))
 compile="const fs=require('fs'),ts=require('typescript');process.stdout.write(ts.transpileModule(fs.readFileSync(0,'utf8'),{compilerOptions:{module:ts.ModuleKind.CommonJS,target:ts.ScriptTarget.ES2022}}).outputText)"
 code=subprocess.run(['node','-e',compile],cwd=ROOT,input=source,text=True,capture_output=True,encoding='utf8',check=True).stdout
 captured=ROOT/'audit-results/skin-capabilities-20261008/final-product';meta=json.loads((captured/'source-0-forehead.json').read_text());photo='data:image/png;base64,'+base64.b64encode((captured/'source-0-forehead.png').read_bytes()).decode()
 with sync_playwright() as pw:
  b=pw.chromium.launch(channel='chrome',headless=True,args=['--enable-precise-memory-info']);c=b.new_context();p=c.new_page();p.goto('http://127.0.0.1:3000/skin');cdp=b.new_browser_cdp_session()
  def memory():
   rows=cdp.send('SystemInfo.getProcessInfo')['processInfo'];total=0
   for row in rows:
    try:total+=psutil.Process(int(row['id'])).memory_info().rss
    except psutil.Error:pass
   return total
  before=memory();p.evaluate('code=>{const exports={};new Function("exports",code)(exports);window.MapService=exports.SkinLocalAnalysis;window.service=new MapService();}',code)
  p.evaluate('''async({photo,meta})=>{window.input=meta;const im=new Image();im.src=photo;await im.decode();const canvas=document.createElement('canvas');canvas.width=meta.width;canvas.height=meta.height;canvas.getContext('2d').drawImage(im,0,0);window.nativePixels=canvas.getContext('2d').getImageData(0,0,meta.width,meta.height).data;}''',{'photo':photo,'meta':meta})
  rows=[];rss=[before,memory()]
  for i in range(4):
   result=p.evaluate('''async()=>{const t=performance.now(),v=await service.analyze({width:input.width,height:input.height,angle:input.pose,meshes:input.meshes,exclusions:input.exclusions},new Uint8ClampedArray(nativePixels),true,()=>true,input.photoId);return {photoId:v.photoId,loadMs:v.loadMs,analysisMs:v.analysisMs,knownAllocatedBytes:v.allocatedBytes,totalMs:performance.now()-t,maps:Object.keys(v.maps),mainHeapBytes:performance.memory?.usedJSHeapSize};}''');assert result['photoId']==meta['photoId'] and len(result['maps'])==5;rows.append(result);rss.append(memory())
  cancelled=p.evaluate('''async()=>{const t=performance.now(),promise=service.analyze({width:input.width,height:input.height,angle:input.pose,meshes:input.meshes,exclusions:input.exclusions},new Uint8ClampedArray(nativePixels),true,()=>true);service.cancel();try{await promise;return {rejected:false}}catch(e){return {rejected:true,error:e.message,ms:performance.now()-t}}}''');assert cancelled['rejected'] and cancelled['error']=='CANCELLED_OR_TIMEOUT'
  # Delay asset response, not worker content. Main-thread heartbeat remains live.
  def delayed(route):time.sleep(3);route.continue_()
  p.route(url,delayed);deadline=p.evaluate('''async()=>{let beats=0;const clock=setInterval(()=>beats++,50),t=performance.now();try{await service.analyze({width:input.width,height:input.height,angle:input.pose,meshes:input.meshes,exclusions:input.exclusions},new Uint8ClampedArray(nativePixels),true,()=>true);return {rejected:false}}catch(e){return {rejected:true,error:e.message,ms:performance.now()-t,heartbeatTicks:beats}}finally{clearInterval(clock)}}''');assert deadline['rejected'] and 2400<=deadline['ms']<=3500 and deadline['heartbeatTicks']>=30,deadline
  p.unroute(url,delayed);p.evaluate('service.cancel()');rss.append(memory());cdp.detach();c.close();b.close()
 proof={'status':'PASS','buildId':(ROOT/'apps/vehicle-app/.next/BUILD_ID').read_text().strip(),'workerSHA256':hashlib.sha256(chunk.read_bytes()).hexdigest(),'workerURL':url,'actualProductionWorker':True,'serviceSourceProbe':True,'physicalCamera':False,'clinicalAcceptance':False,'coldFirstWarmNext':rows,'ownedChromeAggregateRSSBytes':{'baseline':before,'sampledMaximum':max(rss),'afterCancel':rss[-1],'sampling':'working-set sum of owned browser processes; shared pages may be double-counted; sampled, not peak instrumentation'},'cancel':cancelled,'timeout':{'workerAssetFaultDelayMs':3000,**deadline}}
 (OUT/'proof.json').write_text(json.dumps(proof,indent=2),'utf8');print(json.dumps(proof))
if __name__=='__main__':main()

"""Fresh final-build checks. Camera/analysis queue is serial to respect the
actual single-analysis lease. No provider scripts, normal profile or fake save.
Audio/UI callback checks may run in a separate queue; no physical claims.
"""
from pathlib import Path
import sys,os,subprocess,json,time,urllib.request
ROOT=Path(__file__).resolve().parents[2];OUT=ROOT/'audit-results/all-health-20261010'/os.environ.get('ATTUNE_FINAL_RUN_TAG','final');OUT.mkdir(parents=True,exist_ok=True)
build=(ROOT/'apps/vehicle-app/.next/BUILD_ID').read_text().strip();queue=sys.argv[1]
# Normal launcher starts asynchronously. Wait for both actual services, without
# changing vehicle/model/quality state or using a fake response.
deadline=time.monotonic()+45
while True:
 try:
  for url in ('http://127.0.0.1:8000/api/health','http://127.0.0.1:3000/'):
   with urllib.request.urlopen(url,timeout=2) as response:assert response.status==200
  break
 except Exception:
  if time.monotonic()>deadline:raise RuntimeError('Normal launcher services did not become ready')
  time.sleep(.5)
camera=[('vision24',['scripts/audit/run_current_health.py','vision_feedback','final3-vision24']),('vision-size',['scripts/audit/run_current_health.py','vision_frame_size_followup','final3-vision-size']),('vision-memory',['scripts/audit/run_current_health.py','vision_answer_memory_followup','final3-vision-memory']),('vision-negative',['scripts/audit/run_current_health.py','current_vision_negative','final3-vision-negative']),('vision-motion',['scripts/audit/run_current_health.py','vision_motion_pixels','final3-vision-motion']),('vision-transform',['scripts/audit/run_current_health.py','vision_transform_pixels','final3-vision-transform']),('dental-natural',['scripts/audit/dental_natural_ui.py']),('dental-history',['scripts/audit/run_current_health.py','current_dental_history','final3-dental-history']),('dental-camera',['scripts/audit/run_current_health.py','current_dental_capture','final3-dental-camera']),('dental-negative',['scripts/audit/run_current_health.py','current_dental_negative','final3-dental-negative']),('skin',['scripts/audit/run_current_health.py','current_skin_contract','final3-skin']),('skin-history',['scripts/audit/run_current_health.py','current_skin_photo_history','final3-skin-history']),('skin-wipe',['scripts/audit/run_current_health.py','current_skin_photo_wipe_success','final3-skin-wipe']),('natural-skin',['scripts/audit/natural_skin_sources.py']),('responsive',['scripts/audit/run_current_health.py','current_health_responsive','final3-responsive'])]
audio=[('hearing-din24',['scripts/audit/run_current_health.py','current_hearing_positive','final3-hearing-din24']),('hearing-tone',['scripts/audit/run_current_health.py','current_hearing_tone','final3-hearing-tone']),('hearing-threshold',['scripts/audit/hearing_threshold_positive.py']),('mental-asr',['scripts/audit/mental_asr_lifecycle.py']),('mental-control',['scripts/audit/mental_current_control.py']),('audio-focus',['scripts/audit/run_current_health.py','current_audio_focus','final3-audio-focus']),('care',['scripts/audit/run_current_health.py','current_care_contract','final3-care'])]
assert queue in ('camera','audio','all');ledger=[]
selected=camera if queue=='camera' else audio if queue=='audio' else camera+audio
tag=os.environ.get('ATTUNE_FINAL_RUN_TAG','final')
for name,args in selected:
 args=[a.replace('final3-',tag+'-') for a in args]
 assert (ROOT/'apps/vehicle-app/.next/BUILD_ID').read_text().strip()==build,'Do not mix builds'
 started=time.monotonic();env={**os.environ,'PYTHONPATH':str(ROOT/'.runtime/security-20261008')+os.pathsep+str(ROOT/'services/core-api')}
 if name=='dental-negative':env['DENTAL_CAPTURE_INPUT']=str(ROOT/'audit-results/all-health-20261010/e2e'/f'{tag}-dental-camera/capture-request-private.json')
 with (OUT/(name+'.log')).open('w',encoding='utf8') as log:
  try:result=subprocess.run([sys.executable,'-X','utf8',*args],cwd=ROOT,env=env,stdout=log,stderr=log,timeout=1800);code=result.returncode
  except subprocess.TimeoutExpired:code=124
 entry=dict(name=name,buildId=build,exitCode=code,seconds=round(time.monotonic()-started,2),scope='production path; controlled callbacks/photographic/audio fixtures are not physical acceptance')
 ledger.append(entry);(OUT/(queue+'-execution.json')).write_text(json.dumps(ledger,indent=2),'utf8');print(json.dumps(entry),flush=True)
 # Independent remaining checks continue after a failed test. Failures remain
 # in the ledger and require diagnosis, never hidden behind the next PASS.
print(json.dumps(dict(buildId=build,queue=queue,failed=[r['name'] for r in ledger if r['exitCode']],completed=len(ledger))),flush=True)

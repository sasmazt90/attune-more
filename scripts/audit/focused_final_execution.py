"""Fresh normal-production checks; isolated profiles, no paid provider calls.
One named check per invocation. Never import prior-build acceptance.
"""
from pathlib import Path
import json, os, subprocess, sys, time, shutil

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / 'audit-results/all-health-20261010'
CHECKS = {
    'skin-api': ['scripts/audit/skin_focused_api.py'],
    'skin': ['scripts/audit/run_current_health.py', 'current_skin_contract', 'focused-final-skin'],
    'skin-history': ['scripts/audit/run_current_health.py', 'current_skin_photo_history', 'focused-final-history'],
    'skin-wipe': ['scripts/audit/run_current_health.py', 'current_skin_photo_wipe_success', 'focused-final-wipe'],
    'skin-followups': ['scripts/audit/skin_followups_ui.py'],
    'final-ui': ['scripts/audit/final_ui_review.py'],
    'responsive': ['scripts/audit/run_current_health.py', 'current_health_responsive', 'focused-final-responsive'],
    'audio-focus': ['scripts/audit/run_current_health.py', 'current_audio_focus', 'focused-final-audio-focus'],
    'care': ['scripts/audit/run_current_health.py', 'current_care_contract', 'focused-final-care'],
    'guidance': ['scripts/audit/run_current_health.py', 'current_guidance', 'focused-final-guidance'],
    'dental-camera': ['scripts/audit/run_current_health.py', 'current_dental_capture', 'focused-final-dental-camera'],
    'dental-history': ['scripts/audit/run_current_health.py', 'current_dental_history', 'focused-final-dental-history'],
    'vision-negative': ['scripts/audit/run_current_health.py', 'current_vision_negative', 'focused-final-vision-negative'],
}

name = sys.argv[1]
assert name in CHECKS
build = (ROOT / 'apps/vehicle-app/.next/BUILD_ID').read_text().strip()
ledger_path = OUT / 'focused-final-execution.json'
ledger = json.loads(ledger_path.read_text()) if ledger_path.exists() else {}
assert not ledger or ledger['buildId'] == build, 'Existing ledger belongs to another build'
ledger.setdefault('buildId', build)
ledger.setdefault('checks', {})
ledger.update(physicalAcceptance=False, normalUserHistoryTouched=False, newPaidProviderCalls=0)
log = OUT / f'focused-final-{name}.log'
previous=ledger['checks'].get(name)
if previous and log.exists():
    archive=log.with_name(log.stem+f'-previous-{time.time_ns()}.log')
    shutil.copyfile(log,archive)
    ledger.setdefault('priorAttempts',[]).append(dict(name=name,**previous,archivedLog=str(archive.relative_to(ROOT))))
env = dict(os.environ, PYTHONPATH='.runtime/security-20261008;services/core-api',
           PYTHONUTF8='1', PYTHONIOENCODING='utf-8')
start = time.time()
with log.open('w', encoding='utf8') as handle:
    result = subprocess.run([sys.executable, *CHECKS[name]], cwd=ROOT, env=env,
                            stdout=handle, stderr=subprocess.STDOUT)
entry = dict(exit=result.returncode, seconds=time.time()-start, log=str(log.relative_to(ROOT)),
             command=CHECKS[name], buildId=build, controlled=True, physicalAcceptance=False)
ledger['checks'][name] = entry
ledger_path.write_text(json.dumps(ledger, indent=2), 'utf8')
print(json.dumps({name: entry}), flush=True)
sys.exit(result.returncode)

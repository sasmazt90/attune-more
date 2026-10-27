#!/usr/bin/env python3
"""Plan bounded new-seed revisions of unapproved, failed production clips.

Original WAVs are retained. Approved recordings cannot be revised by this tool.
Run only after initial production and pronunciation screening have finished.
"""
import argparse
import copy
import json
from pathlib import Path
from mental_audio_batch import authorize_full_production, PUBLIC, MANIFEST
from validate_mental_audio import fingerprint, atomic_json

FEMALE_MANIFEST=MANIFEST.with_name('female-calm-v1-manifest.json')
REPAIRABLE={'clipped-samples','silent-or-too-quiet','excessive-edge-silence','pronunciation-screen-review'}


def plan(manifest,report,cache,public=PUBLIC):
    if any(not e.get('sha256') for e in manifest['entries']):raise ValueError('INITIAL_PRODUCTION_MUST_FINISH')
    result=copy.deepcopy(manifest);entries={e['assetId']:e for e in result['entries']};failed={}
    for row in report['issues']:
        reasons=set(row['issues'])&REPAIRABLE
        if reasons:failed.setdefault(row['assetId'],set()).update(reasons)
    revisions=[];exhausted=[]
    for key,reasons in failed.items():
        entry=entries[key]
        if entry.get('ownerApprovedAt') or entry['approvalStatus']=='approved':raise ValueError('APPROVED_RECORDING_MUST_NOT_BE_REVISED')
        attempt=entry.get('generationAttempt',0)+1
        if attempt>3:exhausted.append(key);continue
        original=(public/entry['audioPath'].lstrip('/')).resolve()
        if not original.is_relative_to(public.resolve()) or fingerprint(original)!=entry['sha256']:raise ValueError('ORIGINAL_RECORDING_HASH_MISMATCH')
        new_path='/audio/mental/'+entry['assetId']+f'-r{attempt}.wav'
        target=(public/new_path.lstrip('/')).resolve()
        if not target.is_relative_to(public.resolve()) or target.exists():raise ValueError('REVISION_PATH_UNAVAILABLE_NO_OVERWRITE')
        history={name:copy.deepcopy(entry[name]) for name in ('audioPath','sha256','bytes','durationMs','recipe','recipeSha256','qualityMetrics','productionTelemetry') if name in entry}
        history.update(reasons=sorted(reasons),pronunciationEvidence=copy.deepcopy(cache.get('assets',{}).get(key,{})))
        entry.setdefault('supersededRecordings',[]).append(history)
        for name in ('sha256','bytes','durationMs','sampleRate','recipe','recipeSha256','qualityMetrics','productionTelemetry','validatedAt'):entry.pop(name,None)
        entry.update(audioPath=new_path,generationAttempt=attempt,approvalStatus='pending-generation')
        revisions.append({'assetId':key,'newAudioPath':new_path,'generationAttempt':attempt,'reasons':sorted(reasons)})
    return result,{'revisions':revisions,'exhausted':exhausted,'approvedRecordingsChanged':0}


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--report',type=Path,required=True);p.add_argument('--cache',type=Path,required=True)
    p.add_argument('--archive-dir',type=Path,required=True);p.add_argument('--prepare',action='store_true',help='Record the revision plan; otherwise read-only.')
    a=p.parse_args();manifest=json.loads(FEMALE_MANIFEST.read_text());authorize_full_production(manifest)
    cache=json.loads(a.cache.read_text());result,report=plan(manifest,json.loads(a.report.read_text()),cache)
    if a.prepare and report['revisions']:
        a.archive_dir.mkdir(parents=True,exist_ok=False)
        atomic_json(a.archive_dir/'manifest-before-repairs.json',manifest)
        atomic_json(a.archive_dir/'pronunciation-before-repairs.json',cache)
        atomic_json(a.archive_dir/'repair-plan.json',report)
        atomic_json(FEMALE_MANIFEST,result)
    print(json.dumps(report,ensure_ascii=False))


if __name__=='__main__':main()

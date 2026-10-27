#!/usr/bin/env python3
"""Audit the full catalog and record owner-authorized production validation.

Individual owner listening approval remains limited to the nine approved samples.
No audio bytes are changed; incomplete or flagged assets cannot be finalized.
"""
import argparse
from collections import Counter
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
from validate_mental_audio import inspect_wave, fingerprint, normalize, pronunciation, atomic_json

ROOT=Path(__file__).resolve().parents[1]
PUBLIC=ROOT/'apps/vehicle-app/public'
MANIFEST=PUBLIC/'audio/mental/v1/female-calm-v1-manifest.json'


def audit(manifest,content,cache,public=PUBLIC,root=ROOT):
    entries={e['assetId']:e for e in manifest['entries']};rows={r['audioAssetId']:r for r in content['rows']}
    if len(entries)!=414 or len(rows)!=414 or set(entries)!=set(rows):raise ValueError('CATALOG_ID_SET_MISMATCH')
    pinned=json.loads((root/'docs/mental-structured/pinned-runtime.json').read_text())
    authorization=manifest.get('productionAuthorization',{})
    if (manifest['joinSilenceMs']!=120 or manifest.get('joinApprovalStatus')!='approved'
        or manifest['conditioningSha256']!=pinned['referenceSHA256']
        or manifest['generation']!=pinned['generation']
        or authorization.get('conditioningSha256')!=manifest['conditioningSha256']
        or authorization.get('generation')!=manifest['generation']):raise ValueError('OWNER_APPROVED_CONFIGURATION_MISMATCH')
    issues=[];metrics={};screens=Counter();generated=0;owner_listened=0
    for baseline in ('female-approved-recordings.json','female-comparison-baseline.json'):
        proof=json.loads((root/'docs/mental-structured'/baseline).read_text())
        for name,sha in proof['sha256'].items():
            if fingerprint(root/name)!=sha:raise ValueError('PROTECTED_RECORDING_OR_COMPARISON_CHANGED')
    for key,row in rows.items():
        entry=entries[key];language=row['language']
        if (entry['exactScript']!=row['exactText'] or entry['language']!=language or entry['speakerProfile']!='female-calm-v1'
            or row['speakerProfile']!='female-calm-v1'):raise ValueError('CATALOG_SCRIPT_OR_PROFILE_MISMATCH')
        words=set(normalize(row['exactText'],language))
        if words&({'sen','seni','sana','senin','senden'} if language=='tr' else {'du','dich','dir','dein','deine'} if language=='de' else set()):
            issues.append({'assetId':key,'issues':['informal-source-address']})
        if not entry.get('sha256'):
            issues.append({'assetId':key,'issues':['not-generated']});continue
        path=(public/entry['audioPath'].lstrip('/')).resolve()
        if not path.is_relative_to((public/'audio/mental/v1').resolve()) or fingerprint(path)!=entry['sha256']:raise ValueError('AUDIO_INTEGRITY_MISMATCH')
        actual,problems=inspect_wave(path);metrics[key]=actual;generated+=1
        if any(actual[k]!=entry[k] for k in ('durationMs','bytes','sampleRate')):raise ValueError('PCM_MANIFEST_MISMATCH')
        recipe=entry['recipe']
        signature=hashlib.sha256(json.dumps(recipe,sort_keys=True,ensure_ascii=False).encode()).hexdigest()
        if (signature!=entry['recipeSha256'] or recipe['text']!=entry['exactScript'] or recipe['language']!=language
            or recipe['speakerProfile']!='female-calm-v1' or recipe['conditioningSha256']!=manifest['conditioningSha256']
            or recipe['generation']!=manifest['generation'] or recipe['modelRevision']!=pinned['model']['revision']
            or recipe['sourceRevision']!=pinned['model']['sourceRevision']):raise ValueError('APPROVED_RECIPE_MISMATCH')
        owner=bool(entry.get('ownerApprovedAt'));owner_listened+=owner
        screen=cache.get('assets',{}).get(key)
        if not screen or screen['sha256']!=entry['sha256']:
            problems.append('pronunciation-screen-pending')
        else:
            primary=pronunciation(entry['exactScript'],screen['pronunciationScreen']['transcript'],language)
            secondary=screen.get('secondaryPronunciationScreen')
            effective=pronunciation(entry['exactScript'],secondary['transcript'],language) if secondary else primary
            screens[effective['status']]+=1
            if effective['status']=='review-required' and not owner:problems.append('pronunciation-screen-review')
        if problems:issues.append({'assetId':key,'issues':problems})
    if owner_listened!=9:raise ValueError('REPRESENTATIVE_APPROVAL_MISMATCH')
    pairs=0;checked_pairs=0;maximum_pause=0
    by_variant={(r['language'],r['variantId']):r for r in rows.values()}
    for row in rows.values():
        if row['questionNodeId'].startswith('B') and row['exactText'].count('?')!=1:raise ValueError('B_QUESTION_SHAPE_MISMATCH')
        for a_id in row['compatibleAPhrases']:
            a=by_variant.get((row['language'],a_id));pairs+=1
            if not a or a['questionNodeId']!='A' or a['speakerProfile']!=row['speakerProfile']:raise ValueError('A_B_COMPATIBILITY_MISMATCH')
            if a['audioAssetId'] in metrics and row['audioAssetId'] in metrics:
                checked_pairs+=1
                pause=metrics[a['audioAssetId']]['trailingSilenceMs']+manifest['joinSilenceMs']+metrics[row['audioAssetId']]['leadingSilenceMs']
                maximum_pause=max(maximum_pause,pause)
                if pause>1200:issues.append({'assetId':row['audioAssetId'],'aVariant':a_id,'issues':['excessive-effective-join-pause']})
    return {'schema':'mental-audio-catalog-validation-v1','profile':'female-calm-v1','expectedAssets':414,'generatedAssets':generated,
        'byLanguage':{language:sum(e['language']==language and bool(e.get('sha256')) for e in entries.values()) for language in ('tr','en','de')},
        'ownerListenedRepresentativeAssets':owner_listened,'joinSilenceMs':manifest['joinSilenceMs'],
        'allowedABPairs':pairs,'audioVerifiedABPairs':checked_pairs,'maximumEffectiveJoinPauseMs':maximum_pause,
        'clippedSamples':sum(m['clippedSamples'] for m in metrics.values()),'pronunciationScreenCounts':dict(screens),
        'issues':issues,'readyForProductionValidation':generated==414 and checked_pairs==pairs and not issues,
        'referenceSHA256':manifest['conditioningSha256'],'generation':manifest['generation'],
        'verifier':cache.get('verifier'),'secondaryVerifier':cache.get('secondaryVerifier'),
        'limitations':['ASR agreement is a pronunciation screen, not native-speaker or prosody certification.',
            'Nine representative recordings and six joins received explicit owner listening approval.',
            'Remaining assets use owner-authorized routine production validation; individual owner listening is not claimed.',
            'Physical vehicle acceptance is outside Cloud regression tests.']}


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--cache',type=Path,required=True);p.add_argument('--report',type=Path,required=True)
    p.add_argument('--finalize',action='store_true');args=p.parse_args()
    manifest=json.loads(MANIFEST.read_text());content_path=ROOT/'shared/mental/v1/content.json';content=json.loads(content_path.read_text())
    cache=json.loads(args.cache.read_text());report=audit(manifest,content,cache)
    report['validatedAt']=datetime.now(timezone.utc).isoformat();atomic_json(args.report,report)
    if args.finalize:
        if not report['readyForProductionValidation']:raise SystemExit('CATALOG_VALIDATION_INCOMPLETE: see report; no approval status changed.')
        if not manifest.get('productionAuthorization',{}).get('ownerAuthorizedAt'):raise SystemExit('OWNER_PRODUCTION_AUTHORIZATION_REQUIRED')
        for entry in manifest['entries']:
            if entry.get('ownerApprovedAt'):
                entry.setdefault('approvalKind','owner-listened-representative');continue
            entry.update(approvalStatus='approved',approvalKind='owner-authorized-production-validation',validatedAt=report['validatedAt'])
        manifest['catalogValidation']={'status':'passed','validatedAt':report['validatedAt'],'assets':414,'reportSHA256':fingerprint(args.report)}
        content['reviewStatus']='approved';content['reviewBasis']='engineering/editorial catalog validation and explicit owner production authorization; no independent clinical validation claimed'
        atomic_json(MANIFEST,manifest);atomic_json(content_path,content)
    print(json.dumps({k:report[k] for k in ('generatedAssets','expectedAssets','allowedABPairs','audioVerifiedABPairs','clippedSamples','readyForProductionValidation')}))


if __name__=='__main__':main()

"""Runs a given checkout's validate_spoken_summary (read-only) on fixture candidate lines and on prototype lines.
Usage: python -I validator_on_fixture.py CHECKOUT_ROOT FIXTURE_JSON [EXTRA_LINES_JSON] OUT_JSON"""
import json, sys
root, fixture, *rest = sys.argv[1:]
out_path = rest[-1]; extra = rest[0] if len(rest) == 2 else None
sys.path.insert(0, root + '/services/core-api')
from mental_analysis import validate_spoken_summary
fx = json.load(open(fixture, encoding='utf-8'))
res = {'checkout': root, 'fixture': fixture, 'cases': []}
for c in fx['cases']:
    _, status = validate_spoken_summary(c['candidate'], c['language'], [{'role': 'user', 'content': m} for m in fx['users'][c['user']]])
    res['cases'].append({'id': c['id'], 'language': c['language'], 'content': c['content'], 'status': status, 'accepted': status is None})
if extra:
    ex = json.load(open(extra, encoding='utf-8'))
    res['prototypeLines'] = []
    for r in ex['results']:
        for cand in [x for x in [(r.get('line') or {}).get('candidate'), (r.get('line') or {}).get('retryCandidate')] if x]:
            _, status = validate_spoken_summary(cand, r['language'], [{'role': 'user', 'content': m} for m in r['user']])
            res['prototypeLines'].append({'id': r['id'], 'line': cand, 'status': status})
acc = [c for c in res['cases'] if c['accepted']]
res['summary'] = {'n': len(res['cases']), 'accepted': len(acc), 'falseAccepts': [c['id'] for c in acc if c['content'] != 'correct'],
                  'unnecessaryRejects': [c['id'] for c in res['cases'] if not c['accepted'] and c['content'] == 'correct']}
json.dump(res, open(out_path, 'w'), ensure_ascii=False, indent=1)
print(json.dumps(res['summary'], ensure_ascii=False))

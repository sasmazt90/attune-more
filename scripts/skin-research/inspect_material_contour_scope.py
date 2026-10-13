"""Read existing reviewed inventories only; no new archive traversal."""
import json
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2];CENSUS=ROOT/'audit-results/dry-sag-source-census-20261013'
labels=json.loads((ROOT/'audit-results/dry-sag-component-followup-20261013/object-labels.json').read_text('utf8'))['controls'];used={r['group'] for r in labels}
for domain in ['pul','dry-label']:
    selected=json.loads((CENSUS/(domain+'-selection.json')).read_text('utf8'));review=json.loads((CENSUS/(domain+'-visual-review.json')).read_text('utf8'))['records']
    print(domain,'selection type',type(selected).__name__,'keys',list(selected[0] if isinstance(selected,list) else selected)[:10])
    for code in ['F','N','P','C','H']:
        rows=[r for r in review if r['observationCode']==code and r['group'] not in used][:10]
        print(code,[(r.get('censusIndex',r.get('index')),r['sha256'][:8],r['reviewStatus']) for r in rows])
contour=json.loads((CENSUS/'contour-visual-review.json').read_text('utf8'))
rows=contour.get('records',contour.get('rows',[]));print('contour',list(rows[0]),'L',[(r.get('censusIndex',r.get('index')),r['sha256'][:8]) for r in rows if r.get('observationCode')=='L'][:25])
old=ROOT/'audit-results/skin-expanded-20261011/sag-controls'
if old.exists():
    review=json.loads((old/'review.json').read_text('utf8'));print('old targeted sag',[(r['index'],r['sha256'][:8],r['engineeringSagAppearance']) for r in review['rows'] if r['engineeringSagAppearance']])

"""Two previously reviewed sources for fresh browser geometry; no source search."""
import json
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2];OUT=ROOT/'audit-results/native-material-contour-20261013'
old=ROOT/'audit-results/skin-expanded-20261011/sag-controls'
rows=json.loads((old/'candidates.json').read_text('utf8'))+json.loads((old/'additional-candidates.json').read_text('utf8'))
selection=[{**rows[i],'previousReviewIndex':i,'selectionReason':'previously reviewed engineering contour appearance/control; neither age nor source class is truth'} for i in [47,4]]
target=OUT/'contour-browser-selection.json';assert not target.exists();target.write_text(json.dumps(selection,indent=2),'utf8')
print([(r['sha256'][:8],r['previousReviewIndex']) for r in selection])

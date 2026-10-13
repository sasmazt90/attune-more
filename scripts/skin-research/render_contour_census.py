"""Every remaining lower-contour representative, after real pose/quality calculation."""
import hashlib,json
from collections import Counter
from pathlib import Path
from PIL import Image,ImageDraw
ROOT=Path(__file__).resolve().parents[2];OUT=ROOT/'audit-results/dry-sag-source-census-20261013'
rows=json.loads((OUT/'contour-selection.json').read_text('utf8'));observations=[];cell=256;cols=4
for start in range(0,len(rows),24):
    page=rows[start:start+24];sheet=Image.new('RGB',(cols*cell,6*(cell+48)),'#111111');draw=ImageDraw.Draw(sheet)
    for j,r in enumerate(page):
        probe=json.loads((OUT/(r['sha256'][:8]+'-probe.json')).read_text('utf8'))
        x=j%cols*cell;y=j//cols*(cell+48);conditions=probe['conditions'];q=probe['quality']['isValid'];angles=probe['supportedAngles']
        im=Image.open(r['absolutePath']).convert('RGB');im.thumbnail((cell,cell));sheet.paste(im,(x+(cell-im.width)//2,y+48+(cell-im.height)//2))
        draw.text((x+3,y+1),f"{r['censusIndex']:03d} {r['sha256'][:8]}",fill='white')
        draw.text((x+3,y+16),f"yaw {conditions['yaw']:.2f} pitch {conditions['pitch']:.2f} Q{int(q)} {'/'.join(angles)}",fill='#66ff88' if q and angles else '#ffbbbb')
        draw.text((x+3,y+31),f"mouth {probe['mouthOpening'] or 0:.3f} {probe['snapshotFailure'] or ''}"[:42],fill='#bbbbbb')
        observations.append(dict(index=r['censusIndex'],sha256=r['sha256'],group=r['group'],conditions=conditions,quality=probe['quality'],angles=angles,utilityPoseCaptureCompleted=probe['poseCaptureCompleted'],mouthOpening=probe['mouthOpening'],snapshotFailure=probe['snapshotFailure']))
    sheet.save(OUT/f'contour-sheet-{start//24:02d}.jpg',quality=95)
(OUT/'contour-pose-census.json').write_text(json.dumps(dict(rows=observations,allProbesRealMediaPipe=all(json.loads((OUT/(r['sha256'][:8]+'-probe.json')).read_text('utf8'))['realMediaPipe'] for r in rows),counts=dict(representatives=len(rows),qualityAndSupportedPose=sum(bool(v['quality']['isValid'] and v['angles']) for v in observations))),ensure_ascii=False,indent=2),'utf8')
print(json.dumps(dict(sheets=(len(rows)+23)//24,representatives=len(rows),qualityAndSupportedPose=sum(bool(v['quality']['isValid'] and v['angles']) for v in observations))))

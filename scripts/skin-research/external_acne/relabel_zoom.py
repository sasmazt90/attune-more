"""Label-free zoom render of a source-px rectangle with source-px grid (same style as sheets). usage: zoom.py photo x0 y0 x1 y1 out.jpg [grid]"""
import sys, json, cv2
sys.path.insert(0, '.'); from make_label_sheets import render_tile
man = {m['sha256'][:12]: m for m in json.load(open('../pack/manifest.json')) if m['kind'] == 'positive-photo'}
ph = sys.argv[1]; x0, y0, x1, y1 = map(int, sys.argv[2:6]); G = int(sys.argv[7]) if len(sys.argv) > 7 else 20
img = cv2.imread(f"../pack/{man[ph]['file']}"); c = render_tile(img, [x0, y0, x1, y1], G, S=900)
cv2.putText(c, f'{ph} Z [{x0},{y0}-{x1},{y1}]', (48, 12), cv2.FONT_HERSHEY_SIMPLEX, .38, (200, 0, 0), 1); cv2.imwrite(sys.argv[6], c, [cv2.IMWRITE_JPEG_QUALITY, 92])

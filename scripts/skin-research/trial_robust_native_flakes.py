"""One frozen, local-only hypothesis: native DoG with robust background prominence.

No services, training, source mutation, threshold search or hosted inference.
Boxes measure candidate support only; their exterior is unknown.
"""
import hashlib, importlib.util, json, sys, threading, time
from datetime import datetime, timezone
from pathlib import Path
import cv2
import numpy as np
import psutil

ROOT = Path(__file__).resolve().parents[2]
sys.path[:0] = [str(ROOT/'services/core-api'), str(ROOT/'scripts')]
import evaluate_periorbital_and_acne_comparative as audit
PREVIOUS = ROOT/'audit-results/dry-sag-native-followup-20261013'
OUT = ROOT/'audit-results/dry-sag-robust-followup-20261013'
OUT.mkdir(parents=True, exist_ok=True)
PLATE = '--plate' in sys.argv
if PLATE:
    OUT = OUT/'plate'; OUT.mkdir(exist_ok=True)
cv2.setNumThreads(1)
prototype = PREVIOUS/'rejected-native-prototype'
spec = importlib.util.spec_from_file_location('skin_general', prototype/'skin_general.py')
G = importlib.util.module_from_spec(spec); sys.modules['skin_general'] = G; spec.loader.exec_module(G)
spec = importlib.util.spec_from_file_location('robust_trial_analysis', prototype/'appearance_analysis.py')
A = importlib.util.module_from_spec(spec); spec.loader.exec_module(A)
original = A.compute_dryness_signal

def components(signal, eligible):
    count, labels, stats, _ = cv2.connectedComponentsWithStats(((signal>.04)&eligible).astype('uint8'))
    keep = np.zeros(count, bool)
    for label in range(1, count):
        _, _, w, h, pixels = stats[label]
        keep[label] = 3<=pixels<=80 and .3<=w/max(h,1)<=3.3 and pixels/max(w*h,1)>.25
    return signal*eligible*keep[labels]

def robust(gray8, support_mask=None):
    if PLATE:
        median = cv2.medianBlur(gray8,3)
        suspect = np.abs(gray8.astype('int16')-median.astype('int16'))>255*.35
        count, labels, stats, _ = cv2.connectedComponentsWithStats(suspect.astype('uint8'),8)
        ids = np.where((stats[:,cv2.CC_STAT_AREA]<=2)&(np.arange(count)>0))[0]
        gray8 = np.where(np.isin(labels,ids),median,gray8).astype('uint8')
    _, raw, contrast, lbp, dark, high = original(gray8, support_mask)
    # These medians estimate the background, never replace the source image.
    background = cv2.medianBlur(gray8, 11).astype('float32')/255
    deviation = np.abs(gray8.astype('float32')/255-background)
    mad = cv2.medianBlur(np.rint(deviation*255).astype('uint8'), 11).astype('float32')/255
    prominence = gray8.astype('float32')/255-background
    gate = prominence > np.maximum(.025, 3*1.4826*mad)
    if PLATE:
        raw = np.clip((prominence-.025)/.10,0,1)*(lbp<8)
    raw *= gate
    support = np.ones(gray8.shape, bool) if support_mask is None else support_mask
    return components(raw, support&~dark), raw, contrast, lbp, dark, high

A.eligible_flake_components = components
A.compute_dryness_signal = robust
process = psutil.Process(); peak = [process.memory_info().rss]; stopped = threading.Event()
def sample():
    while not stopped.wait(.05): peak[0] = max(peak[0], process.memory_info().rss)
thread = threading.Thread(target=sample, daemon=True); thread.start()
started = time.monotonic(); cpu_start = process.cpu_times(); reports = []
selection = json.loads((PREVIOUS/'probe-selection.json').read_text('utf8'))
selected = {'03605ddd','2cfbfb04','387e1700','594aadd0','e1646fda','0642d4ab','36e4010b','c31892d1','5bd42346'}
for row in selection:
    prefix = row['sha256'][:8]
    if prefix not in selected: continue
    path = Path(row['absolutePath']); assert hashlib.sha256(path.read_bytes()).hexdigest()==row['sha256']
    source = cv2.imread(str(path)); gray = cv2.cvtColor(source, cv2.COLOR_BGR2GRAY)
    signal = robust(gray)[0]; old = original(gray)[0]
    boxes = []
    for ann in row['annotations']:
        if ann['label'] not in ('pul','Dry-Skin'): continue
        x,y,w,h = [int(v) for v in ann['bbox']]
        roi = (slice(max(0,y),min(gray.shape[0],y+h)),slice(max(0,x),min(gray.shape[1],x+w)))
        boxes.append(dict(label=ann['label'],box=ann['bbox'],nativeBefore=int((old[roi]>.04).sum()),
                          nativeAfter=int((signal[roi]>.04).sum()),scope='box support; not pixel truth or severity'))
    overlay = source.copy(); active = signal>.04
    overlay[active] = (overlay[active]*.3+np.array([0,255,255])*.7).astype('uint8')
    cv2.imwrite(str(OUT/(prefix+'-robust-native.png')),overlay)
    product = None
    payload = PREVIOUS/(prefix+'-payload.json')
    if payload.exists():
        p = json.loads(payload.read_text('utf8')); assert not p.get('hostedProcessingConsent')
        response = A.analyze_skin(p)
        (OUT/(prefix+'-robust.json')).write_text(json.dumps(response,ensure_ascii=False),'utf8')
        measurements = [*response['measurements'].items()]
        if 'general' in response: measurements.append(('overview',response['general']['measurements']))
        product = []
        for region, values in measurements:
            for v in values:
                if v['id']!='dry': continue
                alpha = audit.project_map_alpha(response['maps'].get(region+':dry'),source.shape)
                product.append(dict(region=region,value=v['value'],limitation=v['limitationCode'],sourcePixels=int((alpha>0).sum()),
                    reviewedNegativePixels=int((alpha[750:1050,750:1200]>0).sum()) if prefix=='e1646fda' else None))
    report = dict(source=prefix,sha256=row['sha256'],path=str(path),category=row.get('imageCategory'),
                  boxes=boxes,product=product)
    reports.append(report); print(json.dumps(dict(source=prefix,boxes=boxes,product=product)),flush=True)
stopped.set(); thread.join(); cpu_end=process.cpu_times()
receipt = dict(generatedUTC=datetime.now(timezone.utc).isoformat(),hypothesis=('native bright-plate prominence, extreme 1/2-pixel impulses excluded' if PLATE else 'native DoG')+' + median11 background / MAD11 prominence > max(.025,3*1.4826*MAD)',
    thresholdSearch=False,productionChanged=False,seconds=time.monotonic()-started,
    processCPUSeconds=cpu_end.user+cpu_end.system-cpu_start.user-cpu_start.system,
    sampledPeakRSSBytes=peak[0],sources=reports,
    limitations=['Dry-Skin is not peeling truth','box exterior unknown','partial/processed positives not whole-face acceptance',
                 'rejected native prototype uses previous sag code; sag outputs are not evaluated or deployed'])
(OUT/'robust-trial.json').write_text(json.dumps(receipt,ensure_ascii=False,indent=2),'utf8')
print(json.dumps({k:v for k,v in receipt.items() if k!='sources'}))

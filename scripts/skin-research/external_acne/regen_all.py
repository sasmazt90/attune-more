"""Re-generate the stored final boxes of the 34 ultralytics model/mode records with the committed eval_external.py /
eval_hf.py settings (same weights, verified by sha256). Lost with the earlier cloud workspace; used only after an
exact check against the committed per-target records."""
import sys, importlib, json, os
for old, new in {'ultralytics.yolo': 'ultralytics', 'ultralytics.yolo.utils': 'ultralytics.utils', 'ultralytics.yolo.v8': 'ultralytics.models.yolo',
                 'ultralytics.yolo.v8.detect': 'ultralytics.models.yolo.detect', 'ultralytics.yolo.data': 'ultralytics.data'}.items():
    sys.modules[old] = importlib.import_module(new)
for sub in ('loss', 'tal', 'metrics', 'ops', 'checks', 'torch_utils', 'instance'):
    try: sys.modules['ultralytics.yolo.utils.' + sub] = importlib.import_module('ultralytics.utils.' + sub)
    except Exception: pass
import eval_external as E
A6 = {'Acne', 'Pimples', 'papular', 'purulent', 'whitehead', 'cystic'}
E.MODELS.update({'unzelanoor-app': ('unzelanoor-best.pt', 640, {'acne', 'fore'}),
    'tinny-robot': ('hf/Tinny-Robot_acne_acne.pt', 640, {'acne'}), 'drpauloreis-onnx': ('hf/drpauloreis_dermapro-acne-yolov8m_acne-yolov8m.onnx', 640, {'acne'}),
    'hilmizr-m': ('hf/HilmiZr_YOLOv8-AcneDetect_yolov8m-acnedetect-best.pt', 640, A6), 'hilmizr-s': ('hf/HilmiZr_YOLOv8-AcneDetect_yolov8s-acnedetect-best.pt', 640, A6),
    'khaminh-11s': ('hf/KhaMinh_yolov11s-acne-detection_best.pt', 640, {'Papular', 'Purulent', 'Whitehead', 'Cystic', 'Conglobata'}),
    'carsten12': ('hf/carsten12_acne-detection-model_model_V1.pt', 640, {'Acne'}), 'tristan-gray': ('hf/tristan-gray_acne-detector_best.pt', 640, {'Acne'})})
JOBS = [('dewiin-acne', m) for m in ('full', 'crop', 'tiles', 'app')] + [('dewiin-anyacne', m) for m in ('full', 'crop', 'tiles')] + \
       [(n, m) for n in ('unzelanoor', 'unzelanoor-app', 'tinny-robot', 'hilmizr-m', 'hilmizr-s', 'khaminh-11s', 'carsten12', 'tristan-gray', 'drpauloreis-onnx') for m in ('full', 'crop', 'tiles')]
out = 'regen-rows.json'; res = json.load(open(out)) if os.path.exists(out) else {}
for n, m in JOBS:
    k = f'{n}/{m}'
    if k in res: continue
    res[k] = E.run(n, m); json.dump(res, open(out, 'w')); print(k, sum(len(r['final']) for r in res[k]), flush=True)
print('done', len(res))

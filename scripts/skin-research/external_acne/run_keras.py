import json, time, cv2, numpy as np, tensorflow as tf, keras_cv, keras
m = keras.models.load_model('hf/aldinnasrun_acne_detect_yolo_model.keras')
print(type(m).__name__, getattr(m,'num_classes',None), m.prediction_decoder.get_config() if hasattr(m,'prediction_decoder') else None, flush=True)
man = json.load(open('pack/manifest.json')); out = {}
for mode in ('full', 'crop'):
    rows = []
    for it in man:
        img = cv2.imread('pack/' + it['file']); R = it['rects']; t0 = time.perf_counter()
        x0, y0 = min(r[0] for r in R), min(r[1] for r in R); x1, y1 = max(r[2] for r in R), max(r[3] for r in R)
        if mode == 'full': x0, y0, x1, y1 = 0, 0, img.shape[1], img.shape[0]
        c = cv2.cvtColor(img[y0:y1, x0:x1], cv2.COLOR_BGR2RGB); h, w = c.shape[:2]
        y = m.predict(tf.image.resize(tf.cast(c, tf.float32), (640, 640))[None], verbose=0)   # app.py preprocessing (plain resize)
        F = []
        for b, s, k in zip(y['boxes'][0], y['confidence'][0], y['classes'][0]):
            if k < 0 or s < .25: continue
            bx = [float(v) for v in b]                                                    # xyxy at 640x640 (format checked below)
            F.append([x0 + bx[0] * w / 640, y0 + bx[1] * h / 640, x0 + bx[2] * w / 640, y0 + bx[3] * h / 640, float(s)])
        rows.append(dict(sha=it['sha256'], kind=it['kind'], set=it['set'], final=F, sec=time.perf_counter() - t0))
    out[mode] = rows; print(mode, sum(len(r['final']) for r in rows), flush=True)
json.dump(out, open('keras-rows.json', 'w'))

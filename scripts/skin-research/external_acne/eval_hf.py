import sys, importlib, json, glob
for old,new in {'ultralytics.yolo':'ultralytics','ultralytics.yolo.utils':'ultralytics.utils','ultralytics.yolo.v8':'ultralytics.models.yolo','ultralytics.yolo.v8.detect':'ultralytics.models.yolo.detect','ultralytics.yolo.data':'ultralytics.data'}.items():
    sys.modules[old]=importlib.import_module(new)
for sub in ('loss','tal','metrics','ops','checks','torch_utils','instance'):
    try: sys.modules['ultralytics.yolo.utils.'+sub]=importlib.import_module('ultralytics.utils.'+sub)
    except Exception: pass
import eval_external as E
A6={'Acne','Pimples','papular','purulent','whitehead','cystic'}
E.MODELS.update({'tinny-robot':('hf/Tinny-Robot_acne_acne.pt',640,{'acne'}),
 'drpauloreis-onnx':('hf/drpauloreis_dermapro-acne-yolov8m_acne-yolov8m.onnx',640,{'acne'}),
 'hilmizr-m':('hf/HilmiZr_YOLOv8-AcneDetect_yolov8m-acnedetect-best.pt',640,A6),
 'hilmizr-s':('hf/HilmiZr_YOLOv8-AcneDetect_yolov8s-acnedetect-best.pt',640,A6),
 'khaminh-11s':('hf/KhaMinh_yolov11s-acne-detection_best.pt',640,{'Papular','Purulent','Whitehead','Cystic','Conglobata'}),
 'carsten12':('hf/carsten12_acne-detection-model_model_V1.pt',640,{'Acne'}),
 'tristan-gray':('hf/tristan-gray_acne-detector_best.pt',640,{'Acne'})})
res=json.load(open('external-results.json'))
for name in sys.argv[1:]:
    for mode in ('full','crop','tiles'):
        rows=E.run(name,mode); s=E.score(rows); res[f'{name}/{mode}']=dict(score=s,rows=rows)
        print(name,mode,{k:v for k,v in s.items() if k in ('hit50','hit30','smallHit50','smallHit30','final','unlabeled','roiFP','clearFP','medianAreaRatio','medianSec')},flush=True)
    json.dump(res,open('external-results.json','w'))

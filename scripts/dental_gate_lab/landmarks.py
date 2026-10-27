"""Landmarks with the app's own face_landmarker.task (Python runtime; the app uses the WASM runtime)."""
import json,sys,cv2,numpy as np,mediapipe as mp
from mediapipe.tasks.python import vision,BaseOptions
from pathlib import Path
MODEL=str(Path(__file__).resolve().parents[2]/'apps/vehicle-app/public/mediapipe/models/face_landmarker.task')
opt=vision.FaceLandmarkerOptions(base_options=BaseOptions(model_asset_path=MODEL),output_facial_transformation_matrixes=True,num_faces=2)
det=vision.FaceLandmarker.create_from_options(opt)
out=[]
for item in json.load(open(sys.argv[1])):
    im=cv2.imread(item['frame']);rgb=cv2.cvtColor(im,cv2.COLOR_BGR2RGB)
    # The app runs the face model on a <=640 px copy and maps normalized points to full res.
    f=min(1,640/rgb.shape[1]);small=cv2.resize(rgb,(round(rgb.shape[1]*f),round(rgb.shape[0]*f)),interpolation=cv2.INTER_AREA) if f<1 else rgb
    r=det.detect(mp.Image(image_format=mp.ImageFormat.SRGB,data=np.ascontiguousarray(small)))
    if not r.face_landmarks:out.append({**item,'face':False});continue
    pts=[{'x':p.x,'y':p.y,'z':p.z} for p in r.face_landmarks[0]]
    M=np.array(r.facial_transformation_matrixes[0]);out.append({**item,'face':True,'faceCount':len(r.face_landmarks),'landmarks':pts,'faceTransform':M.flatten(order='F').tolist()})
json.dump(out,open(sys.argv[2],'w'))
print('faces',sum(o['face'] for o in out),'/',len(out))

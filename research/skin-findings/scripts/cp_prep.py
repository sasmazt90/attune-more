import os,sys,json,math,numpy as np,cv2,mediapipe as mp
from mediapipe.tasks.python import vision, BaseOptions
W=sys.argv[1]; TASK=sys.argv[2]
REG={'forehead':[54,103,67,109,10,338,297,332,284,293,334,296,336,9,107,66,105,63],
 'nose':[168,193,245,188,174,236,198,209,49,48,64,98,97,2,326,327,294,278,279,429,420,456,399,412,465,417],
 'cheek_imgL':[116,117,118,119,100,142,203,206,216,212,214,192,213,147,123],
 'cheek_imgR':[345,346,347,348,329,371,423,426,436,432,434,416,433,376,352],
 'chin':[43,106,182,83,18,313,406,335,273,422,430,394,395,369,396,175,171,140,170,169,210,202]}
lm=vision.FaceLandmarker.create_from_options(vision.FaceLandmarkerOptions(base_options=BaseOptions(model_asset_path=TASK),output_facial_transformation_matrixes=True,num_faces=1))
os.makedirs(f'{W}/crop',exist_ok=True); out={}
for f in sorted(os.listdir(f'{W}/img')):
  bgr=cv2.imread(f'{W}/img/{f}'); h,w=bgr.shape[:2]
  r=lm.detect(mp.Image(image_format=mp.ImageFormat.SRGB,data=cv2.cvtColor(bgr,cv2.COLOR_BGR2RGB)))
  if not r.face_landmarks: out[f]={'face':False}; print(f,'NOFACE'); continue
  P=np.array([[p.x*w,p.y*h] for p in r.face_landmarks[0]])
  M=np.array(r.facial_transformation_matrixes[0]); m=M.T.flatten()  # column-major like JS
  yaw=math.degrees(math.atan2(m[8],m[10])); pitch=math.degrees(math.asin(-max(-1,min(1,m[9])))); 
  eyeMid=(P[133]+P[362])/2; inner=np.linalg.norm(P[133]-P[362]); ratio=(P[1][0]-eyeMid[0])/(0.8*inner)
  x0,y0=P.min(0); x1,y1=P.max(0); bw,bh=x1-x0,y1-y0; s=max(bw,bh)*1.35; cx,cy=(x0+x1)/2,(y0+y1)/2-0.08*bh
  X0,Y0=int(round(cx-s/2)),int(round(cy-s/2)); S=int(round(s))
  pad=cv2.copyMakeBorder(bgr,S,S,S,S,cv2.BORDER_REPLICATE); crop=pad[Y0+S:Y0+2*S,X0+S:X0+2*S]
  sc=1024/S; crop=cv2.resize(crop,(1024,1024),interpolation=cv2.INTER_AREA); cn=os.path.splitext(f)[0]+'.png'; cv2.imwrite(f'{W}/crop/{cn}',crop)
  Pc=(P-[X0,Y0])*sc
  out[f]={'face':True,'src':[w,h],'crop':cn,'cropBox':[X0,Y0,S],'yawDeg':round(yaw,1),'pitchDeg':round(pitch,1),'noseRatio':round(ratio,3),'faceWidthPx':round(bw,1),
   'regions':{k:Pc[v].round(1).tolist() for k,v in REG.items()}}
  print(f,round(yaw,1),round(ratio,2),int(bw))
json.dump(out,open(f'{W}/prep.json','w'))

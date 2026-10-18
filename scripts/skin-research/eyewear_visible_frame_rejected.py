"""REJECTED geometry experiment. Never import into the capture pipeline.

Requires two enclosing lower/side rims and a connecting bridge. Eyebrows or
ordinary lower-lid folds alone cannot reject a capture. No fitting/photo IDs.
"""
import cv2,numpy as np
VERSION='glasses-free-visible-frame-v1'

def visible_frames(image,eyes):
    gray=cv2.cvtColor(image,cv2.COLOR_BGR2GRAY)
    edge=cv2.Canny(gray,18,45,L2gradient=True)
    near=cv2.dilate(edge,np.ones((3,3),np.uint8))>0
    found=[];candidates=[]
    for endpoints in eyes:
        a,b=np.asarray(endpoints,float);axis=b-a;width=float(np.linalg.norm(axis));u=axis/max(width,1);n=np.array([-u[1],u[0]])
        if n[1]<0:n=-n
        center=(a+b)/2
        radius=max(1,int(round(width*.025)))
        ridge=cv2.morphologyEx(gray,cv2.MORPH_BLACKHAT,cv2.getStructuringElement(cv2.MORPH_ELLIPSE,(radius*2+1,radius*2+1)))>=12
        rim_near=cv2.dilate(ridge.astype(np.uint8),np.ones((3,3),np.uint8))>0
        corners=np.array([center+u*dx*width+n*dy*width for dx in [-1.2,1.2] for dy in [-.9,1.3]])
        h,w=gray.shape;x0=max(0,int(np.floor(corners[:,0].min())));y0=max(0,int(np.floor(corners[:,1].min())));x1=min(w,int(np.ceil(corners[:,0].max())));y1=min(h,int(np.ceil(corners[:,1].max())))
        choices=[]
        if width>=18 and x1>x0 and y1>y0:
            contours,_=cv2.findContours(edge[y0:y1,x0:x1],cv2.RETR_LIST,cv2.CHAIN_APPROX_NONE)
            for contour in contours:
                if len(contour)<18:continue
                points=contour[:,0,:].astype(np.float32)+[x0,y0]
                ellipse=cv2.fitEllipse(points.astype(np.float32));(cx,cy),(ew,eh),angle=ellipse
                # Evaluate fitted ellipse in its own axes. It must enclose the
                # eye, extend below the eyelid and have side + lower support.
                theta=np.linspace(0,2*np.pi,96,endpoint=False);rotation=np.deg2rad(angle)
                ex=np.array([np.cos(rotation),np.sin(rotation)]);ey=np.array([-np.sin(rotation),np.cos(rotation)])
                curve=np.array([cx,cy])+np.cos(theta)[:,None]*ew/2*ex+np.sin(theta)[:,None]*eh/2*ey
                local=(curve-center)@np.c_[u,n]/width
                span=local.max(0)-local.min(0);offset=(np.array([cx,cy])-center)@np.c_[u,n]/width
                if not (1.10<=span[0]<=2.3 and .55<=span[1]<=1.65 and abs(offset[0])<.32 and -.12<offset[1]<.45):continue
                q=(center-np.array([cx,cy]))@np.c_[ex,ey]/[ew/2,eh/2]
                if np.sum(q*q)>.75:continue
                ix=np.rint(curve[:,0]).astype(int);iy=np.rint(curve[:,1]).astype(int);valid=(ix>=0)&(ix<w)&(iy>=0)&(iy<h);supported=np.zeros(96,bool);supported[valid]=rim_near[iy[valid],ix[valid]]
                parts=[(local[:,1]>.25)&(abs(local[:,0])<.6),(local[:,0]<-.5)&(local[:,1]>-.15),(local[:,0]>.5)&(local[:,1]>-.15)]
                ratios=[float(supported[p].mean()) if p.any() else 0 for p in parts]
                if min(ratios)<.55:continue
                choices.append(dict(ellipse=[[float(cx),float(cy)],[float(ew),float(eh)],float(angle)],lowerAndSideSupport=ratios,edgeSupport=float(supported.mean()),eyeWidth=width,curve=curve.tolist()))
            # Thin wire rims may have disconnected contours. A bounded shape
            # trace can connect photometric observations, but cannot invent a
            # side/lower rim or replace the independent bridge requirement.
            theta=np.linspace(0,2*np.pi,96,endpoint=False)
            for power in [1.,.5]:
                for cx in [-.15,0.,.15]:
                    for cy in [0.,.15,.30]:
                        for rx in [.65,.80,.95]:
                            for ry in [.30,.45,.60]:
                                local=np.c_[cx+rx*np.sign(np.cos(theta))*abs(np.cos(theta))**power,cy+ry*np.sign(np.sin(theta))*abs(np.sin(theta))**power]
                                curve=center+local[:,0,None]*width*u+local[:,1,None]*width*n
                                ix=np.rint(curve[:,0]).astype(int);iy=np.rint(curve[:,1]).astype(int);valid=(ix>=0)&(ix<w)&(iy>=0)&(iy<h)
                                if not valid.all():continue
                                support=rim_near[iy,ix];parts=[(local[:,1]>.25)&(abs(local[:,0])<.6),(local[:,0]<-.5)&(local[:,1]>-.15),(local[:,0]>.5)&(local[:,1]>-.15)]
                                ratios=[float(support[p].mean()) if p.any() else 0 for p in parts]
                                if min(ratios)<.55 or support.mean()<.55:continue
                                choices.append(dict(shapeTrace=[cx,cy,rx,ry,power],lowerAndSideSupport=ratios,edgeSupport=float(support.mean()),eyeWidth=width,curve=curve.tolist()))
        candidates.append(choices);found.append(max(choices,key=lambda r:min(r['lowerAndSideSupport'])) if choices else None)
    a=np.asarray(eyes[0][1],float);b=np.asarray(eyes[1][0],float)
    if a[0]>b[0]:a,b=b,a
    vector=b-a;distance=float(np.linalg.norm(vector));normal=np.array([-vector[1],vector[0]])/max(distance,1)
    if normal[1]<0:normal=-normal
    eye_width=min(float(np.linalg.norm(np.diff(np.asarray(e),axis=0))) for e in eyes)
    radius=max(1,int(round(eye_width*.025)))
    bridge_ridge=cv2.morphologyEx(gray,cv2.MORPH_BLACKHAT,cv2.getStructuringElement(cv2.MORPH_ELLIPSE,(radius*2+1,radius*2+1)))>=12
    bridge_near=cv2.dilate(bridge_ridge.astype(np.uint8),np.ones((3,3),np.uint8))>0
    bridge=[]
    for offset in [-.10,.05,.20,.35]:
        curve=a+np.linspace(.25,.75,40)[:,None]*vector+normal*offset*eye_width
        x=np.rint(curve[:,0]).astype(int);y=np.rint(curve[:,1]).astype(int);valid=(x>=0)&(x<gray.shape[1])&(y>=0)&(y<gray.shape[0]);score=float(bridge_near[y[valid],x[valid]].mean()) if valid.all() else 0
        bridge.append(dict(offset=offset,support=score,curve=curve.tolist()))
    strongest=max(bridge,key=lambda r:r['support'])
    blocked=all(r is not None for r in found) and strongest['support']>=.65
    return dict(version=VERSION,status='EYEWEAR_VISIBLE' if blocked else 'NO_VISIBLE_FRAME_EVIDENCE',blocked=blocked,rims=found,bridge=strongest,candidateCounts=[len(x) for x in candidates],limitations=['limited engineering controls','rimless/non-elliptic/tinted eyewear not certified']),edge

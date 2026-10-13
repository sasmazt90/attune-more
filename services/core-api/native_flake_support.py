"""Native-coordinate material proposals. No labels or display zoom enter inference.

This module is not enabled in normal analysis until its reviewed support and
anatomical-path evidence pass. Original pixels are never enlarged or reduced.
"""
import cv2
import numpy as np

VERSION='native-independent-stable-region-ridge-v3'
PARAMETERS=dict(radii=[1,2,3],seedContrast=.025,growthContrast=.018,
                minArea=3,maxArea=1500,minFill=.15,maxElongation=16.,
                ringLumaDifference=3.,boundaryEdge=4/255,boundaryFraction=.35,
                minimumSeedFraction=.05,poreMaximumCoreArea=20,poreRingSectors=3,ridgeAnisotropy=.5)

def odd(value):return max(3,2*int(round(value))+1)

def proposal_tile(bgr,coordinate_scale=1.,return_stages=False,pixel_density=1.,check=None):
    """Geometric units scale with the supplied source-coordinate metric.

    source resize by k -> coordinate_scale by k. Contrast remains photometric;
    derivative magnitude is expressed per reference-coordinate distance.
    """
    s=max(.125,float(coordinate_scale));p=PARAMETERS
    gray=cv2.cvtColor(bgr,cv2.COLOR_BGR2GRAY);g=gray.astype(np.float32)/255
    lab=cv2.cvtColor(bgr,cv2.COLOR_BGR2LAB);luma=lab[:,:,0]
    scales=sorted(set([max(.125,float(pixel_density)),s]));response=np.zeros(g.shape,np.float32)
    region_envelope=np.zeros(g.shape,bool);candidate_regions=[]
    for metric in scales:
        if check is not None:check()
        # The fine-source scale is the observed pixel grid, not an upsample.
        regions,_=cv2.MSER_create(5,max(1,int(round(4*metric*metric))),max(4,int(round(1500*metric*metric))),.25,.2).detectRegions(255-luma)
        for pts in regions:
            region_envelope[pts[:,1],pts[:,0]]=True
            candidate_regions.append((pts,'stable-region',metric))
        for radius in p['radii']:
            sigma=max(.45,radius*metric);smooth=cv2.GaussianBlur(g,(0,0),sigma)
            xx=cv2.Sobel(smooth,cv2.CV_32F,2,0,3)*sigma*sigma
            yy=cv2.Sobel(smooth,cv2.CV_32F,0,2,3)*sigma*sigma
            xy=cv2.Sobel(smooth,cv2.CV_32F,1,1,3)*sigma*sigma
            root=np.sqrt((xx-yy)**2+4*xy*xy);lo=(xx+yy-root)/2;hi=(xx+yy+root)/2
            bright=np.maximum(-lo,0)*(np.abs(hi)<p['ridgeAnisotropy']*np.maximum(-lo,1e-6))
            np.maximum(response,bright,out=response)
    seed=response>p['seedContrast']
    envelope=np.zeros(g.shape,bool)
    envelope|=response>p['growthContrast']
    # Do not grow a weak region with no actual high-contrast native seed.
    count,ids,stats,_=cv2.connectedComponentsWithStats(envelope.astype(np.uint8),8)
    for i in range(1,count):
        x,y,w,h,area=map(int,stats[i]);ys,xs=np.where(ids[y:y+h,x:x+w]==i)
        if seed[y+ys,x+xs].sum()>=max(1,int(np.ceil(area*p['minimumSeedFraction']))):candidate_regions.append((np.c_[xs+x,ys+y].astype(np.int32),'ridge',s))
    gradient=np.hypot(cv2.Sobel(g,cv2.CV_32F,1,0,3),cv2.Sobel(g,cv2.CV_32F,0,1,3))
    dark=cv2.morphologyEx(gray,cv2.MORPH_BLACKHAT,np.ones((odd(3*s),)*2,np.uint8))>35
    n,dark_ids,dark_stats,dark_centers=cv2.connectedComponentsWithStats(dark.astype(np.uint8),8)
    pore_centers={}
    for i in range(1,n):
        x,y,w,h,area=dark_stats[i]
        if area<=p['poreMaximumCoreArea']*s*s and max(w,h)/max(1,min(w,h))<=3.3:
            pore_centers[i]=dark_centers[i]
    stages={name:np.zeros(g.shape,np.float32) for name in ['envelope','seeded','geometry','ring','edge','pore-separated']}
    stages['envelope'][envelope|region_envelope]=1;details=[]
    for region_index,(pts,branch,metric) in enumerate(candidate_regions):
        if check is not None and region_index%32==0:check()
        x,y,w,h=cv2.boundingRect(pts);area=len(pts);local=np.zeros((h,w),bool);local[pts[:,1]-y,pts[:,0]-x]=True
        seed_count=int((seed[y:y+h,x:x+w]&local).sum())
        stages['seeded'][y:y+h,x:x+w][local]=1
        if area<max(1,int(round(p['minArea']*pixel_density**2))) or area>max(4,int(round(p['maxArea']*metric**2))) or area/(w*h)<p['minFill'] or max(w,h)/max(1,min(w,h))>p['maxElongation']:continue
        # An open region at the tile boundary has insufficient ring context.
        if x==0 or y==0 or x+w==g.shape[1] or y+h==g.shape[0]:continue
        stages['geometry'][y:y+h,x:x+w][local]=1
        pad=max(2,int(np.ceil(4*metric)));a=max(0,x-pad);b=max(0,y-pad);c=min(g.shape[1],x+w+pad);d=min(g.shape[0],y+h+pad)
        mask=np.zeros((d-b,c-a),bool);mask[pts[:,1]-b,pts[:,0]-a]=True
        ring=(cv2.dilate(mask.astype(np.uint8),np.ones((odd(3*metric),)*2,np.uint8))>0)&~mask
        if ring.sum()<max(3,int(8*metric*metric)):continue
        reference=float(np.median(luma[b:d,a:c][ring]));contrast=float(np.median(luma[b:d,a:c][mask])-reference)
        if contrast<=p['ringLumaDifference']:continue
        intensity=float(np.clip((contrast-p['ringLumaDifference'])/32,0,1))
        stages['ring'][y:y+h,x:x+w][local]=np.maximum(stages['ring'][y:y+h,x:x+w][local],intensity)
        border=mask&~(cv2.erode(mask.astype(np.uint8),np.ones((odd(metric),)*2,np.uint8))>0)
        edge_fraction=float((gradient[b:d,a:c][border]*metric>p['boundaryEdge']).mean())
        if edge_fraction<p['boundaryFraction']:continue
        stages['edge'][y:y+h,x:x+w][local]=np.maximum(stages['edge'][y:y+h,x:x+w][local],intensity)
        # Only an actual compact dark core with surrounding angular bright
        # support is pore ringing. Mere proximity to a dark lip/shadow is not.
        ys,xs=np.where(mask);xy=np.c_[xs+a,ys+b]
        neighbor=cv2.dilate(mask.astype(np.uint8),np.ones((odd(3*metric),)*2,np.uint8))>0
        candidates=set(int(v) for v in np.unique(dark_ids[b:d,a:c][neighbor]) if int(v) in pore_centers)
        pore_ring=False
        for core in candidates:
            center=pore_centers[core];distance=np.linalg.norm(xy-center,axis=1)
            nearby=xy[distance<=max(3,5*metric)]
            if len(nearby)<3:continue
            sectors=np.unique(np.floor((np.arctan2(nearby[:,1]-center[1],nearby[:,0]-center[0])+np.pi)/(np.pi/4)).astype(int)%8)
            if len(sectors)>=p['poreRingSectors'] and len(nearby)/area>=.25:pore_ring=True;break
        # Remove the compact core's actual annular neighborhood, not an entire
        # large material component just because a dark pore is nearby.
        accepted=local.copy()
        if pore_ring:
            yy_grid,xx_grid=np.mgrid[y:y+h,x:x+w]
            accepted&=np.hypot(xx_grid-center[0],yy_grid-center[1])>max(3,5*metric)
        stages['pore-separated'][y:y+h,x:x+w][accepted]=np.maximum(stages['pore-separated'][y:y+h,x:x+w][accepted],intensity)
        details.append(dict(rect=[x,y,w,h],area=area,seedPixels=seed_count,contrast=contrast,edgeFraction=edge_fraction,branch=branch))
    # No weak photometric tail contributes to density or map support.
    field=stages['pore-separated'];field[field<=.04]=0
    return (field,stages,details) if return_stages else field

def native_field(bgr,coordinate_scale=1.,eligible=None,core=512,pixel_density=1.,check=None):
    """Overlapping source tiles with context, max union and bounded working arrays."""
    h,w=bgr.shape[:2];output=np.zeros((h,w),np.float32)
    halo=max(48,int(np.ceil(40*coordinate_scale)));stride=max(1,core//2);peak_pixels=0;tiles=0
    xs=sorted(set([*range(0,max(1,w-core+1),stride),max(0,w-core)]));ys=sorted(set([*range(0,max(1,h-core+1),stride),max(0,h-core)]))
    for y in ys:
        for x in xs:
            if check is not None:check()
            if eligible is not None and not eligible[y:min(h,y+core),x:min(w,x+core)].any():continue
            a=max(0,x-halo);b=max(0,y-halo);c=min(w,x+core+halo);d=min(h,y+core+halo)
            field=proposal_tile(bgr[b:d,a:c],coordinate_scale,pixel_density=pixel_density,check=check)
            local=field[y-b:min(h,y+core)-b,x-a:min(w,x+core)-a]
            np.maximum(output[y:min(h,y+core),x:min(w,x+core)],local,out=output[y:min(h,y+core),x:min(w,x+core)])
            tiles+=1;peak_pixels=max(peak_pixels,(d-b)*(c-a))
    if eligible is not None:output*=eligible
    return output,dict(version=VERSION,sourceGrid=[w,h],analysisResize=False,coordinateScale=coordinate_scale,tileCore=core,tileStride=stride,halo=halo,tiles=tiles,peakTilePixels=peak_pixels,overlapCountedOnce=True)

def pool_for_display(field,valid,max_dimension=512):
    """Max pooling retains tiny material; source score never depends on this grid."""
    h,w=field.shape;step=max(1,int(np.ceil(max(h,w)/max_dimension)))
    ph=(-h)%step;pw=(-w)%step
    f=np.pad(field,((0,ph),(0,pw)));v=np.pad(valid,((0,ph),(0,pw)))
    shape=(f.shape[0]//step,step,f.shape[1]//step,step)
    pooled=f.reshape(shape).max(axis=(1,3));support=v.reshape(shape).any(axis=(1,3))
    return pooled,support,step

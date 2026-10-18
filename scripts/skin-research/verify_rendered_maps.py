"""Validate actual Chromium SVG clip/mask raster in native source coordinates."""
import argparse,json
from pathlib import Path
import cv2,numpy as np
from PIL import Image
ROOT=Path(__file__).resolve().parents[2]
def main():
 ap=argparse.ArgumentParser();ap.add_argument('--captures',default='audit-results/skin-capabilities-20261008/final-product');args=ap.parse_args();out=(ROOT/args.captures).resolve();assert out.is_relative_to(ROOT/'audit-results');rows=[]
 for file in sorted(out.glob('rendered-map-*.png')):
  key=file.stem.removeprefix('rendered-map-');meta=json.loads((out/('source-'+key+'.json')).read_text());grid=json.loads((out/('map-'+key+'.json')).read_text());alpha=np.array(Image.open(file).convert('RGBA'))[:,:,3];assert alpha.shape==(meta['height'],meta['width']) and alpha.max()<=82 and alpha.max()>0
  mesh=meta['meshes'][meta['region']];edges={tuple(e) for e in mesh['edges']}|{tuple(reversed(e)) for e in mesh['edges']};points=mesh['points'];geometry=np.zeros(alpha.shape,'uint8')
  for a in range(len(points)):
   for b in range(a+1,len(points)):
    if (a,b) not in edges:continue
    for c in range(b+1,len(points)):
     if (a,c) in edges and (b,c) in edges:cv2.fillConvexPoly(geometry,np.round([[points[i]['x'],points[i]['y']] for i in [a,b,c]]).astype('int32'),255)
  # Allow one source pixel solely for clip antialiasing/rounded raster boundaries.
  allowed=cv2.dilate(geometry,np.ones((3,3),'uint8'));assert not alpha[allowed==0].any()
  for box in meta['exclusions']:
   x,y=int(np.ceil(box['x']))+1,int(np.ceil(box['y']))+1;r,b=int(np.floor(box['x']+box['w']))-1,int(np.floor(box['y']+box['h']))-1
   assert not alpha[max(0,y):min(alpha.shape[0],b),max(0,x):min(alpha.shape[1],r)].any()
  h,w=grid['height'],grid['width'];valid=np.array(grid['valid']).reshape(h,w);ys=grid['y']+np.arange(h)*grid['step']+grid['step']//2;xs=grid['x']+np.arange(w)*grid['step']+grid['step']//2
  sampled=alpha[np.ix_(ys,xs)];assert not sampled[valid==0].any()
  rows.append({'capture':key,'nativeSourceSize':[alpha.shape[1],alpha.shape[0]],'maxAlpha':int(alpha.max()),'noFillOutsideMesh':True,'excludedInteriorTransparent':True,'invalidGridCentersTransparent':True})
 assert len(rows)==10,'Need five supported regions at both native zoom settings'
 (out/'rendered-map-proof.json').write_text(json.dumps({'status':'PASS','renderer':'actual production SVG rasterized by Chromium','controlledFixture':True,'physicalCamera':False,'rows':rows},indent=2),'utf8');print('PASS: 10 actual SVG rasters, source-coordinate clip/exclusions/invalid mask and alpha')
if __name__=='__main__':main()

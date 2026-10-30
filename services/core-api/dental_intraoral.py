"""Conservative visible-crown topology for uploads without facial landmarks.

Colour proposes pixels, never a mouth. Admission requires several separately
bounded, convex crowns in a coherent row, real image edges, neighbouring
gingival tissue and an opposed dark oral boundary. No detector predictions,
user checkbox, filename or synthetic facial landmarks establish this region.
"""
import cv2
import numpy as np
from scipy import ndimage
from skimage.segmentation import watershed


def intraoral_region(image):
    h, w = image.shape[:2]
    scale = min(1., 768 / max(h, w))
    small = cv2.resize(image, None, fx=scale, fy=scale, interpolation=cv2.INTER_AREA) if scale < 1 else image
    sh, sw = small.shape[:2]
    gray = cv2.cvtColor(small, cv2.COLOR_BGR2GRAY)
    hsv = cv2.cvtColor(small, cv2.COLOR_BGR2HSV)
    b, g, r = [small[:, :, i].astype(np.float32) for i in range(3)]
    enamel = ((hsv[:, :, 1] < 110) & (gray > 100)).astype(np.uint8)
    enamel = cv2.morphologyEx(enamel, cv2.MORPH_OPEN, np.ones((3, 3), np.uint8))
    gingiva = (r > g * 1.12) & (hsv[:, :, 1] > 55) & (gray > 35)
    gradient = np.hypot(cv2.Sobel(gray.astype(np.float32), cv2.CV_32F, 1, 0),
                        cv2.Sobel(gray.astype(np.float32), cv2.CV_32F, 0, 1)) / 4
    # Image-supported interproximal edges separate touching crowns when a
    # closed bite has no dark gap large enough to split the colour proposal.
    core = (enamel.astype(bool) & (gradient < 12)).astype(np.uint8)
    distance = cv2.GaussianBlur(cv2.distanceTransform(core, cv2.DIST_L2, 5), (0, 0), 1)
    maxima = (distance == cv2.dilate(distance, np.ones((15, 15), np.uint8))) & (distance > max(3, distance.max() * .18))
    markers, count = ndimage.label(maxima)
    # Bound both watershed work and subsequent pairwise geometry checks.
    if count < 3 or count > 128:
        return None
    labels = watershed(gradient / 255, markers, mask=enamel > 0, compactness=.002)
    crowns = []
    for label in range(1, count + 1):
        contours, _ = cv2.findContours((labels == label).astype(np.uint8), cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        if not contours:
            continue
        contour = max(contours, key=cv2.contourArea)
        area = cv2.contourArea(contour)
        x, y, cw, ch = cv2.boundingRect(contour)
        if (area < max(120, sh * sw * .0008) or area > sh * sw * .12
                or not .4 < cw / max(ch, 1) < 1.8 or area / (cw * ch) > .94
                or x == 0 or y == 0 or x + cw >= sw or y + ch >= sh):
            continue
        if area / max(cv2.contourArea(cv2.convexHull(contour)), 1) < .8:
            continue
        if len(cv2.approxPolyDP(contour, .01 * cv2.arcLength(contour, True), True)) < 5:
            continue  # Rectangular wall/window patches are not crowns.
        mask = np.zeros((sh, sw), np.uint8)
        cv2.fillPoly(mask, [contour], 1)
        ring = (cv2.dilate(mask, np.ones((7, 7), np.uint8)) - mask) > 0
        boundary = (mask - cv2.erode(mask, np.ones((3, 3), np.uint8))) > 0
        edge_support = float((gradient[boundary] > 8).mean())
        gum_support = float(gingiva[ring].mean())
        if edge_support < .45 or gum_support < .12:
            continue  # Watershed partitions must have actual photographic edges.
        crowns.append(dict(label=label, x=x, y=y, w=cw, h=ch, cx=x+cw/2, cy=y+ch/2,
                           contour=contour, edge=edge_support, gum=gum_support))
    accepted = set()
    for sign in (-1, 1):
        nodes = list(range(len(crowns)))
        groups = []
        while nodes:
            group = [nodes.pop()]
            for i in group:
                a = crowns[i]
                for j in nodes[:]:
                    b = crowns[j]
                    dx, dy = abs(a['cx']-b['cx']), abs(a['cy']-b['cy'])
                    if (.35*(a['w']+b['w']) < dx < .85*(a['w']+b['w'])
                            and dy < .5*min(a['h'], b['h'])
                            and max(a['h'], b['h']) < 2.5*min(a['h'], b['h'])):
                        nodes.remove(j)
                        group.append(j)
            groups.append(group)
        for group in groups:
            if len(group) < 3:
                continue
            selected = [crowns[i] for i in group]
            span = max(c['x']+c['w'] for c in selected)-min(c['x'] for c in selected)
            x0=min(c['x'] for c in selected);x1=max(c['x']+c['w'] for c in selected)
            y0=min(c['y'] for c in selected);y1=max(c['y']+c['h'] for c in selected)
            height=float(np.median([c['h'] for c in selected]))
            if span / scale < 100 or span < (y1-y0)*1.3:
                continue
            # Confirm an oral-space band across the *row*, opposite tissue.
            # A stain/reflectance split within one crown must not require a
            # separate dark opening beside that artificial watershed partition.
            above=(max(0,int(y0-height*.8)),min(sh,int(y0+height*.2)))
            below=(max(0,int(y1-height*.2)),min(sh,int(y1+height*.8)))
            oral,tissue=(above,below) if sign<0 else (below,above)
            dark=gray[oral[0]:oral[1],x0:x1]<90
            tissue_pixels=gingiva[tissue[0]:tissue[1],x0:x1]
            if not dark.size or not tissue_pixels.size or tissue_pixels.mean()<.15:
                continue
            # Several consecutive rows, not an isolated dark speck.
            dark_rows=dark.mean(axis=1)>=.4
            runs,_=ndimage.label(dark_rows)
            longest=max(np.bincount(runs)[1:],default=0)
            if longest>=max(2,height*.1):
                accepted.update(group)
    if not accepted:
        return None
    # Only the supported row and its immediate margin, never a rectangular
    # full-photo colour cluster or unrelated bright background.
    region = np.zeros((sh, sw), np.uint8)
    for i in accepted:
        cv2.fillPoly(region, [crowns[i]['contour']], 1)
    radius = max(2, int(np.median([crowns[i]['h'] for i in accepted]) * .12))
    region = cv2.dilate(region, cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (radius*2+1, radius*2+1)))
    mouth = cv2.resize(region, (w, h), interpolation=cv2.INTER_NEAREST) > 0
    evidence = dict(version='visible-crown-topology-v1', crownCount=len(accepted),
                    minBoundarySupport=min(crowns[i]['edge'] for i in accepted),
                    minGingivalSupport=min(crowns[i]['gum'] for i in accepted),
                    opposedOralBoundary=True, analysisScale=scale)
    return mouth, evidence

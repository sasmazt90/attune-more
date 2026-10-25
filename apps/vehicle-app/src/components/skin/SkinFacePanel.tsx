'use client';
import {useTranslations} from '../../i18n/LanguageProvider';

import React, { useEffect, useState, useId } from 'react';
import { SkinRegionData } from '../../data/skinDemoFixture';
import { SkinSnapshot } from '../../utils/skinSnapshot';
import Image from 'next/image';
import { SkinRegionNavigator } from './SkinRegionNavigator';
import { cameraCrop } from '../CameraPreparation';
import { StablePreviewCrop } from '../../utils/cameraStability';
import { meshTriangles, closedSurfaceSupportEnabled } from '../../utils/skinSurfaceAnalysis';
import { skinBoxEnvelope } from '../../utils/skinBoxEnvelope';
import { paintPath, paintCentroid, faceWidthPx, PAINT_COLORS, PAINT_LABELS, PAINT_TAG_ANCHOR, SENSITIVE_COLOR, type PaintRegionId, type PaintState } from '../../utils/skinTypePaint';

interface SkinFacePanelProps {
  currentRegion: SkinRegionData;
  snapshot?: SkinSnapshot;
  mode?: 'result' | 'scan' | 'start';
  scanProgress?: number;
  onPrev?: () => void;
  onNext?: () => void;
  videoRef?: React.RefObject<HTMLVideoElement | null>;
  isLiveVideo?: boolean;
  landmarks?: { x: number; y: number }[];
  selectedCriterion?: string | null;
}

function pointInPolygon(x: number, y: number, poly: { x: number; y: number }[]): boolean {
  let inside = false;
  for (let i = 0, j = poly.length - 1; i < poly.length; j = i++) {
    const xi = poly[i].x, yi = poly[i].y;
    const xj = poly[j].x, yj = poly[j].y;
    const intersect = ((yi > y) !== (yj > y)) && (x < (xj - xi) * (y - yi) / ((yj - yi) || 1e-9) + xi);
    if (intersect) inside = !inside;
  }
  return inside;
}

export const SkinFacePanel: React.FC<SkinFacePanelProps> = ({
  currentRegion,
  snapshot,
  mode = 'result',
  onPrev,
  onNext,
  videoRef,
  isLiveVideo = false,
  landmarks,
  selectedCriterion
}) => {
  const { text: i18nText, node: i18nNode } = useTranslations();
  const maskId = useId();
  const [videoRatio, setVideoRatio] = useState(4 / 3);
  const previewCrop = React.useRef(new StablePreviewCrop());
  const crop = isLiveVideo && mode === 'scan'
    ? previewCrop.current.update(cameraCrop(landmarks), performance.now())
    : { x: 0, y: 0, width: 1, height: 1 };
  const updateVideoRatio = (event: React.SyntheticEvent<HTMLVideoElement>) => {
    const v = event.currentTarget;
    if (v.videoWidth && v.videoHeight) setVideoRatio(v.videoWidth / v.videoHeight);
  };
  const [dpr, setDpr] = useState(1);
  const panel = React.useRef<HTMLDivElement>(null);
  const [panelWidth, setPanelWidth] = useState(400);

  useEffect(() => {
    if (!panel.current) return;
    const observer = new ResizeObserver(([entry]) => setPanelWidth(entry.contentRect.width || 400));
    observer.observe(panel.current);
    return () => observer.disconnect();
  }, [snapshot?.photoId]);

  const displayCrop = React.useMemo(() => {
    const base = snapshot?.previewCrop ? {
      x: snapshot.previewCrop.x * snapshot.width,
      y: snapshot.previewCrop.y * snapshot.height,
      width: snapshot.previewCrop.width * snapshot.width,
      height: snapshot.previewCrop.height * snapshot.height
    } : snapshot?.crop;

    if (!snapshot || !base || currentRegion.id === 'overview') {
      return base;
    }

    const targetMeshes = currentRegion.id === 'nose'
      ? ['forehead', 'nose', 'chin'].map(id => snapshot.meshes?.[id]).filter(Boolean)
      : snapshot.meshes?.[currentRegion.id] ? [snapshot.meshes[currentRegion.id]] : [];
    const pts = targetMeshes.flatMap(m => m!.points || []);
    if (pts.length === 0) return base;

    let minX = pts[0].x, maxX = pts[0].x, minY = pts[0].y, maxY = pts[0].y;
    for (let i = 1; i < pts.length; i++) {
      if (pts[i].x < minX) minX = pts[i].x;
      if (pts[i].x > maxX) maxX = pts[i].x;
      if (pts[i].y < minY) minY = pts[i].y;
      if (pts[i].y > maxY) maxY = pts[i].y;
    }
    const rawW = Math.max(40, maxX - minX);
    const rawH = Math.max(40, maxY - minY);
    const padX = Math.max(rawW * 0.28, 24);
    const padY = Math.max(rawH * 0.28, 24);
    const targetAspect = base.width / Math.max(1, base.height);
    let boxW = rawW + padX * 2;
    let boxH = rawH + padY * 2;
    if (boxW / boxH > targetAspect) {
      boxH = boxW / targetAspect;
    } else {
      boxW = boxH * targetAspect;
    }
    boxW = Math.min(snapshot.width, boxW);
    boxH = Math.min(snapshot.height, boxH);
    const centerX = (minX + maxX) / 2;
    const centerY = (minY + maxY) / 2;
    const x0 = Math.max(0, Math.min(snapshot.width - boxW, centerX - boxW / 2));
    const y0 = Math.max(0, Math.min(snapshot.height - boxH, centerY - boxH / 2));
    return {
      x: Math.round(x0 * 10) / 10,
      y: Math.round(y0 * 10) / 10,
      width: Math.round(boxW * 10) / 10,
      height: Math.round(boxH * 10) / 10
    };
  }, [snapshot, currentRegion.id]);

  const clipMeshes = snapshot
    ? currentRegion.id === 'overview'
      ? Object.values(snapshot.meshes)
      : currentRegion.id === 'nose'
        ? ['forehead', 'nose', 'chin'].map(id => snapshot.meshes[id]).filter(Boolean)
        : snapshot.meshes[currentRegion.id]
          ? [snapshot.meshes[currentRegion.id]]
          : []
    : [];

  const candidate = snapshot?.localMaps?.[`${currentRegion.id}:${selectedCriterion}`] || snapshot?.localMaps?.[currentRegion.id];
  const localMap = candidate && candidate.criterion === selectedCriterion && candidate.region === currentRegion.id && candidate.photoId === snapshot?.photoId && candidate.pose === snapshot.angle && candidate.sourceWidth === snapshot.width && candidate.sourceHeight === snapshot.height && ['analytic-pixel-index', 'appearance-proxy'].includes(candidate.validation) ? candidate : undefined;

  const linePaths = React.useMemo(() => {
    if (selectedCriterion !== 'lines') return [];
    if (localMap?.linePaths?.length) return localMap.linePaths;
    const lineInd = currentRegion.indicators?.find(item => item.id === 'lines');
    const compPaths = (lineInd?.appearance?.components as any)?.linePaths || (lineInd?.appearance?.components as any)?.sourceComponents?.linePaths;
    return Array.isArray(compPaths) ? compPaths : [];
  }, [selectedCriterion, localMap, currentRegion.indicators]);

  const regionalTrace = (currentRegion.skinType as any)?.decisionTrace?.regions
    || (snapshot?.general as any)?.skinType?.decisionTrace?.regions
    || (snapshot?.general as any)?.regionalSkinMap?.regions;

  useEffect(() => {
    const update = () => setDpr(window.devicePixelRatio || 1);
    update();
    window.addEventListener('resize', update);
    return () => window.removeEventListener('resize', update);
  }, []);

  return (
    <div className="flex flex-col items-center justify-center w-full">
      {/* Natural portrait pixels; fixed aspect ratio prevents height jumps across region tabs. */}
      <div
        className={`relative w-full ${isLiveVideo && mode === 'scan' || snapshot ? 'max-w-[480px]' : 'max-w-[360px]'} rounded-2xl overflow-hidden select-none`}
        ref={panel}
        style={displayCrop ? { aspectRatio: displayCrop.width / displayCrop.height, maxWidth: 400 } : isLiveVideo && mode === 'scan' ? { aspectRatio: videoRatio * crop.width / crop.height, maxWidth: `min(480px,${65 * videoRatio * crop.width / crop.height}vh)` } : undefined}
        data-face-panel
        data-preview-crop={isLiveVideo && mode === 'scan' ? JSON.stringify(crop) : snapshot?.previewCrop ? JSON.stringify(snapshot.previewCrop) : undefined}
        data-source-pixel-width={displayCrop?.width}
        data-display-dpr={dpr}
      >
        {/* Actual decoded video dimensions keep landmarks aligned without cropping. */}
        {isLiveVideo && mode === 'scan' ? (
          <div data-skin-preview-source className="absolute" style={{ width: `${100 / crop.width}%`, height: `${100 / crop.height}%`, left: `${-100 * crop.x / crop.width}%`, top: `${-100 * crop.y / crop.height}%` }}>
            <video ref={videoRef} onLoadedMetadata={updateVideoRatio} onLoadedData={updateVideoRatio} autoPlay playsInline muted className="w-full h-full object-fill" data-skin-live-video />
            {landmarks && (
              <svg data-skin-live-landmarks viewBox="0 0 100 100" preserveAspectRatio="none" className="absolute inset-0 w-full h-full pointer-events-none" aria-label={i18nText("Gerçek yüz noktaları")}>
                {landmarks.map((point, index) => <circle key={index} cx={point.x * 100} cy={point.y * 100} r=".15" fill="#67e8f9" />)}
              </svg>
            )}
          </div>
        ) : (
          mode === 'start' ? (
            <Image src="/assets/skin-preparation.png" alt={i18nText("Cilt taraması hazırlık görseli")} width={600} height={800} className="w-full h-auto" />
          ) : snapshot ? (
            snapshot.visualError ? (
              <div role="alert" data-skin-segmentation-error className="min-h-64 p-6 flex items-center text-center text-sm text-amber-200">{i18nNode(snapshot.visualError)}</div>
            ) : (
              <svg
                data-skin-snapshot
                data-snapshot-photoid={snapshot.photoId}
                data-local-analysis={snapshot.localAnalysis ? JSON.stringify(snapshot.localAnalysis) : undefined}
                data-snapshot-width={snapshot.width}
                data-snapshot-height={snapshot.height}
                data-mask-width={snapshot.maskWidth}
                data-mask-height={snapshot.maskHeight}
                data-segmentation-ms={snapshot.segmentationMs}
                viewBox={`${displayCrop!.x} ${displayCrop!.y} ${displayCrop!.width} ${displayCrop!.height}`}
                className="w-full h-full"
                role="img"
                aria-label={i18nText(`${currentRegion.nameTr} kabul edilmiş tarama görüntüsü`)}
              >
                <defs>
                  <filter id={maskId} x="-40%" y="-40%" width="180%" height="180%">
                    <feGaussianBlur stdDeviation={displayCrop!.width / 700} />
                  </filter>
                  <clipPath id={`${maskId}-region`} clipPathUnits="userSpaceOnUse">
                    {clipMeshes.flatMap((mesh, meshIndex) =>
                      selectedCriterion === 'acne' && localMap?.method === 'source-box-anatomical-support-v2'
                        ? [<path key={meshIndex} d={skinBoxEnvelope(mesh.points)} />]
                        : meshTriangles(mesh, selectedCriterion === 'bags', closedSurfaceSupportEnabled(selectedCriterion, localMap?.calibrationVersion)).map((triangle, i) => (
                            <path key={meshIndex + ':' + i} d={triangle.map((point, j) => `${j ? 'L' : 'M'}${mesh.points[point].x} ${mesh.points[point].y}`).join('') + 'Z'} />
                          ))
                    )}
                  </clipPath>
                </defs>
                <image href={snapshot.dataUrl} width={snapshot.width} height={snapshot.height} />
                {localMap && clipMeshes.length > 0 && selectedCriterion !== 'lines' && (
                  <>
                    <defs>
                      <mask id={`${maskId}-valid`} maskUnits="userSpaceOnUse" x={localMap.x} y={localMap.y} width={localMap.width * localMap.step} height={localMap.height * localMap.step} style={{ maskType: 'luminance' }}>
                        <image href={localMap.validMaskUrl} x={localMap.x} y={localMap.y} width={localMap.width * localMap.step} height={localMap.height * localMap.step} style={{ imageRendering: 'pixelated' }} />
                        {snapshot.exclusions.map((box, i) => <rect key={i} x={box.x} y={box.y} width={box.w} height={box.h} fill="black" />)}
                        {snapshot.exclusionPolygons?.map((poly, i) => (
                          <polygon key={`poly-${i}`} points={poly.points.map(p => `${p.x},${p.y}`).join(' ')} fill="black" />
                        ))}
                      </mask>
                    </defs>
                    <g data-skin-local-fill={localMap.criterion} data-map-photo={localMap.photoId} data-map-pose={localMap.pose} data-map-method={localMap.method} data-map-resolution={`${localMap.width}x${localMap.height}`} clipPath={`url(#${maskId}-region)`} mask={`url(#${maskId}-valid)`}>
                      <image href={localMap.dataUrl} x={localMap.x} y={localMap.y} width={localMap.width * localMap.step} height={localMap.height * localMap.step} />
                    </g>
                  </>
                )}
                {selectedCriterion === 'lines' && linePaths.length > 0 && (
                  <g data-skin-line-paths clipPath={`url(#${maskId}-region)`}>
                    {linePaths.map((lp: any, idx: number) => (
                      <path
                        key={lp.id || idx}
                        data-skin-line-path={lp.id || `line-${idx + 1}`}
                        d={lp.points.map((pt: { x: number; y: number }, j: number) => `${j ? 'L' : 'M'}${pt.x} ${pt.y}`).join(' ')}
                        fill="none"
                        stroke="#38bdf8"
                        strokeWidth={Math.max(1.2, (displayCrop!.width / 260) * (0.65 + 0.5 * (lp.strength ?? 0.5)))}
                        strokeOpacity={Math.min(0.95, 0.55 + 0.4 * (lp.strength ?? 0.5))}
                        strokeLinecap="round"
                        strokeLinejoin="round"
                      />
                    ))}
                  </g>
                )}
                {['sag', 'bags'].includes(selectedCriterion || '') && snapshot.contoursMeasured?.[currentRegion.id] && (
                  <g clipPath={`url(#${maskId}-region)`}>
                    {(snapshot.contoursMeasured[currentRegion.id].lines || [snapshot.contoursMeasured[currentRegion.id].points]).map((line, i) => (
                      <path key={i} data-skin-contour={currentRegion.id} d={line.map((p, j) => `${j ? 'L' : 'M'}${p.x * snapshot.width} ${p.y * snapshot.height}`).join(' ')} stroke="#c4b5fd" strokeWidth={snapshot.width / 350} fill="none" />
                    ))}
                  </g>
                )}
                {/* Regional skin-type map, HUD style: thin glowing outline per region, dot-matrix fill that is
                    brighter at the edge and fades inward, small tags. Unmeasured = grey dashed outline;
                    sensitive = pink inset dashed ring + sparse pink dots. Never global skinType, never boxes. */}
                {mode === 'result' && !selectedCriterion && regionalTrace && snapshot.landmarks && snapshot.landmarks.length >= 468 && (() => {
                  const lmk = snapshot.landmarks!;
                  const fw = faceWidthPx(lmk, snapshot.width);
                  const ids: PaintRegionId[] = ['forehead', 'nose', 'rightCheek', 'leftCheek', 'chin', 'periorbital'];
                  const rows = ids.flatMap(regionId => {
                    if (currentRegion.id !== 'overview' && currentRegion.id !== 'nose' && currentRegion.id !== regionId) return [];
                    if (currentRegion.id === 'nose' && !['forehead', 'nose', 'chin'].includes(regionId)) return [];
                    const regEntry = regionalTrace[regionId];
                    if (!regEntry) return [];
                    if (snapshot.angle !== 'FRONT' && regEntry.sourcePose && regEntry.sourcePose !== snapshot.angle) return [];
                    if (snapshot.angle !== 'FRONT' && regEntry.sourcePhotoId && snapshot.photoId && regEntry.sourcePhotoId !== snapshot.photoId) return [];
                    const d = paintPath(regionId, lmk, snapshot.width, snapshot.height);
                    if (!d) return [];
                    const raw = regEntry.state;
                    const state: PaintState = raw === 'oily' || raw === 'dry' || raw === 'normal' ? raw : 'unmeasured';
                    return [{ regionId, d, state, sensitive: state !== 'unmeasured' && regEntry.sensitive === true }];
                  });
                  if (!rows.length) return null;
                  const sw = fw / 260, step = fw / 60, fs = fw / 28;
                  return (
                    <g data-skin-type-overlay>
                      <defs>
                        <filter id={`${maskId}-hud-glow`} x="-30%" y="-30%" width="160%" height="160%"><feGaussianBlur stdDeviation={fw / 90} /></filter>
                        {(['oily', 'dry', 'normal', 'unmeasured'] as PaintState[]).map(st => (
                          <pattern key={st} id={`${maskId}-hud-dots-${st}`} patternUnits="userSpaceOnUse" width={step} height={step}>
                            <circle cx={step / 2} cy={step / 2} r={fw / 330} fill={PAINT_COLORS[st]} />
                          </pattern>
                        ))}
                        <pattern id={`${maskId}-hud-dots-sens`} patternUnits="userSpaceOnUse" width={step * 3} height={step * 3}>
                          <circle cx={step * 1.5} cy={step * 1.5} r={fw / 300} fill={SENSITIVE_COLOR} />
                        </pattern>
                        {rows.map(r => <clipPath key={r.regionId} id={`${maskId}-hud-clip-${r.regionId}`}><path d={r.d} clipRule="evenodd" /></clipPath>)}
                      </defs>
                      {rows.map(r => {
                        const c = PAINT_COLORS[r.state], clip = `url(#${maskId}-hud-clip-${r.regionId})`;
                        const cen = r.sensitive ? paintCentroid(r.regionId, lmk, snapshot.width, snapshot.height) : null;
                        return (
                          <g key={r.regionId} data-skin-type-region={r.regionId} data-skin-type-state={r.state} data-skin-type-sensitive={r.sensitive ? 'true' : 'false'}>
                            <path d={r.d} fill={c} fillOpacity="0.10" fillRule="evenodd" />
                            {/* edge-bright inner glow: wide blurred stroke kept inside the outline */}
                            <g clipPath={clip}><path d={r.d} fill="none" stroke={c} strokeWidth={fw / 9} strokeOpacity="0.22" filter={`url(#${maskId}-hud-glow)`} /></g>
                            <path d={r.d} fill={`url(#${maskId}-hud-dots-${r.state})`} fillRule="evenodd" opacity="0.55" />
                            {r.state === 'unmeasured'
                              ? <path data-skin-type-unmeasured={r.regionId} d={r.d} fill="none" stroke={c} strokeWidth={sw} strokeDasharray={`${fw / 40} ${fw / 60}`} strokeLinecap="round" />
                              : <>
                                  <path d={r.d} fill="none" stroke={c} strokeWidth={fw / 70} strokeOpacity="0.35" filter={`url(#${maskId}-hud-glow)`} />
                                  <path d={r.d} fill="none" stroke={c} strokeWidth={sw} strokeLinejoin="round" />
                                </>}
                            {r.sensitive && cen && (
                              <g data-skin-type-sensitive-layer={r.regionId} clipPath={clip}>
                                <path d={r.d} fill={`url(#${maskId}-hud-dots-sens)`} fillRule="evenodd" opacity="0.9" />
                                <path d={r.d} fill="none" stroke={SENSITIVE_COLOR} strokeWidth={fw / 300} strokeDasharray={`${fw / 70} ${fw / 90}`}
                                  transform={`translate(${cen.x} ${cen.y}) scale(0.88) translate(${-cen.x} ${-cen.y})`} />
                              </g>
                            )}
                          </g>
                        );
                      })}
                      {currentRegion.id === 'overview' && rows.filter(r => r.regionId !== 'periorbital').map(r => {
                        const a = PAINT_TAG_ANCHOR[r.regionId as Exclude<PaintRegionId, 'periorbital'>];
                        const x = lmk[a.index].x * snapshot.width + a.dx * fw, y = lmk[a.index].y * snapshot.height + a.dy * fw;
                        const text = i18nText(PAINT_LABELS[r.state]) + (r.sensitive ? ' · ' + i18nText('Hassas') : '');
                        const tw = text.length * fs * 0.58 + fs * 0.9;
                        return (
                          <g key={`tag-${r.regionId}`} data-skin-type-tag={r.regionId}>
                            <rect x={x - tw / 2} y={y - fs * 0.75} width={tw} height={fs * 1.5} rx={fs * 0.75} fill="#0a1220" fillOpacity="0.68" stroke={PAINT_COLORS[r.state]} strokeOpacity="0.9" strokeWidth={fw / 400} />
                            <text x={x} y={y + fs * 0.34} textAnchor="middle" fontSize={fs} fill="#ebf2fa" style={{ fontFamily: 'inherit' }}>{text}</text>
                          </g>
                        );
                      })}
                    </g>
                  );
                })()}
                {selectedCriterion === 'acne' && (
                  <g data-skin-acne-markers clipPath={snapshot.experimentalAcneV5 ? undefined : `url(#${maskId}-region)`}>
                    {(currentRegion.id === 'nose'
                      ? ['forehead', 'nose', 'chin'].flatMap(id => snapshot.acneCandidates?.[id] || [])
                      : snapshot.acneCandidates?.[currentRegion.id] || []
                    ).map((box, i) => {
                      const cx = box.x + box.width / 2;
                      const cy = box.y + box.height / 2;
                      const inBoxExclusion = snapshot.exclusions?.some(ex => cx >= ex.x && cx <= ex.x + ex.w && cy >= ex.y && cy <= ex.y + ex.h);
                      const inPolyExclusion = snapshot.exclusionPolygons?.some(poly => pointInPolygon(cx, cy, poly.points));
                      if (inBoxExclusion || inPolyExclusion) return null;
                      const cls = (box as any).canonicalClass || (box as any).class || 'acne';
                      const pointSource = (box as any).pointSource || 'box_centroid';
                      let fillColor = '#f43f5e';
                      let strokeColor = '#fff1f2';
                      if (cls === 'open_comedo' || cls === 'blackhead') {
                        fillColor = '#0f172a';
                        strokeColor = '#f8fafc';
                      } else if (cls === 'closed_comedo' || cls === 'whitehead') {
                        fillColor = '#f8fafc';
                        strokeColor = '#475569';
                      } else if (cls === 'papule') {
                        fillColor = '#ef4444';
                        strokeColor = '#fee2e2';
                      } else if (cls === 'pustule') {
                        fillColor = '#eab308';
                        strokeColor = '#dc2626';
                      }
                      const r = displayCrop!.width * 3.8 / Math.max(260, panelWidth);
                      return (
                        <circle
                          key={i}
                          data-acne-candidate={i}
                          data-acne-class={cls}
                          data-point-source={pointSource}
                          data-photo-id={(box as any).photoId || snapshot.photoId}
                          cx={cx}
                          cy={cy}
                          r={r}
                          stroke={strokeColor}
                          strokeWidth={displayCrop!.width / 360}
                          fill={fillColor}
                          fillOpacity="0.88"
                        />
                      );
                    })}
                  </g>
                )}
                {/* Anatomical wireframe mesh is ONLY shown in scan mode, never in result view */}
                {mode === 'scan' && snapshot.meshes[currentRegion.id] && (
                  <g data-skin-roi={currentRegion.id} data-skin-mesh={currentRegion.id} stroke="#36e4f1" fill="none" strokeLinejoin="round" strokeLinecap="round">
                    {snapshot.meshes[currentRegion.id].edges.map(([a, b], i) => {
                      const points = snapshot.meshes[currentRegion.id].points;
                      return <path key={i} data-mesh-edge={`${a}-${b}`} d={`M${points[a].x} ${points[a].y}L${points[b].x} ${points[b].y}`} strokeWidth={displayCrop!.width / 330} strokeOpacity=".68" />;
                    })}
                    {snapshot.meshes[currentRegion.id].points.map((p, i) => {
                      const major = snapshot.meshes[currentRegion.id].major.includes(i), r = displayCrop!.width * (major ? 2.6 : 1.25) / 400;
                      return (
                        <g key={i}>
                          <circle cx={p.x} cy={p.y} r={r * 1.6} fill="#36e4f1" stroke="none" opacity=".25" filter={`url(#${maskId})`} />
                          {major ? <path d={`M${p.x} ${p.y - r}l${r} ${r}l-${r} ${r}l-${r} -${r}Z`} fill="#85f8ff" stroke="none" /> : <circle cx={p.x} cy={p.y} r={r} fill="#7af2fc" stroke="none" />}
                        </g>
                      );
                    })}
                  </g>
                )}
              </svg>
            )
          ) : (
            <div data-skin-photo-empty className="min-h-64 flex items-center justify-center p-8 text-center text-sm text-slate-400">
              {i18nText("Bu kayıtta yüz fotoğrafı yok. Yalnız sayısal sonuçlar saklandı.")}
            </div>
          )
        )}
      </div>

      {/* Yüzün Altındaki Sayaç ve İndikatör */}
      {mode === 'result' && onPrev && onNext && (
        <SkinRegionNavigator
          currentRegion={currentRegion}
          onPrev={onPrev}
          onNext={onNext}
        />
      )}
    </div>
  );
};

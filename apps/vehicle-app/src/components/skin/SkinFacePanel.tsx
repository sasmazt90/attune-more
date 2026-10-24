'use client';
import {useTranslations} from '../../i18n/LanguageProvider';


import React, { useEffect, useState } from 'react';
import { SkinRegionData } from '../../data/skinDemoFixture';
import { SkinSnapshot } from '../../utils/skinSnapshot';
import Image from 'next/image';
import { useId } from 'react';
import { SkinRegionNavigator } from './SkinRegionNavigator';
import { cameraCrop } from '../CameraPreparation';
import { StablePreviewCrop } from '../../utils/cameraStability';
import { meshTriangles,closedSurfaceSupportEnabled } from '../../utils/skinSurfaceAnalysis';
import { skinBoxEnvelope } from '../../utils/skinBoxEnvelope';

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
  selectedCriterion?:string|null;
}

export const SkinFacePanel: React.FC<SkinFacePanelProps> = ({
  currentRegion, snapshot,
  mode = 'result',
  onPrev,
  onNext,
  videoRef,
  isLiveVideo = false,
  landmarks,selectedCriterion
}) => {
 const {text:i18nText,node:i18nNode}=useTranslations();
  const maskId = useId();
  const [videoRatio,setVideoRatio]=useState(4/3);
  const previewCrop=React.useRef(new StablePreviewCrop());
  const crop=isLiveVideo&&mode==='scan'?previewCrop.current.update(cameraCrop(landmarks),performance.now()):{x:0,y:0,width:1,height:1};
  const updateVideoRatio=(event:React.SyntheticEvent<HTMLVideoElement>)=>{const v=event.currentTarget;if(v.videoWidth && v.videoHeight)setVideoRatio(v.videoWidth/v.videoHeight);};
  const [dpr,setDpr]=useState(1);
  const panel=React.useRef<HTMLDivElement>(null);const [panelWidth,setPanelWidth]=useState(400);
  useEffect(()=>{if(!snapshot?.experimentalAcneV5||!panel.current)return;const observer=new ResizeObserver(([entry])=>setPanelWidth(entry.contentRect.width||400));observer.observe(panel.current);return()=>observer.disconnect();},[snapshot?.experimentalAcneV5]);
  const displayCrop = React.useMemo(() => {
    const base = snapshot?.previewCrop ? {
      x: snapshot.previewCrop.x * snapshot.width,
      y: snapshot.previewCrop.y * snapshot.height,
      width: snapshot.previewCrop.width * snapshot.width,
      height: snapshot.previewCrop.height * snapshot.height
    } : snapshot?.crop;

    if (!snapshot || !snapshot.previewCrop || currentRegion.id === 'overview' || !snapshot.meshes?.[currentRegion.id]?.points?.length) {
      return base;
    }

    const pts = snapshot.meshes[currentRegion.id].points;
    let minX = pts[0].x, maxX = pts[0].x, minY = pts[0].y, maxY = pts[0].y;
    for (let i = 1; i < pts.length; i++) {
      if (pts[i].x < minX) minX = pts[i].x;
      if (pts[i].x > maxX) maxX = pts[i].x;
      if (pts[i].y < minY) minY = pts[i].y;
      if (pts[i].y > maxY) maxY = pts[i].y;
    }
    const w = maxX - minX;
    const h = maxY - minY;
    const padX = Math.max(w * 0.25, 20);
    const padY = Math.max(h * 0.25, 20);
    const cx = minX - padX;
    const cy = minY - padY;
    const cw = w + padX * 2;
    const ch = h + padY * 2;
    return {
      x: Math.max(0, cx),
      y: Math.max(0, cy),
      width: Math.min(snapshot.width - Math.max(0, cx), cw),
      height: Math.min(snapshot.height - Math.max(0, cy), ch)
    };
  }, [snapshot, currentRegion.id]);
  const clipMeshes=snapshot ? currentRegion.id==="overview" ? Object.values(snapshot.meshes) : snapshot.meshes[currentRegion.id] ? [snapshot.meshes[currentRegion.id]] : [] : [];
  const candidate=snapshot?.localMaps?.[`${currentRegion.id}:${selectedCriterion}`]||snapshot?.localMaps?.[currentRegion.id];
  const localMap=candidate&&candidate.criterion===selectedCriterion&&candidate.region===currentRegion.id&&candidate.photoId===snapshot?.photoId&&candidate.pose===snapshot.angle&&candidate.sourceWidth===snapshot.width&&candidate.sourceHeight===snapshot.height&&['analytic-pixel-index','appearance-proxy'].includes(candidate.validation)?candidate:undefined;
  useEffect(()=>{const update=()=>setDpr(window.devicePixelRatio||1);update();window.addEventListener('resize',update);return()=>window.removeEventListener('resize',update);},[]);

  return (
    <div className="flex flex-col items-center justify-center w-full">
      {/* Natural portrait pixels; no outline or shadow on the photo. */}
      <div className={`relative w-full ${isLiveVideo && mode === 'scan' || snapshot ? 'max-w-[480px]' : 'max-w-[360px]'} rounded-2xl overflow-hidden select-none`} ref={panel} style={displayCrop ? { aspectRatio: displayCrop.width / displayCrop.height, maxWidth: 400 } : isLiveVideo && mode === 'scan' ? {aspectRatio:videoRatio*crop.width/crop.height,maxWidth:`min(480px,${65*videoRatio*crop.width/crop.height}vh)`} : undefined} data-face-panel data-preview-crop={isLiveVideo&&mode==='scan'?JSON.stringify(crop):snapshot?.previewCrop?JSON.stringify(snapshot.previewCrop):undefined} data-source-pixel-width={displayCrop?.width} data-display-dpr={dpr}>
        {/* Actual decoded video dimensions keep landmarks aligned without cropping. */}
        {isLiveVideo && mode === 'scan' ? (
          <div data-skin-preview-source className="absolute" style={{width:`${100/crop.width}%`,height:`${100/crop.height}%`,left:`${-100*crop.x/crop.width}%`,top:`${-100*crop.y/crop.height}%`}}><video ref={videoRef} onLoadedMetadata={updateVideoRatio} onLoadedData={updateVideoRatio} autoPlay playsInline muted className="w-full h-full object-fill" data-skin-live-video />{landmarks && <svg data-skin-live-landmarks viewBox="0 0 100 100" preserveAspectRatio="none" className="absolute inset-0 w-full h-full pointer-events-none" aria-label={i18nText("Gerçek yüz noktaları")}>{landmarks.map((point,index)=><circle key={index} cx={point.x*100} cy={point.y*100} r=".15" fill="#67e8f9" />)}</svg>}</div>
        ) : (
          mode === 'start' ? <Image src="/assets/skin-preparation.png" alt={i18nText("Cilt taraması hazırlık görseli")} width={600} height={800} className="w-full h-auto" /> : snapshot ? snapshot.visualError ? <div role="alert" data-skin-segmentation-error className="min-h-64 p-6 flex items-center text-center text-sm text-amber-200">{i18nNode(snapshot.visualError)}</div> : <svg data-skin-snapshot data-snapshot-photoid={snapshot.photoId} data-local-analysis={snapshot.localAnalysis?JSON.stringify(snapshot.localAnalysis):undefined} data-snapshot-width={snapshot.width} data-snapshot-height={snapshot.height} data-mask-width={snapshot.maskWidth} data-mask-height={snapshot.maskHeight} data-segmentation-ms={snapshot.segmentationMs} viewBox={`${displayCrop!.x} ${displayCrop!.y} ${displayCrop!.width} ${displayCrop!.height}`} className="w-full h-full" role="img" aria-label={i18nText(`${currentRegion.nameTr} kabul edilmiş tarama görüntüsü`)}>
            <defs><filter id={maskId} x="-40%" y="-40%" width="180%" height="180%"><feGaussianBlur stdDeviation={displayCrop!.width / 700}/></filter><clipPath id={`${maskId}-region`} clipPathUnits="userSpaceOnUse">{clipMeshes.flatMap((mesh,meshIndex)=>selectedCriterion==='acne'&&localMap?.method==='source-box-anatomical-support-v2'?[<path key={meshIndex} d={skinBoxEnvelope(mesh.points)}/>]:meshTriangles(mesh,selectedCriterion==='bags',closedSurfaceSupportEnabled(selectedCriterion,localMap?.calibrationVersion)).map((triangle,i)=><path key={meshIndex+':'+i} d={triangle.map((point,j)=>`${j?'L':'M'}${mesh.points[point].x} ${mesh.points[point].y}`).join('')+'Z'}/>))}</clipPath></defs>
            <image href={snapshot.dataUrl} width={snapshot.width} height={snapshot.height}/>
            {localMap&&clipMeshes.length>0&&<>
              <defs>
                <mask id={`${maskId}-valid`} maskUnits="userSpaceOnUse" x={localMap.x} y={localMap.y} width={localMap.width*localMap.step} height={localMap.height*localMap.step} style={{maskType:'luminance'}}><image href={localMap.validMaskUrl} x={localMap.x} y={localMap.y} width={localMap.width*localMap.step} height={localMap.height*localMap.step} style={{imageRendering:'pixelated'}}/>{snapshot.exclusions.map((box,i)=><rect key={i} x={box.x} y={box.y} width={box.w} height={box.h} fill="black"/>)}</mask>
              </defs>
              <g data-skin-local-fill={localMap.criterion} data-map-photo={localMap.photoId} data-map-pose={localMap.pose} data-map-method={localMap.method} data-map-resolution={`${localMap.width}x${localMap.height}`} clipPath={`url(#${maskId}-region)`} mask={`url(#${maskId}-valid)`}><image href={localMap.dataUrl} x={localMap.x} y={localMap.y} width={localMap.width*localMap.step} height={localMap.height*localMap.step}/></g>
            </>}
            {['sag','bags'].includes(selectedCriterion||'')&&snapshot.contoursMeasured?.[currentRegion.id]&&<g clipPath={`url(#${maskId}-region)`}>{(snapshot.contoursMeasured[currentRegion.id].lines||[snapshot.contoursMeasured[currentRegion.id].points]).map((line,i)=><path key={i} data-skin-contour={currentRegion.id} d={line.map((p,j)=>`${j?'L':'M'}${p.x*snapshot.width} ${p.y*snapshot.height}`).join(' ')} stroke="#c4b5fd" strokeWidth={snapshot.width/350} fill="none"/>)}</g>}
            {/* Regional Skin Type Transparent Overlay when in result mode and no specific criterion is active */}
            {mode === 'result' && !selectedCriterion && snapshot.meshes && currentRegion.skinType?.value && (
              <g data-skin-type-overlay opacity="0.30">
                {Object.entries(snapshot.meshes).map(([regionId, mesh]) => {
                  const skinVal = currentRegion.skinType?.value;
                  let fillColor = 'none';
                  if (skinVal === 'dry') {
                    fillColor = '#3388ff';
                  } else if (skinVal === 'oily') {
                    fillColor = '#22c55e';
                  } else if (skinVal === 'combination') {
                    if (['forehead', 'nose', 'chin'].includes(regionId)) {
                      fillColor = '#22c55e';
                    } else if (['leftCheek', 'rightCheek'].includes(regionId)) {
                      fillColor = '#3388ff';
                    }
                  }
                  if (fillColor === 'none') return null;

                  return (
                    <g key={regionId} data-skin-type-region={regionId} fill={fillColor}>
                      {meshTriangles(mesh, false, false).map((tri, i) => (
                        <path
                          key={i}
                          d={tri.map((ptIdx, j) => `${j ? 'L' : 'M'}${mesh.points[ptIdx].x} ${mesh.points[ptIdx].y}`).join('') + 'Z'}
                          stroke="none"
                        />
                      ))}
                    </g>
                  );
                })}
              </g>
            )}
            {selectedCriterion==='acne'&&<g data-skin-acne-markers clipPath={snapshot.experimentalAcneV5?undefined:`url(#${maskId}-region)`}>{snapshot.acneCandidates?.[currentRegion.id]?.map((box,i)=>{
              const cx = box.x + box.width / 2;
              const cy = box.y + box.height / 2;
              const isExcluded = snapshot.exclusions?.some(ex => cx >= ex.x && cx <= ex.x + ex.w && cy >= ex.y && cy <= ex.y + ex.h);
              if (isExcluded) return null;
              const cls = (box as any).canonicalClass || (box as any).class || 'acne';
              let fillColor = snapshot.experimentalAcneV5 ? "#fda4af" : "none";
              let strokeColor = "#fda4af";
              if (cls === 'open_comedo' || cls === 'blackhead') {
                fillColor = '#0f172a';
                strokeColor = '#f8fafc';
              } else if (cls === 'closed_comedo' || cls === 'whitehead') {
                fillColor = '#ffffff';
                strokeColor = '#64748b';
              } else if (cls === 'papule') {
                fillColor = '#ef4444';
                strokeColor = '#991b1b';
              } else if (cls === 'pustule') {
                fillColor = '#eab308';
                strokeColor = '#dc2626';
              }
              const r = snapshot.experimentalAcneV5 ? displayCrop!.width*3.5/panelWidth : Math.max(box.width,box.height)/2+snapshot.width/500;
              return <circle key={i} data-acne-candidate={i} data-acne-class={cls} cx={cx} cy={cy} r={r} stroke={strokeColor} strokeWidth={displayCrop!.width/400} fill={fillColor}/>;
            })}</g>}
            {/* Anatomical wireframe mesh is ONLY shown in scan mode, never in result view */}
            {snapshot.meshes[currentRegion.id] && (!selectedCriterion || mode === 'scan') && <g data-skin-roi={currentRegion.id} data-skin-mesh={currentRegion.id} stroke="#36e4f1" fill="none" strokeLinejoin="round" strokeLinecap="round">
              {snapshot.meshes[currentRegion.id].edges.map(([a,b],i)=>{const points=snapshot.meshes[currentRegion.id].points;return <path key={i} data-mesh-edge={`${a}-${b}`} d={`M${points[a].x} ${points[a].y}L${points[b].x} ${points[b].y}`} strokeWidth={displayCrop!.width / 330} strokeOpacity=".68"/>;})}
              {snapshot.meshes[currentRegion.id].points.map((p,i)=>{const major=snapshot.meshes[currentRegion.id].major.includes(i),r=displayCrop!.width*(major?2.6:1.25)/400;return <g key={i}><circle cx={p.x} cy={p.y} r={r*1.6} fill="#36e4f1" stroke="none" opacity=".25" filter={`url(#${maskId})`}/>{major?<path d={`M${p.x} ${p.y-r}l${r} ${r}l-${r} ${r}l-${r} -${r}Z`} fill="#85f8ff" stroke="none"/>:<circle cx={p.x} cy={p.y} r={r} fill="#7af2fc" stroke="none"/>}</g>;})}
            </g>}
          </svg> : <div data-skin-photo-empty className="min-h-64 flex items-center justify-center p-8 text-center text-sm text-slate-400">{i18nText("Bu kayıtta yüz fotoğrafı yok. Yalnız sayısal sonuçlar saklandı.")}</div>
        )}


      </div>


      {/* Yüzün Altındaki Sayaç ve İndikatör (2 / 6 Sağ Yanak) */}
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

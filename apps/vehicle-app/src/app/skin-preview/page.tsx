'use client';
/* Development-only design preview of the skin result screen with a synthetic character (not shipped). */
import React from 'react';
import fixture from './fixture.json';
import { SkinResultView } from '../../components/skin/SkinResultView';
import { buildSkinViewModel, SKIN_VIEW_ORDER, type SkinViewId } from '../../utils/skinOverview';
import { buildSkinMesh, supportedSkinMesh } from '../../utils/skinMesh';
import type { SkinSnapshot } from '../../utils/skinSnapshot';

export default function SkinPreview() {
  const [view, setView] = React.useState<SkinViewId>('overview');
  React.useEffect(() => { const v = new URLSearchParams(window.location.search).get('view') as SkinViewId | null; if (v) setView(v); }, []);
  const { width, height, landmarks } = fixture as any;
  const snapshot = React.useMemo(() => {
    const meshes = Object.fromEntries(['forehead', 'nose', 'chin', 'periorbital', 'rightCheek', 'leftCheek'].map(id => [id, supportedSkinMesh(buildSkinMesh(id, landmarks, width, height), landmarks, width, height)]));
    const xs = landmarks.map((p: any) => p.x * width), ys = landmarks.map((p: any) => p.y * height);
    const x0 = Math.min(...xs), x1 = Math.max(...xs), y0 = Math.min(...ys), y1 = Math.max(...ys), pad = (x1 - x0) * 0.22;
    const crop = { x: Math.max(0, x0 - pad), y: Math.max(0, y0 - pad * 1.3), width: Math.min(width, x1 - x0 + 2 * pad), height: Math.min(height, y1 - y0 + 2.3 * pad) };
    return { dataUrl: '/dev-preview/face.jpg', width, height, angle: 'FRONT', meshes, rois: [], exclusions: [], faceContour: [], contours: {}, crop, landmarks, photoId: 'preview' } as unknown as SkinSnapshot;
  }, [landmarks, width, height]);
  const result = {
    general: {
      skinType: { value: 'combination', sensitive: true, quality: 'valid', confidence: null, methodVersion: 'preview', modelHash: null, limitationCode: null },
      regionalSkinMap: {
        skinType: { value: 'combination', sensitive: true, quality: 'valid' },
        regions: { forehead: { state: 'oily' }, nose: { state: 'oily' }, chin: { state: 'normal' }, rightCheek: { state: 'normal', sensitive: true }, leftCheek: { state: 'normal', sensitive: true } }
      },
      indicators: []
    }
  };
  const region = buildSkinViewModel(view, result);
  const findings = (fixture as any).findings.findings as any[];
  // synthetic earlier scans: same findings with drifting scores
  const history = [[-75, -14], [-59, -9], [-47, -5], [-32, -8], [-16, -3]].map(([d, k]) => ({
    at: new Date(Date.UTC(2026, 9, 26 + d, 6, 40)).toISOString(),
    findings: findings.map(f => ({ ...f, ...(f.severity !== undefined ? { severity: Math.max(0, f.severity + k) } : {}), ...(f.areaPct !== undefined ? { areaPct: Math.max(0, f.areaPct + k) } : {}) }))
  }));
  const order = SKIN_VIEW_ORDER;
  return (
    <main className="p-10 max-w-[1600px] mx-auto w-full min-h-screen bg-[#070b12]">
      <SkinResultView currentRegion={region} snapshot={snapshot} findings={findings} findingsHistory={history} scanAt="2026-10-26T06:40:00.000Z" onRescan={() => {}} onSelectView={v => setView(v as SkinViewId)}
        onPrev={() => setView(order[(order.indexOf(view) - 1 + order.length) % order.length])} onNext={() => setView(order[(order.indexOf(view) + 1) % order.length])}
        onOpenModal={() => {}} onNavigateToCare={() => {}} />
    </main>
  );
}

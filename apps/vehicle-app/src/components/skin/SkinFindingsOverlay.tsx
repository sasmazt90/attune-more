'use client';
import React, { useId } from 'react';
import type { SkinSnapshot } from '../../utils/skinSnapshot';
import { POINT_FINDINGS, SKIN_FINDING_COLORS, sourceMatchedFindings } from '../../utils/skinFindingPresentation';

export function SkinFindingsOverlay({ snapshot, criterion, clipId, displayWidth, panelWidth }: {
  snapshot: SkinSnapshot; criterion?: string | null; clipId: string; displayWidth: number; panelWidth: number;
}) {
  const id = useId();
  const findings = sourceMatchedFindings(snapshot.findings, snapshot, criterion);
  if (!findings.length || !criterion) return null;
  const color = SKIN_FINDING_COLORS[criterion] || '#fda4af';
  return <g clipPath={`url(#${clipId})`} mask={`url(#${id}-skin)`} data-skin-findings={criterion}>
    <defs><mask id={`${id}-skin`} maskUnits="userSpaceOnUse" x="0" y="0" width={snapshot.width} height={snapshot.height} style={{ maskType: 'luminance' }}>
      <rect width={snapshot.width} height={snapshot.height} fill="white" />
      {snapshot.exclusions.map((b, i) => <rect key={i} x={b.x} y={b.y} width={b.w} height={b.h} fill="black" />)}
    </mask></defs>
    {POINT_FINDINGS.has(criterion) ? findings.map((f, i) => <circle key={i}
      cx={f.box.x + f.box.width / 2} cy={f.box.y + f.box.height / 2}
      r={displayWidth * 3.5 / Math.max(panelWidth, 1)} fill={color} />)
      : criterion === 'lines' ? findings.flatMap((f, i) => {
        const points = f.line;
        if (!points || points.length < 2 || !points.every(p => Number.isFinite(p.x) && Number.isFinite(p.y) && p.x >= f.box.x && p.x <= f.box.x+f.box.width && p.y >= f.box.y && p.y <= f.box.y+f.box.height)) return [];
        return [<path key={i} d={points.map((p, j) => `${j ? 'L' : 'M'}${p.x} ${p.y}`).join(' ')} fill="none" stroke={color} strokeWidth={displayWidth/350} strokeLinecap="round" />];
      }) : <>
        <defs>
          <filter id={`${id}-soft`} x="-20%" y="-20%" width="140%" height="140%"><feGaussianBlur stdDeviation={displayWidth/180} /></filter>
          <mask id={`${id}-area`} maskUnits="userSpaceOnUse" x="0" y="0" width={snapshot.width} height={snapshot.height} style={{ maskType: 'luminance' }}>
            <g filter={`url(#${id}-soft)`}>{findings.map((f, i) => <rect key={i} {...f.box} fill="white" />)}</g>
            {snapshot.exclusions.map((b, i) => <rect key={i} x={b.x} y={b.y} width={b.w} height={b.h} fill="black" />)}
          </mask>
        </defs>
        {/* One union layer: overlapping boxes do not accumulate opacity. */}
        <rect width={snapshot.width} height={snapshot.height} fill={color} opacity=".32" mask={`url(#${id}-area)`} />
      </>}
  </g>;
}

/** Display geometry never changes numerical measurements or lesion boundaries. */
export const SKIN_FINDING_COLORS: Record<string, string> = {
  dry: '#3b82f6', oil: '#22c55e', eczema: '#1e3a8a', redness: '#ef4444',
  rosacea: '#ef4444', dark: '#a78bfa', bags: '#fbbf24', tone: '#f59e0b',
};
export const POINT_FINDINGS = new Set(['acne', 'whiteheads', 'blackheads', 'pores', 'coldSore', 'mole']);
export type SkinFinding = {
  criterion: string; photoId: string; pose: string; sourceWidth: number; sourceHeight: number;
  modelHash: string; confidence: number; box: { x: number; y: number; width: number; height: number };
  line?: { x: number; y: number }[];
};
export function sourceMatchedFindings(findings: SkinFinding[] | undefined, source: { photoId?: string; angle: string; width: number; height: number }, criterion: string | null | undefined): SkinFinding[] {
  if (typeof source.photoId !== 'string' || !source.photoId.trim()) return [];
  return (findings || []).filter(f => {
    const b = f.box;
    return f.criterion === criterion && f.photoId === source.photoId && f.pose === source.angle &&
      f.sourceWidth === source.width && f.sourceHeight === source.height && /^[a-f0-9]{64}$/.test(f.modelHash) &&
      Number.isFinite(f.confidence) && f.confidence >= 0 && f.confidence <= 1 &&
      !!b && [b.x, b.y, b.width, b.height].every(Number.isFinite) &&
      b.x >= 0 && b.y >= 0 && b.width > 0 && b.height > 0 &&
      b.x + b.width <= source.width && b.y + b.height <= source.height;
  });
}

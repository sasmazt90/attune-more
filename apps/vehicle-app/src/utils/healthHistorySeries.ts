import {getLocale,t} from '../i18n/core';
/** Read-only presentation adapters. They never persist or change measurement precision. */
import type { HealthRecord } from './healthRecords';
import { HEALTH_MODULE_IDS, type HealthModule } from './healthModules';
import { performanceBySize, isLetterProtocol, type LetterTrial } from './spokenVision';
import { SIGN_LABELS, skinCriterionLabel, samplingSupportVersion } from './skinIndicators';
import { skinDisplayKind } from './skinPresentation';
import { DENTAL_ACCUMULATION_LABEL } from './dentalResult';

export type HistoryRecords = Record<HealthModule, HealthRecord[]>;
export type HistoryPoint = { id: string; recordId: string; time: number; value: number | null; detail: string; numerator?: number; denominator?: number };
export type HistorySeries = { id: string; module: HealthModule; criterion: string; label: string; region: string; regionLabel: string; unit: string; method: string; source: string; points: HistoryPoint[] };
export const EMPTY_HISTORY: HistoryRecords = { vision: [], skin: [], dental: [], hearing: [], mental: [] };
export const REGION_LABELS: Record<string, string> = { overview: 'Genel Bakış', forehead: 'Alın', rightCheek: 'Sağ yanak', leftCheek: 'Sol yanak', nose: 'T-Bölgesi', chin: 'Çene', periorbital: 'Göz çevresi', RIGHT: 'Sağ göz', LEFT: 'Sol göz', BOTH: 'İki göz', FRONT: 'Ön görünüm', BITE: 'Doğal kapanış', left: 'Sol kulak', right: 'Sağ kulak' };
const number = (v: unknown): number | null => typeof v === 'number' && Number.isFinite(v) ? v : null;
export function historyTime(record: HealthRecord) {
  const value = record.timestamp || record.date || record.completedAt;
  return typeof value === 'string' && Number.isFinite(Date.parse(value)) ? Date.parse(value) : null;
}
export function usableHistory(module: HealthModule, records: HealthRecord[]) {
  return records.filter(r => r.completed !== false && r.consented !== false && (module !== 'mental' || ![2, 3].includes(r.schemaVersion) || r.completed === true && r.consented === true));
}
export function recordsInRange(records: HealthRecord[], days: number | null, now = Date.now()) {
  return days === null ? records : records.filter(r => { const t = historyTime(r); return t !== null && t >= now - days * 86400000 && t <= now; });
}
export function formatHistoryValue(value: number, unit: string) {
  return `${new Intl.NumberFormat(getLocale(), { maximumFractionDigits: unit === '%' ? 0 : 3 }).format(value)}${unit === '%' ? '%' : unit ? ' ' + t(unit) : ''}`;
}
export function moduleOverview(module: HealthModule, records: HealthRecord[]): { date: number | null; text: string; count: number } {
  const rows = usableHistory(module, records).filter(r => r.quality !== 'invalid' && r.quality !== 'unreliable' && r.quality?.isValid !== false).slice().sort((a, b) => (historyTime(b) ?? -Infinity) - (historyTime(a) ?? -Infinity));
  const last = rows[0];
  if (!last) return { date: null, text: 'Kayıt yok', count: 0 };
  let text: string;
  if (module === 'vision') text = isLetterProtocol(last.protocolVersion) ? `${Array.isArray(last.trials) ? last.trials.filter((t: LetterTrial) => t.valid).length + ' geçerli harf/yön yanıtı' : 'Harf/yön oturumu'}` : 'Önceki görme protokolü';
  else if (module === 'skin') text = last.analysisMode === 'instant-appearance-v2' ? 'Anlık bölgesel görünüm' : 'Önceki cilt yöntemi';
  else if (module === 'dental') text = `${last.sourceType === 'upload' ? 'Yüklenen fotoğraf' : last.sourceType === 'camera' ? 'Kamera' : 'Kaynak kaydedilmemiş'} · ${Array.isArray(last.measurements) ? last.measurements.length + ' görünüm' : 'ölçüm ayrıntıları'}`;
  else if (module === 'hearing') text = Array.isArray(last.thresholds) ? 'Saf ses · dijital eşikler' : number(last.value) !== null ? `Sayı/gürültü · ${formatHistoryValue(last.value, 'dB SNR')}` : 'Sayı/gürültü · eşik ölçülemedi';
  else text = `${rows.length} görüşme · ${Array.isArray(last.themes) && last.themes.length ? [...new Set(last.themes)].map(theme=>t(theme)).join(' • ') : 'Tema kaydı yok'}`;
  return { date: historyTime(last), text, count: rows.length };
}

export function buildHistorySeries(module: HealthModule, records: HealthRecord[]): HistorySeries[] {
  const map = new Map<string, HistorySeries>(), rows = usableHistory(module, records).filter(r => historyTime(r) !== null).sort((a, b) => historyTime(a)! - historyTime(b)!);
  const add = (record: HealthRecord, spec: Omit<HistorySeries, 'id' | 'module' | 'points'>, compatibility: unknown[], value: number | null, suffix = '', detail = '', ratio?: { correct: number; total: number }) => {
    const id = JSON.stringify([module, spec.criterion, spec.region, spec.unit, ...compatibility]);
    if (!map.has(id)) map.set(id, { ...spec, id, module, points: [] });
    map.get(id)!.points.push({ id: record.id + ':' + suffix, recordId: record.id, time: historyTime(record)!, value, detail, ...(ratio ? { numerator: ratio.correct, denominator: ratio.total } : {}) });
  };
  for (const r of rows) {
    if (module === 'vision') {
      if (isLetterProtocol(r.protocolVersion) && Array.isArray(r.trials)) {
        for (const eye of ['RIGHT', 'LEFT'] as const) for (const group of performanceBySize(r.trials, eye)) {
          const trials = r.trials.filter((t: LetterTrial) => t.valid && t.eye === eye && t.renderedGeometry?.viewportWidthCssPx === group.widthCssPx && t.renderedGeometry?.viewportHeightCssPx === group.heightCssPx);
          // Split sessions further if source symbol stroke/path or screen conditions differ.
          const geometries = [...new Set(trials.map((t: LetterTrial) => JSON.stringify([t.renderedGeometry?.pathWidthCssPx, t.renderedGeometry?.pathHeightCssPx, t.renderedGeometry?.strokeWidthCssPx])))];
          for (const shape of geometries) {
            const subset = trials.filter((t: LetterTrial) => JSON.stringify([t.renderedGeometry?.pathWidthCssPx, t.renderedGeometry?.pathHeightCssPx, t.renderedGeometry?.strokeWidthCssPx]) === shape);
            const scoped = performanceBySize(subset, eye)[0];
            for (const [criterion, label] of [['letter', 'Harf tanımlama skoru'], ['orientation', 'Harf yönü skoru'], ['average', 'Toplam ortalama skor']] as const) {
              const a = criterion === 'average' ? {correct: 0, total: scoped.letter.total, percentage: scoped.average} : scoped[criterion];
              add(r, { criterion, label, region: eye, regionLabel: REGION_LABELS[eye], unit: '%', method: `Sesli harf · ${group.widthCssPx.toFixed(1)} × ${group.heightCssPx.toFixed(1)} CSS px`, source: '' }, [r.protocolVersion, r.methodVersion || r.protocolVersion, group.size, shape, r.deviceContext || { unknown: r.id }, r.distanceMethod || 'unknown'], a.percentage, eye + group.size + shape + criterion, criterion === 'average' ? '' : `${a.correct}/${a.total} doğru/geçerli yanıt`, criterion === 'average' ? undefined : a);
            }
          }
        }
      } else if (Array.isArray(r.trials) && /landolt-orientation/.test(r.protocolVersion || '')) {
        for (const eye of ['RIGHT', 'LEFT', 'BOTH']) {
          const values = r.trials.filter((t: any) => t.eye === eye && t.valid === true && number(t.minimumCircularError) !== null).map((t: any) => t.minimumCircularError as number);
          if (values.length) add(r, { criterion: 'angle', label: 'Yön açısı hatası', region: eye, regionLabel: REGION_LABELS[eye], unit: '°', method: r.protocolVersion, source: '' }, [r.protocolVersion, r.screenContext || r.deviceContext || { unknown: r.id }, r.calibration || null], values.reduce((a: number, b: number) => a + b, 0) / values.length, eye, `${values.length} geçerli yön yanıtı`);
        }
      }
    } else if (module === 'skin' && r.indicators && typeof r.indicators === 'object') {
      for (const [region, entries] of Object.entries({...r.indicators,...(r.general?.indicators?{overview:r.general.indicators}:{})})) if (Array.isArray(entries)) for (const entry of entries) {
        const a = entry.appearance, m = entry.measurement, kind = skinDisplayKind(entry), longitudinal = a?.type === 'longitudinal_measurement';
        const unit = longitudinal ? 'kontur farkı' : kind === 'percent' ? '%' : kind === 'count' ? 'aday' : m?.unit || entry.unit || '';
        const raw = longitudinal ? entry.referenceDelta : a ? a.value : m ? m.rawValue : entry.score;
        const valid = (!a || a.quality === 'valid') && (!m || m.quality === 'valid') && a?.limitationCode !== 'REFERENCE_CREATED';
        add(r, { criterion: entry.id, label: skinCriterionLabel(entry.id,region==="overview"?"whole-face":"regional"), region, regionLabel: REGION_LABELS[region] || region, unit, method: `${a?.methodVersion || m?.methodVersion || entry.method || 'Eski yöntem'}${longitudinal ? ' · kişisel referans farkı' : ' · mevcut görünüm'}`, source: '' }, [a?.methodVersion || m?.methodVersion || entry.method, a?.type || m?.validation || 'legacy', a?.unit || m?.unit || entry.unit, m?.modelHash || a?.modelHash || null, a?.normalizationVersion || null, samplingSupportVersion(a), a?.captureConditions?.skinCapturePolicy || null, a?.captureConditions?.skinEyewearModelHash || null, m?.datasetHash || null, m?.evidenceHash || null, longitudinal ? a?.referenceId || r.referenceId || r.id : null], valid ? number(raw) : null, region + entry.id, valid ? '' : entry.reason || 'Bu kayıtta ölçülemiyor');
      }
    } else if (module === 'dental' && Array.isArray(r.measurements)) {
      const source = r.sourceType === 'upload' ? 'Yüklenen fotoğraf' : r.sourceType === 'camera' ? 'Kamera' : 'Kaynak kaydedilmemiş';
      for (const [index, view] of r.measurements.entries()) {
        const pose = view.pose || 'FRONT', poseLabel = pose === 'RIGHT' ? 'Sağ görünüm' : pose === 'LEFT' ? 'Sol görünüm' : REGION_LABELS[pose] || pose;
        for (const [criterion, label, metric, unit] of [['caries', 'Çürük aday sayısı', view.caries, 'aday'], ['accumulation', DENTAL_ACCUMULATION_LABEL, view.accumulation, '%']] as const) {
          if (!metric) continue;
          add(r, { criterion, label, region: pose, regionLabel: poseLabel, unit, method: metric.modelVersion || metric.methodVersion || r.methodVersion || 'Eski yöntem', source }, [r.sourceType || { unknown: r.id }, r.measurements.length, metric.evidenceScope || metric.viewSupport || null, metric.methodVersion || r.methodVersion, metric.modelVersion || null, metric.modelHash || null, metric.decisionThreshold ?? metric.confidenceThreshold ?? metric.threshold ?? metric.components?.decisionThreshold ?? (criterion === 'caries' ? { unknown: r.id } : null), metric.unit || unit], metric.quality === 'valid' ? number(metric.value) : null, String(index) + criterion, source + (r.measurements.length === 1 ? ' · tek görünüm' : ' · çoklu görünüm'));
        }
        if (view.alignment?.rows) for (const [row, metric] of Object.entries(view.alignment.rows) as [string, any][]) add(r, { criterion: 'alignment', label: 'Görünür dizilim', region: pose + ':' + row, regionLabel: poseLabel + ' · ' + (row === 'upper' ? 'Üst sıra' : 'Alt sıra'), unit: '°', method: view.alignment.methodVersion || r.methodVersion || 'Eski yöntem', source }, [r.sourceType || { unknown: r.id }, r.measurements.length, view.alignment.methodVersion || r.methodVersion, view.alignment.unit || 'degrees'], view.alignment.quality === 'valid' && metric.quality !== 'insufficient' ? number(metric.value) : null, String(index) + row, source);
      }
    } else if (module === 'hearing') {
      const conditions = [r.methodVersion, r.deviceSession || { unknown: r.id }, r.calibrationProfile || null, r.captureConditions || null];
      if (Array.isArray(r.thresholds)) {
        for (const [index, t] of r.thresholds.entries()) if (!t.repeat) add(r, { criterion: 'tone', label: 'Saf ses dijital eşiği', region: t.ear + ':' + t.frequency, regionLabel: (REGION_LABELS[t.ear] || t.ear) + ' · ' + t.frequency + ' Hz', unit: 'dBFS peak', method: r.methodVersion || 'Eski saf ses yöntemi', source: '' }, [...conditions, t.unit || r.unit], r.quality === 'unreliable' || t.status !== 'threshold' ? null : number(t.value), String(index), t.status === 'threshold' ? 'Tekrar ölçümü ayrı kayıtta tutulur.' : 'Bu frekansta eşik bulunamadı.');
      } else {
        const compatible = [...conditions, r.bankVersion || { unknown: r.id }, r.bankManifest || null];
        for (const [criterion, label, value, unit] of [['snr', 'Sayı/gürültü eşiği', number(r.value), 'dB SNR'], ['digit', 'Doğru sayı oranı', number(r.digitAccuracy), '%'], ['triplet', 'Tam üçlü doğruluğu', number(r.tripletAccuracy), '%']] as const) add(r, { criterion, label, region: 'binaural', regionLabel: 'İki kulak', unit, method: r.methodVersion || 'Eski sayı/gürültü yöntemi', source: '' }, compatible, value === null || ['invalid', 'unreliable', 'insufficient'].includes(r.quality) ? null : unit === '%' ? value * 100 : value, criterion, typeof r.validTrials === 'number' ? `${r.validTrials} geçerli deneme` : 'Deneme sayısı kaydedilmemiş');
      }
    }
  }
  // A missing measurement/date within a session is a gap, not an invented zero.
  // Incompatible sessions likewise never form a bridge between measurements.
  for (const series of map.values()) {
    const present = new Set(series.points.map(p => p.recordId));
    for (const r of rows) if (!present.has(r.id)) series.points.push({ id: r.id + ':missing', recordId: r.id, time: historyTime(r)!, value: null, detail: 'Bu kayıtta seçilen koşulla karşılaştırılabilir ölçüm yok.' });
    series.points.sort((a, b) => a.time - b.time || a.id.localeCompare(b.id));
  }
  return [...map.values()];
}

export function themeDistribution(records: HealthRecord[]) {
  const counts = new Map<string, number>();
  for (const r of usableHistory('mental', records)) for (const theme of new Set<string>((Array.isArray(r.themes) ? r.themes : []).filter((v: unknown): v is string => typeof v === 'string').map((v: string) => v.trim()).filter(Boolean))) counts.set(theme, (counts.get(theme) || 0) + 1);
  const total = [...counts.values()].reduce((a, b) => a + b, 0);
  const rows = [...counts].map(([label, count]) => ({ label, count, percent: total ? Math.floor(count / total * 100) : 0, remainder: total ? count / total * 100 % 1 : 0 }));
  const sorted = [...rows].sort((a, b) => b.remainder - a.remainder || a.label.localeCompare(b.label));
  for (let i = 0, remaining = total ? 100 - rows.reduce((a, b) => a + b.percent, 0) : 0; i < remaining; i++) sorted[i].percent++;
  return { total, rows };
}
export function sessionCountSeries(records: HealthRecord[]): HistorySeries {
  const days = new Map<string, HealthRecord[]>();
  for (const r of usableHistory('mental', records)) { const time = historyTime(r); if (time === null) continue; const key = new Date(time).toLocaleDateString(getLocale()); days.set(key, [...(days.get(key) || []), r]); }
  return { id: 'mental-count', module: 'mental', criterion: 'sessions', label: 'Kayıtlı görüşme sayısı', region: '', regionLabel: '', unit: 'görüşme', method: '', source: '', points: [...days.values()].map(rows => ({ id: rows.map(r => r.id).join('|'), recordId: rows[0].id, time: Math.min(...rows.map(r => historyTime(r)!)), value: rows.length, detail: rows.map(r => new Date(historyTime(r)!).toLocaleString(getLocale())).join(' · ') })).sort((a, b) => a.time - b.time) };
}
export function emptyHistoryRecords(): HistoryRecords { const records = { ...EMPTY_HISTORY }; for (const id of HEALTH_MODULE_IDS) records[id] = []; return records; }

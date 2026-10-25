'use client';
import {useTranslations} from '../../i18n/LanguageProvider';
import { AccessibleDialog } from '../AccessibleDialog';
import { PAINT_REGION_NAMES } from '../../utils/skinTypePaint';

/** Reasons the regional skin map could not reach a confident result for one region (codes from regional_skin_v3). */
const REASONS: Record<string, string[]> = {
  LOW_CONFIDENCE: ['Bu bölgede ışık, gölge veya parlama kesin bir sonuç için yeterince dengeli değildi.', 'Yüzün kameraya göre açısı bölgenin bir kısmını gizlemiş olabilir.'],
  BEARD_OR_LINES_COVER_REGION: ['Sakal veya kırışıklık çizgileri bölgenin büyük kısmını kaplıyor; değerlendirilebilecek açık cilt alanı yetersiz kaldı.'],
  INSUFFICIENT_VISIBLE_AREA: ['Bölge kadrajda yeterince görünmüyordu (açı, saç veya kadraj dışında kalma).'],
  NOT_VISIBLE_IN_THIS_POSE: ['Bu bölge bu pozda görünmüyor; değerlendirme diğer pozdan yapılır.'],
};

export function SkinInconclusiveDialog({ regionId, reason, onClose }: { regionId: string; reason?: string | null; onClose: () => void }) {
  const {text:i18nText,node:i18nNode}=useTranslations();
  const name = PAINT_REGION_NAMES[regionId as keyof typeof PAINT_REGION_NAMES] || regionId;
  const reasons = REASONS[reason || ''] || REASONS.LOW_CONFIDENCE;
  const title = `${name}: Kesinleştirilemedi`;
  return (
    <AccessibleDialog title={i18nText(title)} onClose={onClose} className="w-full max-w-lg rounded-2xl border border-white/20 bg-cockpit-surface p-5 space-y-4">
      <div className="flex items-start justify-between gap-3" data-skin-inconclusive-dialog={regionId} data-reason={reason || 'LOW_CONFIDENCE'}>
        <h2 className="text-lg font-bold">{i18nNode(title)}</h2>
        <button type="button" aria-label={i18nText("Bilgi penceresini kapat")} onClick={onClose} className="min-h-11 min-w-11 rounded-xl border border-white/20">✕</button>
      </div>
      <p className="text-sm text-slate-300">{i18nText("Bu taramada bu bölge için kesin bir sonuca varılamadı. Olası nedenler:")}</p>
      <ul className="list-disc pl-5 space-y-1.5 text-sm text-slate-300">
        {reasons.map(r => <li key={r}>{i18nNode(r)}</li>)}
      </ul>
      <p className="text-sm text-togg-turquoise">{i18nText("Daha net bir sonuç için yeni bir taramayı aydınlık ve gölgesiz bir ortamda, yüzünüz kameraya dönük şekilde yapabilirsiniz.")}</p>
    </AccessibleDialog>
  );
}

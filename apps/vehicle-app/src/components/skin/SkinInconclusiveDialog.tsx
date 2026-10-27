'use client';
import {useTranslations} from '../../i18n/LanguageProvider';
import { AccessibleDialog } from '../AccessibleDialog';
import { PAINT_REGION_NAMES } from '../../utils/skinTypePaint';

/** Each measurable cause (regional_skin_v3.capture_causes) has its reason and, when the user can act on it, its advice.
 * Only the causes detected for this region are listed, and only their advice is shown (product wording). */
const CAUSES: Record<string, { reason: string; advice?: string }> = {
  LIGHTING: {
    reason: 'Işık, gölge veya parlaklık yeterince dengeli olmamış olabilir.',
    advice: 'Eşit şekilde aydınlatıldığından ve belirgin gölge veya parlaklık farkları oluşmadığından',
  },
  ANGLE: {
    reason: 'Kamera açısı bölgenin tamamının görüntülenmesini engellemiş olabilir.',
    advice: 'Kameraya dönük ve doğru açıda konumlandırıldığından',
  },
  COVER: {
    reason: 'Sakal veya kırışıklık çizgileri bölgenin büyük kısmını kaplamış olabilir.',
  },
};
const ORDER = ['LIGHTING', 'ANGLE', 'COVER'];

export function SkinInconclusiveDialog({ regionId, causes, onClose }: { regionId: string; causes?: string[] | null; onClose: () => void }) {
  const {text:i18nText,node:i18nNode,language}=useTranslations();
  const name = PAINT_REGION_NAMES[regionId as keyof typeof PAINT_REGION_NAMES] || regionId;
  const found = ORDER.filter(c => (causes && causes.length ? causes : ['LIGHTING', 'ANGLE']).includes(c));
  const advice = found.map(c => CAUSES[c].advice).filter(Boolean) as string[];
  const title = `${name}: Kesinleştirilemedi`;
  return (
    <AccessibleDialog title={i18nText(title)} onClose={onClose} className="w-full max-w-lg rounded-2xl border border-white/20 bg-cockpit-surface p-5 space-y-4">
      <div className="flex items-start justify-between gap-3" data-skin-inconclusive-dialog={regionId} data-causes={found.join(',')}>
        <h2 className="text-lg font-bold">{i18nNode(title)}</h2>
        <button type="button" aria-label={i18nText("Bilgi penceresini kapat")} onClick={onClose} className="min-h-11 min-w-11 rounded-xl border border-white/20">✕</button>
      </div>
      <p className="text-sm text-slate-300">{i18nText("Taramada aşağıdaki olası neden(ler)den dolayı bölgesel sonuca varılamadı:")}</p>
      <ul className="list-disc pl-5 space-y-1.5 text-sm text-slate-300" data-skin-inconclusive-reasons>
        {found.map(c => <li key={c} data-cause={c}>{i18nNode(CAUSES[c].reason)}</li>)}
      </ul>
      {advice.length > 0 && (
        <div className="space-y-1.5 text-sm text-togg-turquoise" data-skin-inconclusive-advice>
          <p>{i18nText("Taramayı tekrarlamadan önce yüzünüzün:")}</p>
          <ul className="list-disc pl-5 space-y-1.5">
            {/* punctuation follows the language: TR list ends before 'emin olun.', EN/DE list ends with a full stop */}
            {advice.map((a, i) => <li key={a}>{i18nText(a)}{i < advice.length - 1 ? ',' : language === 'tr' ? '' : '.'}</li>)}
          </ul>
          {language === 'tr' && <p>{i18nText("emin olun.")}</p>}
        </div>
      )}
    </AccessibleDialog>
  );
}

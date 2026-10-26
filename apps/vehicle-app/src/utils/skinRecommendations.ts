/** Ingredient-based suggestions per finding, by visibility score band (no brand names). Source of truth: the
 * "Cilt Bulguları: Belirginliğe Göre Öneriler" doc. Generated from it; keep both in sync. Score findings use five
 * 20-point bands (acne marks and unclassified spots: three), acne and moles use the count range, cold sores one level. */
import type { SkinFinding, SkinFindingId } from './skinFindings';
export type RecBand = { range: string; ingredients: string[]; morning?: string; evening?: string; usage?: string; habit: string };
export const REC_NOTES: Partial<Record<SkinFindingId, string>> = {
  hoodedEyelids: "Kozmetik ürünlerin bu bulgu üzerindeki etkisi sınırlıdır; öneriler göz çevresi derisini desteklemeye yöneliktir.",
  downturnedCorners: "Bu görünüm çoğunlukla yapısaldır ve bilgi amaçlı gösterilir.",
  mole: "Benler için kozmetik içerik önerilmez; öneriler güneşten korunma ve düzenli kontrol üzerinedir.",
};
const R: Record<SkinFindingId, { upTo?: number[]; bands: RecBand[] }> = {
  eyeBags: { upTo: [20, 40, 60, 80, 100], bands: [
    {"range": "%0–20", "ingredients": ["Hyalüronik asit"], "morning": "Hafif, jel kıvamlı göz nemlendiricisi", "evening": "Aynı nemlendirici", "habit": "Akşamları daha az tuz tüketin."},
    {"range": "%21–40", "ingredients": ["Kafein", "Hyalüronik asit"], "morning": "Buzdolabında soğutulmuş kafeinli göz serumu", "evening": "Hyalüronik asitli göz kremi", "habit": "Uyku saatlerinizi düzenli tutun."},
    {"range": "%41–60", "ingredients": ["Kafein", "Peptitler", "Niasinamid"], "morning": "Kafeinli göz serumu", "evening": "Peptitli göz kremi", "habit": "Başınız hafif yüksekte uyuyun."},
    {"range": "%61–80", "ingredients": ["Kafein", "Peptitler", "Düşük oranlı retinol"], "morning": "Kafeinli göz serumu", "evening": "Haftada 2–3 gece göz çevresine uygun retinol, diğer geceler peptitli krem", "habit": "Alerji mevsiminde gözlerinizi ovmaktan kaçının."},
    {"range": "%81–100", "ingredients": ["Peptitler", "Göz çevresine uygun retinol"], "morning": "Kafeinli göz serumu", "evening": "Retinol ve peptit içeren göz kremi", "habit": "Kalıcı torbalarda kozmetik etkisi sınırlıdır; dermatolog veya plastik cerrah görüşü alın."},
  ] },
  darkCircles: { upTo: [20, 40, 60, 80, 100], bands: [
    {"range": "%0–20", "ingredients": ["Kafein"], "morning": "Kafeinli göz serumu", "evening": "Hafif göz nemlendiricisi", "habit": "Gün içinde yeterli su için."},
    {"range": "%21–40", "ingredients": ["Kafein", "C vitamini"], "morning": "C vitaminli göz serumu", "evening": "Kafeinli göz kremi", "habit": "Ekran başında düzenli mola verin."},
    {"range": "%41–60", "ingredients": ["C vitamini", "Niasinamid"], "morning": "C vitaminli göz serumu", "evening": "Niasinamidli göz kremi", "habit": "Güneş gözlüğü ve göz çevresine uygun güneş koruyucu kullanın."},
    {"range": "%61–80", "ingredients": ["Niasinamid", "K vitamini", "Peptitler"], "morning": "C vitamini ve güneş koruyucu", "evening": "K vitamini ve peptit içeren göz kremi", "habit": "Gözlerinizi ovmayın; makyajı nazikçe temizleyin."},
    {"range": "%81–100", "ingredients": ["Göz çevresine uygun düşük oranlı retinol", "C vitamini"], "morning": "C vitamini ve güneş koruyucu", "evening": "Haftada 2–3 gece retinollü göz kremi", "habit": "Alerji veya kansızlık morluğu artırabilir; sürerse doktora danışın."},
  ] },
  hoodedEyelids: { upTo: [20, 40, 60, 80, 100], bands: [
    {"range": "%0–20", "ingredients": ["Hyalüronik asit"], "morning": "Göz nemlendiricisi", "evening": "Göz nemlendiricisi", "habit": "Bilgi amaçlı izleyin."},
    {"range": "%21–40", "ingredients": ["Peptitler", "Hyalüronik asit"], "morning": "Peptitli göz kremi", "evening": "Peptitli göz kremi", "habit": "Göz çevresini güneşten koruyun."},
    {"range": "%41–60", "ingredients": ["Peptitler", "Seramid"], "morning": "Peptitli göz kremi", "evening": "Seramid içeren göz kremi", "habit": "Göz makyajını ovmadan temizleyin."},
    {"range": "%61–80", "ingredients": ["Peptitler", "Göz çevresine uygun düşük oranlı retinol"], "morning": "Peptitli göz kremi", "evening": "Haftada 2–3 gece retinollü göz kremi", "habit": "Görüş alanınızda daralma fark ederseniz göz doktoruna başvurun."},
    {"range": "%81–100", "ingredients": [], "habit": "Göz doktoru veya plastik cerrah değerlendirmesi önerilir."},
  ] },
  downturnedCorners: { upTo: [20, 40, 60, 80, 100], bands: [
    {"range": "%0–20", "ingredients": [], "habit": "Bilgi amaçlı izleyin."},
    {"range": "%21–40", "ingredients": ["Hyalüronik asit"], "morning": "Göz nemlendiricisi", "evening": "Göz nemlendiricisi", "habit": "Güneş gözlüğü kullanın."},
    {"range": "%41–60", "ingredients": ["Peptitler", "Hyalüronik asit"], "morning": "Peptitli göz kremi", "evening": "Peptitli göz kremi", "habit": "Güneş koruması göz çevresi derisinin esnekliğini korur."},
    {"range": "%61–80", "ingredients": ["Peptitler", "Göz çevresine uygun düşük oranlı retinol"], "morning": "Peptitli göz kremi", "evening": "Haftada 2–3 gece retinollü göz kremi", "habit": "Uyku düzeninizi koruyun."},
    {"range": "%81–100", "ingredients": ["Peptitler", "Retinol"], "morning": "Peptitli göz kremi", "evening": "Retinollü göz kremi", "habit": "Estetik seçenekler için dermatolog veya plastik cerrahla görüşün."},
  ] },
  crowsFeet: { upTo: [20, 40, 60, 80, 100], bands: [
    {"range": "%0–20", "ingredients": ["Hyalüronik asit"], "morning": "Göz nemlendiricisi", "evening": "Göz nemlendiricisi", "habit": "Güneş gözlüğü gözünüzü kısmanızı azaltır."},
    {"range": "%21–40", "ingredients": ["Hyalüronik asit", "Peptitler"], "morning": "Hyalüronik asitli göz kremi", "evening": "Peptitli göz kremi", "habit": "Ekran parlaklığını ortama göre ayarlayın."},
    {"range": "%41–60", "ingredients": ["Peptitler", "Niasinamid"], "morning": "Antioksidanlı göz kremi ve güneş koruyucu", "evening": "Peptitli göz kremi", "habit": "Göz çevresine güneş koruyucuyu da sürün."},
    {"range": "%61–80", "ingredients": ["Göz çevresine uygun düşük oranlı retinol (%0,1–0,25)", "Peptitler"], "morning": "Peptitli göz kremi ve güneş koruyucu", "evening": "Haftada 2–3 gece retinollü göz kremi", "habit": "Ürünü kemik çizgisinin üzerine uygulayın, gözün içine kaçırmayın."},
    {"range": "%81–100", "ingredients": ["Retinol veya retinal içeren göz kremi"], "morning": "Peptitli göz kremi ve güneş koruyucu", "evening": "Cilt alıştıkça her gece retinoid", "habit": "Botulinum toksini gibi işlemler için dermatologla görüşün."},
  ] },
  foreheadLines: { upTo: [20, 40, 60, 80, 100], bands: [
    {"range": "%0–20", "ingredients": ["Hyalüronik asit"], "morning": "Nemlendirici ve güneş koruyucu", "evening": "Nemlendirici", "habit": "Günlük güneş koruyucu çizgilerin derinleşmesini yavaşlatır."},
    {"range": "%21–40", "ingredients": ["Hyalüronik asit", "C vitamini"], "morning": "C vitamini serumu", "evening": "Hyalüronik asitli nemlendirici", "habit": "Kaşlarınızı kaldırma alışkanlığınızı fark etmeye çalışın."},
    {"range": "%41–60", "ingredients": ["Peptitler", "Retinol (%0,25)"], "morning": "C vitamini serumu", "evening": "Haftada 2–3 gece retinol", "habit": "Retinol kullanırken güneş korumasını aksatmayın."},
    {"range": "%61–80", "ingredients": ["Retinol (%0,5)", "Peptitler"], "morning": "Peptitli serum ve güneş koruyucu", "evening": "Gün aşırı retinol", "habit": "Cilt kurursa retinolden önce nemlendirici sürün."},
    {"range": "%81–100", "ingredients": ["Retinal veya retinol (%1)"], "morning": "Peptitli serum ve güneş koruyucu", "evening": "Cilt alıştıkça her gece retinoid", "habit": "Botulinum toksini veya dolgu gibi işlemler için dermatologla görüşün."},
  ] },
  acne: { bands: [
    {"range": "1–2", "ingredients": ["Salisilik asit (%0,5–2)"], "morning": "Salisilik asitli temizleyici", "evening": "Sivilcenin üzerine noktasal salisilik asit", "habit": "Sivilceleri sıkmayın."},
    {"range": "3–5", "ingredients": ["Salisilik asit", "Niasinamid (%4–5)"], "morning": "Salisilik asitli temizleyici", "evening": "Niasinamid serumu", "habit": "Gözenek tıkamayan (non-komedojenik) nemlendirici kullanın."},
    {"range": "6–10", "ingredients": ["Benzoil peroksit (%2,5–5)", "Azelaik asit (%10)"], "morning": "Azelaik asit", "evening": "Sivilcelerin üzerine benzoil peroksit", "habit": "Yastık kılıfınızı haftada iki kez değiştirin; benzoil peroksit kumaşları ağartabilir."},
    {"range": "11–20", "ingredients": ["Adapalen (%0,1)", "Benzoil peroksit"], "morning": "Benzoil peroksitli temizleyici", "evening": "Haftada 3 geceden başlayarak adapalen", "habit": "Telefon ekranını ve sık dokunduğunuz yüzeyleri temizleyin."},
    {"range": "20+", "ingredients": ["Adapalen ve benzoil peroksit"], "morning": "Benzoil peroksitli temizleyici", "evening": "Adapalen", "habit": "Derin, ağrılı veya iz bırakan sivilcelerde dermatoloğa danışın. Adapalen bazı ülkelerde reçetelidir."},
  ] },
  acneMarks: { upTo: [40, 70, 100], bands: [
    {"range": "%0–40", "ingredients": ["Niasinamid", "C vitamini (%10–15)"], "morning": "C vitamini serumu ve güneş koruyucu", "evening": "Niasinamid serumu", "habit": "Günlük güneş koruyucu izlerin koyulaşmasını önler."},
    {"range": "%41–70", "ingredients": ["Azelaik asit (%10–15)", "Alfa arbutin", "Traneksamik asit"], "morning": "C vitamini serumu ve güneş koruyucu", "evening": "Haftada 3–4 gece azelaik asit veya traneksamik asit", "habit": "Yeni iz oluşmaması için sivilceleri sıkmayın."},
    {"range": "%71–100", "ingredients": ["Retinol (%0,3–0,5)", "Glikolik asit (%8–10)"], "morning": "C vitamini serumu ve güneş koruyucu", "evening": "Retinol ve glikolik asit dönüşümlü gecelerde; aynı gece kullanmayın", "habit": "Çukur izlerde lazer veya mikroiğneleme gibi işlemler için dermatoloğa danışın."},
  ] },
  melasma: { upTo: [20, 40, 60, 80, 100], bands: [
    {"range": "%0–20", "ingredients": ["Niasinamid"], "morning": "Geniş spektrumlu SPF 50", "evening": "Niasinamid serumu", "habit": "Öğle saatlerinde doğrudan güneşten kaçının."},
    {"range": "%21–40", "ingredients": ["Niasinamid", "C vitamini"], "morning": "C vitamini serumu ve SPF 50", "evening": "Niasinamid serumu", "habit": "Demir oksit içeren renkli güneş koruyucu görünür ışığa karşı da korur."},
    {"range": "%41–60", "ingredients": ["Azelaik asit (%15)", "C vitamini"], "morning": "C vitamini serumu ve renkli SPF 50", "evening": "Azelaik asit", "habit": "Dışarıdayken güneş koruyucuyu 2 saatte bir yenileyin."},
    {"range": "%61–80", "ingredients": ["Traneksamik asit", "Alfa arbutin", "Azelaik asit"], "morning": "C vitamini serumu ve renkli SPF 50", "evening": "Traneksamik asit veya alfa arbutin", "habit": "Şapka kullanın; sıcak ortam ve sauna lekeyi koyulaştırabilir."},
    {"range": "%81–100", "ingredients": ["Traneksamik asit", "Azelaik asit", "Retinol"], "morning": "Renkli SPF 50", "evening": "Dönüşümlü gecelerde retinol", "habit": "Dermatoloğa danışın. Hamilelik ve hormon tedavisi melazmayı etkileyebilir; uzmana belirtin."},
  ] },
  mole: { bands: [
    {"range": "1–3", "ingredients": [], "habit": "SPF 50 kullanın. Ayda bir aynada ABCDE kuralıyla kontrol edin: asimetri, sınır düzensizliği, renk farklılığı, 6 mm'den büyük çap, değişim."},
    {"range": "4–10", "ingredients": [], "habit": "SPF 50 kullanın. Benlerinizi ayda bir kontrol edin ve fotoğraflarını düzenli kaydedin."},
    {"range": "10+", "ingredients": [], "habit": "Yılda bir dermatolog kontrolü yaptırın. Değişen her ben için beklemeden uzmana başvurun."},
  ] },
  spots: { upTo: [40, 70, 100], bands: [
    {"range": "%0–40", "ingredients": ["C vitamini", "Niasinamid"], "morning": "C vitamini serumu ve SPF 30 veya üzeri", "evening": "Niasinamid serumu", "habit": "Her gün güneş koruyucu kullanın."},
    {"range": "%41–70", "ingredients": ["Azelaik asit", "Alfa arbutin"], "morning": "C vitamini serumu ve SPF 50", "evening": "Azelaik asit", "habit": "Lekelerde artış olursa uzmana danışın."},
    {"range": "%71–100", "ingredients": [], "habit": "Lekenin türünün belirlenmesi için dermatoloğa danışın."},
  ] },
  redness: { upTo: [20, 40, 60, 80, 100], bands: [
    {"range": "%0–20", "ingredients": ["Pantenol"], "morning": "Pantenollü nemlendirici", "evening": "Aynı nemlendirici", "habit": "Yüzünüzü ılık suyla yıkayın."},
    {"range": "%21–40", "ingredients": ["Seramid", "Pantenol"], "morning": "Seramidli nemlendirici", "evening": "Pantenollü bakım kremi", "habit": "Alkollü tonik ve tanecikli peelinglerden kaçının."},
    {"range": "%41–60", "ingredients": ["Centella asiatica özü (cica)", "Seramid"], "morning": "Cica içeren nemlendirici", "evening": "Seramidli bakım kremi", "habit": "Yeni ürünleri tek tek ve yama testiyle deneyin."},
    {"range": "%61–80", "ingredients": ["Azelaik asit (%10)", "Düşük oranlı niasinamid (%2–4)"], "morning": "Çinko oksitli mineral güneş koruyucu", "evening": "Azelaik asit", "habit": "Tetikleyicileri not edin: sıcak içecek, baharat, alkol, güneş."},
    {"range": "%81–100", "ingredients": ["Seramid", "Pantenol"], "morning": "Mineral güneş koruyucu", "evening": "Seramidli bakım kremi", "habit": "Kızarıklık sürüyorsa dermatoloğa danışın."},
  ] },
  rosacea: { upTo: [20, 40, 60, 80, 100], bands: [
    {"range": "%0–20", "ingredients": ["Seramid", "Cica"], "morning": "Mineral güneş koruyucu", "evening": "Seramidli nemlendirici", "habit": "Tetikleyicileri not edin: sıcak içecek, baharat, alkol, güneş."},
    {"range": "%21–40", "ingredients": ["Azelaik asit (%10)", "Seramid"], "morning": "Mineral güneş koruyucu", "evening": "Azelaik asit", "habit": "Yüzünüzü ovmadan, havluyla bastırarak kurulayın."},
    {"range": "%41–60", "ingredients": ["Azelaik asit (%15)", "Cica"], "morning": "Mineral güneş koruyucu", "evening": "Azelaik asit", "habit": "Kesin değerlendirme için dermatoloğa danışın."},
    {"range": "%61–80", "ingredients": ["Seramid", "Pantenol"], "morning": "Mineral güneş koruyucu", "evening": "Seramidli bakım kremi", "habit": "Dermatoloğa danışın; reçeteli tedaviler uzman kararıyla kullanılır."},
    {"range": "%81–100", "ingredients": [], "habit": "Dermatoloğa başvurun."},
  ] },
  eczema: { bands: [
    {"range": "", "ingredients": ["Seramid", "Kolloidal yulaf", "Pantenol"], "morning": "Parfümsüz, seramidli nemlendirici", "evening": "Kolloidal yulaf içeren yatıştırıcı krem", "habit": "Kaşımayın; yüzünüzü ılık suyla ve sabunsuz bir temizleyiciyle yıkayın. Kesin değerlendirme için dermatoloğa danışın."},
  ] },
  flaking: { bands: [
    {"range": "", "ingredients": ["Seramid", "Gliserin", "Skualan", "Üre (%5)"], "morning": "Seramidli nemlendirici ve güneş koruyucu", "evening": "Üre veya gliserin içeren zengin nemlendirici", "habit": "Pulları ovarak veya peelingle gidermeye çalışmayın; kapalı ortamda havayı nemli tutun."},
  ] },
  coldSore: { bands: [
    {"range": "", "ingredients": ["Asiklovir veya dokosanol içeren uçuk kremi", "Çinko oksit"], "usage": "İlk karıncalanmada başlayın, prospektüsteki sıklıkla sürün", "habit": "Bölgeye dokunmayın; havlu, bardak ve dudak ürünü paylaşmayın. SPF içeren dudak koruyucu güneşin tetiklediği uçukları azaltır. Yaygın, ağrılı veya yılda birkaç kez tekrarlayan uçuklarda doktora başvurun."},
  ] },
};
/** Count ranges reported by the server → band index (finer acne ranges first, legacy three-range values mapped). */
const COUNT_BAND: Record<string, number> = { '1-2': 0, '3-5': 1, '6-10': 2, '11-20': 3, '20+': 4, '1-3': 0, '4-10': 2, '10+': 4 };
const MOLE_BAND: Record<string, number> = { '1-3': 0, '4-10': 1, '10+': 2 };
/** The 0–100 value a finding is shown and banded by: the validated visibility score, else the area share. */
export const findingScore = (f: SkinFinding): number | undefined => f.severity ?? f.areaPct;
/** Band of the finding's measured score or count. null when the band depends on a value this scan did not measure:
 * a missing score or count is never read as the lowest band. Single-band findings do not depend on a value. */
export function recommendationBand(f: SkinFinding): { band: RecBand; index: number; total: number } | null {
  const r = R[f.id], total = r.bands.length;
  if (total === 1) return { band: r.bands[0], index: 0, total };
  let index: number | undefined;
  if (f.id === 'mole') index = f.count !== undefined ? (f.count <= 3 ? 0 : f.count <= 10 ? 1 : 2) : MOLE_BAND[f.countRange || ''];
  else if (f.id === 'acne') index = f.count !== undefined ? (f.count <= 2 ? 0 : f.count <= 5 ? 1 : f.count <= 10 ? 2 : f.count <= 20 ? 3 : 4) : COUNT_BAND[f.countRange || ''];
  else if (r.upTo) { const v = findingScore(f); const i = v === undefined ? -1 : r.upTo.findIndex(u => v <= u); index = i < 0 ? undefined : i; }
  return index === undefined ? null : { band: r.bands[index], index, total };
}

import type { SkinIndicator } from './skinIndicators';
import type { SkinTypeId } from './skinOverview';

export type SkinRoutineSection = { id: string; title: string; items: string[] };
/** Suggestions follow measured findings, never fixture metrics or missing rows.
 * This is cosmetic product selection, not a disease treatment or severity scale.
 */
export function buildSkinRoutine(rows: SkinIndicator[], skinType?: { value: SkinTypeId | null; quality: string }): SkinRoutineSection[] {
  const has = (...ids: string[]) => rows.some(row => ids.includes(row.id) &&
    (row.appearance?.quality || row.measurement?.quality) === 'valid' &&
    typeof row.score === 'number' && Number.isFinite(row.score) && row.score > 0);
  const type = skinType?.quality === 'valid' ? skinType.value : null;
  const dry = has('dry') || type === 'dry';
  const oily = has('oil') || type === 'oily';
  const combination = type === 'combination';
  const reactive = has('redness', 'eczema', 'rosacea', 'psoriasis');
  const spots = has('acne', 'whiteheads', 'blackheads', 'pores');
  const measured = rows.some(row => (row.appearance?.quality || row.measurement?.quality) === 'valid' &&
    typeof row.score === 'number' && Number.isFinite(row.score));
  if (!measured && !type) return [];

  const cleanse = [reactive || dry
    ? 'Kuruluk veya kızarıklık görünümü için parfümsüz, sabun içermeyen nazik bir temizleyici tercih edebilirsiniz.'
    : 'Yüzünüzü nazik bir temizleyiciyle temizleyebilirsiniz; ovalama ve sert peelingden kaçının.'];
  const care: string[] = [];
  if (reactive) care.push('Kızarıklık veya tahriş görünümünde bakımınızı sade tutabilirsiniz; asitli peeling ve güçlü aktifleri aynı rutine eklemeyin.');
  else if (dry) care.push('Kuruluk görünümü için gliserin veya hyalüronik asit içeren nem destekleyici bir serum tercih edebilirsiniz.');
  else if (spots) care.push('Sivilce, siyah veya beyaz nokta görünümü için salisilik asit içeren tek bir bakım ürünü tercih edebilirsiniz; yanma veya tahriş olursa kullanmayı bırakın.');
  else care.push('Mevcut sonuçlar ek bir aktif serum gerektirmiyor; sade bir bakım rutini tercih edebilirsiniz.');
  if (combination) care.push('Karma ciltte T bölgesiyle yanakları ayrı değerlendirebilirsiniz; yağlı bölgeye seçtiğiniz ürünü kuru bölgelere yaymayın.');
  const moisturize = [dry || reactive
    ? 'Kuruluk görünümü için seramid, gliserin veya hyalüronik asit içeren parfümsüz bir nemlendirici tercih edebilirsiniz.'
    : 'Hafif dokulu, komedojenik olmayan bir nemlendirici tercih edebilirsiniz.'];
  if (combination) moisturize.push('T bölgesinde hafif bir doku, kuru yanaklarda daha yoğun bir nemlendirici tercih edebilirsiniz.');
  const sunscreen = ['Her gün geniş spektrumlu, SPF 30 veya üzeri bir güneş koruyucu tercih edebilirsiniz.'];
  if (oily || combination || spots) sunscreen.push('Yağlı veya sivilceye eğilimli bölgeler için komedojenik olmayan, hafif dokulu bir formül tercih edebilirsiniz.');
  if (reactive) sunscreen.push('Kızarıklık ve tahriş eğiliminde parfümsüz, çinko oksit veya titanyum dioksit içeren bir formül tercih edebilirsiniz.');
  return [
    { id: 'cleanse', title: 'Temizleme', items: cleanse },
    { id: 'care', title: 'Bakım', items: care },
    { id: 'moisturize', title: 'Nemlendirme', items: moisturize },
    { id: 'sunscreen', title: 'Güneş kremi', items: sunscreen },
  ];
}

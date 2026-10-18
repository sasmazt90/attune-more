import { HEALTH_MODULES } from './healthModules';
import { readHealthRecords,recordDate } from './healthRecords';
import { VisionSummaryData, SkinSummaryData, MentalSummaryData } from './healthSelectors';

export interface ShareSelection { vision: boolean; skin: boolean; mental: boolean; dental?:boolean; hearing?:boolean }
export interface ShareSection { title: string; text: string; dateTr: string }

export function measuredShareSection(category:'dental'|'hearing'):ShareSection|null {
  const records=readHealthRecords(category);
  const time=(r:typeof records[number])=>{const t=Date.parse(r.timestamp||r.date||r.completedAt||'');return Number.isFinite(t)?t:-Infinity;};
  // Current stores prepend; imported legacy stores may have another order.
  // Select by source time without sorting or rewriting the stored records.
  const r=records.reduce<typeof records[number]|undefined>((latest,row)=>!latest||time(row)>time(latest)?row:latest,undefined);if(!r)return null;
  const finite=(value:unknown)=>typeof value==='number'&&Number.isFinite(value);
  const usable=(metric:any)=>metric?.quality==='valid'&&finite(metric.value);
  const hearingValid=!['invalid','unreliable','insufficient'].includes(r.quality);
  const text=category==='dental'?(r.sourceType==='upload'?'Yüklenen tek fotoğraf':'Kamera')+' · '+(r.measurements||[]).map((v:any)=>`${v.pose}: ${!usable(v.caries)?'Çürük adayı değerlendirilemiyor':v.caries.value+' görünür aday'}; birikim ${!usable(v.accumulation)?'değerlendirilemiyor':Math.round(v.accumulation.value)+'% görünür sınır alanı'}`).join('. '):r.thresholds?r.thresholds.map((t:any)=>`${t.ear==='left'?'Sol':'Sağ'} ${t.frequency} Hz: ${!hearingValid||t.status!=='threshold'||!finite(t.value)?'eşik bulunamadı':t.value+' dBFS peak'}`).join('. '):`${finite(r.validTrials)?r.validTrials:'Kaydedilmemiş sayıda'} geçerli üçlü · ${!hearingValid||!finite(r.value)?'kararlı eşik bulunamadı':r.value+' dB SNR'}`;
  return {title:HEALTH_MODULES[category].name,dateTr:recordDate(r),text};
}
export function buildShareSections(selection: ShareSelection, vision: VisionSummaryData, skin: SkinSummaryData, mental: MentalSummaryData,dental?:ShareSection|null,hearing?:ShareSection|null): ShareSection[] {
  const sections: ShareSection[] = [];
  if (selection.vision && vision.hasData) sections.push({ title: HEALTH_MODULES.vision.name, dateTr: vision.dateTr,
    text: `Keskinlik: ${vision.acuitySummary}. Kontrast: ${vision.contrastSummary}.` });
  if (selection.skin && skin.hasData) sections.push({ title: HEALTH_MODULES.skin.name, dateTr: skin.dateTr,
    text: `${skin.regionNameTr}: ${skin.changeLabel}. ${skin.recommendation}.` });
  if (selection.mental && mental.hasData) sections.push({ title: HEALTH_MODULES.mental.name, dateTr: mental.dateTr,
    text: `Kayıtlı temalar: ${mental.primaryTheme}. ${mental.sessionCountLabel}.` });
  if(selection.dental&&dental)sections.push(dental);
  if(selection.hearing&&hearing)sections.push(hearing);
  return sections;
}

// Only selected, human-readable fields enter this disposable print document.
export function printHealthSummary(sections: ShareSection[], demo: boolean): void {
  if (!sections.length) throw new Error('No selected results');
  const frame = document.createElement('iframe');
  frame.title = 'Seçilmiş sağlık özeti yazdırma';
  frame.style.cssText = 'position:fixed;width:1px;height:1px;left:-10000px;border:0';
  document.body.appendChild(frame);
  const target = frame.contentWindow;
  const doc = frame.contentDocument;
  if (!target || !doc) { frame.remove(); throw new Error('Print unavailable'); }
  doc.open(); doc.write('<!doctype html><html lang="tr"><head><meta charset="utf-8"><title>Seçilmiş değerlendirme özeti</title></head><body></body></html>'); doc.close();
  const add = (tag: string, text: string) => { const el = doc.createElement(tag); el.textContent = text; doc.body.appendChild(el); };
  const style = doc.createElement('style');
  style.textContent = 'body{font:14px Arial,sans-serif;color:#111;padding:24px}h1{font-size:22px}h2{font-size:17px}p{white-space:pre-wrap;line-height:1.5}';
  doc.head.appendChild(style);
  add('h1', 'Hekimle paylaşılabilir değerlendirme özeti');
  add('p', demo ? 'Demo rapor — örnek kullanıcı' : 'Yerel kullanıcı — kimlik doğrulanmadı');
  add('p', new Date().toLocaleString('tr-TR'));
  sections.forEach(section => { add('h2', section.title); add('p', section.dateTr); add('p', section.text); });
  add('p', 'Bu cihazdaki değerlendirmeler klinik tanı veya gerçek araç sensörü doğrulaması değildir. Hekime otomatik gönderim yapılmaz.');
  target.addEventListener('afterprint', () => frame.remove(), { once: true });
  target.focus(); target.print();
  // Some browsers omit afterprint on cancellation; do not retain sensitive DOM indefinitely.
  window.setTimeout(() => frame.remove(), 120000);
}

"use client";
import { useEffect, useState } from 'react';
import { defaultReminderDate, readSkinReminder, saveSkinReminder, cancelSkinReminder, downloadReminderCalendar, SkinReminder } from '../../utils/skinReminder';
const localInput = (date: Date) => new Date(date.getTime() - date.getTimezoneOffset() * 60000).toISOString().slice(0,16);
export function SkinReminderForm() {
  const [date, setDate] = useState('');
  const [reminder, setReminder] = useState<SkinReminder | null>(null);
  const [notice, setNotice] = useState('');
  useEffect(() => { try { const item = readSkinReminder(); setReminder(item); setDate(localInput(item ? new Date(item.dueAt) : defaultReminderDate())); } catch { setNotice('Hatırlatma kaydı okunamadı.'); } }, []);
  return <div className="space-y-3 text-xs border border-slate-700 rounded-xl p-4" data-reminder-form>
    <p>Varsayılan: 4 hafta (28 gün). Uygulama içi plan cihazda saklanır. Uygulama kapalıyken bildirim için takvim dosyasını kendi takviminize içe aktarın ve takvim uyarısını etkinleştirin.</p>
    <label className="block">Hatırlatma tarihi ve saati<input aria-label="Hatırlatma tarihi ve saati" type="datetime-local" value={date} onChange={e=>setDate(e.target.value)} className="block bg-slate-950 p-2 rounded" /></label>
    <button className="text-togg-turquoise" onClick={()=>{ try { const item=saveSkinReminder(new Date(date));setReminder(item);setNotice('Uygulama içi plan kaydedildi. İşletim sistemi bildirimi kurulmadı.'); } catch { setNotice('Plan kaydedilemedi. Tarihi ve cihaz depolamasını kontrol edin.'); } }}>Hatırlatmayı kaydet</button>
    {reminder && <div className="flex gap-4"><button onClick={()=>{try{downloadReminderCalendar(reminder);setNotice('Takvim dosyası hazırlandı. İçe aktarım veya takvim bildirimi etkinliği uygulama tarafından doğrulanamaz.');}catch{setNotice('Takvim dosyası oluşturulamadı.');}}}>Takvim dosyasını indir (.ics)</button>
      <button onClick={()=>{try{cancelSkinReminder();setReminder(null);setNotice('Uygulama içi plan iptal edildi. Daha önce takvime aktardıysanız takvim kaydını ayrıca silin.');}catch{setNotice('İptal işlemi doğrulanamadı.');}}}>Hatırlatmayı iptal et</button></div>}
    {notice && <p role="status">{notice}</p>}
  </div>;
}

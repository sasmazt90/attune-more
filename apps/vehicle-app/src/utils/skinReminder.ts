import { STORAGE_KEYS, isDemoMode } from './attuneMode';
export interface SkinReminder { id: string; dueAt: string }
export function defaultReminderDate(now = new Date()): Date {
  const due = new Date(now); due.setDate(due.getDate() + 28); return due;
}
export function readSkinReminder(): SkinReminder | null {
  const raw = localStorage.getItem(STORAGE_KEYS.SKIN_REMINDER);
  if (!raw) return null;
  const item = JSON.parse(raw);
  if (typeof item.id !== 'string' || !/^[a-zA-Z0-9-]+$/.test(item.id) || !Number.isFinite(Date.parse(item.dueAt))) throw new Error('Invalid reminder');
  return { id: item.id, dueAt: item.dueAt };
}
export function saveSkinReminder(due: Date): SkinReminder {
  if (isDemoMode()) throw new Error('Demo mode cannot persist a real reminder');
  if (!Number.isFinite(due.getTime()) || due.getTime() <= Date.now()) throw new Error('Invalid future date');
  const item = { id: readSkinReminder()?.id || crypto.randomUUID(), dueAt: due.toISOString() };
  localStorage.setItem(STORAGE_KEYS.SKIN_REMINDER, JSON.stringify(item));
  if (localStorage.getItem(STORAGE_KEYS.SKIN_REMINDER) !== JSON.stringify(item)) throw new Error('Save failed');
  window.dispatchEvent(new Event('attune-reminder')); return item;
}
export function cancelSkinReminder(): void {
  localStorage.removeItem(STORAGE_KEYS.SKIN_REMINDER);
  if (localStorage.getItem(STORAGE_KEYS.SKIN_REMINDER)) throw new Error('Cancel failed');
  window.dispatchEvent(new Event('attune-reminder'));
}
export function buildReminderCalendar(item: SkinReminder): string {
  if (!/^[a-zA-Z0-9-]+$/.test(item.id) || !Number.isFinite(Date.parse(item.dueAt))) throw new Error('Invalid reminder');
  const stamp = (date: Date) => date.toISOString().replace(/[-:]/g, '').replace(/\.\d{3}Z$/, 'Z');
  return ['BEGIN:VCALENDAR', 'VERSION:2.0', 'PRODID:-//Attune//Local Follow-up//TR', 'BEGIN:VEVENT',
    `UID:${item.id}@attune.local`, `DTSTAMP:${stamp(new Date())}`, `DTSTART:${stamp(new Date(item.dueAt))}`,
    'DURATION:PT15M', 'SUMMARY:Planlanan takip', 'DESCRIPTION:Uygulamadaki planlanan takibi kontrol edin.',
    'BEGIN:VALARM', 'TRIGGER:PT0M', 'ACTION:DISPLAY', 'DESCRIPTION:Planlanan takip', 'END:VALARM',
    'END:VEVENT', 'END:VCALENDAR', ''].join('\r\n');
}
export function downloadReminderCalendar(item: SkinReminder): void {
  const url = URL.createObjectURL(new Blob([buildReminderCalendar(item)], { type: 'text/calendar;charset=utf-8' }));
  const link = document.createElement('a'); link.href = url; link.download = 'planlanan-takip.ics';
  document.body.appendChild(link); link.click(); link.remove(); window.setTimeout(() => URL.revokeObjectURL(url), 1000);
}

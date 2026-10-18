import {deleteDentalPhotosWithRecords,recoverDentalPhotoDeletion,DENTAL_PHOTO_DELETE_PENDING} from './dentalPhotoHistory';
import {serviceAllowed} from './serviceConsent';
import {deleteSkinPhotosWithRecords,recoverSkinPhotoDeletion,SKIN_PHOTO_DELETE_PENDING} from './skinPhotoHistory';
import { HEALTH_MODULES } from './healthModules';
import { STORAGE_KEYS } from './attuneMode';
import { localBackend } from './localBackend';

export type HealthCategory = 'vision' | 'skin' | 'mental' | 'dental' | 'hearing';
export type HealthRecord = { id: string; date?: string; timestamp?: string; dateTr?: string; [key: string]: any };
export const RECORD_LABELS = Object.fromEntries(Object.entries(HEALTH_MODULES).map(([key,module])=>[key,module.name])) as Record<HealthCategory,string>;
export const RECORD_JOURNAL = 'attune_health_transaction_v1';
const KEYS = {
  vision: { history: 'togg_health_vision_history', latest: STORAGE_KEYS.LATEST_VISION },
  skin: { history: STORAGE_KEYS.SKIN_HISTORY, latest: STORAGE_KEYS.LATEST_SKIN },
  dental: { history: 'attune_dental_history_v1', latest: 'attune_dental_latest_v1' },
  hearing: { history: 'attune_hearing_history_v1', latest: 'attune_hearing_latest_v1' },
  mental: { history: STORAGE_KEYS.MENTAL_HISTORY, latest: STORAGE_KEYS.LATEST_MENTAL }
};

export function recordDate(record: HealthRecord): string {
  const value = record.date || record.timestamp;
  return value && Number.isFinite(Date.parse(value)) ? new Date(value).toLocaleString('tr-TR') : record.dateTr || 'Tarih kaydı yok';
}

function recover() {
  const raw = localStorage.getItem(RECORD_JOURNAL);
  if (!raw) return;
  const backup = JSON.parse(raw);
  if (!backup || typeof backup !== 'object' || Array.isArray(backup)) throw new Error('Kayıt işlemi doğrulanamadı.');
  const allowed = new Set<string>(['attune_skin_appearance_reference_v1','attune_skin_appearance_single_reference_v1',...Object.values(KEYS).flatMap(k => [k.history, k.latest]), STORAGE_KEYS.SKIN_BASELINE, STORAGE_KEYS.SKIN_BASELINE_META, STORAGE_KEYS.SKIN_MULTI_BASELINE, STORAGE_KEYS.SKIN_SIGNS_BASELINE, STORAGE_KEYS.SKIN_SINGLE_SIGNS_BASELINE, STORAGE_KEYS.SKIN_REMINDER, STORAGE_KEYS.REFERRAL_CONTEXT]);
  for (const [key, value] of Object.entries(backup)) {
    if (!allowed.has(key) || (value !== null && typeof value !== 'string')) throw new Error('Kayıt işlemi doğrulanamadı.');
    if (value === null) localStorage.removeItem(key); else localStorage.setItem(key, value as string);
  }
  localStorage.removeItem(RECORD_JOURNAL);
}

function commit(changes: Record<string, string | null>, finalize = true) {
  recover();
  const before = Object.fromEntries(Object.keys(changes).map(key => [key, localStorage.getItem(key)]));
  // A persisted undo journal makes interrupted multi-key writes recoverable on reopen.
  localStorage.setItem(RECORD_JOURNAL, JSON.stringify(before));
  try {
    for (const [key, value] of Object.entries(changes)) {
      if (value === null) localStorage.removeItem(key); else localStorage.setItem(key, value);
      if (localStorage.getItem(key) !== value) throw new Error('Kayıt değişikliği doğrulanamadı.');
    }
    if(finalize)localStorage.removeItem(RECORD_JOURNAL);
  } catch (error) {
    try { recover(); } catch { /* Retain journal and report failure; next read retries recovery. */ }
    throw error;
  }
}

function mentalLatest(records: HealthRecord[]) {
  const item = records.at(-1);
  return item ? JSON.stringify({ ...item, dateTr: recordDate(item), primaryTheme: Array.isArray(item.themes) ? item.themes.join(' • ') || 'Günlük paylaşım' : item.primaryTheme || 'Tema kaydı yok', sessionCount: records.length, recommendation: 'Kayıtlı görüşme özeti' }) : null;
}

function readRecordsLocked(category: HealthCategory, writable = true): HealthRecord[] {
  if (writable) recover();
  else if (localStorage.getItem(RECORD_JOURNAL)) throw new Error('Kayıt işlemi sürüyor.');
  const keys = KEYS[category];
  const raw = localStorage.getItem(keys.history);
  const parsed = JSON.parse(raw || '[]');
  if (!Array.isArray(parsed) || parsed.some(r => !r || typeof r !== 'object' || Array.isArray(r))) throw new Error('Eski kayıtlar okunamadı; veriler değiştirilmedi.');
  let changed = false;
  const ids = new Set<string>();
  const records = parsed.map(r => {
    const id = typeof r.id === 'string' && r.id && !ids.has(r.id) ? r.id : crypto.randomUUID();
    ids.add(id); if (id !== r.id) changed = true;
    return { ...r, id } as HealthRecord;
  });
  const latestRaw = localStorage.getItem(keys.latest);
  let latest = latestRaw ? JSON.parse(latestRaw) : null;
  if (latest && (typeof latest !== 'object' || Array.isArray(latest))) throw new Error('Son kayıt okunamadı; veriler değiştirilmedi.');
  if (latest) {
    let match = records.find(r => r.id === latest.id);
    if (!match && !latest.id) {
      const signature = (r: any) => JSON.stringify(Object.fromEntries(Object.entries(r).filter(([k]) => k !== 'id').sort(([a], [b]) => a.localeCompare(b))));
      match = records.find(r => signature(r) === signature(latest));
      if (category === 'mental' && !match) match = records.find(r => r.summaryText === latest.summaryText && Array.isArray(r.themes) && r.themes.join(' • ') === latest.primaryTheme);
    }
    if (!match) {
      latest = { ...latest, id: typeof latest.id === 'string' && latest.id && !ids.has(latest.id) ? latest.id : crypto.randomUUID() };
      records.push(latest); changed = true;
    } else if (latest.id !== match.id) { latest = { ...latest, id: match.id }; changed = true; }
  }
  if (changed) {
    if (!writable) throw new Error('Eski kayıtlar hazırlanıyor.');
    commit({ [keys.history]: JSON.stringify(records), [keys.latest]: latest ? JSON.stringify(latest) : null });
  }
  return records;
}

// Every writer and crash recovery shares the same cross-tab lock. Readers never
// undo another tab's active journal. Unsupported browsers fail closed for writes.
export async function withRecordsLock<T>(operation: () => T | Promise<T>): Promise<T> {
  if (!navigator.locks) return Promise.reject(new Error('Bu tarayıcı güvenli kayıt işlemini desteklemiyor. Güncel Chrome kullanın.'));
  return await navigator.locks.request('attune-health-records', operation) as T;
}
const preparing = new Map<HealthCategory, Promise<HealthRecord[]>>();
export function prepareHealthRecords(category: HealthCategory): Promise<HealthRecord[]> {
  const pending = preparing.get(category);
  if (pending) return pending;
  const operation = withRecordsLock(async () => {
    await recoverSkinPhotoDeletion(recover,()=>localStorage.removeItem(RECORD_JOURNAL));await recoverDentalPhotoDeletion(recover,()=>localStorage.removeItem(RECORD_JOURNAL));
    const before = JSON.stringify([...Object.values(KEYS).flatMap(k => [k.history, k.latest]), RECORD_JOURNAL].map(k => localStorage.getItem(k)));
    const records = readRecordsLocked(category);
    const after = JSON.stringify([...Object.values(KEYS).flatMap(k => [k.history, k.latest]), RECORD_JOURNAL].map(k => localStorage.getItem(k)));
    if (before !== after) window.dispatchEvent(new Event('attune-records'));
    return records;
  }).finally(() => preparing.delete(category));
  preparing.set(category, operation);
  return operation;
}
export function readHealthRecords(category: HealthCategory): HealthRecord[] {
  try { if(localStorage.getItem(SKIN_PHOTO_DELETE_PENDING)||localStorage.getItem(DENTAL_PHOTO_DELETE_PENDING))throw new Error('Kayıt silme işlemi doğrulanıyor.');return readRecordsLocked(category, false); }
  catch (error) {
    void prepareHealthRecords(category).catch(() => {});
    throw error;
  }
}

export async function appendHealthRecord(category: HealthCategory, record: HealthRecord, additionalChanges: Record<string, string | null> = {}, beforeWrite: () => boolean = () => true): Promise<HealthRecord[]> {
  return withRecordsLock(async () => {
  await recoverSkinPhotoDeletion(recover,()=>localStorage.removeItem(RECORD_JOURNAL));await recoverDentalPhotoDeletion(recover,()=>localStorage.removeItem(RECORD_JOURNAL));
  const containsMedia = (value: unknown): boolean => {
    if (typeof value === 'string') return /^data:(image|audio|video)\//i.test(value);
    if (!value || typeof value !== 'object') return false;
    return Object.entries(value).some(([key, item]) => /^(image|video|audio|pixels|frames|base64|canvas)$/i.test(key) || containsMedia(item));
  };
  if (containsMedia(record) || Object.values(additionalChanges).some(v => v && containsMedia(JSON.parse(v)))) throw new Error('Ham medya kalıcı kayda alınamaz.');
  const history = readRecordsLocked(category).filter(r => r.id !== record.id);
  if (!serviceAllowed(category) || !beforeWrite()) throw new Error('Kayıt izni veya işlem durumu değişti; kayıt eklenmedi.');
  // Keep all surviving user records; old ten-record truncation discarded history.
  const records = category === 'mental' ? [...history, record] : [record, ...history];
  commit({ ...additionalChanges, [KEYS[category].history]: JSON.stringify(records), [KEYS[category].latest]: category === 'mental' ? mentalLatest(records) : JSON.stringify(record) });
  window.dispatchEvent(new Event('attune-records'));
  return records;
  });
}

export async function deleteHealthRecord(category: HealthCategory, id: string): Promise<string> {
  const operation = async () => {
    await recoverSkinPhotoDeletion(recover,()=>localStorage.removeItem(RECORD_JOURNAL));await recoverDentalPhotoDeletion(recover,()=>localStorage.removeItem(RECORD_JOURNAL));
    const record = readRecordsLocked(category).find(r => r.id === id);
    if (!record) throw new Error('Kayıt bulunamadı. Listeyi yenileyin.');
    // Current capture/conversation UI stores locally. Linked backend records must
    // be confirmed deleted before local copies can be removed; never guess ownership.
    if (record.backendSessionId) {
      if (category !== 'mental' || !record.backendDeletionToken) throw new Error('Sunucu kaydının silme yetkisi doğrulanamadı. Yerel kayıt korundu.');
      const controller = new AbortController();
      const deadline = setTimeout(() => controller.abort(), 8000);
      try {
        const response = await fetch(localBackend(`/api/mental/sessions/${encodeURIComponent(record.backendSessionId)}`), { method: 'DELETE', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ deletionToken: record.backendDeletionToken }), signal: controller.signal });
        if (!response.ok || (await response.json()).deleted !== true) throw new Error('Backend deletion unconfirmed');
      } catch { throw new Error('Sunucu kaydı silinemedi veya doğrulanamadı. Yerel kayıt korundu; tekrar deneyebilirsiniz.'); }
      finally { clearTimeout(deadline); }
    }
    // Read again after network await so another surviving record is never overwritten.
    const remaining = readRecordsLocked(category).filter(r => r.id !== id);
    const keys = KEYS[category];
    const latest = category === 'mental' ? mentalLatest(remaining) : remaining[0] ? JSON.stringify(remaining[0]) : null;
    const changes: Record<string, string | null> = { [keys.history]: JSON.stringify(remaining), [keys.latest]: latest };
    let referenceRemoved = false;
    if (category === 'skin') {
      for(const key of ['attune_skin_appearance_reference_v1','attune_skin_appearance_single_reference_v1']){
        const ref=JSON.parse(localStorage.getItem(key)||'null');
        if(ref?.id===id){changes[key]=null;referenceRemoved=true;}
        else if(ref){let changed=false;
          for(const rows of Object.values(ref.indicators||{}) as any[][])for(const row of rows)if(row.appearance?.referenceId===id){
            row.score=null;row.appearance.value=null;row.appearance.quality='insufficient';row.appearance.referenceId=null;
            row.appearance.components={};row.appearance.limitationCode='REFERENCE_DELETED';
            if(row.measurement){row.measurement.rawValue=null;row.measurement.quality='insufficient';row.measurement.unavailableReason='REFERENCE_DELETED';}
            delete row.referenceDelta;changed=true;
          }
          if(changed){changes[key]=JSON.stringify(ref);referenceRemoved=true;}
        }
      }
      const single = JSON.parse(localStorage.getItem(STORAGE_KEYS.SKIN_BASELINE_META) || 'null');
      const multi = JSON.parse(localStorage.getItem(STORAGE_KEYS.SKIN_MULTI_BASELINE) || 'null');
      const signs = JSON.parse(localStorage.getItem(STORAGE_KEYS.SKIN_SIGNS_BASELINE) || 'null');
      if(signs?.id===id){changes[STORAGE_KEYS.SKIN_SIGNS_BASELINE]=null;referenceRemoved=true;}
      const singleSigns = JSON.parse(localStorage.getItem(STORAGE_KEYS.SKIN_SINGLE_SIGNS_BASELINE) || 'null');
      if(singleSigns?.id===id){changes[STORAGE_KEYS.SKIN_SINGLE_SIGNS_BASELINE]=null;referenceRemoved=true;}
      if (single?.id === id || (!single?.id && record.schemaVersion !== 3 && record.isBaseline && record.comparisonScope !== 'three-angle-v2')) {
        changes[STORAGE_KEYS.SKIN_BASELINE] = null; changes[STORAGE_KEYS.SKIN_BASELINE_META] = null; referenceRemoved = true;
      }
      if (multi?.id === id) { changes[STORAGE_KEYS.SKIN_MULTI_BASELINE] = null; referenceRemoved = true; }
      for(const item of remaining)for(const rows of Object.values(item.indicators||{}) as any[][])for(const row of rows)if(row.appearance?.referenceId===id){
        delete row.referenceDelta;row.appearance.referenceId=null;delete row.appearance.components.normalizedContourDelta;row.appearance.limitationCode='REFERENCE_DELETED';
      }
      for (const item of remaining) if (item.baselineId === id) {
        item.comparisonUnavailable = true; item.referenceDeleted = true;
        delete item.highestChangePct; item.referralSuggested = false;
        for (const region of Object.values(item.regions || {}) as any[]) { delete region.changeFromBaselinePct; region.comparisonUnavailable = true; }
        for (const rows of Object.values(item.indicators || {}) as any[][]) for(const row of rows){delete row.referenceDelta;if(row.appearance){row.appearance.referenceId=null;delete row.appearance.components.normalizedContourDelta;row.appearance.limitationCode='REFERENCE_DELETED';}}
        item.clinicalNoteTr = 'Bu karşılaştırmanın referansı silindi. Yeni bir referans taraması gerekiyor.';
      }
      changes[keys.history] = JSON.stringify(remaining);
      changes[keys.latest] = remaining[0] ? JSON.stringify(remaining[0]) : null;
      if (referenceRemoved) changes[STORAGE_KEYS.SKIN_REMINDER] = null;
    }
    const referral = JSON.parse(localStorage.getItem(STORAGE_KEYS.REFERRAL_CONTEXT) || 'null');
    if (referral?.sourceModule === category.toUpperCase()) changes[STORAGE_KEYS.REFERRAL_CONTEXT] = null;
    try {
      if(category==='skin')await deleteSkinPhotosWithRecords(id,()=>commit(changes,false),recover,()=>localStorage.removeItem(RECORD_JOURNAL));
      else if(category==='dental'&&record.sourceAssociationVersion==='dental-source-identity-v1')await deleteDentalPhotosWithRecords(id,()=>commit(changes,false),recover,()=>localStorage.removeItem(RECORD_JOURNAL));
      else commit(changes);
    }
    catch { throw new Error(record.backendSessionId ? 'Sunucu silindi; yerel kopya silinemedi. Yerel kayıt için tekrar deneyin.' : 'Yerel kayıt silinemedi veya doğrulanamadı. Tekrar deneyebilirsiniz.'); }
    window.dispatchEvent(new Event('attune-records')); window.dispatchEvent(new Event('attune-reminder'));
    return referenceRemoved ? 'Kayıt silindi. Yeni bir cilt referansı gerekiyor.' : 'Kayıt kalıcı olarak silindi.';
  };
  return withRecordsLock(operation);
}

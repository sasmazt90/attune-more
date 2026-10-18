"""
Session Memory Manager (Local-First Persistence & Privacy Enforced)
Lisans: UNLICENSED

Her görüşmeden:
- timestamp
- kısa kullanıcı onaylı özet
- yüksek seviyeli temalar
- mood (önce/sonra)
- professional support flag
saklanabilir.

GİZLİLİK KURALLARI:
- Ham ses veya tam konuşma dökümü KESİNLİKLE KALICI OLARAK SAKLANMAZ.
- Kullanıcı gizlilik tercihinde seans özetlerini saklamayı kapattıysa (save_mental_summaries=False),
  oturum özeti diske/belleğe ASLA yazılmaz.
"""

import json
import os
import secrets
import hashlib
import hmac
from uuid import uuid4
from threading import RLock
from typing import List, Dict, Any, Optional
from datetime import datetime
from pathlib import Path

DATA_DIR = Path(os.getenv("ATTUNE_DATA_DIR", str(Path(__file__).resolve().parent / "data")))
SESSIONS_FILE = DATA_DIR / "mental_sessions.json"
DELETIONS_FILE = DATA_DIR / 'mental_deletions.json'
_storage_lock = RLock()

DEFAULT_SESSIONS = [
    {
        "sessionId": "men-001",
        "date": "2026-09-14T08:30:00Z",
        "durationSeconds": 240,
        "moodBefore": "STRESSED",
        "moodAfter": "FOCUSED",
        "recurringThemes": ["iş yoğunluğu", "toplantı trafiği"],
        "summaryText": "Sabah trafiğinde yoğun iş temposu üzerine konuşuldu. Kısa odaklanma desteği sağlandı.",
        "clinicalEscalationSuggested": False
    },
    {
        "sessionId": "men-002",
        "date": "2026-09-19T19:10:00Z",
        "durationSeconds": 380,
        "moodBefore": "TIRED",
        "moodAfter": "TIRED",
        "recurringThemes": ["uyku düzensizliği", "fiziksel yorgunluk"],
        "summaryText": "Son görüşmelerde uyku düzeni ve kronikleşen yorgunluk hissi tekrar eden ortak tema olarak öne çıktı.",
        "clinicalEscalationSuggested": True,
        "suggestedActionNote": "Son görüşmelerinizde uyku ve yorgunluk temalarının tekrar ettiği gözlemlendi. Bir klinik psikolog ile görüşmek faydalı olabilir."
    }
]

class SessionMemoryManager:
    @staticmethod
    def _ensure_storage():
        DATA_DIR.mkdir(parents=True, exist_ok=True)
        if not SESSIONS_FILE.exists():
            with open(SESSIONS_FILE, "w", encoding="utf-8") as f:
                json.dump([], f, ensure_ascii=False, indent=2)

    @classmethod
    def _read_sessions(cls) -> List[Dict[str, Any]]:
        cls._ensure_storage()
        try:
            with open(SESSIONS_FILE, "r", encoding="utf-8") as f:
                sessions = json.load(f)
                if not isinstance(sessions, list):
                    raise ValueError("Invalid session store")
                return sessions
        except (OSError, ValueError) as error:
            raise RuntimeError("Session storage could not be read; history is unverified") from error

    @classmethod
    def get_all_sessions(cls) -> List[Dict[str, Any]]:
        with _storage_lock:
            return [{k: v for k, v in row.items() if k != 'deletionToken'} for row in cls._read_sessions()]

    @staticmethod
    def _write(path, value):
        temporary = path.with_suffix('.tmp')
        with temporary.open('w', encoding='utf-8') as stream:
            json.dump(value, stream, ensure_ascii=False, indent=2)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, path)

    @classmethod
    def delete_session(cls, session_id: str, token: str) -> bool:
        with _storage_lock:
            sessions = cls._read_sessions()
            deleted = json.loads(DELETIONS_FILE.read_text(encoding='utf-8')) if DELETIONS_FILE.exists() else {}
            digest = hashlib.sha256(token.encode()).hexdigest()
            matches = [row for row in sessions if row.get('sessionId') == session_id]
            if not matches:
                return bool(deleted.get(session_id) and hmac.compare_digest(deleted[session_id], digest))
            # Legacy records without an ownership capability remain protected.
            if len(matches) != 1 or not matches[0].get('deletionToken') or not hmac.compare_digest(matches[0]['deletionToken'], token):
                return False
            # Keep only a token digest for safe retries, never a deleted health summary.
            deleted[session_id] = digest
            cls._write(DELETIONS_FILE, deleted)
            cls._write(SESSIONS_FILE, [row for row in sessions if row.get('sessionId') != session_id])
            return True

    @classmethod
    def add_session(
        cls,
        summary_text: str,
        recurring_themes: List[str],
        duration_seconds: Optional[int] = None,
        mood_before: Optional[str] = None,
        mood_after: Optional[str] = None,
        escalation_suggested: bool = False,
        suggested_action: Optional[str] = None,
        save_mental_summaries: bool = False
    ) -> Dict[str, Any]:
        """
        Oturum özetini kaydeder.
        Eğer kullanıcı gizlilik tercihinde save_mental_summaries kapalıysa kayıt YAPMAZ.
        """
        if not save_mental_summaries:
            return {
                "sessionId": None,
                "persisted": False,
                "reason": "PRIVACY_PREFERENCE_DISABLED",
                "summaryText": summary_text,
                "recurringThemes": recurring_themes,
                "message": "Kullanıcı gizlilik tercihi gereğince bu oturum özeti kalıcı olarak kaydedilmedi."
            }

        cls._ensure_storage()
        with _storage_lock:
            return cls._add_owned_session(summary_text, recurring_themes, duration_seconds, mood_before, mood_after, escalation_suggested, suggested_action)

    @classmethod
    def _add_owned_session(cls, summary_text, recurring_themes, duration_seconds, mood_before, mood_after, escalation_suggested, suggested_action):
        sessions = cls._read_sessions()
        new_session = {
            "sessionId": f"men-{uuid4()}",
            "deletionToken": secrets.token_hex(32),
            "date": datetime.utcnow().isoformat() + "Z",
            "durationSeconds": duration_seconds,
            "moodBefore": mood_before,
            "moodAfter": mood_after,
            "recurringThemes": recurring_themes,
            "summaryText": summary_text,
            "clinicalEscalationSuggested": escalation_suggested,
            "suggestedActionNote": suggested_action,
            "persisted": True
        }
        sessions.append(new_session)
        cls._write(SESSIONS_FILE, sessions)
        return new_session

    @classmethod
    def clear_all(cls) -> None:
        with _storage_lock:
            cls._ensure_storage()
            cls._write(SESSIONS_FILE, [])
            cls._write(DELETIONS_FILE, {})

import pytest
from pathlib import Path
import sys

root_dir = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(root_dir / "services" / "core-api"))

from mental_provider import (
    MentalConversationProvider,
    LocalFallbackMentalProvider,
    OpenAICompatibleMentalProvider,
    LocalFallbackSessionAnalyzer,
    check_mental_crisis,
    get_active_mental_provider,
    get_active_session_analyzer
)
from session_memory import SessionMemoryManager

def test_mental_provider_fallback_when_no_api_key(monkeypatch):
    """API anahtarı olmadığında sistem açıkça LocalFallbackMentalProvider (Demo) kullanmalıdır."""
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    provider = get_active_mental_provider()
    assert isinstance(provider, LocalFallbackMentalProvider)
    assert provider.is_live_llm() is False
    assert "LOCAL_DEMO" in provider.get_provider_name()

def test_mental_driving_mode_response_constraint():
    """Araç hareket halindeyken (is_driving=True) yanıt kısa, sakin ve dikkati yola odaklayıcı olmalıdır."""
    provider = LocalFallbackMentalProvider()
    reply_obj = provider.generate_reply(
        user_message="Bugün trafikte çok yoruldum ve biraz dinlenmek istiyorum",
        is_driving=True,
        history=[]
    )
    
    assert reply_obj["isDriving"] is True
    assert reply_obj["escalationSuggested"] is False
    # Kısa olmalı
    word_count = len(reply_obj["reply"].split())
    assert word_count <= 35, f"Yanıt sürüş modu için fazla uzun: {word_count} kelime"
    assert any(term in reply_obj["reply"].lower() for term in ["yol", "sürüş", "dikkat", "park"])

def test_mental_crisis_flow_112_present_and_182_strictly_forbidden():
    """
    ZORUNLU KRİZ GÜVENLİK TESTİ:
    Akut kriz durumunda '112' Acil Çağrı bulunmalı;
    '182' KESİNLİKLE kriz cevabında yer almamalıdır!
    """
    crisis_messages = [
        "artık yaşamak istemiyorum",
        "kendime zarar vermek istiyorum",
        "canıma kıymak istiyorum",
        "ölmek istiyorum"
    ]

    for msg in crisis_messages:
        # Park halinde kriz
        parked_result = check_mental_crisis(msg, is_driving=False)
        assert parked_result["isCrisis"] is True
        assert parked_result["riskLevel"] == "IMMINENT"
        assert "112" in parked_result["reply"]
        assert "182" not in parked_result["reply"], f"HATA: 182 kriz cevabında yer alamaz! Mesaj: {parked_result['reply']}"

        # Sürüş halinde kriz
        driving_result = check_mental_crisis(msg, is_driving=True)
        assert driving_result["isCrisis"] is True
        assert "112" in driving_result["reply"]
        assert "182" not in driving_result["reply"]
        assert "ekrana bakmayın" in driving_result["reply"].lower()
        assert "güvenli bir yerde durdurun" in driving_result["reply"].lower()

def test_mental_session_summary_is_generated_from_actual_conversation_not_hardcoded():
    """Oturum analizi sabit ezbere tema yazmamalı, kullanıcının gerçek içeriğinden türetilmelidir."""
    analyzer = LocalFallbackSessionAnalyzer()
    
    # Kullanıcı aile ve ilişkiler konuşuyor (iş stresi veya uyku demedi!)
    family_messages = [
        {"role": "user", "content": "Bugün çocukları okuldan aldım, ailece evde zaman geçirdik, çok mutluyum."}
    ]
    family_analysis = analyzer.analyze_session(family_messages)
    assert "sosyal ilişkiler" in family_analysis["themes"]
    assert "uyku düzeni" not in family_analysis["themes"]
    assert family_analysis["moodTrend"] == "RELAXED"

    # Kullanıcı uykusuzluktan yakınıyor
    sleep_messages = [
        {"role": "user", "content": "Gece 3 defa uyandım, hiç uyuyamıyorum ve halsizim."}
    ]
    sleep_analysis = analyzer.analyze_session(sleep_messages)
    assert "uyku düzeni" in sleep_analysis["themes"]
    assert "sosyal ilişkiler" not in sleep_analysis["themes"]

def test_privacy_preference_off_prevents_session_persistence():
    """Kullanıcı gizlilik ayarında save_mental_summaries=False yaptıysa oturum ASLA diske yazılmamalıdır."""
    SessionMemoryManager.clear_all()
    assert len(SessionMemoryManager.get_all_sessions()) == 0

    # Gizlilik tercihi KAPALI oturum kaydetme denemesi
    res = SessionMemoryManager.add_session(
        summary_text="Gizli seans",
        recurring_themes=["genel"],
        save_mental_summaries=False
    )

    assert res["persisted"] is False
    assert res["reason"] == "PRIVACY_PREFERENCE_DISABLED"
    # Veritabanında hiçbir kayıt oluşmamalı
    assert len(SessionMemoryManager.get_all_sessions()) == 0

    # Gizlilik tercihi AÇIK oturum kaydetme
    res_allowed = SessionMemoryManager.add_session(
        summary_text="Kayıtlı seans",
        recurring_themes=["genel"],
        save_mental_summaries=True
    )
    assert res_allowed["persisted"] is True
    assert len(SessionMemoryManager.get_all_sessions()) == 1

def test_live_provider_failure_is_explicit_without_demo_fallback(monkeypatch):
    """Provider failure is a sanitized 503; no fabricated personalized demo reply."""
    import pytest
    import mental_provider
    from fastapi import HTTPException
    def unavailable(*args, **kwargs):
        raise RuntimeError('PRIVATE_PROVIDER_ERROR_DO_NOT_EXPOSE')
    monkeypatch.setattr(mental_provider, 'get_openai_client', unavailable)
    broken_provider = OpenAICompatibleMentalProvider(api_key='noncredential-test-fixture')
    with pytest.raises(HTTPException) as caught:
        broken_provider.generate_reply(user_message='Merhaba', is_driving=False, history=[])
    assert caught.value.status_code == 503
    assert 'PRIVATE_PROVIDER_ERROR' not in str(caught.value.detail)

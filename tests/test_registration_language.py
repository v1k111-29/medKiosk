"""Registration chat reply language (no network: _call_groq is stubbed)."""
import asyncio

from app.services import llm_service


def _run(monkeypatch, language, groq_result):
    seen = {}

    async def fake_call_groq(system_prompt, user_prompt, **kwargs):
        seen["system_prompt"] = system_prompt
        return groq_result

    monkeypatch.setattr(llm_service, "_call_groq", fake_call_groq)
    result = asyncio.run(llm_service.call_llm_registration(
        user_text="hi", collected_fields={}, language=language,
    ))
    return result, seen.get("system_prompt", "")


def test_tamil_adds_language_rule(monkeypatch):
    _, prompt = _run(monkeypatch, "ta", {"extracted": {}, "reply": "சரி"})
    assert "The patient chose Tamil" in prompt


def test_english_has_no_tamil_rule(monkeypatch):
    _, prompt = _run(monkeypatch, "en", {"extracted": {}, "reply": "ok"})
    assert "The patient chose Tamil" not in prompt


def test_tamil_fallback_reply_when_llm_fails(monkeypatch):
    result, _ = _run(monkeypatch, "ta", None)
    assert result["reply"] == llm_service.REGISTRATION_FALLBACK_REPLY["ta"]


def test_unknown_language_falls_back_to_english(monkeypatch):
    result, prompt = _run(monkeypatch, "auto", None)
    assert "The patient chose Tamil" not in prompt
    assert result["reply"] == llm_service.REGISTRATION_FALLBACK_REPLY["en"]

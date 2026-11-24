import pytest

from app.services.clinical_rules import detect_red_flags, escalate, keyword_department, max_urgency


def flags(text, age=None):
    return detect_red_flags(text, age=age)


# ── Positive cases ────────────────────────────────────────────────────────────

@pytest.mark.parametrize("text,code,urgency", [
    # English
    ("I have severe chest pain since morning", "chest_pain", "emergency"),
    ("tightness in my chest and sweating", "chest_pain", "emergency"),
    ("I can't breathe properly", "severe_breathlessness", "emergency"),
    ("difficulty in breathing at night", "severe_breathlessness", "emergency"),
    ("shortness of breath when walking", "breathlessness", "urgent"),
    ("my father collapsed at home", "unconscious", "emergency"),
    ("she fainted in the bus", "fainting", "urgent"),
    ("my son had a seizure", "seizure", "emergency"),
    ("he is getting fits", "seizure", "emergency"),
    ("face drooping and slurred speech", "stroke", "emergency"),
    ("sudden weakness on one side of the body", "stroke", "emergency"),
    ("heavy bleeding from the wound", "heavy_bleeding", "emergency"),
    ("vomiting blood", "heavy_bleeding", "emergency"),
    ("severe burns on both arms", "severe_burns", "emergency"),
    ("got electric shock", "severe_burns", "emergency"),
    ("he drank pesticide", "poisoning", "emergency"),
    ("snake bite on leg", "poisoning", "emergency"),
    ("I want to kill myself", "suicidal", "emergency"),
    ("having suicidal thoughts", "suicidal", "emergency"),
    ("I am 6 months pregnant and bleeding", "pregnancy_bleeding", "emergency"),
    ("my baby has fever and is very drowsy", "child_fever_lethargy", "urgent"),
    ("road accident, hit his head", "trauma", "urgent"),
    # Tanglish
    ("nenju vali romba irukku", "chest_pain", "emergency"),
    ("nenjula vali and viyarvai", "chest_pain", "emergency"),
    ("mooch vida mudiyala", "severe_breathlessness", "emergency"),
    ("moochu thinaral", "severe_breathlessness", "emergency"),
    ("suya ninaivu illama irukkaar", "unconscious", "emergency"),
    ("mayangi vizhundhutaanga", "fainting", "urgent"),
    ("valippu vandhuchu", "seizure", "emergency"),
    ("vaai koniduchu, pakkavatham maadhiri irukku", "stroke", "emergency"),
    ("ratham nikkala", "heavy_bleeding", "emergency"),
    ("paambu kadichiduchu", "poisoning", "emergency"),
    ("poochi marundhu kudichitaan", "poisoning", "emergency"),
    ("saaganum pola irukku", "suicidal", "emergency"),
    ("karpamaa irukken, ratham varudhu", "pregnancy_bleeding", "emergency"),
    ("kuzhandhaikku kaichal, romba sornthu irukku", "child_fever_lethargy", "urgent"),
    # Tamil script
    ("நெஞ்சு வலி அதிகமா இருக்கு", "chest_pain", "emergency"),
    ("மார்பு வலி", "chest_pain", "emergency"),
    ("மூச்சு விட முடியவில்லை", "severe_breathlessness", "emergency"),
    ("மூச்சுத் திணறல்", "severe_breathlessness", "emergency"),
    ("சுயநினைவின்றி இருக்கிறார்", "unconscious", "emergency"),
    ("அவருக்கு வலிப்பு வந்தது", "seizure", "emergency"),
    ("பக்கவாதம் போல் இருக்கு", "stroke", "emergency"),
    ("இரத்த வாந்தி", "heavy_bleeding", "emergency"),
    ("விஷம் குடித்துவிட்டார்", "poisoning", "emergency"),
    ("தற்கொலை எண்ணம் வருகிறது", "suicidal", "emergency"),
    ("கர்ப்பமா இருக்கேன், ரத்தம் வருது", "pregnancy_bleeding", "emergency"),
    ("குழந்தைக்கு காய்ச்சல், சோர்வா இருக்கு", "child_fever_lethargy", "urgent"),
])
def test_red_flag_positive(text, code, urgency):
    r = flags(text)
    assert code in r["flags"], (text, r)
    assert r["urgency"] == max_urgency(urgency, r["urgency"])
    assert r["urgency"] in ("urgent", "emergency")


# ── Negatives / negation ──────────────────────────────────────────────────────

@pytest.mark.parametrize("text", [
    "fever and cold for two days",
    "sore throat and cough",
    "knee pain after a fall",
    "no chest pain",
    "I have no chest pain, just a headache",
    "denies chest pain",
    "without any breathing difficulty",
    "I don't want to die",
    "nenju vali illa",
    "nenju valiyilla, kaichal mattum",
    "நெஞ்சு வலி இல்லை",
    "நெஞ்சுவலியில்லை",
    "மயக்கம் இல்லை",
    "food poisoning with loose motion",
    "I am pregnant, blood test due today",
    "pregnant, checking blood pressure",
    "visha kaichal",            # colloquial "viral fever", not poisoning
    "விஷக்காய்ச்சல்",
    "burning sensation while urinating",
    "fever not responding to tablets",
    "vaa konjam",
    "my child has a cough",
    "12 months old baby with fever",  # infant rule is for under 3 months
    "",
])
def test_red_flag_negative(text):
    r = flags(text)
    assert r["urgency"] is None, (text, r)
    assert r["flags"] == []


def test_negation_is_clause_scoped():
    r = flags("no fever but chest pain since morning")
    assert "chest_pain" in r["flags"]
    r = flags("nenju vali illa aana mooch vida mudiyala")
    assert r["flags"] == ["severe_breathlessness"]


def test_severe_supersedes_mild_variant():
    r = flags("short of breath and now can't breathe at all")
    assert "severe_breathlessness" in r["flags"]
    assert "breathlessness" not in r["flags"]


def test_child_by_age():
    assert "child_fever_lethargy" in flags("fever and very sleepy", age=4)["flags"]
    assert flags("fever and very sleepy", age=40)["flags"] == []


def test_young_infant_fever():
    assert "infant_fever" in flags("newborn with fever")["flags"]
    assert "infant_fever" in flags("2 months old baby has fever")["flags"]


# ── Escalation ────────────────────────────────────────────────────────────────

def test_escalate_takes_max_and_records_reasons():
    r = escalate("normal", "chest pain", vitals=None)
    assert r["urgency"] == "emergency"
    assert any("Chest pain" in x for x in r["escalation_reasons"])

    r = escalate("urgent", "fever and cold", vitals=None)
    assert r["urgency"] == "urgent"
    assert r["escalation_reasons"] == ["AI triage: urgent"]

    r = escalate("normal", "fever and cold", vitals=None)
    assert r == {"urgency": "normal", "escalation_reasons": [], "red_flags": [], "news2": None}


def test_escalate_never_downgrades():
    r = escalate("emergency", "mild headache")
    assert r["urgency"] == "emergency"


def test_escalate_news2():
    # single parameter scoring 3 (SpO2 90) → at least urgent
    r = escalate("normal", "fever", vitals={"spo2": 90})
    assert r["urgency"] == "urgent"
    assert any("NEWS2" in x for x in r["escalation_reasons"])
    # aggregate ≥ 7 → emergency
    r = escalate("normal", "fever", vitals={"resp_rate": 26, "spo2": 92, "pulse": 120, "temperature": 39.5})
    assert r["news2"]["band"] == "high"
    assert r["urgency"] == "emergency"


# ── Keyword department fallback ───────────────────────────────────────────────

@pytest.mark.parametrize("text,dept", [
    ("knee pain after fall", "ortho"),
    ("skin rash and itching", "derm"),
    ("eye redness", "ophthal"),
    ("ear pain and hearing loss", "ent"),
    ("I am pregnant", "gyne"),
    ("my child has cough", "paeds"),
    ("palpitations", "cardio"),
    ("fever and cold", "general"),
    ("mutti vali", "ortho"),
    ("காது வலி", "ent"),
    ("தோல் அரிப்பு", "derm"),
    ("heartburn after food", "general"),
])
def test_keyword_department(text, dept):
    assert keyword_department(text) == dept


def test_keyword_department_child_age():
    assert keyword_department("fever", age=5) == "paeds"

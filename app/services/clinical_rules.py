"""
Deterministic clinical safety layer.

The LLM is advisory only. Everything here is rule-based and testable:

- `detect_red_flags(text, age)` — keyword red-flag detector over symptom text in
  English, Tamil script and romanised Tamil (Tanglish), with simple negation
  handling ("no chest pain", "nenju vali illa", "நெஞ்சு வலி இல்லை").
- `news2(vitals)` — NEWS2 aggregate score (SpO2 scale 1). Consciousness and
  supplemental oxygen are not captured by the kiosk, so they are assumed
  "alert" / "air" and the result is marked `partial: true`.
- `escalate(...)` — final urgency = max(LLM urgency, red-flag urgency, NEWS2
  urgency) with a list of human-readable `escalation_reasons`.
- `keyword_department(text, age)` — keyword department routing used when the
  LLM is unavailable.

Keyword lists must be reviewed by clinicians and a native Tamil speaker before
production use. Matching is intentionally conservative (over-triage is safer
than under-triage at an unattended kiosk); every escalation is visible to staff
with its reason.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Iterable, Optional

from app.core.config import settings

URGENCY_ORDER = {"normal": 0, "urgent": 1, "emergency": 2}

# Age (years) below which a patient is treated as a child (CHILD_AGE_YEARS setting).
CHILD_AGE_YEARS = settings.CHILD_AGE_YEARS


def max_urgency(*levels: Optional[str]) -> str:
    best = "normal"
    for lvl in levels:
        if lvl in URGENCY_ORDER and URGENCY_ORDER[lvl] > URGENCY_ORDER[best]:
            best = lvl
    return best


# ═══════════════════════════════════════════════════════════════════════════════
# Text normalisation + negation
# ═══════════════════════════════════════════════════════════════════════════════

# Clause boundaries: punctuation and contrastive conjunctions (English, Tanglish, Tamil).
_CLAUSE_SPLIT = re.compile(
    r"[.,;:!?\n।]+|\s(?:but|however|although|though|aana|anaa|aanaa|anal|aanal)\s|\sஆனா(?:ல்)?\s",
    re.IGNORECASE,
)

# English negators that come BEFORE the symptom ("no chest pain", "denies fever").
_PRE_NEGATORS = {
    "no", "not", "never", "without", "denies", "denied", "deny", "nil", "none",
    "dont", "don't", "doesnt", "doesn't", "didnt", "didn't", "havent", "haven't",
    "hasnt", "hasn't", "isnt", "isn't", "wasnt", "wasn't", "free",
}
_PRE_NEGATION_WINDOW = 3  # tokens

# Tamil / Tanglish negators that come AFTER the symptom ("nenju vali illa").
_POST_NEGATORS = {
    "illa", "illai", "ille", "illae", "illey", "ila", "illaa", "illama", "illaama",
    "இல்லை", "இல்ல", "இல்லே", "இல்லாம", "இல்லாமல்", "கிடையாது", "kidaiyathu", "kidaiyadhu",
}
# Negator glued to the end of the matched word ("valiyilla", "வலியில்லை").
_POST_NEGATION_SUFFIX = re.compile(r"^\S*?(?:illa|ille|illai|இல்ல|ில்ல)", re.IGNORECASE)

_TOKEN_RE = re.compile(r"[^\s]+")


def _normalise(text: str) -> str:
    text = (text or "").lower()
    text = text.replace("’", "'").replace("‘", "'")
    # Zero-width joiners sometimes appear in Tamil input.
    text = text.replace("‌", "").replace("‍", "")
    return re.sub(r"[ \t]+", " ", text)


def _clauses(text: str) -> list[str]:
    return [c.strip() for c in _CLAUSE_SPLIT.split(text) if c and c.strip()]


def _is_negated(clause: str, start: int, end: int) -> bool:
    before = _TOKEN_RE.findall(clause[:start])[-_PRE_NEGATION_WINDOW:]
    if any(tok.strip("'\"()") in _PRE_NEGATORS for tok in before):
        return True
    rest = clause[end:]
    if rest and not rest[0].isspace() and _POST_NEGATION_SUFFIX.match(rest):
        return True
    after = _TOKEN_RE.findall(rest)
    # Skip the remainder of the matched word if the match ended mid-token.
    if after and rest and not rest[0].isspace():
        after = after[1:]
    return bool(after) and after[0].strip("'\"()") in _POST_NEGATORS


# Latin-script word boundary helpers (\b does not work with Tamil combining marks,
# so Tamil patterns are plain substrings / regexes without boundaries).
_B = r"(?<![a-z])"   # start of a Latin word
_E = r"(?![a-z])"    # end of a Latin word


def _en(*patterns: str) -> list[re.Pattern]:
    return [re.compile(_B + p + _E) for p in patterns]


def _ta(*patterns: str) -> list[re.Pattern]:
    return [re.compile(p) for p in patterns]


def _find(patterns: Iterable[re.Pattern], clauses: list[str]) -> Optional[str]:
    """First non-negated match of any pattern in any clause, or None."""
    for clause in clauses:
        for pat in patterns:
            for m in pat.finditer(clause):
                if not _is_negated(clause, m.start(), m.end()):
                    return m.group(0)
    return None


# ═══════════════════════════════════════════════════════════════════════════════
# Red-flag rules
# ═══════════════════════════════════════════════════════════════════════════════

@dataclass(frozen=True)
class Rule:
    code: str
    label: str
    urgency: str  # "emergency" | "urgent"
    patterns: tuple[re.Pattern, ...]


_RATHAM = r"(?:raththam|rattham|ratham|ratthum)"
_RATHA = r"ra(?:th|tth|thth)a"
# "blood" but not "blood pressure/test/sugar/..." (routine, not bleeding)
_BLOOD = r"blood(?!\s*(?:test|pressure|sugar|report|group|count|check|reading))"
_KUZHANTHAI = r"ku(?:zh|l|z)a(?:n|nd|nt)h?ai\w*"

RULES: tuple[Rule, ...] = (
    # ── Chest pain / heart attack ──────────────────────────────────────────────
    Rule("chest_pain", "Chest pain", "emergency", tuple(
        _en(
            r"chest\s*pains?", r"pain\s+in\s+(?:my|the|his|her)?\s*chest", r"chest\s+(?:pressure|tightness|heaviness)",
            r"tight(?:ness)?\s+(?:in\s+)?(?:my\s+)?chest", r"heavy\s+chest", r"crushing\s+(?:chest|pain)",
            r"heart\s*attack", r"cardiac\s+arrest",
            # Tanglish
            r"nenj(?:u|i)?\s*vali(?!\w*ill)\w*", r"nenj(?:ula|ulla|il|ila|ile|la|le)\s*vali(?!\w*ill)\w*",
            r"nenj(?:u|i)?\s*(?:adaippu|adaipu|iruk+am|anaippu|baram|bharam)",
            r"maarbu\s*vali(?!\w*ill)\w*", r"marbu\s*vali(?!\w*ill)\w*", r"maaradaippu", r"maradaippu",
        )
        + _ta(
            r"நெஞ்சு\s*வலி", r"நெஞ்சுவலி", r"நெஞ்சி?(?:ல்|ல|லே)\s*வலி", r"நெஞ்சுல\s*வலி",
            r"நெஞ்சு\s*(?:அடைப்பு|இறுக்கம்|பாரம்|கனம்)", r"மார்பு\s*வலி", r"மார்பில்\s*வலி",
            r"மார்பு\s*(?:அடைப்பு|இறுக்கம்)", r"மாரடைப்பு", r"ஹார்ட்\s*அட்டாக்",
        )
    )),
    # ── Severe breathlessness ─────────────────────────────────────────────────
    Rule("severe_breathlessness", "Severe difficulty breathing", "emergency", tuple(
        _en(
            r"can'?t\s+breathe?", r"cannot\s+breathe?", r"can\s+not\s+breathe?", r"unable\s+to\s+breathe?",
            r"not\s+able\s+to\s+breathe?", r"difficulty\s+(?:in\s+)?breathing", r"trouble\s+breathing",
            r"struggling\s+to\s+breathe?", r"hard\s+to\s+breathe?", r"gasping", r"choking",
            r"severe(?:ly)?\s+(?:breathless(?:ness)?|short\s+of\s+breath)", r"breathing\s+difficulty",
            r"lips?\s+(?:turning\s+|are\s+|is\s+)?(?:blue|bluish)",
            # Tanglish
            r"moo?ch(?:u|chu)?\s*(?:vida|vidave|vida\s*kooda)\s*(?:mudiyala|mudiyalai|mudiyavillai|mudila|kashtam|kastam|kastama|kashtama|siramam)",
            r"moo?ch(?:u|chu)?\s*th?(?:i|e)naral\w*", r"moo?ch(?:u|chu)?\s*th?(?:i|e)naru\w*",
            r"moo?ch(?:u|chu)?\s*mutt\w*", r"swasa?m?\s*(?:kashtam|kastam|vida\s*mudiyala)",
        )
        + _ta(
            r"மூச்சு\s*விட\s*(?:முடிய(?:வில்லை|லை|ல)|கஷ்டம|கஷ்டமா|சிரமம)", r"மூச்சுவிட\s*முடிய",
            r"மூச்சுத்?\s*திணற", r"மூச்சு\s*முட்ட", r"சுவாசிக்க\s*முடிய(?:வில்லை|லை|ல)",
            r"மூச்சு\s*விடுவதில்\s*சிரமம்", r"உதடு\s*நீலமா",
        )
    )),
    Rule("breathlessness", "Shortness of breath", "urgent", tuple(
        _en(
            r"short(?:ness)?\s+of\s+breath", r"breathless(?:ness)?", r"breathing\s+(?:problem|issue)s?",
            r"wheez(?:e|ing)", r"out\s+of\s+breath",
            r"moo?ch(?:u|chu)?\s*vaang\w*", r"moo?ch(?:u|chu)?\s*vang\w*", r"iraippu", r"eraippu",
        )
        + _ta(r"மூச்சு\s*வாங்கு", r"மூச்சிரைப்பு", r"இரைப்பு", r"மூச்சு\s*பிரச்சனை")
    )),
    # ── Unconscious / fainting ────────────────────────────────────────────────
    Rule("unconscious", "Unconscious / unresponsive", "emergency", tuple(
        _en(
            r"unconscious(?:ness)?", r"unresponsive", r"(?:is|was|he'?s|she'?s)\s+not\s+responding", r"loss\s+of\s+consciousness",
            r"lost\s+consciousness", r"collaps(?:e|ed|ing)", r"won'?t\s+wake\s*up", r"not\s+waking\s+up",
            r"suya?\s*ninaiv(?:u|e)\s*(?:illa\w*|illama|ilama|poch\w*|izhand\w*)",
            r"pe?chu?\s*moo?ch(?:u|chu)?\s*(?:illa\w*|ila)", r"mayangi\s*(?:kidakk|kedakk)\w*",
        )
        + _ta(
            r"சுய\s*நினைவு\s*(?:இல்ல|இழந்|இன்றி|போச்சு)", r"சுயநினைவி(?:ன்றி|ல்லாமல்|ல்லை)",
            r"நினைவு\s*இழந்", r"நினைவிழந்", r"பேச்சு\s*மூச்சு\s*இல்ல", r"மயங்கி\s*கிட",
        )
    )),
    Rule("fainting", "Fainting / blackout", "urgent", tuple(
        _en(
            r"faint(?:ed|ing|s)?", r"passed\s+out", r"pass(?:ing)?\s+out", r"black(?:ed)?\s*out",
            r"mayakk?am(?!\w*ill)\w*", r"mayangi\s*(?:vizh|vilu|vizu|vilunth|vizhunth)\w*", r"mayangi(?:tt?en|ttaa?n|ttaa?l)",
        )
        + _ta(r"மயக்கம", r"மயங்கி\s*விழு", r"மயங்கிவிழு", r"மயங்கிட்ட")
    )),
    # ── Seizure ───────────────────────────────────────────────────────────────
    Rule("seizure", "Seizure / convulsion", "emergency", tuple(
        _en(
            r"seizures?", r"convulsions?", r"convulsing", r"fits", r"fitting", r"(?:a|having|had|got)\s+fit",
            r"epilep(?:sy|tic)\s+(?:attack|fit)", r"jerking", r"fits\s*vanth\w*",
            r"valippu\w*", r"kaa?kk?a\s*valippu", r"janni",
        )
        + _ta(r"வலிப்பு", r"ஜன்னி", r"ஃபிட்ஸ்", r"பிட்ஸ்")
    )),
    # ── Stroke ────────────────────────────────────────────────────────────────
    Rule("stroke", "Possible stroke", "emergency", tuple(
        _en(
            r"stroke", r"face\s+(?:is\s+)?droop\w*", r"facial\s+droop\w*", r"droop\w*\s+face",
            r"slurr(?:ed|ing)\s*(?:speech|words)?", r"speech\s+(?:is\s+)?slurred",
            r"sudden(?:ly)?\s+(?:can'?t|cannot|unable\s+to|not\s+able\s+to)\s+(?:speak|talk)", r"unable\s+to\s+move\s+(?:my|his|her)\s+(?:arm|leg)",
            r"speech\s+(?:is\s+)?(?:unclear|garbled)",
            r"sudden\s+(?:weakness|numbness)", r"one\s+side\s+(?:of\s+(?:my|the|his|her)\s+(?:body|face)\s+)?(?:is\s+)?(?:weak|numb|paraly[sz]ed)",
            r"paraly[sz](?:is|ed|e)", r"mouth\s+(?:is\s+)?(?:deviated|twisted|droop\w*)",
            # Tanglish
            r"pakk?a\s*vaa?(?:th|tth|d|dh)am", r"vaa(?:i|y|yi)\s*kon(?:i|al|ichu|iduchu|ikk?itt?)\w*",
            r"pe?chu\s*kuzh?ar\w*", r"thideer(?:nu|endru)?\s*pesa\s*mudiya(?:la|lai|villai)",
            r"oru\s*pakk?am\s*(?:kai|kaal|udambu|udal)?\s*(?:asaiya\w*|marathu\w*|maraththu\w*|velai\s*seyya\w*|seyal\s*izh\w*)",
        )
        + _ta(
            r"பக்கவாதம்", r"வாய்\s*கோண", r"முகம்\s*கோண", r"பேச்சு\s*குழற", r"திடீர்(?:னு|என்று)?\s*பேச\s*முடிய(?:வில்லை|லை|ல)",
            r"ஒரு\s*பக்கம்?\s*(?:கை|கால்|உடம்பு|உடல்)?\s*(?:அசைய|மரத்து|செயலிழ|வேலை\s*செய்ய)",
            r"கை\s*கால்\s*செயலிழ",
        )
    )),
    # ── Heavy bleeding ────────────────────────────────────────────────────────
    Rule("heavy_bleeding", "Heavy bleeding", "emergency", tuple(
        _en(
            r"heavy\s+bleeding", r"bleeding\s+(?:heavily|a\s+lot|badly|profusely|non\s*stop)", r"profuse\s+bleeding",
            r"severe\s+bleeding", r"uncontrolled\s+bleeding", r"lots?\s+of\s+blood",
            r"bleeding\s+(?:that\s+)?(?:won'?t|will\s+not|doesn'?t|does\s+not|is\s+not|isn'?t)\s+stop\w*",
            r"(?:won'?t|will\s+not)\s+stop\s+bleeding", r"vomit(?:ing|ed|s)?\s+blood", r"blood\s+(?:in\s+)?vomit\w*",
            r"cough(?:ing|ed|s)?\s+(?:up\s+)?blood", r"spurting\s+blood",
            # Tanglish
            r"niraiya?\s*(?:" + _RATHAM + "|blood)", _RATHAM + r"\s*niraiya?", _RATHAM + r"\s*(?:nikk?a(?:la|lai|villai)|nikkave\s*illa)",
            _RATHA + r"\s*vaa?n(?:th|dh)i", _RATHAM + r"\s*kott\w*", _RATHA + r"\s*pokku\s*(?:athigam|adhigam|niraiya)",
        )
        + _ta(
            r"நிறைய\s*இ?ரத்தம்", r"இ?ரத்தம்\s*நிறைய", r"அதிக\s*இ?ரத்தப்?\s*போக்கு", r"இ?ரத்தம்\s*நிற்க(?:வில்லை|லை|ல)",
            r"இ?ரத்த\s*வாந்தி", r"இ?ரத்தம்\s*கொட்டு", r"இ?ரத்தம்\s*வாந்தி",
        )
    )),
    # ── Burns / electric shock ────────────────────────────────────────────────
    Rule("severe_burns", "Severe burns / electric shock", "emergency", tuple(
        _en(
            r"severe(?:ly)?\s+burn\w*", r"bad(?:ly)?\s+burn\w*", r"major\s+burns?", r"burn\w*\s+(?:all\s+over|whole\s+body)",
            r"fire\s+accident", r"acid\s+(?:attack|burn\w*)", r"electric(?:al)?\s+(?:shock|burn\w*)", r"electrocut\w*",
            r"current\s+(?:shock|adich\w*|adichu\w*|pudich\w*)",
        )
        + _ta(
            r"தீ\s*விபத்து", r"(?:பெரிய|கடுமையான|உடல்\s*முழு[^\s]*)\s*தீக்?\s*காயம்", r"மின்சாரம்\s*தாக்", r"கரண்ட்\s*(?:அடி|ஷாக்)",
            r"ஆசிட்\s*(?:வீச்சு|பட்டு|ஊத்தி)",
        )
    )),
    Rule("burns", "Burn injury", "urgent", tuple(
        _en(
            r"(?:got|have|has|had)\s+(?:a\s+)?burn(?:s|t|ed)?", r"burn\s+injur\w*", r"burnt\s+(?:my|his|her)",
            r"scald(?:ed|s)?", r"th?ee\s*k?k?aa?yam", r"th?ee\s*pattu", r"theeppattu",
        )
        + _ta(r"தீக்?\s*காயம்", r"தீப்பட்டு", r"தீ\s*பட்டு", r"சுடு\s*தண்ணீர்\s*(?:கொட்டி|பட்டு)")
    )),
    # ── Poisoning / overdose / envenomation ───────────────────────────────────
    Rule("poisoning", "Poisoning / overdose / bite", "emergency", tuple(
        _en(
            r"(?<!food\s)poison(?:ed|ing|ous)?", r"over\s*dose\w*",
            r"(?:swallowed|drank|drunk|ate|consumed|took)\s+(?:some\s+|a\s+lot\s+of\s+|many\s+|too\s+many\s+)?(?:pills|tablets|poison|acid|kerosene|pesticide|insecticide|phenyl|bleach|chemicals?)",
            r"pesticide", r"insecticide", r"rat\s+poison", r"snake\s*bit\w*", r"bitten\s+by\s+(?:a\s+)?snake",
            r"scorpion\s+(?:bite|sting)\w*",
            # Tanglish
            r"visham\w*", r"poochi\s*marun\w*", r"eli\s*(?:marun\w*|paa?shanam)",
            r"paa?mbu\s*kad\w*", r"th?el\s*(?:kad\w*|kott\w*)", r"mannenn?ai\s*kud\w*",
        )
        + _ta(
            r"விஷம்", r"விஷத்தை", r"விஷம்\s*குடி", r"பூச்சி\s*மருந்து", r"பூச்சிக்கொல்லி", r"எலி\s*(?:மருந்து|பாஷாணம்)",
            r"பாம்பு\s*கடி", r"தேள்\s*(?:கடி|கொட்டி)", r"மண்ணெண்ணெய்\s*குடி",
            r"(?:நிறைய|அதிகமா|அதிகமாக)\s*மாத்திரை\s*(?:சாப்பிட்|போட்|முழுங்)",
        )
    )),
    # ── Suicidal thoughts / self-harm ─────────────────────────────────────────
    Rule("suicidal", "Suicidal thoughts / self-harm", "emergency", tuple(
        _en(
            r"suicid(?:e|al)", r"kill\s+(?:my\s*self|myself)", r"end\s+(?:my|it)\s+(?:life|all)", r"want\s+to\s+die",
            r"wanna\s+die", r"don'?t\s+want\s+to\s+live", r"self[\s-]*harm\w*", r"hurt(?:ing)?\s+myself",
            r"cut(?:ting)?\s+myself", r"take\s+my\s+(?:own\s+)?life",
            # Tanglish
            r"thar\s*kolai", r"tharkolai", r"saaga(?:num|nu|poren|porean|venum|ponum)", r"saga(?:num|poren|venum)",
            r"seth?h?(?:u|th)?d(?:a|u)(?:lam|laam|ven|reen)", r"vaazha?\s*pidikk?a(?:la|lai|villai)",
        )
        + _ta(
            r"தற்கொலை", r"சாகணும்", r"சாக\s*வேண்டும்", r"சாகப்\s*போ", r"செத்துடலாம்", r"செத்துப்\s*போக",
            r"உயிரை\s*மாய்", r"வாழ\s*பிடிக்க(?:வில்லை|லை|ல)", r"வாழ\s*விருப்பம்\s*இல்லை",
            r"என்னை\s*நானே\s*(?:காயப்படுத்த|கொல்ல)",
        )
    )),
    # ── Severe allergic reaction ──────────────────────────────────────────────
    Rule("anaphylaxis", "Possible severe allergic reaction", "emergency", tuple(
        _en(
            r"anaphyla\w*", r"throat\s+(?:is\s+)?(?:swelling|swollen|closing)", r"tongue\s+(?:is\s+)?(?:swelling|swollen)",
            r"lips?\s+(?:and\s+\w+\s+)?(?:swelling|swollen)",
        )
        + _ta(r"நாக்கு\s*வீங்", r"தொண்டை\s*வீங்கி\s*மூச்சு")
    )),
    # ── Injury ────────────────────────────────────────────────────────────────
    Rule("trauma", "Accident / head injury", "urgent", tuple(
        _en(
            r"(?:road|bike|car|bus|traffic)\s+accident", r"accident", r"head\s+injur\w*", r"hit\s+(?:my|his|her)\s+head",
            r"thalai(?:yil|la|le)?\s*(?:adi|adipattu|kaayam)\w*", r"vi(?:b|p)a(?:th|tth)u",
        )
        + _ta(r"விபத்து", r"தலையில்\s*(?:அடி|காயம்)", r"தலைல\s*அடி")
    )),
    Rule("thunderclap_headache", "Sudden severe headache", "urgent", tuple(
        _en(r"worst\s+headache", r"sudden\s+(?:severe|terrible|very\s+bad)\s+headache", r"thunderclap")
    )),
)

# ── Composite rules (need two or three concepts in the same text) ────────────

_PREGNANCY = tuple(
    _en(
        r"pregnan(?:t|cy)", r"expecting\s+(?:a\s+)?baby", r"antenatal", r"\d+\s*(?:months?|weeks?)\s+pregnant",
        r"karp?p?am\w*", r"garbh?am\w*", r"maa?sa?ma\s*irukk?\w*", r"muzhu?gaa?ma\w*",
    )
    + _ta(r"கர்ப்ப", r"கர்ப்பிணி", r"மாசமா\s*இருக்", r"முழுகாம", r"கரு\s*(?:உண்டா|தரி)")
)
_BLEEDING = tuple(
    _en(r"bleed\w*", _BLOOD, r"spotting", _RATHAM, _RATHA + r"\s*pokku", r"u(?:dh|th)ira\s*pokku")
    + _ta(r"இ?ரத்த(?!\s*(?:அழுத்த|பரிசோதனை|சர்க்கரை|வகை|டெஸ்ட்))", r"உதிரப்?\s*போக்கு")
)
_WATER_BROKE = tuple(
    _en(r"water\s+(?:has\s+)?(?:broke|broken|break|leak\w*)", r"pani\s*kudam\s*\w*", r"panikudam\w*")
    + _ta(r"பனிக்குடம்", r"பனிக்\s*குடம்")
)
_BABY_NOT_MOVING = tuple(
    _en(r"baby\s+(?:is\s+)?not\s+moving", r"no\s+(?:fetal|foetal|baby)\s+movements?", r"reduced\s+(?:fetal|foetal|baby)\s+movements?",
        _KUZHANTHAI + r"\s*asai(?:yala|yalai|vu\s*illa\w*|ve\s*illa\w*)")
    + _ta(r"குழந்தை\s*அசை(?:வு\s*இல்ல|யல|யவில்லை)")
)

_CHILD = tuple(
    _en(
        r"child(?:ren)?", r"baby", r"babies", r"infant", r"toddler", r"new\s*born", r"newborn", r"kid", r"kids",
        r"my\s+(?:son|daughter|boy|girl)", r"\d+\s*(?:month|year)s?\s*old\s+(?:son|daughter|boy|girl|child)",
        _KUZHANTHAI, r"pa?appa", r"paiyan", r"magan", r"magal",
    )
    + _ta(r"குழந்தை", r"பாப்பா", r"மகன்", r"மகள்", r"பையன்", r"கைக்குழந்தை")
)
_INFANT = tuple(
    _en(r"new\s*born", r"newborn", r"\d+\s*(?:week|day)s?\s*old", r"(?<!\d)[0-2]\s*months?\s*old", r"kai\s*" + _KUZHANTHAI)
    + _ta(r"கைக்குழந்தை", r"பிறந்த\s*குழந்தை")
)
_FEVER = tuple(
    _en(r"fever\w*", r"temperature", r"kaa?(?:i|y)ch(?:a|e)l", r"jw?aram", r"juram", r"suram")
    + _ta(r"காய்ச்சல்", r"ஜுரம்", r"ஜூரம்", r"சுரம்")
)
_LETHARGY = tuple(
    _en(
        r"letharg(?:y|ic)", r"drowsy", r"floppy", r"limp", r"very\s+(?:sleepy|weak|tired|dull)", r"(?:too|extremely)\s+sleepy",
        r"sleeping\s+all\s+(?:the\s+)?(?:time|day)", r"hard\s+to\s+wake", r"not\s+(?:active|alert|playing|feeding|drinking|eating)",
        r"(?:won'?t|will\s+not|refus\w+\s+to)\s+(?:feed|drink|eat)",
        r"sornth?\w*", r"sorv(?:a|aa|u|aaga|aga)\w*", r"mandham\w*", r"thoongi\w*\s*(?:kitte|kittey)?\s*iruk\w*",
        r"paal\s*kudikk?a(?:la|lai|villai)", r"saapda(?:la|lai|ve\s*illa)", r"vilayada(?:la|lai|villai)",
    )
    + _ta(
        r"சோர்வ", r"சோர்ந்து", r"மந்தமா", r"தூங்கிக்கிட்டே", r"பால்\s*குடிக்க(?:வில்லை|லை|ல)",
        r"சாப்பிட(?:வில்லை|லை|ல)", r"விளையாட(?:வில்லை|லை|ல)", r"எழுந்திருக்க(?:வில்லை|லை|ல)",
    )
)


def detect_red_flags(text: Optional[str], age: Optional[int] = None) -> dict:
    """Detect red flags in free-text symptoms.

    Returns {"flags": [code...], "matches": [{code,label,urgency,term}], "urgency": "emergency"|"urgent"|None}.
    """
    norm = _normalise(text or "")
    clauses = _clauses(norm)
    matches: list[dict] = []

    def add(code: str, label: str, urgency: str, term: str) -> None:
        matches.append({"code": code, "label": label, "urgency": urgency, "term": term})

    if clauses:
        for rule in RULES:
            term = _find(rule.patterns, clauses)
            if term:
                add(rule.code, rule.label, rule.urgency, term)

        # Pregnancy + bleeding / waters broken / reduced fetal movement.
        preg = _find(_PREGNANCY, clauses)
        water = _find(_WATER_BROKE, clauses)
        if water:
            add("pregnancy_waters", "Waters broken / leaking (pregnancy)", "emergency", water)
        if preg:
            bleed = _find(_BLEEDING, clauses)
            if bleed:
                add("pregnancy_bleeding", "Bleeding in pregnancy", "emergency", f"{preg} + {bleed}")
            not_moving = _find(_BABY_NOT_MOVING, clauses)
            if not_moving:
                add("reduced_fetal_movement", "Reduced fetal movement", "urgent", not_moving)

        # Child with fever + lethargy; any fever in a young infant.
        is_child = (age is not None and age < CHILD_AGE_YEARS) or _find(_CHILD, clauses) is not None
        fever = _find(_FEVER, clauses)
        if is_child and fever:
            lethargy = _find(_LETHARGY, clauses)
            if lethargy:
                add("child_fever_lethargy", "Child with fever and lethargy", "urgent", f"{fever} + {lethargy}")
            infant = _find(_INFANT, clauses)
            if infant or (age is not None and age < 1):
                add("infant_fever", "Fever in a young infant", "urgent", f"{infant or 'age<1'} + {fever}")

    # De-duplicate: severe variant supersedes its milder sibling.
    codes = {m["code"] for m in matches}
    superseded = {"breathlessness": "severe_breathlessness", "fainting": "unconscious", "burns": "severe_burns"}
    matches = [m for m in matches if not (m["code"] in superseded and superseded[m["code"]] in codes)]

    urgency = None
    for m in matches:
        urgency = max_urgency(urgency, m["urgency"])
    return {"flags": [m["code"] for m in matches], "matches": matches, "urgency": urgency}


# ═══════════════════════════════════════════════════════════════════════════════
# NEWS2 (Royal College of Physicians, 2017) — SpO2 scale 1
# ═══════════════════════════════════════════════════════════════════════════════

NEWS2_PARAMS = ("resp_rate", "spo2", "bp_sys", "pulse", "temperature")


def _num(v) -> Optional[float]:
    if v is None or isinstance(v, bool):
        return None
    try:
        return float(v)
    except (TypeError, ValueError):
        return None


def _score_resp_rate(rr: float) -> int:
    if rr <= 8:
        return 3
    if rr <= 11:
        return 1
    if rr <= 20:
        return 0
    if rr <= 24:
        return 2
    return 3


def _score_spo2(s: float) -> int:  # scale 1
    if s <= 91:
        return 3
    if s <= 93:
        return 2
    if s <= 95:
        return 1
    return 0


def _score_bp_sys(bp: float) -> int:
    if bp <= 90:
        return 3
    if bp <= 100:
        return 2
    if bp <= 110:
        return 1
    if bp <= 219:
        return 0
    return 3


def _score_pulse(p: float) -> int:
    if p <= 40:
        return 3
    if p <= 50:
        return 1
    if p <= 90:
        return 0
    if p <= 110:
        return 1
    if p <= 130:
        return 2
    return 3


def _score_temperature(t: float) -> int:
    if t <= 35.0:
        return 3
    if t <= 36.0:
        return 1
    if t <= 38.0:
        return 0
    if t <= 39.0:
        return 1
    return 2


_SCORERS = {
    "resp_rate": _score_resp_rate,
    "spo2": _score_spo2,
    "bp_sys": _score_bp_sys,
    "pulse": _score_pulse,
    "temperature": _score_temperature,
}


def news2(vitals: Optional[dict]) -> Optional[dict]:
    """NEWS2 from a vitals dict, or None when no NEWS2 parameter is present.

    Consciousness (assumed Alert) and supplemental O2 (assumed air) are not
    captured, so `partial` is always true; `missing` lists absent parameters.
    """
    if not vitals:
        return None
    points: dict[str, int] = {}
    missing: list[str] = []
    for key in NEWS2_PARAMS:
        val = _num(vitals.get(key))
        if val is None or val <= 0:
            missing.append(key)
            continue
        points[key] = _SCORERS[key](val)
    if not points:
        return None
    points["consciousness"] = 0  # assumed Alert (not captured)
    points["supplemental_o2"] = 0  # assumed room air (not captured)
    score = sum(points.values())
    any_three = any(p == 3 for p in points.values())
    if score >= 7:
        band = "high"
    elif score >= 5:
        band = "medium"
    elif any_three:
        band = "low-medium"
    else:
        band = "low"
    return {
        "score": score,
        "points": points,
        "band": band,
        "any_single_3": any_three,
        "partial": True,
        "missing": missing + ["consciousness", "supplemental_o2"],
    }


def news2_urgency(result: Optional[dict]) -> Optional[str]:
    if not result:
        return None
    if result["band"] == "high":
        return "emergency"
    if result["band"] in ("medium", "low-medium") or result["any_single_3"]:
        return "urgent"
    return None


# ═══════════════════════════════════════════════════════════════════════════════
# Escalation
# ═══════════════════════════════════════════════════════════════════════════════

def escalate(
    llm_urgency: Optional[str],
    symptoms: Optional[str],
    vitals: Optional[dict] = None,
    age: Optional[int] = None,
    llm_label: str = "AI triage",
) -> dict:
    """Combine LLM urgency, red flags and NEWS2 into a final urgency the client cannot lower.

    Returns {"urgency", "escalation_reasons": [str], "red_flags": [code], "news2": dict|None}.
    """
    reasons: list[str] = []
    base = llm_urgency if llm_urgency in URGENCY_ORDER else "normal"
    if base != "normal":
        reasons.append(f"{llm_label}: {base}")

    flags = detect_red_flags(symptoms, age=age)
    for m in flags["matches"]:
        reasons.append(f"Red flag ({m['urgency']}): {m['label']} [{m['term']}]")

    n2 = news2(vitals)
    n2_urg = news2_urgency(n2)
    if n2_urg:
        threes = [k for k, p in n2["points"].items() if p == 3]
        detail = f"; score 3 in {', '.join(threes)}" if threes else ""
        reasons.append(f"NEWS2 {n2['score']} ({n2['band']}{detail}, partial) -> {n2_urg}")

    final = max_urgency(base, flags["urgency"], n2_urg)
    return {"urgency": final, "escalation_reasons": reasons, "red_flags": flags["flags"], "news2": n2}


# ═══════════════════════════════════════════════════════════════════════════════
# Keyword department routing (LLM fallback)
# ═══════════════════════════════════════════════════════════════════════════════

_DEPT_KEYWORDS: tuple[tuple[str, tuple[re.Pattern, ...]], ...] = (
    ("gyne", tuple(
        _en(r"pregnan\w*", r"periods?", r"menstru\w*", r"pcos", r"pcod", r"white\s+discharge", r"vaginal\w*",
            r"g?karp?p?am\w*", r"maadha?vidaai?", r"maathavidai", r"maasama\s*irukk?\w*")
        + _ta(r"கர்ப்ப", r"மாதவிடாய்", r"மாசமா\s*இருக்", r"வெள்ளைப்படு")
    )),
    ("paeds", _CHILD),
    ("cardio", tuple(
        _en(r"chest\s*pain\w*", r"palpitation\w*", r"heart(?:beat)?", r"nenj(?:u|i)?\s*vali(?!\w*ill)\w*", r"padapadapp?u", r"i(?:r|ru)(?:dh|th)aya\w*")
        + _ta(r"நெஞ்சு\s*வலி", r"இதய", r"படபடப்பு", r"மார்பு\s*வலி")
    )),
    ("ortho", tuple(
        _en(r"joint\w*", r"knee\w*", r"back\s*pain", r"neck\s*pain", r"shoulder\w*", r"fractur\w*", r"sprain\w*",
            r"bone\w*", r"hip\s*pain", r"mutt?i\s*vali(?!\w*ill)\w*", r"idupp?u\s*vali(?!\w*ill)\w*", r"mudhugu\s*vali(?!\w*ill)\w*", r"kazhuthu\s*vali(?!\w*ill)\w*",
            r"elumbu\w*")
        + _ta(r"மூட்டு\s*வலி", r"முழங்கால்", r"இடுப்பு\s*வலி", r"முதுகு\s*வலி", r"கழுத்து\s*வலி", r"எலும்பு")
    )),
    ("derm", tuple(
        _en(r"rash\w*", r"itch\w*", r"skin\w*", r"eczema", r"psoriasis", r"acne", r"pimple\w*", r"hair\s*fall",
            r"arippu", r"sori\w*", r"thadippu", r"thol\s*(?:noi|arippu|pirachanai)")
        + _ta(r"அரிப்பு", r"தோல்", r"சொறி", r"தடிப்பு", r"முடி\s*கொட்டு")
    )),
    ("ophthal", tuple(
        _en(r"eyes?", r"vision", r"blurr\w*", r"cataract", r"kann?u?\s*(?:vali|erichal|sivapp?u|theriya\w*|arippu)")
        + _ta(r"கண்", r"பார்வை")
    )),
    ("ent", tuple(
        _en(r"ears?", r"hearing", r"deaf\w*", r"sinus\w*", r"tonsil\w*", r"vertigo",
            r"kaa?(?:dh|th)u\s*(?:vali\w*|ketk?a\w*|kekk?a\w*|seezh\w*|adaippu)")
        + _ta(r"காது", r"காதில்", r"சைனஸ்")
    )),
)


def keyword_department(text: Optional[str], age: Optional[int] = None) -> str:
    """Best-effort department id from keywords; "general" when nothing matches."""
    if age is not None and age < CHILD_AGE_YEARS:
        return "paeds"
    clauses = _clauses(_normalise(text or ""))
    if not clauses:
        return "general"
    for dept_id, patterns in _DEPT_KEYWORDS:
        if _find(patterns, clauses):
            return dept_id
    return "general"

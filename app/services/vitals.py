"""Clinical flag computation for vitals readings."""

from __future__ import annotations


def compute_flags(vitals: dict) -> dict:
    """Compute BMI and clinical flags from raw vitals values."""
    flags: list[str] = []
    bmi = None

    h = vitals.get("height")
    w = vitals.get("weight")
    if h and w and h > 0:
        bmi = round(w / ((h / 100) ** 2), 1)
        if bmi < 18.5:
            flags.append("Underweight")
        elif bmi >= 30:
            flags.append("Obese")
        elif bmi >= 25:
            flags.append("Overweight")

    bp_sys = vitals.get("bp_sys")
    bp_dia = vitals.get("bp_dia")
    if bp_sys:
        if bp_sys >= 180 or (bp_dia and bp_dia >= 120):
            flags.append("Hypertensive Crisis")
        elif bp_sys >= 140 or (bp_dia and bp_dia >= 90):
            flags.append("Stage 2 Hypertension")
        elif bp_sys >= 130 or (bp_dia and bp_dia >= 80):
            flags.append("Stage 1 Hypertension")
        elif bp_sys < 90:
            flags.append("Low BP")

    spo2 = vitals.get("spo2")
    if spo2:
        if spo2 < 90:
            flags.append("Critical SpO₂ — Needs Oxygen")
        elif spo2 < 95:
            flags.append("Low SpO₂")

    pulse = vitals.get("pulse")
    if pulse:
        if pulse > 120:
            flags.append("Severe Tachycardia")
        elif pulse > 100:
            flags.append("Tachycardia")
        elif pulse < 50:
            flags.append("Bradycardia")

    temp = vitals.get("temperature")
    if temp:
        if temp >= 39.5:
            flags.append("High Fever")
        elif temp >= 38.0:
            flags.append("Fever")
        elif temp < 35.0:
            flags.append("Hypothermia")

    rr = vitals.get("resp_rate")
    if rr:
        if rr > 24:
            flags.append("Rapid Breathing")
        elif rr < 10:
            flags.append("Slow Breathing")

    glucose = vitals.get("glucose")
    if glucose:
        if glucose >= 300:
            flags.append("Very High Blood Sugar")
        elif glucose >= 200:
            flags.append("High Blood Sugar")
        elif glucose < 70:
            flags.append("Low Blood Sugar")

    if vitals.get("diabetes"):
        flags.append("Known Diabetic")
    if vitals.get("hypertension"):
        flags.append("Known Hypertensive")

    return {"bmi": bmi, "flags": flags}

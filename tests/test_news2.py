import pytest

from app.services.clinical_rules import news2, news2_urgency


@pytest.mark.parametrize("value,points", [
    (8, 3), (9, 1), (11, 1), (12, 0), (20, 0), (21, 2), (24, 2), (25, 3), (40, 3),
])
def test_resp_rate(value, points):
    assert news2({"resp_rate": value})["points"]["resp_rate"] == points


@pytest.mark.parametrize("value,points", [
    (85, 3), (91, 3), (92, 2), (93, 2), (94, 1), (95, 1), (96, 0), (100, 0),
])
def test_spo2_scale1(value, points):
    assert news2({"spo2": value})["points"]["spo2"] == points


@pytest.mark.parametrize("value,points", [
    (80, 3), (90, 3), (91, 2), (100, 2), (101, 1), (110, 1), (111, 0), (219, 0), (220, 3),
])
def test_systolic_bp(value, points):
    assert news2({"bp_sys": value})["points"]["bp_sys"] == points


@pytest.mark.parametrize("value,points", [
    (35, 3), (40, 3), (41, 1), (50, 1), (51, 0), (90, 0), (91, 1), (110, 1), (111, 2), (130, 2), (131, 3),
])
def test_pulse(value, points):
    assert news2({"pulse": value})["points"]["pulse"] == points


@pytest.mark.parametrize("value,points", [
    (34.0, 3), (35.0, 3), (35.1, 1), (36.0, 1), (36.1, 0), (38.0, 0), (38.1, 1), (39.0, 1), (39.1, 2), (41.0, 2),
])
def test_temperature(value, points):
    assert news2({"temperature": value})["points"]["temperature"] == points


def test_no_params_returns_none():
    assert news2(None) is None
    assert news2({}) is None
    assert news2({"bp_dia": 80, "glucose": 100}) is None
    assert news2_urgency(None) is None


def test_normal_vitals_low_band_and_partial():
    r = news2({"resp_rate": 16, "spo2": 98, "bp_sys": 120, "pulse": 72, "temperature": 36.8})
    assert r["score"] == 0
    assert r["band"] == "low"
    assert r["partial"] is True
    assert r["points"]["consciousness"] == 0 and r["points"]["supplemental_o2"] == 0
    assert set(r["missing"]) == {"consciousness", "supplemental_o2"}
    assert news2_urgency(r) is None


def test_missing_params_listed():
    r = news2({"spo2": 97})
    assert "pulse" in r["missing"] and "resp_rate" in r["missing"]


def test_band_low_medium_single_three():
    r = news2({"spo2": 91, "pulse": 70})
    assert r["score"] == 3
    assert r["band"] == "low-medium"
    assert news2_urgency(r) == "urgent"


def test_band_low_score_4():
    r = news2({"resp_rate": 22, "pulse": 115})  # 2 + 2
    assert r["score"] == 4
    assert r["band"] == "low"
    assert news2_urgency(r) is None


def test_band_medium():
    r = news2({"resp_rate": 22, "pulse": 115, "temperature": 38.5})  # 2 + 2 + 1
    assert r["score"] == 5
    assert r["band"] == "medium"
    assert news2_urgency(r) == "urgent"


def test_band_high():
    r = news2({"resp_rate": 25, "spo2": 93, "pulse": 115})  # 3 + 2 + 2
    assert r["score"] == 7
    assert r["band"] == "high"
    assert news2_urgency(r) == "emergency"


def test_ignores_bad_values():
    r = news2({"spo2": "abc", "pulse": 0, "temperature": True, "resp_rate": 18})
    assert r["points"] == {"resp_rate": 0, "consciousness": 0, "supplemental_o2": 0}

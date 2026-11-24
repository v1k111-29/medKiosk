"""Server-side escalation in /conversation/triage (LLM unavailable in tests) and /appointment/book."""


def _patient(client, age=40, name="Safety Test"):
    r = client.post("/register", json={"name": name, "age": age, "face_consent": False})
    assert r.status_code == 200, r.text
    return r.json()["id"]


def test_triage_falls_back_to_rules_when_llm_unavailable(client):
    r = client.post("/conversation/triage", json={"text": "knee pain after a fall"})
    assert r.status_code == 200
    body = r.json()
    assert body["intent"] == "symptoms"
    assert body["dept_id"] == "ortho"
    assert body["urgency"] == "normal"
    assert any("rule-based" in x for x in body["escalation_reasons"])
    assert body["disclaimer"]["en"] == "This is not a diagnosis."


def test_triage_red_flag_forces_emergency(client):
    r = client.post("/conversation/triage", json={"text": "nenju vali and sweating"})
    body = r.json()
    assert body["urgency"] == "emergency"
    assert body["dept_id"] == "emergency"
    assert body["intent"] == "emergency"
    assert "chest_pain" in body["red_flags"]
    assert body["room"] == "ER-1"


def test_triage_uses_todays_vitals(client):
    pid = _patient(client)
    v = client.post("/vitals", json={"patient_id": pid, "spo2": 90, "pulse": 80})
    assert v.status_code == 200
    assert v.json()["news2"]["points"]["spo2"] == 3
    body = client.post("/conversation/triage", json={"text": "cough", "patient_id": pid}).json()
    assert body["urgency"] == "urgent"
    assert body["news2"]["band"] == "low-medium"


def test_vitals_range_validation(client):
    pid = _patient(client)
    assert client.post("/vitals", json={"patient_id": pid, "temperature": 98.6}).status_code == 422
    assert client.post("/vitals", json={"patient_id": pid, "pulse": 400}).status_code == 422
    ok = client.post("/vitals", json={"patient_id": pid, "temperature": 37.0, "resp_rate": 16, "glucose": 110})
    assert ok.status_code == 200


def test_book_client_cannot_downgrade_red_flag(client):
    pid = _patient(client)
    r = client.post("/appointment/book", json={
        "patient_id": pid, "dept_id": "general", "symptoms": "chest pain since 1 hour", "urgency": "normal",
    })
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["urgency"] == "emergency"
    assert body["dept_id"] == "emergency"
    assert body["wait_mins"] == 0
    assert any("Chest pain" in x for x in body["escalation_reasons"])

    appt = client.get(f"/appointment/{body['appointment_id']}").json()
    assert isinstance(appt["escalation_reasons"], list) and appt["escalation_reasons"]


def test_book_news2_escalates_to_urgent(client):
    pid = _patient(client)
    client.post("/vitals", json={"patient_id": pid, "bp_sys": 88})
    body = client.post("/appointment/book", json={
        "patient_id": pid, "dept_id": "general", "symptoms": "tiredness", "urgency": "normal",
    }).json()
    assert body["urgency"] == "urgent"
    assert body["dept_id"] == "general"


def test_book_plain_stays_normal(client):
    pid = _patient(client)
    body = client.post("/appointment/book", json={
        "patient_id": pid, "dept_id": "general", "symptoms": "fever and cold",
    }).json()
    assert body["urgency"] == "normal"
    assert body["escalation_reasons"] == []


def test_book_keeps_client_upgrade(client):
    pid = _patient(client)
    body = client.post("/appointment/book", json={
        "patient_id": pid, "dept_id": "general", "symptoms": "fever", "urgency": "urgent",
    }).json()
    assert body["urgency"] == "urgent"

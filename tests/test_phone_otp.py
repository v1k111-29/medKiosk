"""Phone OTP identification, face consent on /register, and admin face deletion."""

from datetime import timedelta

import pytest
from sqlalchemy import select

from app.core.database import session_scope
from app.core.models import FaceEmbedding, Patient, PhoneOtp
from app.core.security import create_phone_verification_token, create_access_token, verified_phone_from_token
from app.services import otp_service
from app.services.sms import normalize_phone_in

CODE = "123456"


@pytest.fixture(autouse=True)
def fixed_otp(monkeypatch):
    monkeypatch.setattr(otp_service, "generate_otp", lambda: CODE)


def _start(client, phone):
    return client.post("/identify/phone/start", json={"phone": phone})


def _verify(client, phone, otp=CODE):
    return client.post("/identify/phone/verify", json={"phone": phone, "otp": otp})


DEFAULT_PHONE = "9876599999"


def _register(client, **kw):
    """Register; without a face template, attach a phone-verification token for the phone."""
    body = {"name": "Test Patient", "gender": "Woman", "age": 34, "face_consent": False}
    body.update(kw)
    if not (body["face_consent"] and body.get("embedding")):
        body.setdefault("phone", DEFAULT_PHONE)
        body.setdefault("phone_verification_token", create_phone_verification_token(normalize_phone_in(body["phone"])))
    return client.post("/register", json=body)


def test_start_same_response_for_known_and_unknown(client):
    _register(client, phone="9876500001")
    known = _start(client, "9876500001")
    unknown = _start(client, "9876500002")
    assert known.status_code == unknown.status_code == 200
    assert known.json() == unknown.json() == {"status": "otp_sent"}


def test_otp_is_stored_hashed(client):
    _start(client, "9876500003")
    with session_scope() as s:
        row = s.scalars(select(PhoneOtp).where(PhoneOtp.phone == "+919876500003")).first()
        assert row is not None
        assert CODE not in row.otp_hash
        assert len(row.otp_hash) == 64


def test_invalid_phone_rejected(client):
    r = _start(client, "12345")
    assert r.status_code in (400, 422)
    r = _start(client, "1234567890")  # Indian mobiles start with 6-9
    assert r.status_code == 400


def test_unknown_phone_verifies_as_new(client):
    phone = "9876500010"
    assert _start(client, phone).status_code == 200
    r = _verify(client, phone)
    assert r.status_code == 200
    body = r.json()
    assert {k: body[k] for k in ("status", "phone")} == {"status": "new", "phone": "+919876500010"}
    assert verified_phone_from_token(body["phone_verification_token"]) == "+919876500010"


def test_known_phone_verifies_as_found(client):
    reg = _register(client, name="Meena", phone="+91 98765 00020")
    pid = reg.json()["id"]
    _start(client, "09876500020")  # different formatting of the same number
    r = _verify(client, "9876500020")
    assert r.status_code == 200
    body = r.json()
    assert body["status"] == "found"
    assert body["id"] == pid
    assert body["name"] == "Meena"
    assert {"gender", "age", "phone", "visits"} <= body.keys()
    assert body["other_patients"] == []


def test_shared_phone_lists_other_patients(client):
    a = _register(client, name="Parent", phone="9876500030").json()["id"]
    b = _register(client, name="Child", age=6, phone="9876500030").json()["id"]
    _start(client, "9876500030")
    body = _verify(client, "9876500030").json()
    assert body["status"] == "found"
    assert {body["id"], *(p["id"] for p in body["other_patients"])} == {a, b}


def test_code_is_single_use(client):
    phone = "9876500040"
    _start(client, phone)
    assert _verify(client, phone).status_code == 200
    assert _verify(client, phone).status_code == 400


def test_wrong_code_counts_attempts_then_locks(client):
    phone = "9876500050"
    _start(client, phone)
    for left in (4, 3, 2, 1):
        r = _verify(client, phone, "000000")
        assert r.status_code == 400
        assert f"{left} attempt" in r.json()["message"]["en"]
    r = _verify(client, phone, "000000")
    assert r.status_code == 429
    # Even the right code no longer works after lock-out.
    assert _verify(client, phone).status_code == 400


def test_expired_code(client):
    phone = "9876500060"
    _start(client, phone)
    with session_scope() as s:
        row = s.scalars(select(PhoneOtp).where(PhoneOtp.phone == "+919876500060")).first()
        row.expires_at = row.created_at - timedelta(seconds=1)
    r = _verify(client, phone)
    assert r.status_code == 400
    assert "expired" in r.json()["message"]["en"]


def test_new_code_invalidates_previous(client, monkeypatch):
    phone = "9876500070"
    _start(client, phone)
    monkeypatch.setattr(otp_service, "generate_otp", lambda: "654321")
    _start(client, phone)
    assert _verify(client, phone, CODE).status_code == 400
    assert _verify(client, phone, "654321").status_code == 200


def test_start_rate_limited_per_phone(client):
    phone = "9876500080"
    for _ in range(otp_service.OTP_RATE_LIMIT):
        assert _start(client, phone).status_code == 200
    r = _start(client, phone)
    assert r.status_code == 429
    # Another number is unaffected.
    assert _start(client, "9876500081").status_code == 200


# ── /register consent ─────────────────────────────────────────────────────────

def test_register_requires_explicit_face_consent(client):
    r = client.post("/register", json={"name": "No Consent Field"})
    assert r.status_code == 422


def _fake_embedding_hex() -> str:
    import numpy as np

    return np.ones(512, dtype=np.float32).tobytes().hex()


def test_register_without_consent_discards_embedding(client):
    r = _register(client, name="Opt Out", embedding=_fake_embedding_hex(), face_consent=False)
    assert r.status_code == 200
    pid = r.json()["id"]
    with session_scope() as s:
        p = s.get(Patient, pid)
        assert p.face_consent is False
        assert p.embedding is None
        assert p.consent_version is None
        assert s.scalars(select(FaceEmbedding).where(FaceEmbedding.patient_id == pid)).first() is None


def test_register_with_consent_stores_embedding_and_version(client):
    from app.services.face_service import deserialize_embedding

    emb = _fake_embedding_hex()
    if deserialize_embedding(bytes.fromhex(emb)) is None:
        pytest.skip("embedding size differs from face_service expectations")
    r = _register(client, name="Opted In", embedding=emb, face_consent=True)
    assert r.status_code == 200
    pid = r.json()["id"]
    with session_scope() as s:
        p = s.get(Patient, pid)
        assert p.face_consent is True
        assert p.consent_version == "v1-2026-11"
        assert p.consent_at is not None
        assert s.scalars(select(FaceEmbedding).where(FaceEmbedding.patient_id == pid)).first() is not None


def test_admin_deletes_face_data(client, admin_headers):
    from app.services.face_service import deserialize_embedding

    emb = _fake_embedding_hex()
    if deserialize_embedding(bytes.fromhex(emb)) is None:
        pytest.skip("embedding size differs from face_service expectations")
    pid = _register(client, name="Withdraws", embedding=emb, face_consent=True).json()["id"]

    assert client.delete(f"/patients/{pid}/face").status_code == 401
    r = client.delete(f"/patients/{pid}/face", headers=admin_headers)
    assert r.status_code == 200
    assert r.json()["templates_deleted"] >= 1
    with session_scope() as s:
        p = s.get(Patient, pid)
        assert p is not None  # patient record kept
        assert p.face_consent is False
        assert p.embedding is None
        assert s.scalars(select(FaceEmbedding).where(FaceEmbedding.patient_id == pid)).first() is None

    assert client.delete("/patients/999999/face", headers=admin_headers).status_code == 404


# ── /register phone-verification enforcement ──────────────────────────────────

def _register_raw(client, **kw):
    body = {"name": "Raw Patient", "age": 30, "face_consent": False}
    body.update(kw)
    return client.post("/register", json=body)


def test_register_without_face_requires_phone_token(client):
    r = _register_raw(client, phone="9876500100")
    assert r.status_code == 403
    r = _register_raw(client)  # no phone at all
    assert r.status_code == 403


def test_register_consent_without_embedding_still_requires_phone_token(client):
    r = _register_raw(client, phone="9876500101", face_consent=True)
    assert r.status_code == 403


def test_register_rejects_token_for_other_phone(client):
    token = create_phone_verification_token("+919876500102")
    r = _register_raw(client, phone="9876500103", phone_verification_token=token)
    assert r.status_code == 403


def test_register_rejects_bad_or_expired_token(client, monkeypatch):
    from app.core.config import settings

    assert _register_raw(client, phone="9876500104", phone_verification_token="garbage").status_code == 403
    monkeypatch.setattr(settings, "PHONE_VERIFICATION_TOKEN_MINUTES", -1)
    expired = create_phone_verification_token("+919876500104")
    assert _register_raw(client, phone="9876500104", phone_verification_token=expired).status_code == 403


def test_staff_jwt_is_not_a_phone_token(client):
    from app.core.models import User

    with session_scope() as s:
        admin = s.scalars(select(User).where(User.username == "admin")).first()
        staff_token = create_access_token(admin)
    assert verified_phone_from_token(staff_token) is None
    r = _register_raw(client, phone="9876500105", phone_verification_token=staff_token)
    assert r.status_code == 403


def test_otp_flow_token_registers_patient(client):
    phone = "9876500106"
    _start(client, phone)
    token = _verify(client, phone).json()["phone_verification_token"]
    # Different formatting of the same number is accepted; stored as E.164. Reusable within its
    # lifetime so a family sharing one number can register each member.
    r1 = _register_raw(client, name="First", phone="+91 98765 00106", phone_verification_token=token)
    r2 = _register_raw(client, name="Second", phone=phone, phone_verification_token=token)
    assert r1.status_code == r2.status_code == 200
    with session_scope() as s:
        assert s.get(Patient, r1.json()["id"]).phone == "+919876500106"


def test_found_response_includes_phone_token(client):
    _register(client, name="Known", phone="9876500107")
    _start(client, "9876500107")
    body = _verify(client, "9876500107").json()
    assert body["status"] == "found"
    assert verified_phone_from_token(body["phone_verification_token"]) == "+919876500107"


def test_purge_expired_keeps_rate_limit_window(client):
    phone = "+919876500108"
    with session_scope() as s:
        now = otp_service.utcnow()
        old = now - otp_service.OTP_RATE_WINDOW - timedelta(minutes=1)
        recent = now - timedelta(minutes=6)  # expired code, but still inside the rate window
        s.add(PhoneOtp(phone=phone, otp_hash="x" * 64, created_at=old, expires_at=old + otp_service.OTP_TTL))
        s.add(PhoneOtp(phone=phone, otp_hash="y" * 64, created_at=recent, expires_at=recent + otp_service.OTP_TTL))
    with session_scope() as s:
        assert otp_service.purge_expired(s) >= 1
        rows = s.scalars(select(PhoneOtp).where(PhoneOtp.phone == phone)).all()
        assert [r.otp_hash for r in rows] == ["y" * 64]

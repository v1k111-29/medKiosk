"""Face matching safety rules. The face engine is stubbed: no TensorFlow needed."""
import numpy as np
import pytest
from sqlalchemy import func, select

from app.core.database import session_scope
from app.core.models import FaceEmbedding
from app.routers import face as face_router
from app.services import face_service
from app.services.face_service import FaceEngineError, SpoofSuspected, _largest_face, serialize_embedding

IMG = "data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAIAAACQd1PeAAAADElEQVR4nGP4z8AAAAMBAQDJ/pLvAAAAAElFTkSuQmCC"
rng = np.random.default_rng(42)


def unit(v):
    return (v / np.linalg.norm(v)).astype(np.float32)


def at_distance(base, dist):
    """A unit vector whose cosine distance to `base` is exactly `dist`."""
    base = unit(base)
    u = rng.normal(size=512)
    u = unit(u - (u @ base) * base)
    c = 1.0 - dist
    return unit(c * base + np.sqrt(1 - c * c) * u)


def register(client, name, emb, phone):
    r = client.post("/register", json={"name": name, "phone": phone, "face_consent": True,
                                       "embedding": serialize_embedding(emb).hex()})
    assert r.status_code == 200, r.text
    return r.json()["id"]


def gallery_size(pid):
    with session_scope() as s:
        return s.scalar(select(func.count()).select_from(FaceEmbedding).where(FaceEmbedding.patient_id == pid))


@pytest.fixture
def scan(monkeypatch):
    """scan(result) makes the next /identify see `result` (an embedding or an exception)."""
    box = {}

    async def fake(img, anti_spoofing=None):
        if isinstance(box["r"], Exception):
            raise box["r"]
        return box["r"]

    monkeypatch.setattr(face_router, "get_embedding_async", fake)
    monkeypatch.setattr(face_router, "detect_gender_async", lambda img: _async("Unknown"))

    def set_result(r):
        box["r"] = r
    return set_result


async def _async(v):
    return v


def test_largest_face_wins_and_tiny_faces_ignored():
    faces = [
        {"facial_area": {"w": 120, "h": 130}, "id": "small"},
        {"facial_area": {"w": 300, "h": 320}, "id": "big"},
        {"facial_area": {"w": 30, "h": 30}, "id": "tiny"},
    ]
    assert _largest_face(faces)["id"] == "big"
    assert _largest_face([{"facial_area": {"w": 30, "h": 30}}]) is None


def test_borderline_match_does_not_grow_gallery(client, scan):
    base = unit(rng.normal(size=512))
    pid = register(client, "Gallery Guard", base, "9100000001")
    assert gallery_size(pid) == 1

    scan(at_distance(base, 0.40))          # matches (< 0.45) but not clearly
    r = client.post("/identify", json={"image": IMG, "match_only": True}).json()
    assert r["status"] == "found" and r["id"] == pid
    assert gallery_size(pid) == 1

    scan(at_distance(base, 0.10))          # clearly the same person
    client.post("/identify", json={"image": IMG, "match_only": True})
    assert gallery_size(pid) == 2


def test_two_lookalike_patients_are_ambiguous(client, scan):
    base = unit(rng.normal(size=512))
    a = at_distance(base, 0.15)
    b = at_distance(base, 0.17)
    register(client, "Twin A", a, "9100000002")
    register(client, "Twin B", b, "9100000003")

    scan(base)
    for match_only in (True, False):
        r = client.post("/identify", json={"image": IMG, "match_only": match_only}).json()
        assert r == {"status": "ambiguous"}   # no name, id or embedding leaks


def test_clear_winner_is_not_ambiguous(client, scan):
    base = unit(rng.normal(size=512))
    pid = register(client, "Clear Winner", at_distance(base, 0.05), "9100000004")
    register(client, "Distant Relative", at_distance(base, 0.40), "9100000005")
    scan(base)
    r = client.post("/identify", json={"image": IMG, "match_only": True}).json()
    assert r["status"] == "found" and r["id"] == pid


def test_spoof_routes_to_phone(client, scan):
    scan(SpoofSuspected())
    assert client.post("/identify", json={"image": IMG}).json() == {"status": "spoof"}


def test_engine_failure_is_503_not_no_face(client, scan):
    scan(FaceEngineError("UnicodeEncodeError: 'charmap' codec"))
    r = client.post("/identify", json={"image": IMG})
    assert r.status_code == 503
    assert "mobile number" in r.json()["message"]["en"]


def test_503_while_models_warming(client, scan, monkeypatch):
    monkeypatch.setitem(face_service._warm_state, "state", "warming")
    scan(unit(rng.normal(size=512)))
    assert client.post("/identify", json={"image": IMG}).status_code == 503


def test_corrupt_image_message_has_no_internals(client):
    r = client.post("/identify", json={"image": "data:image/jpeg;base64,AAAA"})
    assert r.status_code == 400
    assert "BytesIO" not in r.text and "0x" not in r.text

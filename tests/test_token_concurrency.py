"""Parallel bookings must get distinct, sequential tokens (run against PostgreSQL via TEST_DATABASE_URL too)."""

from concurrent.futures import ThreadPoolExecutor

from app.core.security import create_phone_verification_token

N = 20


def test_parallel_bookings_get_distinct_sequential_tokens(client):
    token = create_phone_verification_token("+919876522222")
    r = client.post("/register", json={"name": "Concurrent", "age": 40, "face_consent": False,
                                       "phone": "9876522222", "phone_verification_token": token})
    assert r.status_code == 200, r.text
    pid = r.json()["id"]

    def book(_):
        res = client.post("/appointment/book", json={
            "patient_id": pid, "dept_id": "derm", "symptoms": "itchy skin rash", "service": "symptoms",
        })
        assert res.status_code == 200, res.text
        return res.json()

    with ThreadPoolExecutor(max_workers=N) as pool:
        results = list(pool.map(book, range(N)))

    numbers = sorted(b["token_number"] for b in results)
    assert len(set(numbers)) == N, numbers
    assert numbers == list(range(numbers[0], numbers[0] + N)), numbers
    assert {b["token"] for b in results} == {f"D-{n:03d}" for n in numbers}

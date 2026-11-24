# medKiosk

Self check-in kiosk for hospital outpatient departments (OPD), in Tamil and English. A patient is
identified by face or by phone and OTP, registers by voice or on-screen form, describes their
symptoms, enters vitals, and gets a department token. Nurses see the live queue, and a
waiting-room screen shows the tokens being called.

> **Status:** pilot software. It is **not a medical device** and gives no diagnosis. Triage
> output is advisory and must be confirmed by clinical staff. Complete the
> [before go-live checklist](#before-go-live-checklist) before any real patient uses it.

---

## Architecture

```
 Kiosk screens (Chromium kiosk mode)      Staff PCs / waiting-room TV
 ┌──────────────────────────┐             ┌────────────────────────────────────┐
 │ frontend/  patient kiosk │             │ staff/  /queue   nurse dashboard   │
 │ React + Vite, camera+mic │             │         /display waiting-room board│
 └────────────┬─────────────┘             │         /admin   users, patients   │
              │ HTTP (X-Kiosk-Key)        └──────────────┬─────────────────────┘
              │                                          │ HTTP (JWT) + WebSocket
              ▼                                          ▼
        ┌───────────────────────────────────────────────────────────┐
        │ app/  FastAPI backend (single process)                    │──► Groq (Whisper STT, LLM)
        │ routers: face, phone OTP, conversation, vitals, booking,  │──► Sarvam (optional Tamil STT/TTS)
        │ queue, display, auth, admin, ws                           │──► Twilio (optional SMS)
        └──────────────────────────────┬────────────────────────────┘
                                       ▼
                         PostgreSQL 16 (SQLite in dev)
```

- **Kiosk (`frontend/`)**: patient-facing touch screen. Talks to the backend with a device key.
- **Staff app (`staff/`)**: `/queue` (nurses: call, start, complete, no-show, requeue), `/display`
  (public board, no patient details: called tokens with chime and spoken announcement),
  `/admin/users` and `/admin/patients` (admin only).
- **Backend (`app/`)**: FastAPI, SQLAlchemy 2, Alembic migrations, in-process WebSocket hub.
- **Database**: PostgreSQL in production; SQLite file `patients.db` by default in dev.
- The API contract is in [`docs/CONTRACT.md`](docs/CONTRACT.md).

No hospital HIS/EMR or ABDM integration exists.

## Features (as built)

**Patient kiosk**
- Language choice (English / Tamil) and on-screen consent before any face template is stored.
  The splash camera only tries to match patients who already consented, and stores nothing for
  anyone else.
- Identification:
  - **Face**: ArcFace embeddings via DeepFace. Each patient has a gallery of up to 5 templates;
    matching is by cosine distance (`FACE_MATCH_THRESHOLD`). The largest face in the frame is
    used. A face that looks like a photo or screen (anti-spoofing), or that is almost equally
    close to two patients, is never matched: the visitor checks in by phone instead. Model
    weights (~800 MB) download on first run (`python -m app.services.face_service`).
  - **Phone + OTP**: for visitors who decline face recognition. A 6-digit SMS code is stored only
    as an HMAC, expires after 5 minutes, allows 5 wrong attempts, and is rate-limited to
    3 codes per phone per 10 minutes. Several patients can share one number, for example a
    family.
  - Registering without a face template needs a signed `phone_verification_token` from the OTP
    step. The server enforces this.
- Registration by voice conversation (the LLM extracts name, age and other fields) or by form.
- Symptom intake by voice or text, and department routing by the Groq LLM.
- **Deterministic clinical safety layer** (`app/services/clinical_rules.py`): red-flag keywords
  (English, Tamil, Tanglish, simple negation) and a NEWS2 score from vitals. These can raise
  urgency but never lower it. Emergencies route to the Emergency department. The LLM's output
  is advisory only, and the kiosk falls back to keyword routing if the LLM is unavailable.
- Vitals **entered by hand** on screen: BP, SpO₂, pulse, temperature, respiratory rate,
  glucose, height and weight. Implausible values are rejected. No medical devices are
  integrated.
- Booking: sequential per-department daily tokens (`C-001`, `C-002` …), allocated atomically.
  The kiosk shows room, queue position and estimated wait. An optional SMS confirmation is
  available.
- Speech: Groq Whisper speech-to-text by default, or Sarvam (`saaras`) for Indic speech.
  Prompts are read aloud by the browser's `speechSynthesis`, or by Sarvam TTS (`bulbul`), which
  the server caches.
- Idle timeout returns the kiosk to the start screen.

**Staff**
- JWT login with `nurse` and `admin` roles. Admins manage users and can delete a patient's
  face data, which withdraws consent.
- Live queue over WebSocket, ordered by urgency (emergency, then urgent, then normal), then by
  token. Each entry shows vitals, NEWS2 and the reasons for any escalation.
- Waiting-room display board that receives live updates.

## Development setup

Requirements: Python 3.11, Node 20+ (CI uses 24), a Groq API key.

```bash
python -m venv .venv
.venv\Scripts\activate            # Windows  (Linux/macOS: source .venv/bin/activate)
pip install -r requirements.txt -r requirements-dev.txt
cp .env.example .env              # then set GROQ_API_KEY (everything else has dev defaults)

# Backend: runs migrations + seeds departments/doctors/demo users on startup
python -m uvicorn app.main:app --reload --port 8000     # or start.bat / start.sh

# Kiosk  (http://localhost:5173)
cd frontend && npm install && npm run dev
# Staff  (http://localhost:5174 → /login, /queue, /display, /admin/users)
cd staff && npm install && npm run dev
```

Both Vite dev servers proxy API calls to `http://localhost:8000`. Without `KIOSK_DEVICE_KEYS`,
and with `ENV=dev`, the kiosk key check is disabled. With `SMS_PROVIDER=mock`, OTP codes and
SMS texts are written to the backend log.

`requirements.txt` includes DeepFace and TensorFlow, which are large. To skip them, install
only `requirements-dev.txt`. The backend still starts, but `/identify` fails, so use phone
identification.

Tests and lint:

```bash
pytest -q                     # SQLite temp database
ruff check .
# Against PostgreSQL (database name must contain "test"; its schema is wiped):
TEST_DATABASE_URL=postgresql+psycopg://user:pass@localhost:5432/medkiosk_test pytest -q
```

## Production (Docker Compose)

One on-prem server runs everything. See **[docs/DEPLOY.md](docs/DEPLOY.md)** for the full
procedure, TLS, firewall and backups.

```bash
cp .env.example .env          # ENV=prod, secrets, keys — see the table below
docker compose up -d --build
```

| Service | Port | What |
|---|---|---|
| `kiosk` | 8080 | Kiosk SPA (nginx). Proxies the kiosk API and adds `X-Kiosk-Key` from `KIOSK_PROXY_KEY`. |
| `staff` | 8081 | Staff SPA (nginx). Proxies the API and `/ws` WebSockets. |
| `backend` | internal | FastAPI. Runs `alembic upgrade head`, then **one** uvicorn worker. |
| `db` | internal | PostgreSQL 16, volume `pgdata`. |

**Single worker only.** The realtime hub (`app/services/realtime.py`) keeps WebSocket clients in
process memory, so the backend must run exactly one uvicorn worker. Running more workers or
replicas would need Redis pub/sub, which is not built. One worker easily handles a few kiosks
and staff screens. CPU-heavy work (ArcFace) runs in a thread pool.

## Configuration keys

All settings are in `.env` (see `.env.example`), read by `app/core/config.py`.

| Key | Needed | Notes |
|---|---|---|
| `GROQ_API_KEY` | **Required** | Speech-to-text (Whisper) and LLM. Get one at https://console.groq.com |
| `JWT_SECRET` | **Required in prod** (generate) | `python -c "import secrets; print(secrets.token_urlsafe(48))"`. Startup fails in prod if left at the default. |
| `KIOSK_DEVICE_KEYS` | **Required in prod** (generate) | Comma-separated list, one random value per kiosk, e.g. `secrets.token_urlsafe(32)`. |
| `KIOSK_PROXY_KEY` | Docker | One of `KIOSK_DEVICE_KEYS`, injected by the kiosk nginx. |
| `POSTGRES_PASSWORD` | Docker | Database password (URL-safe characters). |
| `ENV` | Prod: `prod` | Enables the prod safety checks. |
| `SEED_DEMO_USERS` | Prod: `false` | See [demo accounts](#demo-accounts). |
| `SARVAM_API_KEY` | Optional | Tamil and English STT/TTS. Set `STT_PROVIDER=sarvam` and/or `TTS_PROVIDER=sarvam`. |
| `SMS_PROVIDER`, `TWILIO_ACCOUNT_SID`, `TWILIO_AUTH_TOKEN`, `TWILIO_FROM_NUMBER` | Optional | `mock` (the default) only logs messages, so phone OTP **does not reach patients** until Twilio is configured. |
| `HOSPITAL_NAME` | Optional | Used in SMS text. |
| `OTP_*`, `PHONE_VERIFICATION_TOKEN_MINUTES`, `CONSENT_VERSION`, `CHILD_AGE_YEARS` | Optional | OTP limits, consent text version, child age cut-off. Defaults are in `.env.example`. |
| `FACE_MATCH_THRESHOLD`, `FACE_GALLERY_SIZE`, `FACE_GALLERY_UPDATE_MAX_DIST`, `FACE_AMBIGUITY_MARGIN`, `FACE_ANTI_SPOOFING` | Optional | Face matching tuning and safety. |

## Demo accounts

When `SEED_DEMO_USERS=true` and the `users` table is empty, the backend creates:

| Username | Password | Role |
|---|---|---|
| `nurse1` | `Nurse@123` | nurse |
| `admin` | `Admin@123` | admin |

**Before real use:** set `SEED_DEMO_USERS=false`, create real accounts under `/admin/users`, and
then deactivate the demo accounts or change their passwords. The passwords above are public.

## Kiosk hardware notes

- Run the kiosk in Chromium or Chrome kiosk mode, for example:
  `chromium --kiosk --noerrdialogs --disable-translate --autoplay-policy=no-user-gesture-required http://<server>:8080`
- Allow **camera and microphone** for the kiosk origin, either once by hand or with an
  enterprise policy (`VideoCaptureAllowedUrls`, `AudioCaptureAllowedUrls`).
- **Browsers only allow camera and microphone in a secure context**, meaning HTTPS or
  `localhost`. A kiosk opening `http://<server-ip>:8080` across the LAN will not get the camera
  unless you do one of the following:
  1. **Recommended:** put a TLS reverse proxy (Caddy or nginx with an internal CA certificate
     trusted by the kiosks) in front of ports 8080 and 8081. See docs/DEPLOY.md.
  2. On a closed kiosk machine only, mark the origin as secure:
     `--unsafely-treat-insecure-origin-as-secure=http://<server-ip>:8080 --user-data-dir=<dir>`
- A USB webcam at face height and a decent microphone (a directional or array mic in noisy OPD
  areas) noticeably improve recognition and transcription.
- Tamil voice output depends on a Tamil voice being installed for `speechSynthesis`, or on
  Sarvam TTS.
- The waiting-room TV opens `http://<server>:8081/display`. It needs a click or the autoplay
  flag before it can play sound.

## Before go-live checklist

- [ ] **Clinical review** by a clinician of the red-flag keyword lists and escalation rules in
      `app/services/clinical_rules.py`, the NEWS2 thresholds, the child age cut-off, and the
      LLM triage prompt (`app/services/llm_service.py`).
- [ ] **Native Tamil review** of all UI strings (`frontend/src/i18n/locales/ta.json` and inline
      strings in views), the spoken prompts, and the bilingual server error messages.
- [ ] **Legal review of the DPDP Act consent text** (face template consent, phone use, data
      retention). Bump `CONSENT_VERSION` whenever the text changes.
- [ ] **Twilio**: register the sender and templates for India **DLT**, set
      `SMS_PROVIDER=twilio`, and test OTP delivery to several carriers.
- [ ] `ENV=prod`, a strong `JWT_SECRET`, one `KIOSK_DEVICE_KEYS` value per kiosk,
      `SEED_DEMO_USERS=false`, real staff accounts, and demo accounts disabled.
- [ ] TLS in place, and the firewall limits port 8080 to kiosk machines and 8081 to staff
      PCs and the display.
- [ ] **Backups**: nightly `pg_dump`, copied off the server, with a restore tested (docs/DEPLOY.md).
- [ ] Face threshold checked on site with real lighting (`/identify/debug` in dev).
- [ ] A fallback procedure for front-desk registration when the kiosk, network or Groq is down.

## Repository layout

```
app/            FastAPI backend (core/ config, db, models, security; routers/; services/)
alembic/        database migrations
frontend/       patient kiosk (Vite + React + TS)      → Dockerfile, nginx.conf.template
staff/          staff queue / display / admin app       → Dockerfile, nginx.conf
tests/          pytest suite
docs/           CONTRACT.md (API spec), DEPLOY.md (server setup, backups)
docker-compose.yml, Dockerfile, docker/   production stack
```

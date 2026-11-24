# medKiosk v3 — Build Contract

Shared spec for all parallel work. Backend and frontends must match this exactly.
Paths keep their current style (no `/api` prefix) so existing kiosk calls keep working.

## Deployment model
- One on-prem server runs the FastAPI backend + PostgreSQL. Several kiosk screens and staff PCs connect over the hospital LAN.
- Dev mode: `DATABASE_URL` defaults to SQLite (`sqlite:///./patients.db`) so the app runs without Postgres.
- AI: Groq cloud only (Whisper STT + LLM). No local models.
- Not in scope: hospital HIS/EMR integration, ABDM.

## Config (`app/core/config.py`, pydantic-settings, reads `.env`)
| Var | Default | Notes |
|---|---|---|
| `ENV` | `dev` | `dev` or `prod`. In `prod`, startup fails if `JWT_SECRET` is default or `KIOSK_DEVICE_KEYS` empty. |
| `DATABASE_URL` | `sqlite:///./patients.db` | Postgres: `postgresql+psycopg://user:pass@host:5432/medkiosk` |
| `GROQ_API_KEY`, `GROQ_MODEL`, `GROQ_TRIAGE_MODEL`, `GROQ_WHISPER_MODEL`, `GROQ_TIMEOUT`, `GROQ_WHISPER_TIMEOUT` | as today | |
| `JWT_SECRET` | `dev-insecure-secret` | HS256 |
| `JWT_EXPIRE_MINUTES` | `720` | one nurse shift |
| `KIOSK_DEVICE_KEYS` | empty | comma list. Kiosk sends `X-Kiosk-Key`. Empty + `ENV=dev` = check disabled. |
| `CORS_ORIGINS` | `http://localhost:5173,http://localhost:5174` | comma list |
| `FACE_MATCH_THRESHOLD` | `0.45` | ArcFace cosine distance |
| `FACE_GALLERY_SIZE` | `5` | |
| `SMS_PROVIDER` | `mock` | `mock` (log only) or `twilio` |
| `TWILIO_ACCOUNT_SID`, `TWILIO_AUTH_TOKEN`, `TWILIO_FROM_NUMBER` | empty | |
| `HOSPITAL_NAME` | `City Hospital` | used in SMS text |
| `SEED_DEMO_USERS` | `true` | seeds demo staff accounts if `users` table empty |

## Database (SQLAlchemy 2.0 models in `app/core/models.py`, Alembic migrations in `alembic/`)
Existing tables keep their columns. New / changed:

- `departments` — `id` TEXT PK (`general`,`cardio`,`ortho`,`paeds`,`gyne`,`derm`,`ent`,`ophthal`,`emergency`), `name_en`, `name_ta`, `room`, `token_prefix`, `avg_wait_mins` INT, `color` TEXT, `icon` TEXT, `active` BOOL. **Single source of truth** for rooms. Seeded once:

| id | name_en | name_ta | room | prefix | wait | color | icon |
|---|---|---|---|---|---|---|---|
| general | General Medicine | பொது மருத்துவம் | OPD-1 | G | 20 | #2E7D96 | 🏥 |
| paeds | Paediatrics | குழந்தை நலம் | OPD-2 | P | 15 | #059669 | 👶 |
| cardio | Cardiology | இதய நோயியல் | OPD-3 | C | 30 | #DC2626 | ❤️ |
| ortho | Orthopaedics | எலும்பு சிகிச்சை | OPD-4 | O | 25 | #7C3AED | 🦴 |
| gyne | Gynaecology | மகளிர் நலம் | OPD-5 | GY | 20 | #DB2777 | 👩 |
| derm | Dermatology | தோல் நோய் | OPD-6 | D | 15 | #D97706 | ✨ |
| ent | ENT | காது மூக்கு தொண்டை | OPD-7 | E | 15 | #4F46E5 | 👂 |
| ophthal | Ophthalmology | கண் நோய் | OPD-8 | OP | 20 | #2563EB | 👁️ |
| emergency | Emergency | அவசர சிகிச்சை | ER-1 | EM | 0 | #B91C1C | 🚨 |

  Doctor seed rooms must match this table.
- `token_counters` — PK (`dept_id`, `queue_date` DATE), `last_number` INT. Incremented atomically (`UPDATE ... RETURNING` on Postgres; transaction on SQLite).
- `appointments` — add `token_number` INT, `queue_date` DATE, `urgency` TEXT (`normal`|`urgent`|`emergency`, default `normal`), `status` TEXT (`waiting`|`called`|`in_consult`|`done`|`no_show`), `called_at`, `started_at`, `completed_at` DATETIME, `handled_by` INT FK users, `sms_opt_in` BOOL, `sms_status` TEXT (`not_requested`|`sent`|`failed`|`mocked`). Unique (`dept_id`,`queue_date`,`token_number`).
- `users` — `id`, `username` UNIQUE, `password_hash` (bcrypt via `passlib` or `bcrypt`), `full_name`, `role` (`nurse`|`admin`), `active` BOOL, `created_at`.
- `patients` — add `face_consent` BOOL default false, `consent_at` DATETIME, `consent_version` TEXT.
- `vitals` — add `pulse` INT, `temperature` REAL (°C), `resp_rate` INT, `glucose` REAL (mg/dL). All nullable.

Demo users (only when `SEED_DEMO_USERS=true` and table empty; log a warning in prod):
- `nurse1` / `Nurse@123` (role nurse, "Demo Nurse")
- `admin` / `Admin@123` (role admin, "Demo Admin")

## Tokens
Format `{token_prefix}-{n:03d}`, e.g. `C-001`. Sequential per department per day, starting at 1. Never random.

## Endpoints

### Public kiosk (require `X-Kiosk-Key` when keys configured)
Existing: `/identify`, `/register`, `/transcribe`, `/conversation/*`, `/vitals`, `/doctors`, `/appointment/*` — unchanged request shapes except:

- `GET /departments` → `{"departments": [{id,name_en,name_ta,room,token_prefix,avg_wait_mins,color,icon,active}]}` (active only)
- `POST /appointment/book` request adds optional `urgency` (default `normal`), `sms_opt_in` (bool, default false). `room` and `dept_name` from client are ignored; server uses `departments` table. Response:
```json
{"appointment_id":1,"token":"C-004","token_number":4,"dept_id":"cardio","dept_name":"Cardiology",
 "room":"OPD-3","queue_position":3,"wait_mins":60,"service":"symptoms","symptoms":"...",
 "urgency":"normal","doctor_id":null,"doctor_name":null,"sms_status":"mocked",
 "created_at":"ISO","status":"success"}
```
  `queue_position` = count of today's `waiting` appointments in that dept created before this one + 1. `wait_mins` = (queue_position − 1) × `avg_wait_mins` (emergency → 0).
  If `sms_opt_in` and patient has phone → send SMS: `"{HOSPITAL_NAME}: Your token is {token}. Please go to {room} ({dept_name}). Approx wait {wait_mins} min."` Phone normalised to E.164 `+91XXXXXXXXXX`. SMS failure never fails booking.

### Staff auth
- `POST /auth/login` body `{"username","password"}` → `{"access_token","token_type":"bearer","user":{"id","username","full_name","role"}}`; 401 on bad creds.
- `GET /auth/me` (Bearer) → user object.
- `GET /admin/users`, `POST /admin/users` `{username,password,full_name,role}`, `PATCH /admin/users/{id}` `{active?,password?,full_name?,role?}` — admin only.

### Queue (Bearer, role nurse or admin)
- `GET /queue?dept_id=&status=` → today's appointments ordered: urgency (emergency, urgent, normal), then token_number.
```json
{"date":"2026-11-24","items":[{"appointment_id":1,"token":"C-004","dept_id":"cardio","dept_name":"Cardiology",
 "room":"OPD-3","status":"waiting","urgency":"normal","symptoms":"...","created_at":"ISO","called_at":null,
 "patient":{"id":3,"name":"Ravi","age":35,"gender":"Man","phone_masked":"******3210"},
 "vitals":{"bp_sys":130,"bp_dia":85,"spo2":97,"pulse":88,"temperature":37.1,"glucose":null,"flags":["Stage 1 Hypertension"]} }],
 "counts":{"waiting":5,"called":1,"in_consult":2,"done":10,"no_show":0}}
```
  `vitals` = latest vitals today for that patient or null.
- `POST /queue/{appointment_id}/call` → status `called`, sets `called_at`, `handled_by`. Allowed from `waiting` or `called` (recall).
- `POST /queue/{id}/start` → `in_consult`. `POST /queue/{id}/complete` → `done`. `POST /queue/{id}/no-show` → `no_show`. `POST /queue/{id}/requeue` → back to `waiting`.
  Invalid transition → 409. Each returns the updated item (same shape as list item).
- `POST /queue/call-next?dept_id=X` → calls highest-priority waiting item in dept; 404 if none.

### Display board (public, NO patient PII)
- `GET /display/now-serving?dept_id=` → `{"now_serving":[{"token","room","dept_id","dept_name","called_at"}], "waiting_counts":{"cardio":4,...}}` — last 10 `called` items today, newest first.

### WebSockets
- `WS /ws/queue?token=<JWT>` — staff. Server pushes `{"type":"queue.updated","data":<queue item>}` on book and every status change. Close 4401 on bad token.
- `WS /ws/display` — public. Pushes `{"type":"token.called","data":{"token","room","dept_id","dept_name","called_at"}}` on call/recall, and `{"type":"counts","data":{waiting_counts}}` on any change.
- Single-process in-memory hub (`app/services/realtime.py`). Document that multi-worker needs Redis pub/sub (not built now).

## Speech providers (batch 2)
- Config: `STT_PROVIDER` (`groq`|`sarvam`, default `groq`), `TTS_PROVIDER` (`browser`|`sarvam`, default `browser`), `SARVAM_API_KEY`, `SARVAM_STT_MODEL`, `SARVAM_TTS_MODEL`, `SARVAM_TTS_SPEAKER_TA`, `SARVAM_TTS_SPEAKER_EN`, `SARVAM_TIMEOUT`.
- `POST /transcribe` unchanged shape; response `provider` is `groq` or `sarvam`. If Sarvam fails, fall back to Groq when `GROQ_API_KEY` set.
- `POST /tts` (kiosk key) body `{"text": str (max 500 chars), "language": "ta"|"en"}` → `audio/wav` bytes. 503 when `TTS_PROVIDER=browser` or Sarvam unavailable; kiosk then uses browser `speechSynthesis`. Server caches audio by (language, speaker, text hash) in memory (LRU) since kiosk prompts repeat.
- `GET /tts/config` (public) → `{"provider":"browser"|"sarvam"}` so kiosk knows which to use.

## Frontends
- `frontend/` — patient kiosk, port 5173 (existing).
- `staff/` — new Vite + React + TS + Tailwind app, port 5174. Routes: `/login`, `/queue` (nurse dashboard), `/display` (public waiting-room board, no login, big type, Tamil + English, plays a chime + speaks "Token C-004, room OPD-3" via speechSynthesis when a token is called), `/admin/users` (admin only).
- Both read API base from `VITE_API_URL` (default `''` with Vite proxy to `http://localhost:8000`, including `/ws` with `ws: true`).

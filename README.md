# medKiosk

**Voice-first, bilingual (Tamil/English) patient check-in kiosk for Indian hospital OPD settings.**

medKiosk automates hospital front-desk registration using face recognition, voice-based intake, and real-time vitals capture — removing the literacy and language barriers that make most self-check-in kiosks unusable for Indian patients, while giving nurses and triage staff live visibility into who's arrived and how urgent they are.

---

## Problem

Indian hospital OPDs — especially Tier 2/3 and high-footfall govt/semi-govt hospitals — are bottlenecked at manual registration: paper forms, language barriers, long queues before any clinical triage happens, and zero real-time visibility for staff about incoming patients.

Existing solutions fall short:
- **Manual front-desk registration** — slow, no automated triage, doesn't sync to clinical systems
- **Token/queue kiosks** — still require manual data entry, no identity verification or symptom capture
- **App-based check-in** — assumes smartphone literacy, excludes elderly/rural/first-time patients
- **International self-check-in kiosks** — text/touch-only, no regional language or voice support

medKiosk solves this with voice-first Tamil intake, face-based re-identification for returning patients, and real-time sync to clinical staff — at low infra cost (no heavy cloud dependency).

---

## Architecture

Three connected React/Vite frontends + a FastAPI backend, synced in real time over WebSocket:

| Frontend | Port | Purpose |
|---|---|---|
| Kiosk (patient-facing) | `5173` | Face ID check-in, voice intake, vitals capture |
| Nurse | `5174` | Live incoming patient queue with vitals + urgency |
| Triage | `5175` | MEWS-style priority flagging (CRITICAL / WARNING / NONE) |




---

## Tech Stack

**Frontend:** React + Vite, three separate apps for kiosk/nurse/triage isolation

**Backend:** FastAPI + SQLite, WebSocket for real-time broadcast

**Voice pipeline (Sarvam AI):**
uses-openAI's whisper model

**Face recognition:**
- Client-side detection: `face-api.js`
- Server-side identity match: DeepFace / Facenet512, cosine similarity threshold `0.70`

**Vitals hardware:**
- SpO2 + pulse oximeter
- Blood pressure cuff
- Glucometer

---

## Patient Flow

1. **Identify** — Face scan matches returning patient or triggers new-patient enrollment
2. **Voice intake** — Bilingual (Tamil/English) conversational symptom capture via Sarvam pipeline, live transcription
3. **Vitals capture** — Guided 3-step flow: SpO2/pulse → BP → blood sugar, auto-populated into patient record
4. **Auto-triage** — MEWS-style scoring from symptoms + vitals produces a priority tag (CRITICAL / WARNING / NONE)
5. **Real-time staff sync** — Nurse and triage dashboards update instantly via WebSocket, no manual re-entry
6. **Queue** — Patient sees live queue position / estimated wait

---



Set the following environment variables for the backend:

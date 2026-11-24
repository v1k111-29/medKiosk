# medKiosk Staff

Staff web app: nurse queue dashboard, public waiting-room display board, admin user management.
React 18 + TypeScript + Vite + Tailwind. API spec: `docs/CONTRACT.md`.

## Run

```
npm install
npm run dev        # http://localhost:5174
```

The dev server proxies `/auth /queue /display /admin /departments /ws` to the backend
(default `http://localhost:8000`).

## Build

```
npm run build      # type-check + production bundle in dist/
npm run preview
```

## Env vars

| Var | Default | Purpose |
|---|---|---|
| `VITE_API_URL` | `''` (same origin, via proxy) | API base URL, e.g. `http://192.168.1.10:8000`. WebSocket URLs derive from it. |
| `VITE_PROXY_TARGET` | `http://localhost:8000` | Dev-server proxy target only. |

## Routes

- `/login` - staff sign in (demo accounts hinted in dev builds only)
- `/queue` - nurse dashboard (nurse, admin)
- `/display` - public board, no login; optional `?dept=cardio`. Click "Enable sound" once so the browser allows chime/speech.
- `/admin/users` - user management (admin only)

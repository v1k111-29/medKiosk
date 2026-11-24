# Deploying medKiosk (on-prem server)

Target: one Linux server on the hospital LAN running the backend, PostgreSQL and the two web
apps with Docker Compose. Kiosk screens and staff PCs are browsers on the LAN. The server needs
outbound HTTPS to Groq (required), and to Sarvam or Twilio if you use them.

## 1. Server

- Ubuntu 24.04 LTS (or similar) with 4 or more CPU cores, 8 GB RAM and 40 GB disk. ArcFace runs
  on the CPU. The backend image is about 2–3 GB because it includes TensorFlow.
- A static LAN IP or DNS name, for example `medkiosk.hospital.lan`.
- Docker Engine and the Compose plugin: https://docs.docker.com/engine/install/
- Correct time (NTP): OTP expiry and token dates depend on it.

```bash
sudo mkdir -p /opt/medkiosk && sudo chown $USER /opt/medkiosk
git clone <repo> /opt/medkiosk && cd /opt/medkiosk
cp .env.example .env && chmod 600 .env
```

## 2. Configure `.env`

Set at least:

```ini
ENV=prod
GROQ_API_KEY=...
JWT_SECRET=<python -c "import secrets; print(secrets.token_urlsafe(48))">
KIOSK_DEVICE_KEYS=<key1>          # comma list; generate with secrets.token_urlsafe(32)
KIOSK_PROXY_KEY=<key1>            # the key the kiosk nginx sends
POSTGRES_PASSWORD=<python -c "import secrets; print(secrets.token_hex(24))">
SEED_DEMO_USERS=false             # or true for the first start only, see step 4
CORS_ORIGINS=https://medkiosk.hospital.lan:8443,https://medkiosk.hospital.lan:9443
SMS_PROVIDER=mock                 # twilio once DLT registration is done
HOSPITAL_NAME=...
```

Compose builds the backend's `DATABASE_URL` from `POSTGRES_PASSWORD`, so `DATABASE_URL` in
`.env` is ignored inside the stack.

`INSTALL_FACE=false` builds a backend image without DeepFace and TensorFlow. Face
identification is then unavailable, and every visitor uses phone + OTP.

## 3. Start

```bash
docker compose up -d --build
docker compose ps                       # backend should become "healthy"
docker compose logs -f backend          # migrations, seeding, "Server ready"
```

On its first start the backend downloads the ArcFace weights (about 130 MB, from GitHub) into
the `deepface` volume. If the server has no outbound GitHub access, copy
`~/.deepface/weights/arcface_weights.h5` from a machine that has it into the volume
(`/data/.deepface/weights/`).

| URL | Who |
|---|---|
| `http://<server>:8080` | kiosk screens |
| `http://<server>:8081/queue` | nurses |
| `http://<server>:8081/display` | waiting-room TV |
| `http://<server>:8081/admin/users` | admins |

## 4. First admin account

With `SEED_DEMO_USERS=false` and an empty `users` table, nobody can log in. Either:

- start once with `SEED_DEMO_USERS=true`, log in as `admin` / `Admin@123`, create real admin
  and nurse accounts, **deactivate `admin` and `nurse1`**, then set `SEED_DEMO_USERS=false` and
  run `docker compose up -d`; or
- create an admin directly:

  ```bash
  docker compose exec backend python -c "
  from app.core.database import session_scope
  from app.core.models import User
  from app.core.security import hash_password
  with session_scope() as s:
      s.add(User(username='sister.mary', full_name='Sister Mary', role='admin', active=True,
                 password_hash=hash_password('<strong password>')))"
  ```

## 5. TLS (needed for the kiosk camera and microphone)

Browsers expose the camera and microphone only on HTTPS or `localhost`. Put a TLS reverse
proxy in front of the two web ports, using a certificate the kiosks and staff PCs trust (an
internal hospital CA, or `caddy`'s internal CA with its root installed on each machine).

Example with Caddy on the host (`/etc/caddy/Caddyfile`):

```
medkiosk.hospital.lan:8443 {
    tls internal
    reverse_proxy 127.0.0.1:8080
}
medkiosk.hospital.lan:9443 {
    tls internal
    reverse_proxy 127.0.0.1:8081
}
```

Then bind the compose ports to localhost only, by setting `KIOSK_PORT=127.0.0.1:8080` and
`STAFF_PORT=127.0.0.1:8081` in `.env`, and point browsers at the `https://` URLs. Caddy
proxies WebSockets automatically.

The insecure alternative, for a locked-down kiosk machine only, is to launch Chromium with
`--unsafely-treat-insecure-origin-as-secure=http://<server>:8080 --user-data-dir=/var/lib/kiosk-chrome`.

## 6. Firewall

The kiosk nginx adds the kiosk device key to every API request, so **any machine that can reach
the kiosk port acts as a kiosk**. Restrict it:

```bash
sudo ufw default deny incoming
sudo ufw allow from <kiosk-ip-1> to any port 8443 proto tcp     # (or 8080 without TLS)
sudo ufw allow from <staff-subnet> to any port 9443 proto tcp    # (or 8081)
sudo ufw allow from <admin-ip> to any port 22 proto tcp
sudo ufw enable
```

Docker-published ports bypass `ufw` unless they are bound to `127.0.0.1`, which is another
reason to use the TLS proxy setup above.

## 7. Kiosk machines

- Chromium kiosk mode autostarted at login:
  `chromium --kiosk --noerrdialogs --disable-translate --autoplay-policy=no-user-gesture-required https://medkiosk.hospital.lan:8443`
- Grant camera and microphone to that origin (a policy such as `VideoCaptureAllowedUrls` /
  `AudioCaptureAllowedUrls`, or allow them once by hand).
- Disable OS sleep and screen blanking. Use a user account with no other apps.

## 8. Backups and restore

The database holds all patient data, so back it up nightly and keep copies **off the server**,
encrypted.

`/opt/medkiosk/backup.sh`:

```bash
#!/bin/sh
set -e
cd /opt/medkiosk
DEST=/var/backups/medkiosk
mkdir -p "$DEST"
STAMP=$(date +%Y%m%d-%H%M)
docker compose exec -T db pg_dump -U medkiosk -d medkiosk -Fc > "$DEST/medkiosk-$STAMP.dump"
find "$DEST" -name 'medkiosk-*.dump' -mtime +30 -delete
# then copy off-site, e.g.: rclone copy "$DEST" remote:medkiosk-backups
```

Cron (`sudo crontab -e`):

```
30 2 * * * /opt/medkiosk/backup.sh >> /var/log/medkiosk-backup.log 2>&1
```

Restore, which replaces the current data:

```bash
docker compose stop backend
docker compose exec -T db dropdb -U medkiosk medkiosk
docker compose exec -T db createdb -U medkiosk medkiosk
docker compose exec -T db pg_restore -U medkiosk -d medkiosk --no-owner < /var/backups/medkiosk/medkiosk-YYYYMMDD-HHMM.dump
docker compose start backend      # runs any newer migrations
```

Test a restore into a scratch server or database at least once before go-live.

Also keep `.env` (the secrets) somewhere safe. Changing `JWT_SECRET` logs out all staff
and invalidates any OTP codes still pending.

## 9. Updates

```bash
cd /opt/medkiosk
./backup.sh
git pull
docker compose up -d --build      # backend applies migrations on start
```

## 10. Operations notes

- **Single backend worker** by design, because the WebSocket hub is in-process. Do not scale
  the `backend` service.
- Logs: `docker compose logs backend`. Tokens in query strings (`?token=`) are redacted in the
  backend and nginx logs. OTP codes appear in logs only with `SMS_PROVIDER=mock`.
- Health: `docker compose exec backend curl -s localhost:8000/health`.
- Expired phone OTP rows are purged on startup and automatically while the system is in use.

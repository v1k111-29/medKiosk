# medKiosk backend (FastAPI). Build: docker compose build backend
#
# INSTALL_FACE=true (default) installs DeepFace + TensorFlow for face recognition (~2 GB image).
# INSTALL_FACE=false builds a small image without it; /identify then returns an error and
# visitors use phone + OTP identification.
FROM python:3.11-slim

ARG INSTALL_FACE=true

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    # DeepFace downloads ArcFace weights here on first start (persisted by a volume).
    DEEPFACE_HOME=/data \
    TF_CPP_MIN_LOG_LEVEL=2

# libgl1/libglib2.0-0: runtime libs for opencv-python (a DeepFace dependency). curl: healthcheck.
RUN apt-get update \
 && apt-get install -y --no-install-recommends curl \
 && if [ "$INSTALL_FACE" = "true" ]; then apt-get install -y --no-install-recommends libgl1 libglib2.0-0; fi \
 && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY requirements-base.txt requirements.txt ./
RUN if [ "$INSTALL_FACE" = "true" ]; then pip install -r requirements.txt; \
    else pip install -r requirements-base.txt; fi

RUN useradd --create-home --uid 10001 --shell /usr/sbin/nologin kiosk \
 && mkdir -p /data && chown kiosk:kiosk /data

COPY --chown=kiosk:kiosk alembic.ini ./
COPY --chown=kiosk:kiosk alembic ./alembic
COPY --chown=kiosk:kiosk app ./app
COPY --chown=kiosk:kiosk docker/backend-entrypoint.sh /usr/local/bin/backend-entrypoint.sh

USER kiosk
VOLUME ["/data"]
EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=10s --start-period=120s --retries=3 \
  CMD curl -fsS http://127.0.0.1:8000/health || exit 1

ENTRYPOINT ["sh", "/usr/local/bin/backend-entrypoint.sh"]

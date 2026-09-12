# syntax=docker/dockerfile:1.6

# ---- Builder stage ----
FROM python:3.11-slim AS builder

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

WORKDIR /build

# System deps needed to compile Python C extensions (cryptography, Pillow, cffi, reportlab)
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    libc6-dev \
    libssl-dev \
    libffi-dev \
    libjpeg-dev \
    zlib1g-dev \
    libfreetype6-dev \
    && rm -rf /var/lib/apt/lists/*

# Isolate installed packages in a venv so we can copy just the venv to the runtime stage
RUN python -m venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"

COPY requirements.txt .
RUN pip install --upgrade pip && \
    pip install -r requirements.txt


# ---- Runtime stage ----
FROM python:3.11-slim AS runtime

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PATH="/opt/venv/bin:$PATH" \
    DJANGO_SETTINGS_MODULE=core.settings

WORKDIR /app

# Runtime libraries only. postgresql-client for pg_dump/psql inside the container.
# curl for the healthcheck.
RUN apt-get update && apt-get install -y --no-install-recommends \
    postgresql-client \
    libjpeg62-turbo \
    zlib1g \
    libfreetype6 \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Copy the venv from the builder stage
COPY --from=builder /opt/venv /opt/venv

# Non-root user
RUN groupadd --system --gid 1001 app && \
    useradd --system --uid 1001 --gid app --create-home --shell /bin/bash app

# Copy application source (respecting .dockerignore)
COPY --chown=app:app . .

# Ensure runtime dirs exist with correct ownership
RUN mkdir -p /app/media /app/staticfiles /app/static/img && \
    chown -R app:app /app

# Collect static files at build time so the image ships ready-to-serve.
# Only SECRET_KEY and settings need to load; values don't matter for collectstatic.
RUN SECRET_KEY=build-time-dummy DEBUG=True \
    python manage.py collectstatic --noinput --clear

# Entrypoint handles migrations and superuser bootstrap on container start
COPY --chown=app:app docker-entrypoint.sh /usr/local/bin/docker-entrypoint.sh
RUN chmod +x /usr/local/bin/docker-entrypoint.sh

USER app

EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=5s --start-period=30s --retries=3 \
    CMD curl -fsS http://localhost:8000/ || exit 1

ENTRYPOINT ["docker-entrypoint.sh"]
CMD ["daphne", "-b", "0.0.0.0", "-p", "8000", "core.asgi:application"]
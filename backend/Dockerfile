# =============================================================================
# Stage 1: Build Dependencies
# =============================================================================
FROM python:3.12-slim AS builder

WORKDIR /build

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

# Install build dependencies for compiled extensions (psycopg, numpy, etc.)
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    libpq-dev \
    gcc \
    && rm -rf /var/lib/apt/lists/*

# Create virtual environment
RUN python -m venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"

# Copy pyproject.toml and install Python packages
COPY pyproject.toml /build/
RUN pip install --upgrade pip setuptools wheel \
    && pip install .

# =============================================================================
# Stage 2: Production Minimal Runtime
# =============================================================================
FROM python:3.12-slim AS runtime

WORKDIR /app

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PATH="/opt/venv/bin:$PATH" \
    PYTHONPATH="/app"

# Install minimal runtime dependencies (libpq for postgres, curl for health check)
RUN apt-get update && apt-get install -y --no-install-recommends \
    libpq5 \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Copy virtual environment from builder stage
COPY --from=builder /opt/venv /opt/venv

# Create non-root system user and group for security compliance
RUN groupadd -g 10001 opspilot \
    && useradd -u 10001 -g opspilot -m -d /home/opspilot -s /bin/bash opspilot \
    && mkdir -p /app/app /app/data /tmp/opspilot \
    && chown -R opspilot:opspilot /app /tmp/opspilot

# Copy application source code
COPY --chown=opspilot:opspilot app /app/app
COPY --chown=opspilot:opspilot pyproject.toml /app/pyproject.toml

# Copy pre-trained ML models directory if present
COPY --chown=opspilot:opspilot ml_models /app/ml_models

# Switch to unprivileged non-root user
USER opspilot

EXPOSE 8000

# Health check probe against API health endpoint
HEALTHCHECK --interval=15s --timeout=5s --start-period=20s --retries=3 \
  CMD curl -f http://localhost:8000/api/v1/health || exit 1

STOPSIGNAL SIGTERM

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]

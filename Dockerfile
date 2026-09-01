# SUTRA Production Container Definition
# Multi-stage build for minimal runtime image and non-root execution

# Stage 1: Build & dependency installation
FROM python:3.13-slim AS builder

WORKDIR /build

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

RUN apt-get update && apt-get install -y --no-install-recommends \
    git \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

COPY backend/requirements.txt .
RUN pip install --no-cache-dir --prefix=/install -r requirements.txt

# Stage 2: Production Runtime
FROM python:3.13-slim AS runner

WORKDIR /app

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PYTHONPATH=/app/backend \
    PORT=8000

# Install runtime Git dependency
RUN apt-get update && apt-get install -y --no-install-recommends \
    git \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Create non-root system user and group (UID 1000)
RUN groupadd -g 1000 sutra && \
    useradd -u 1000 -g sutra -s /bin/bash -m sutra

# Copy installed dependencies from builder
COPY --from=builder /install /usr/local

# Copy application source
COPY backend /app/backend
COPY alembic.ini /app/alembic.ini
COPY backend/alembic /app/backend/alembic

# Create storage directory and set permissions
RUN mkdir -p /app/data/repositories && \
    chown -R sutra:sutra /app

# Switch to non-root user
USER sutra:sutra

EXPOSE 8000

HEALTHCHECK --interval=10s --timeout=3s --start-period=5s --retries=3 \
  CMD curl -f http://localhost:8000/health || exit 1

CMD ["uvicorn", "app.main:app", "--app-dir", "backend", "--host", "0.0.0.0", "--port", "8000"]

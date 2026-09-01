# SUTRA Production Deployment Procedure

## Executive Overview
This document defines the zero-downtime, fail-closed deployment workflow for SUTRA v0.3.7.

---

## Pre-Deployment Requirements
1. Environment variables set: `APP_ENV=production`, `DEBUG=false`, `JWT_SECRET` (>=32 chars, non-default), `EVENT_INTEGRITY_KEY` (>=32 chars, non-default), `DATABASE_URL`.
2. Docker / OCI container runtime available with non-root execution support.

---

## Step-by-Step Deployment Sequence

```bash
# 1. Build Production Container Artifact
docker build -t sutra-api:v0.3.7 -f Dockerfile .

# 2. Verify Database Schema Migration Status
python -m alembic current
python -m alembic upgrade head

# 3. Start Application Service (Non-Root User)
docker run -d \
  --name sutra-api \
  --user 1000:1000 \
  -p 8000:8000 \
  -e APP_ENV=production \
  -e DEBUG=false \
  -e DATABASE_URL="$DATABASE_URL" \
  -e JWT_SECRET="$JWT_SECRET" \
  -e EVENT_INTEGRITY_KEY="$EVENT_INTEGRITY_KEY" \
  -v /var/sutra/data:/app/data \
  sutra-api:v0.3.7

# 4. Verify Health and Readiness
curl -f http://localhost:8000/health
curl -f http://localhost:8000/ready
```

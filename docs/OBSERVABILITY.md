# SUTRA Observability & Structured Logging Specification

## Executive Overview
SUTRA enforces structured JSON logging and Prometheus-compatible metric collection (`/metrics`) for operational monitoring.

---

## Log Sanitization & Correlation Rules

1. **Correlation Information**: Log records include `request_id`, `task_id`, `pull_request_id`, `change_id`, `repository_id`, `actor_id`.
2. **Redaction Rules**: Secrets, JWT tokens, passwords, HMAC keys, and `DATABASE_URL` credentials are automatically redacted (`[REDACTED]`).
3. **Metrics Endpoint**: `GET /metrics` exposes Prometheus counters for HTTP requests, Git merges, CAS failures, CI sandbox failures, and task completions.

# SUTRA Disaster Recovery Plan (RPO / RTO)

## Executive Overview
This document specifies Recovery Point Objectives (RPO) and Recovery Time Objectives (RTO) for SUTRA infrastructure components.

---

## Recovery Targets

| Component | Target RPO | Target RTO | Strategy |
|---|---|---|---|
| PostgreSQL 17 Database | < 15 minutes | < 30 minutes | WAL archiving / PITR + `db_restore.ps1` |
| Bare Git Repositories | < 1 hour | < 1 hour | Storage snapshot / disk rsync |
| API Containers | 0 seconds | < 2 minutes | Stateless container re-deployment |
| Worker Processes | 0 seconds | < 1 minute | Worker lease recovery protocol |

---

## Secret Rotation Procedure
1. Generate new `JWT_SECRET` and `EVENT_INTEGRITY_KEY` (>= 32 characters).
2. Update production environment variables.
3. Perform rolling container restart (`docker restart sutra-api`).
4. Re-issue agent authentication tokens.

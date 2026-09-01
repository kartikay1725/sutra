# SUTRA Production Rollback Procedure

## Executive Overview
This document details the procedure to safely roll back SUTRA to a previous verified release without data loss or schema corruption.

---

## Safe Rollback Sequence

1. **Traffic Draining**: Redirect ingress router to maintenance mode or previous container instance.
2. **Database Schema Integrity**: SUTRA migrations are strictly backward-compatible. Do NOT execute destructive schema downgrades on active production databases.
3. **Container Rollback**:
   ```bash
   docker stop sutra-api
   docker run -d --name sutra-api --user 1000:1000 -p 8000:8000 sutra-api:v0.3.6
   ```
4. **Readiness Verification**:
   ```bash
   curl -f http://localhost:8000/ready
   ```
5. **Git Storage Audit**: Re-read Git repository storage integrity using `git rev-parse refs/heads/main`.

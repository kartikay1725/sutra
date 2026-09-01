# SUTRA — CI Container Sandbox Architecture (v0.3.4-sandbox)

## Overview
This document specifies the containerized sandbox architecture for SUTRA's CI Runner (v0.3.4-sandbox). The sandbox converts CI job execution from host-process execution to ephemeral, containerized execution using OCI / Docker runtime isolation.

---

## Architectural Isolation Boundary

```
FastAPI / CIService
       │
       ▼
  CIRunner.execute_job
       │
       ▼
  CISandbox.run_container(job)
       │
       ▼
  docker run
    --rm
    --network=none
    --user=1000:1000
    --cap-drop=ALL
    --security-opt=no-new-privileges:true
    --cpus=1.0
    --memory=512m
    --pids-limit=100
    --env CI=true
    --env SUTRA_CI_JOB_ID={job_id}
    --env SUTRA_CI_COMMIT_SHA={commit_sha}
    python:3.13-slim python -c "..."
```

---

## Security Controls & Invariants

1. **Network Namespace Isolation (`--network=none`)**:
   - Complete network isolation. The execution container cannot reach `localhost`, `127.0.0.1`, `::1`, PostgreSQL (port 55432), SUTRA API, Docker daemon socket, or outbound internet.
2. **Filesystem & Mount Isolation**:
   - The SUTRA application host filesystem, `.env` file, database credentials, host user profiles, and application code are **NEVER mounted** into the container.
   - Container execution takes place entirely within an ephemeral container environment destroyed upon exit (`--rm`).
3. **Process Namespace & Capability Hardening**:
   - Non-root user (`--user=1000:1000`).
   - Drop all Linux capabilities (`--cap-drop=ALL`).
   - Prevent privilege escalation (`--security-opt=no-new-privileges:true`).
   - Isolated container PID namespace.
4. **Resource Constraints**:
   - Max 1 CPU core (`--cpus=1.0`).
   - Max 512 MB RAM (`--memory=512m`).
   - Max 100 process threads (`--pids-limit=100`).
   - Execution timeout enforced at runner boundary (30 seconds).
5. **Secret Stripping**:
   - `DATABASE_URL`, `SECRET_KEY`, `JWT_SECRET`, agent tokens, and cloud credentials are excluded from container environment variables.

# SUTRA Production Architecture & Topology Specification

## Executive Overview
SUTRA v0.3.7 is an AI-native, Git-compatible engineering platform with safe server-side Git merge transport, Docker OCI container sandbox isolation, PostgreSQL 17 transaction safety, and worker lease recovery guarantees.

---

## Topology & Core Components

```
                +----------------------------+
                |  Reverse Proxy / Ingress   |
                |  (TLS Termination / NGINX) |
                +-------------+--------------+
                              |
       +----------------------+----------------------+
       |                                             |
+------v--------------------+             +----------v-----------------+
|  SUTRA API Server (FastAPI)|             |  Background Event Worker   |
|  - Auth, PRs, Tasks, Git  |             |  - GitPushEvent Processing |
|  - Compare-and-Swap (CAS) |             |  - Worker Lease Recovery   |
+--------------+------------+             +----------+-----------------+
               |                                     |
               +------------------+------------------+
                                  |
            +---------------------+---------------------+
            |                                           |
+-----------v---------------+               +-----------v---------------+
|  PostgreSQL 17 Database   |               |  Bare Git Storage (/data) |
|  - Transactional DDL      |               |  - CAS Ref Updates        |
|  - Change / PR / Tasks    |               |  - Non-root UID 1000      |
+---------------------------+               +---------------------------+
                                  |
                    +-------------v-------------+
                    | Docker CI Sandbox (OCI)   |
                    | --network=none            |
                    | --cap-drop=ALL            |
                    | --user=1000:1000          |
                    +---------------------------+
```

---

## Component Inventory

1. **API Server (FastAPI)**: Stateless API instance, handles HTTP requests, authentication, authorization, PR orchestration, and Git HTTP transport.
2. **PostgreSQL 17**: Transactional state storage (`changes`, `pull_requests`, `tasks`, `users`, `actors`, `change_events`, `ci_jobs`).
3. **Bare Git Storage**: Local persistent disk storage (`./data/repositories`) for Git repositories using atomic Compare-and-Swap (CAS) ref updates.
4. **CI Runner & Sandbox**: Docker/OCI container isolation (`--network=none`, `--cap-drop=ALL`, `--user=1000:1000`, 512MB RAM, 1 CPU).
5. **Background Workers**: Asynchronous event consumers processing `git_push_events` with lease locks and recovery handlers.

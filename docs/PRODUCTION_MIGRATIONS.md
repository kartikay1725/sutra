# SUTRA Production Database Migrations Specification

## Executive Overview
SUTRA uses Alembic with PostgreSQL 17 for schema migrations. All migrations are transactional DDL compliant and verified with zero production DB audit violations.

---

## Migration Invariants

1. **Explicit Execution**: Migrations are NOT executed automatically on API startup. They are executed explicitly via release automation (`alembic upgrade head`).
2. **Current Head**: `a2b3c4d5e678` (add_tasks_table).
3. **No Automatic DDL (`create_all`)**: `Base.metadata.create_all()` is prohibited in production runtime.
4. **Production DB Audit**: Every migration must pass `scripts/production_db_audit.py` with 0 violations.

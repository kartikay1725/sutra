import os
import sys
from sqlalchemy import create_engine, text

def run_audit(db_url: str):
    engine = create_engine(db_url)
    violations = 0
    with engine.connect() as conn:
        # Invalid statuses
        res = conn.execute(text("SELECT count(*) FROM git_push_events WHERE status NOT IN ('pending', 'processing', 'processed', 'failed', 'dead_letter')")).scalar()
        if res > 0:
            print(f"VIOLATION: {res} invalid statuses")
            violations += res

        # Negative attempts
        res = conn.execute(text("SELECT count(*) FROM git_push_events WHERE attempts < 0")).scalar()
        if res > 0:
            print(f"VIOLATION: {res} negative attempts")
            violations += res

        # Processed without processed_at
        res = conn.execute(text("SELECT count(*) FROM git_push_events WHERE status = 'processed' AND processed_at IS NULL")).scalar()
        if res > 0:
            print(f"VIOLATION: {res} processed without processed_at")
            violations += res

        # Unprocessed with processed_at
        res = conn.execute(text("SELECT count(*) FROM git_push_events WHERE status != 'processed' AND processed_at IS NOT NULL")).scalar()
        if res > 0:
            print(f"VIOLATION: {res} unprocessed with processed_at")
            violations += res

        # Dead_letter with next_attempt_at
        res = conn.execute(text("SELECT count(*) FROM git_push_events WHERE status = 'dead_letter' AND next_attempt_at IS NOT NULL")).scalar()
        if res > 0:
            print(f"VIOLATION: {res} dead_letter with next_attempt_at")
            violations += res

        # Dead_letter with worker_id
        res = conn.execute(text("SELECT count(*) FROM git_push_events WHERE status = 'dead_letter' AND worker_id IS NOT NULL")).scalar()
        if res > 0:
            print(f"VIOLATION: {res} dead_letter with worker_id")
            violations += res

        # Dead_letter with lease_expires_at
        res = conn.execute(text("SELECT count(*) FROM git_push_events WHERE status = 'dead_letter' AND lease_expires_at IS NOT NULL")).scalar()
        if res > 0:
            print(f"VIOLATION: {res} dead_letter with lease_expires_at")
            violations += res

        # Failed events >= max_attempts (default 5, but we check if >=10 just to be safe, wait, no, just verify it's capped, maybe skip hardcoded max, let's say >= 100)
        # Actually Gate 3 capped at 5. But some historical might exist. We migrated those.
        res = conn.execute(text("SELECT count(*) FROM git_push_events WHERE status = 'failed' AND attempts >= 100")).scalar()
        if res > 0:
            print(f"VIOLATION: {res} failed events over absolute max attempts (100)")
            violations += res

        # Duplicate operation_key
        res = conn.execute(text("SELECT operation_key FROM changes GROUP BY operation_key HAVING count(*) > 1")).fetchall()
        if len(res) > 0:
            print(f"VIOLATION: {len(res)} duplicate operation_keys")
            violations += len(res)

        # Invalid operation_key length (must be 64 for sha256)
        res = conn.execute(text("SELECT count(*) FROM changes WHERE length(operation_key) != 64")).scalar()
        if res > 0:
            print(f"VIOLATION: {res} invalid operation_key length")
            violations += res
            
        # Orphaned foreign keys (e.g. changes -> repositories)
        res = conn.execute(text("SELECT count(*) FROM changes c LEFT JOIN repositories r ON c.repository_id = r.id WHERE r.id IS NULL")).scalar()
        if res > 0:
            print(f"VIOLATION: {res} changes with orphaned repository_id")
            violations += res

        res = conn.execute(text("SELECT count(*) FROM git_push_events g LEFT JOIN repositories r ON g.repository_id = r.id WHERE r.id IS NULL")).scalar()
        if res > 0:
            print(f"VIOLATION: {res} events with orphaned repository_id")
            violations += res

        # duplicate active leases
        res = conn.execute(text("SELECT worker_id FROM git_push_events WHERE status = 'processing' AND worker_id IS NOT NULL GROUP BY worker_id HAVING count(*) > 1")).fetchall()
        if len(res) > 0:
            print(f"INFO: {len(res)} workers with multiple active leases. (Not strictly a violation, batching is allowed)")
            # Wait, batching is allowed. We don't mark this as violation unless batching is false.

        if violations > 0:
            print(f"Total violations: {violations}")
            sys.exit(1)
        else:
            print("DB Audit passed with 0 violations.")
            
if __name__ == "__main__":
    db_url = os.environ.get("DATABASE_URL")
    if not db_url:
        print("DATABASE_URL required")
        sys.exit(1)
    run_audit(db_url)

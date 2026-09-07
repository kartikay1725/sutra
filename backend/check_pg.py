from app.db.session import SessionLocal
from sqlalchemy import text

db = SessionLocal()
res = db.execute(text("SELECT pid, wait_event_type, wait_event, state, left(query, 120) FROM pg_stat_activity WHERE datname = 'sutra' AND pid != pg_backend_pid();")).fetchall()
for r in res:
    print(r)
db.close()

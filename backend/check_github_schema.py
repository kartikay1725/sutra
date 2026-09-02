from app.core.config import settings
from sqlalchemy import create_engine, text

engine = create_engine(settings.database_url)

with engine.connect() as conn:
    print("RELATION:")
    print(conn.execute(text("""
        SELECT
            n.nspname AS schema_name,
            c.relname,
            c.relkind,
            pg_get_userbyid(c.relowner) AS owner
        FROM pg_class c
        JOIN pg_namespace n ON n.oid = c.relnamespace
        WHERE c.relname = 'ix_github_installations_user_id';
    """)).mappings().all())

    print("\nTABLE:")
    print(conn.execute(text("""
        SELECT to_regclass('public.github_installations');
    """)).scalar())

    print("\nINDEXES:")
    print(conn.execute(text("""
        SELECT indexname, indexdef
        FROM pg_indexes
        WHERE schemaname = 'public'
          AND tablename = 'github_installations';
    """)).mappings().all())

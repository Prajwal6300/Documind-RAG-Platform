"""Run SQL migrations against the Supabase PostgreSQL database."""

import os
import sys
from pathlib import Path
import psycopg
from dotenv import load_dotenv

ROOT_DIR = Path(__file__).resolve().parent.parent
MIGRATIONS_DIR = ROOT_DIR / "migrations"

load_dotenv()


def run_migrations():
    db_url = os.getenv("DATABASE_URL", "").strip()
    if not db_url:
        print("[ERROR] DATABASE_URL is not set in environment or .env file.")
        sys.exit(1)

    print("=" * 70)
    print("DOCUMIND SUPABASE MIGRATION RUNNER")
    print("=" * 70)

    migration_files = sorted(MIGRATIONS_DIR.glob("*.sql"))
    if not migration_files:
        print(f"[WARN] No .sql migration files found in {MIGRATIONS_DIR}")
        return

    print(f"Connecting to database and running {len(migration_files)} migration(s)...")

    with psycopg.connect(db_url, autocommit=True) as conn:
        with conn.cursor() as cur:
            for sql_file in migration_files:
                print(f"\n--> Applying migration: {sql_file.name}")
                with open(sql_file, "r", encoding="utf-8") as f:
                    sql_content = f.read()

                # Split statements by semicolon where appropriate, or execute full script
                cur.execute(sql_content)
                print(f"    [OK] Applied {sql_file.name}")

            # Verify tables created
            cur.execute("""
                SELECT table_name 
                FROM information_schema.tables 
                WHERE table_schema = 'public'
                ORDER BY table_name;
            """)
            tables = [r[0] for r in cur.fetchall()]
            print("\n[VERIFICATION] Public tables in Supabase:")
            for t in tables:
                print(f"  - {t}")

            # Verify indexes
            cur.execute("""
                SELECT indexname, tablename 
                FROM pg_indexes 
                WHERE schemaname = 'public'
                ORDER BY tablename, indexname;
            """)
            indexes = cur.fetchall()
            print("\n[VERIFICATION] Indexes in Supabase:")
            for idx_name, tbl_name in indexes:
                print(f"  - {tbl_name}.{idx_name}")

    print("\n" + "=" * 70)
    print("ALL MIGRATIONS APPLIED SUCCESSFULLY!")
    print("=" * 70)


if __name__ == "__main__":
    run_migrations()

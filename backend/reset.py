"""
reset_db.py
───────────────────────────────────────────────────
Drops all SentinelIQ tables and recreates them fresh.
Run this from the backend folder:

    python reset_db.py

It reads DATABASE_URL from your .env automatically.
───────────────────────────────────────────────────
"""
import os
import sys

# Load .env manually (no extra libs needed)
env_path = os.path.join(os.path.dirname(__file__), ".env")
if os.path.exists(env_path):
    with open(env_path) as f:
        for line in f:
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                key, _, val = line.partition("=")
                os.environ.setdefault(key.strip(), val.strip())

db_url = os.environ.get("DATABASE_URL")
if not db_url:
    print("ERROR: DATABASE_URL not found in .env")
    sys.exit(1)

print(f"  Connecting to: {db_url}\n")

from sqlalchemy import create_engine, text

engine = create_engine(db_url)

DROP_SQL = """
DROP TABLE IF EXISTS sessions CASCADE;
DROP TABLE IF EXISTS user_devices CASCADE;
DROP TABLE IF EXISTS user_behavior_profiles CASCADE;
DROP TABLE IF EXISTS login_events CASCADE;
DROP TABLE IF EXISTS users CASCADE;
DROP TABLE IF EXISTS alembic_version CASCADE;
DROP TYPE IF EXISTS userrole CASCADE;
DROP TYPE IF EXISTS loginoutcome CASCADE;
"""

print("  Dropping all tables...")
with engine.begin() as conn:
    conn.execute(text(DROP_SQL))
print("  Done — all tables dropped.\n")

print("  Now run:  alembic upgrade head")
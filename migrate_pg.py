#!/usr/bin/env python3
"""
PostgreSQL Migration Script - Add missing columns to businesses table
Idempotent: safe to run multiple times
"""

import os
import sys
import psycopg2
from psycopg2 import sql

def migrate():
    """Apply migrations to PostgreSQL"""
    database_url = os.environ.get("DATABASE_URL")

    if not database_url:
        print("ERROR: DATABASE_URL environment variable not set")
        sys.exit(1)

    # Migrations to apply (idempotent with IF NOT EXISTS)
    migrations = [
        "ALTER TABLE businesses ADD COLUMN IF NOT EXISTS business_code VARCHAR(6) UNIQUE",
        "ALTER TABLE businesses ADD COLUMN IF NOT EXISTS logo_url TEXT",
    ]

    try:
        conn = psycopg2.connect(database_url)
        cur = conn.cursor()

        print("Applying PostgreSQL migrations...")
        for migration_sql in migrations:
            print(f"  → {migration_sql}")
            cur.execute(migration_sql)

        conn.commit()
        cur.close()
        conn.close()

        print("\n✅ Migration completed successfully!")
        return 0

    except psycopg2.Error as e:
        print(f"\n❌ Database error: {e}")
        sys.exit(1)
    except Exception as e:
        print(f"\n❌ Error: {e}")
        sys.exit(1)

if __name__ == "__main__":
    migrate()

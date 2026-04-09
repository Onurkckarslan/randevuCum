#!/usr/bin/env python3
"""
Database Migration Script - Add subscription columns
Run from Render shell: python add_columns.py
"""
import os
from sqlalchemy import text
from app.database import engine, SessionLocal

def run_migrations():
    db = SessionLocal()
    try:
        print("🔧 Starting migrations...")

        # 1. Add subscription columns
        columns = {
            "subscription_status": "VARCHAR(20) DEFAULT 'trial'",
            "paytr_card_token": "VARCHAR(255)",
            "card_last4": "VARCHAR(4)",
            "card_brand": "VARCHAR(20)",
            "next_billing_date": "TIMESTAMP",
            "payment_failed_count": "INTEGER DEFAULT 0"
        }

        for col_name, col_type in columns.items():
            try:
                query = f"ALTER TABLE businesses ADD COLUMN {col_name} {col_type}"
                db.execute(text(query))
                print(f"✅ Added column: {col_name}")
            except Exception as e:
                if "already exists" in str(e) or "duplicate" in str(e):
                    print(f"⏭️  Column {col_name} already exists")
                else:
                    print(f"❌ Error adding {col_name}: {e}")

        # 2. Create payments table
        try:
            db.execute(text("""
                CREATE TABLE IF NOT EXISTS payments (
                    id SERIAL PRIMARY KEY,
                    business_id INTEGER NOT NULL REFERENCES businesses(id) ON DELETE CASCADE,
                    amount INTEGER NOT NULL,
                    plan_type VARCHAR(20),
                    status VARCHAR(20) DEFAULT 'pending',
                    paytr_ref_no VARCHAR(100),
                    error_msg VARCHAR(255),
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    paid_at TIMESTAMP
                )
            """))
            print("✅ Created payments table")
        except Exception as e:
            print(f"⏭️  Payments table already exists or error: {e}")

        # 3. Create indexes
        indexes = [
            ("idx_payments_business_id", "CREATE INDEX IF NOT EXISTS idx_payments_business_id ON payments(business_id)"),
            ("idx_payments_status", "CREATE INDEX IF NOT EXISTS idx_payments_status ON payments(status)"),
            ("idx_businesses_subscription", "CREATE INDEX IF NOT EXISTS idx_businesses_subscription ON businesses(subscription_status)")
        ]

        for idx_name, idx_query in indexes:
            try:
                db.execute(text(idx_query))
                print(f"✅ Created index: {idx_name}")
            except Exception as e:
                print(f"⏭️  Index {idx_name} already exists")

        db.commit()
        print("\n✨ All migrations completed successfully!")

    except Exception as e:
        db.rollback()
        print(f"❌ Migration failed: {e}")
        import traceback
        traceback.print_exc()
    finally:
        db.close()

if __name__ == "__main__":
    run_migrations()

-- Migration: Add subscription columns to businesses table
-- Run this directly on your Render PostgreSQL database

-- 1. Add subscription columns to businesses table
ALTER TABLE businesses ADD COLUMN IF NOT EXISTS subscription_status VARCHAR(20) DEFAULT 'trial';
ALTER TABLE businesses ADD COLUMN IF NOT EXISTS paytr_card_token VARCHAR(255);
ALTER TABLE businesses ADD COLUMN IF NOT EXISTS card_last4 VARCHAR(4);
ALTER TABLE businesses ADD COLUMN IF NOT EXISTS card_brand VARCHAR(20);
ALTER TABLE businesses ADD COLUMN IF NOT EXISTS next_billing_date TIMESTAMP;
ALTER TABLE businesses ADD COLUMN IF NOT EXISTS payment_failed_count INTEGER DEFAULT 0;

-- 2. Create payments table
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
);

-- 3. Create index for faster lookups
CREATE INDEX IF NOT EXISTS idx_payments_business_id ON payments(business_id);
CREATE INDEX IF NOT EXISTS idx_payments_status ON payments(status);
CREATE INDEX IF NOT EXISTS idx_businesses_subscription_status ON businesses(subscription_status);

-- Done
SELECT 'Migration completed successfully' as status;

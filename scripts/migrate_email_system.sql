-- Email System Migration SQL Script
-- Run this on your Render PostgreSQL database to add email verification and password reset
--
-- How to use on Render (Free Tier):
-- 1. Go to Render Dashboard → Your PostgreSQL Database
-- 2. Click "Info" → Copy "External Database URL"
-- 3. Install psql locally if needed
-- 4. Connect: psql <external-database-url>
-- 5. Copy and paste this entire file

-- =============================================================================
-- STEP 1: Add email verification columns
-- =============================================================================

DO $$
BEGIN
    -- Add email_verified column
    IF NOT EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE table_name = 'Users' AND column_name = 'email_verified'
    ) THEN
        ALTER TABLE "Users" ADD COLUMN email_verified BOOLEAN DEFAULT FALSE NOT NULL;
        RAISE NOTICE 'Column email_verified added successfully';
    ELSE
        RAISE NOTICE 'Column email_verified already exists';
    END IF;

    -- Add verification_token column
    IF NOT EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE table_name = 'Users' AND column_name = 'verification_token'
    ) THEN
        ALTER TABLE "Users" ADD COLUMN verification_token VARCHAR(100) UNIQUE;
        RAISE NOTICE 'Column verification_token added successfully';
    ELSE
        RAISE NOTICE 'Column verification_token already exists';
    END IF;

    -- Add verification_token_expires column
    IF NOT EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE table_name = 'Users' AND column_name = 'verification_token_expires'
    ) THEN
        ALTER TABLE "Users" ADD COLUMN verification_token_expires TIMESTAMP;
        RAISE NOTICE 'Column verification_token_expires added successfully';
    ELSE
        RAISE NOTICE 'Column verification_token_expires already exists';
    END IF;
END $$;

-- =============================================================================
-- STEP 2: Add password reset columns
-- =============================================================================

DO $$
BEGIN
    -- Add reset_token column
    IF NOT EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE table_name = 'Users' AND column_name = 'reset_token'
    ) THEN
        ALTER TABLE "Users" ADD COLUMN reset_token VARCHAR(100) UNIQUE;
        RAISE NOTICE 'Column reset_token added successfully';
    ELSE
        RAISE NOTICE 'Column reset_token already exists';
    END IF;

    -- Add reset_token_expires column
    IF NOT EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE table_name = 'Users' AND column_name = 'reset_token_expires'
    ) THEN
        ALTER TABLE "Users" ADD COLUMN reset_token_expires TIMESTAMP;
        RAISE NOTICE 'Column reset_token_expires added successfully';
    ELSE
        RAISE NOTICE 'Column reset_token_expires already exists';
    END IF;
END $$;

-- =============================================================================
-- STEP 3: Add session management column
-- =============================================================================

DO $$
BEGIN
    -- Add session_token column
    IF NOT EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE table_name = 'Users' AND column_name = 'session_token'
    ) THEN
        ALTER TABLE "Users" ADD COLUMN session_token VARCHAR(100);
        RAISE NOTICE 'Column session_token added successfully';
    ELSE
        RAISE NOTICE 'Column session_token already exists';
    END IF;
END $$;

-- =============================================================================
-- STEP 4: Add email notification preference columns
-- =============================================================================

DO $$
BEGIN
    -- Add email_notifications_enabled column
    IF NOT EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE table_name = 'Users' AND column_name = 'email_notifications_enabled'
    ) THEN
        ALTER TABLE "Users" ADD COLUMN email_notifications_enabled BOOLEAN DEFAULT TRUE NOT NULL;
        RAISE NOTICE 'Column email_notifications_enabled added successfully';
    ELSE
        RAISE NOTICE 'Column email_notifications_enabled already exists';
    END IF;

    -- Add email_workout_reminders column
    IF NOT EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE table_name = 'Users' AND column_name = 'email_workout_reminders'
    ) THEN
        ALTER TABLE "Users" ADD COLUMN email_workout_reminders BOOLEAN DEFAULT FALSE NOT NULL;
        RAISE NOTICE 'Column email_workout_reminders added successfully';
    ELSE
        RAISE NOTICE 'Column email_workout_reminders already exists';
    END IF;

    -- Add email_group_activity column
    IF NOT EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE table_name = 'Users' AND column_name = 'email_group_activity'
    ) THEN
        ALTER TABLE "Users" ADD COLUMN email_group_activity BOOLEAN DEFAULT TRUE NOT NULL;
        RAISE NOTICE 'Column email_group_activity added successfully';
    ELSE
        RAISE NOTICE 'Column email_group_activity already exists';
    END IF;
END $$;

-- =============================================================================
-- STEP 5: Initialize session tokens for existing users
-- =============================================================================

UPDATE "Users"
SET session_token = md5(random()::text || user_id::text)
WHERE session_token IS NULL;

-- =============================================================================
-- STEP 6: Create SecurityEvents table
-- =============================================================================

CREATE TABLE IF NOT EXISTS "SecurityEvents" (
    event_id SERIAL PRIMARY KEY,
    email VARCHAR(100),
    ip_address VARCHAR(50) NOT NULL,
    event_type VARCHAR(50) NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Create indexes for better query performance
CREATE INDEX IF NOT EXISTS idx_security_events_email
ON "SecurityEvents"(email);

CREATE INDEX IF NOT EXISTS idx_security_events_ip
ON "SecurityEvents"(ip_address);

CREATE INDEX IF NOT EXISTS idx_security_events_created
ON "SecurityEvents"(created_at DESC);

-- =============================================================================
-- VERIFICATION: Check that everything worked
-- =============================================================================

-- Show all new columns in Users table
SELECT column_name, data_type, is_nullable, column_default
FROM information_schema.columns
WHERE table_name = 'Users'
  AND column_name IN (
    'email_verified', 'verification_token', 'verification_token_expires',
    'reset_token', 'reset_token_expires', 'session_token',
    'email_notifications_enabled', 'email_workout_reminders', 'email_group_activity'
  )
ORDER BY column_name;

-- Verify SecurityEvents table exists
SELECT table_name
FROM information_schema.tables
WHERE table_name = 'SecurityEvents';

-- Show user count and how many have session tokens
SELECT
    COUNT(*) as total_users,
    COUNT(session_token) as users_with_session_token,
    COUNT(CASE WHEN email_verified THEN 1 END) as verified_users
FROM "Users";


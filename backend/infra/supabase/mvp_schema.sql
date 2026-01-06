-- ============================================================================
-- SnapGrid MVP Schema Migration
-- ============================================================================
-- This file adds the necessary tables for the MVP web application.
-- Run this AFTER the base schema.sql has been applied.
--
-- USAGE:
-- 1. Go to your Supabase project dashboard
-- 2. Navigate to SQL Editor
-- 3. Paste this entire file and run it
-- ============================================================================

-- ============================================================================
-- MODIFY EXISTING TABLES
-- ============================================================================

-- Add user_id to existing projects table for auth integration
ALTER TABLE projects ADD COLUMN IF NOT EXISTS user_id UUID REFERENCES auth.users(id);
CREATE INDEX IF NOT EXISTS idx_projects_user_id ON projects(user_id);

-- Add user_id to existing files table
ALTER TABLE files ADD COLUMN IF NOT EXISTS user_id UUID REFERENCES auth.users(id);
CREATE INDEX IF NOT EXISTS idx_files_user_id ON files(user_id);

-- ============================================================================
-- JOBS TABLE - Job Queue for Processing
-- ============================================================================
-- Tracks extraction jobs with their status and results.
-- Each job processes one file and produces area_results.

CREATE TABLE IF NOT EXISTS jobs (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID NOT NULL REFERENCES auth.users(id) ON DELETE CASCADE,
    project_id UUID NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
    file_id UUID NOT NULL REFERENCES files(id) ON DELETE CASCADE,

    -- Job type and status
    job_type TEXT NOT NULL DEFAULT 'area_text',  -- 'area_text', 'doors_text', 'area_cv', 'doors_cv'
    status TEXT NOT NULL DEFAULT 'queued',       -- 'queued', 'processing', 'completed', 'failed'

    -- Processing configuration
    config JSONB DEFAULT '{}',  -- {page_number, scale, balcony_factor, etc.}

    -- Results (denormalized for quick access)
    result_json JSONB,          -- Full extraction result
    total_area_m2 REAL,         -- Quick access aggregates
    total_rooms INTEGER,

    -- Error handling
    error_message TEXT,
    retry_count INTEGER DEFAULT 0,

    -- Timing
    queued_at TIMESTAMPTZ DEFAULT NOW(),
    started_at TIMESTAMPTZ,
    completed_at TIMESTAMPTZ,
    processing_time_ms INTEGER,

    created_at TIMESTAMPTZ DEFAULT NOW(),

    -- Constraints
    CONSTRAINT valid_job_type CHECK (job_type IN ('area_text', 'doors_text', 'area_cv', 'doors_cv', 'drywall_text', 'flooring_text')),
    CONSTRAINT valid_status CHECK (status IN ('queued', 'processing', 'completed', 'failed'))
);

CREATE INDEX IF NOT EXISTS idx_jobs_user_id ON jobs(user_id);
CREATE INDEX IF NOT EXISTS idx_jobs_project_id ON jobs(project_id);
CREATE INDEX IF NOT EXISTS idx_jobs_file_id ON jobs(file_id);
CREATE INDEX IF NOT EXISTS idx_jobs_status ON jobs(status);
CREATE INDEX IF NOT EXISTS idx_jobs_queued ON jobs(status, queued_at) WHERE status = 'queued';
CREATE INDEX IF NOT EXISTS idx_jobs_created_at ON jobs(created_at DESC);

COMMENT ON TABLE jobs IS 'Job queue for PDF extraction processing';
COMMENT ON COLUMN jobs.job_type IS 'Type of extraction: area_text (NRF from text), doors_text (door schedule), etc.';
COMMENT ON COLUMN jobs.config IS 'JSON configuration: {page_number, scale, balcony_factor, wall_height_m}';

-- ============================================================================
-- AREA_RESULTS TABLE - Individual Room Extractions with Audit Trail
-- ============================================================================
-- Stores each extracted room with full traceability back to source PDF.
-- Critical for zero-hallucination principle: every number traces to source.

CREATE TABLE IF NOT EXISTS area_results (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    job_id UUID NOT NULL REFERENCES jobs(id) ON DELETE CASCADE,

    -- Room identification
    room_id TEXT NOT NULL,           -- e.g., "B.03.1.001"
    room_name TEXT,                  -- e.g., "TRH B1", "Nutzungseinheit"
    room_type TEXT,                  -- e.g., "Stairwell", "Unit", "Balcony"

    -- Measurements
    area_m2 REAL NOT NULL,
    perimeter_m REAL,
    ceiling_height_m REAL,

    -- Balkon/Terrasse factor (configurable)
    area_factor REAL DEFAULT 1.0,    -- 0.5 for Balkon/Terrasse/Loggia
    effective_area_m2 REAL,          -- area_m2 * area_factor

    -- Audit trail (zero-hallucination principle)
    source_text TEXT,                -- Raw NRF text: "NRF: 42,18 m2"
    source_page INTEGER NOT NULL,
    source_bbox JSONB,               -- {x, y, width, height} in PDF coordinates
    confidence REAL DEFAULT 0.95,
    extraction_method TEXT DEFAULT 'text_extraction',

    created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_area_results_job_id ON area_results(job_id);
CREATE INDEX IF NOT EXISTS idx_area_results_room_type ON area_results(room_type);
CREATE INDEX IF NOT EXISTS idx_area_results_created_at ON area_results(created_at DESC);

COMMENT ON TABLE area_results IS 'Individual room extractions with full audit trail';
COMMENT ON COLUMN area_results.source_text IS 'Raw text from PDF that this value was extracted from';
COMMENT ON COLUMN area_results.source_bbox IS 'Bounding box in PDF coordinates: {x, y, width, height}';
COMMENT ON COLUMN area_results.area_factor IS 'Factor applied: 1.0 for normal rooms, 0.5 for Balkon/Terrasse/Loggia';

-- ============================================================================
-- JOB_TOTALS TABLE - Aggregated Totals per Job
-- ============================================================================
-- Pre-computed totals for quick display. Updated when job completes.

CREATE TABLE IF NOT EXISTS job_totals (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    job_id UUID UNIQUE NOT NULL REFERENCES jobs(id) ON DELETE CASCADE,

    -- Aggregated values
    total_rooms INTEGER DEFAULT 0,
    total_area_m2 REAL DEFAULT 0,
    total_effective_area_m2 REAL DEFAULT 0,  -- With factors applied
    total_perimeter_m REAL DEFAULT 0,

    -- Breakdown by type
    area_by_type JSONB DEFAULT '{}',  -- {"Unit": 450.5, "Stairwell": 120.0, "Balcony": 25.0}

    -- Configuration used
    balcony_factor REAL DEFAULT 0.5,

    computed_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_job_totals_job_id ON job_totals(job_id);

COMMENT ON TABLE job_totals IS 'Pre-computed aggregates for quick results display';

-- ============================================================================
-- STRIPE PLACEHOLDERS (Phase 2)
-- ============================================================================
-- Scaffolding for Stripe billing integration. No keys yet.

CREATE TABLE IF NOT EXISTS stripe_customers (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID UNIQUE NOT NULL REFERENCES auth.users(id) ON DELETE CASCADE,
    stripe_customer_id TEXT UNIQUE,
    email TEXT,
    name TEXT,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
    -- TODO Phase 2: Add payment_method_id, default_payment_method, etc.
);

CREATE INDEX IF NOT EXISTS idx_stripe_customers_user_id ON stripe_customers(user_id);
CREATE INDEX IF NOT EXISTS idx_stripe_customers_stripe_id ON stripe_customers(stripe_customer_id);

COMMENT ON TABLE stripe_customers IS 'Stripe customer records - Phase 2 placeholder';

CREATE TABLE IF NOT EXISTS subscriptions (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID NOT NULL REFERENCES auth.users(id) ON DELETE CASCADE,
    stripe_subscription_id TEXT UNIQUE,
    stripe_customer_id TEXT REFERENCES stripe_customers(stripe_customer_id),
    status TEXT DEFAULT 'inactive',  -- 'active', 'canceled', 'past_due', 'trialing', 'inactive'
    plan_id TEXT,                    -- 'free', 'pro', 'enterprise'
    current_period_start TIMESTAMPTZ,
    current_period_end TIMESTAMPTZ,
    cancel_at TIMESTAMPTZ,
    canceled_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
    -- TODO Phase 2: Add price_id, quantity, trial_end, etc.
);

CREATE INDEX IF NOT EXISTS idx_subscriptions_user_id ON subscriptions(user_id);
CREATE INDEX IF NOT EXISTS idx_subscriptions_status ON subscriptions(status);
CREATE INDEX IF NOT EXISTS idx_subscriptions_stripe_id ON subscriptions(stripe_subscription_id);

COMMENT ON TABLE subscriptions IS 'User subscriptions - Phase 2 placeholder';

-- ============================================================================
-- ROW LEVEL SECURITY (RLS) POLICIES
-- ============================================================================
-- Enable RLS on all tables to ensure users can only access their own data.

-- Projects
ALTER TABLE projects ENABLE ROW LEVEL SECURITY;

DROP POLICY IF EXISTS "Users can view own projects" ON projects;
CREATE POLICY "Users can view own projects" ON projects
    FOR SELECT USING (auth.uid() = user_id);

DROP POLICY IF EXISTS "Users can create projects" ON projects;
CREATE POLICY "Users can create projects" ON projects
    FOR INSERT WITH CHECK (auth.uid() = user_id);

DROP POLICY IF EXISTS "Users can update own projects" ON projects;
CREATE POLICY "Users can update own projects" ON projects
    FOR UPDATE USING (auth.uid() = user_id);

DROP POLICY IF EXISTS "Users can delete own projects" ON projects;
CREATE POLICY "Users can delete own projects" ON projects
    FOR DELETE USING (auth.uid() = user_id);

-- Files
ALTER TABLE files ENABLE ROW LEVEL SECURITY;

DROP POLICY IF EXISTS "Users can view files in own projects" ON files;
CREATE POLICY "Users can view files in own projects" ON files
    FOR SELECT USING (
        user_id = auth.uid() OR
        project_id IN (SELECT id FROM projects WHERE user_id = auth.uid())
    );

DROP POLICY IF EXISTS "Users can create files in own projects" ON files;
CREATE POLICY "Users can create files in own projects" ON files
    FOR INSERT WITH CHECK (
        user_id = auth.uid() OR
        project_id IN (SELECT id FROM projects WHERE user_id = auth.uid())
    );

DROP POLICY IF EXISTS "Users can delete own files" ON files;
CREATE POLICY "Users can delete own files" ON files
    FOR DELETE USING (
        user_id = auth.uid() OR
        project_id IN (SELECT id FROM projects WHERE user_id = auth.uid())
    );

-- Jobs
ALTER TABLE jobs ENABLE ROW LEVEL SECURITY;

DROP POLICY IF EXISTS "Users can view own jobs" ON jobs;
CREATE POLICY "Users can view own jobs" ON jobs
    FOR SELECT USING (user_id = auth.uid());

DROP POLICY IF EXISTS "Users can create jobs" ON jobs;
CREATE POLICY "Users can create jobs" ON jobs
    FOR INSERT WITH CHECK (user_id = auth.uid());

DROP POLICY IF EXISTS "Users can update own jobs" ON jobs;
CREATE POLICY "Users can update own jobs" ON jobs
    FOR UPDATE USING (user_id = auth.uid());

-- Area Results
ALTER TABLE area_results ENABLE ROW LEVEL SECURITY;

DROP POLICY IF EXISTS "Users can view own area results" ON area_results;
CREATE POLICY "Users can view own area results" ON area_results
    FOR SELECT USING (
        job_id IN (SELECT id FROM jobs WHERE user_id = auth.uid())
    );

-- Job Totals
ALTER TABLE job_totals ENABLE ROW LEVEL SECURITY;

DROP POLICY IF EXISTS "Users can view own job totals" ON job_totals;
CREATE POLICY "Users can view own job totals" ON job_totals
    FOR SELECT USING (
        job_id IN (SELECT id FROM jobs WHERE user_id = auth.uid())
    );

-- Stripe Customers
ALTER TABLE stripe_customers ENABLE ROW LEVEL SECURITY;

DROP POLICY IF EXISTS "Users can view own stripe data" ON stripe_customers;
CREATE POLICY "Users can view own stripe data" ON stripe_customers
    FOR SELECT USING (user_id = auth.uid());

-- Subscriptions
ALTER TABLE subscriptions ENABLE ROW LEVEL SECURITY;

DROP POLICY IF EXISTS "Users can view own subscriptions" ON subscriptions;
CREATE POLICY "Users can view own subscriptions" ON subscriptions
    FOR SELECT USING (user_id = auth.uid());

-- ============================================================================
-- SERVICE ROLE POLICIES (for Edge Functions)
-- ============================================================================
-- These policies allow the service role to manage data during job processing.

-- Allow service role to insert area_results
DROP POLICY IF EXISTS "Service role can insert area results" ON area_results;
CREATE POLICY "Service role can insert area results" ON area_results
    FOR INSERT WITH CHECK (true);

-- Allow service role to insert job_totals
DROP POLICY IF EXISTS "Service role can insert job totals" ON job_totals;
CREATE POLICY "Service role can insert job totals" ON job_totals
    FOR INSERT WITH CHECK (true);

-- Allow service role to update jobs
DROP POLICY IF EXISTS "Service role can update jobs" ON jobs;
CREATE POLICY "Service role can update jobs" ON jobs
    FOR UPDATE USING (true);

-- ============================================================================
-- STORAGE BUCKET POLICIES
-- ============================================================================
-- These need to be created via Supabase Dashboard > Storage > Policies
-- Bucket: snapgrid-files (private)
--
-- Policy 1: Users can upload to their own folders
--   Operation: INSERT
--   Policy: (bucket_id = 'snapgrid-files') AND (auth.uid()::text = (storage.foldername(name))[1])
--
-- Policy 2: Users can view their own files
--   Operation: SELECT
--   Policy: (bucket_id = 'snapgrid-files') AND (auth.uid()::text = (storage.foldername(name))[1])
--
-- Policy 3: Users can delete their own files
--   Operation: DELETE
--   Policy: (bucket_id = 'snapgrid-files') AND (auth.uid()::text = (storage.foldername(name))[1])
--
-- Storage paths follow pattern: {user_id}/{project_id}/{file_id}/{filename}

-- ============================================================================
-- HELPER FUNCTIONS
-- ============================================================================

-- Function to get user's active subscription
CREATE OR REPLACE FUNCTION get_user_subscription(p_user_id UUID)
RETURNS TABLE (
    plan_id TEXT,
    status TEXT,
    current_period_end TIMESTAMPTZ
) AS $$
BEGIN
    RETURN QUERY
    SELECT s.plan_id, s.status, s.current_period_end
    FROM subscriptions s
    WHERE s.user_id = p_user_id
    AND s.status IN ('active', 'trialing')
    ORDER BY s.created_at DESC
    LIMIT 1;
END;
$$ LANGUAGE plpgsql SECURITY DEFINER;

-- Function to check if user has active subscription
CREATE OR REPLACE FUNCTION user_has_active_subscription(p_user_id UUID)
RETURNS BOOLEAN AS $$
BEGIN
    RETURN EXISTS (
        SELECT 1 FROM subscriptions
        WHERE user_id = p_user_id
        AND status IN ('active', 'trialing')
    );
END;
$$ LANGUAGE plpgsql SECURITY DEFINER;

-- ============================================================================
-- GRANTS
-- ============================================================================

-- Grant usage on schema to authenticated users
GRANT USAGE ON SCHEMA public TO authenticated;

-- Grant select on all tables to authenticated users (RLS will filter)
GRANT SELECT ON ALL TABLES IN SCHEMA public TO authenticated;

-- Grant insert/update/delete on user-owned tables
GRANT INSERT, UPDATE, DELETE ON projects TO authenticated;
GRANT INSERT, UPDATE, DELETE ON files TO authenticated;
GRANT INSERT, UPDATE ON jobs TO authenticated;

-- Grant execute on helper functions
GRANT EXECUTE ON FUNCTION get_user_subscription(UUID) TO authenticated;
GRANT EXECUTE ON FUNCTION user_has_active_subscription(UUID) TO authenticated;

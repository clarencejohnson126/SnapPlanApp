-- SnapGrid Supabase Schema
-- ========================
-- This file defines the database schema for SnapGrid's persistence layer.
--
-- USAGE:
-- 1. Go to your Supabase project dashboard
-- 2. Navigate to SQL Editor
-- 3. Paste this entire file and run it
-- 4. Create the storage bucket manually (see below)
--
-- STORAGE BUCKET:
-- Name: snapgrid-files
-- Public: false (private bucket)
-- Create via: Supabase Dashboard > Storage > New Bucket
--
-- The bucket stores uploaded PDFs which are referenced by files.storage_path
-- Storage paths follow the pattern: {project_id}/{file_id}/{original_filename}

-- ============================================================================
-- PROJECTS TABLE
-- ============================================================================
-- Projects group related files and extractions together.
-- A project might represent a building, construction site, or document set.

create table if not exists projects (
    id uuid primary key default gen_random_uuid(),
    name text not null,
    description text,
    created_at timestamptz not null default now(),
    updated_at timestamptz not null default now()
);

-- Index for listing projects by creation date
create index if not exists idx_projects_created_at on projects(created_at desc);

comment on table projects is 'Projects group related construction documents together';
comment on column projects.name is 'Human-readable project name (e.g., "Nordring Office Building")';
comment on column projects.description is 'Optional description or notes about the project';

-- ============================================================================
-- FILES TABLE
-- ============================================================================
-- Tracks uploaded PDF files and their storage location.
-- Each file belongs to an optional project and has a reference to Supabase Storage.

create table if not exists files (
    id uuid primary key default gen_random_uuid(),
    project_id uuid references projects(id) on delete set null,
    original_filename text not null,
    storage_path text not null,
    file_type text not null default 'schedule',
    file_size_bytes bigint,
    mime_type text default 'application/pdf',
    uploaded_by text,
    uploaded_at timestamptz not null default now(),

    -- Ensure storage paths are unique
    constraint unique_storage_path unique (storage_path)
);

-- Indexes for common queries
create index if not exists idx_files_project_id on files(project_id);
create index if not exists idx_files_uploaded_at on files(uploaded_at desc);
create index if not exists idx_files_file_type on files(file_type);

comment on table files is 'Uploaded PDF files stored in Supabase Storage';
comment on column files.storage_path is 'Path in Supabase Storage bucket (e.g., "project-id/file-id/filename.pdf")';
comment on column files.file_type is 'Type of document: schedule, drawing, other';
comment on column files.uploaded_by is 'Identifier of uploader (for future auth integration)';

-- ============================================================================
-- EXTRACTIONS TABLE
-- ============================================================================
-- Stores extraction results from processed files.
-- Each extraction is linked to a source file and contains the raw JSON output.

create table if not exists extractions (
    id uuid primary key default gen_random_uuid(),
    file_id uuid not null references files(id) on delete cascade,
    extraction_type text not null default 'schedule',
    status text not null default 'completed',
    raw_result_json jsonb not null,
    summary_json jsonb,
    row_count integer,
    table_count integer,
    processing_time_ms integer,
    created_at timestamptz not null default now(),

    -- Constraint to ensure valid status values
    constraint valid_status check (status in ('pending', 'processing', 'completed', 'failed'))
);

-- Indexes for common queries
create index if not exists idx_extractions_file_id on extractions(file_id);
create index if not exists idx_extractions_extraction_type on extractions(extraction_type);
create index if not exists idx_extractions_status on extractions(status);
create index if not exists idx_extractions_created_at on extractions(created_at desc);

-- GIN index for querying inside the JSON
create index if not exists idx_extractions_summary_gin on extractions using gin(summary_json);

comment on table extractions is 'Results from PDF extraction processing';
comment on column extractions.extraction_type is 'Type: schedule (tables), vector (measurements), ocr';
comment on column extractions.status is 'Processing status: pending, processing, completed, failed';
comment on column extractions.raw_result_json is 'Complete extraction output with all tables and auditability data';
comment on column extractions.summary_json is 'Aggregated summary (counts by type, dimensions, etc.)';

-- ============================================================================
-- HELPER FUNCTIONS
-- ============================================================================

-- Function to update the updated_at timestamp
create or replace function update_updated_at_column()
returns trigger as $$
begin
    new.updated_at = now();
    return new;
end;
$$ language plpgsql;

-- Trigger for projects table
drop trigger if exists update_projects_updated_at on projects;
create trigger update_projects_updated_at
    before update on projects
    for each row
    execute function update_updated_at_column();

-- ============================================================================
-- ROW LEVEL SECURITY (RLS) - Prepared for future auth
-- ============================================================================
-- RLS is disabled by default. Enable when adding authentication.
--
-- Example policies (uncomment when auth is implemented):
--
-- alter table projects enable row level security;
-- alter table files enable row level security;
-- alter table extractions enable row level security;
--
-- create policy "Users can view their own projects"
--     on projects for select
--     using (auth.uid()::text = created_by);

-- ============================================================================
-- SAMPLE DATA (Optional - for testing)
-- ============================================================================
-- Uncomment to insert a default project:
--
-- insert into projects (name, description)
-- values ('Sample Project', 'Default project for testing')
-- on conflict do nothing;

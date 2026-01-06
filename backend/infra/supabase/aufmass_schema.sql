-- ============================================
-- SNAPGRID AUFMASS ENGINE SCHEMA
-- ============================================
-- Additional tables for blueprint analysis, object detection, and measurement.
-- Extends the existing schema.sql tables (projects, files, extractions).
--
-- Run this AFTER schema.sql to add Aufmaß engine capabilities.
-- ============================================

-- ============================================
-- DETECTED OBJECTS
-- ============================================
-- Stores objects detected by the CV pipeline (doors, windows, rooms, etc.)

CREATE TABLE IF NOT EXISTS detected_objects (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),

    -- Foreign keys
    file_id UUID NOT NULL REFERENCES files(id) ON DELETE CASCADE,
    analysis_id UUID NOT NULL,  -- Groups objects from same analysis run

    -- Object identification
    object_type TEXT NOT NULL,  -- "door", "window", "room", "fixture", etc.
    label TEXT,  -- OCR-extracted label if found nearby

    -- Location in page (pixel coordinates)
    page_number INTEGER NOT NULL,
    bbox_x REAL NOT NULL,
    bbox_y REAL NOT NULL,
    bbox_width REAL NOT NULL,
    bbox_height REAL NOT NULL,

    -- Detection metadata
    confidence REAL NOT NULL CHECK (confidence >= 0 AND confidence <= 1),
    detection_method TEXT NOT NULL,  -- "yolov8", "vector_pattern", "manual"
    model_version TEXT,

    -- Flexible attributes for object-specific data
    -- Examples: {"fire_rating": "T30-RS", "swing_direction": "left"}
    attributes JSONB DEFAULT '{}',

    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- Indexes for efficient queries
CREATE INDEX IF NOT EXISTS idx_detected_objects_analysis
    ON detected_objects(analysis_id);
CREATE INDEX IF NOT EXISTS idx_detected_objects_type
    ON detected_objects(object_type);
CREATE INDEX IF NOT EXISTS idx_detected_objects_file
    ON detected_objects(file_id);
CREATE INDEX IF NOT EXISTS idx_detected_objects_attributes
    ON detected_objects USING GIN (attributes);

COMMENT ON TABLE detected_objects IS 'Objects detected in blueprints by the CV pipeline';
COMMENT ON COLUMN detected_objects.analysis_id IS 'Groups objects from the same analysis run';
COMMENT ON COLUMN detected_objects.attributes IS 'Flexible JSON for object-specific attributes like fire ratings';


-- ============================================
-- SECTORS / ZONES
-- ============================================
-- Stores sectors/zones for area calculations and spatial queries.
-- Sectors can be rooms, zones, floors, or any defined area.

CREATE TABLE IF NOT EXISTS sectors (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),

    -- Foreign key
    file_id UUID NOT NULL REFERENCES files(id) ON DELETE CASCADE,

    -- Sector identification
    name TEXT NOT NULL,  -- "Apartment 3", "Corridor B", "B.01.1.017 Vorraum"
    sector_type TEXT,  -- "room", "zone", "floor", "unit"

    -- Geometry (closed polygon as JSON array of [x,y] points in pixels)
    polygon_points JSONB NOT NULL,
    page_number INTEGER NOT NULL,

    -- Calculated values (populated after scale calibration)
    area_m2 REAL,
    perimeter_m REAL,

    -- Additional attributes
    attributes JSONB DEFAULT '{}',

    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- Indexes
CREATE INDEX IF NOT EXISTS idx_sectors_file ON sectors(file_id);
CREATE INDEX IF NOT EXISTS idx_sectors_type ON sectors(sector_type);

COMMENT ON TABLE sectors IS 'Sectors/zones for area calculations and spatial queries';
COMMENT ON COLUMN sectors.polygon_points IS 'JSON array of [x,y] vertices defining the sector boundary';


-- ============================================
-- MEASUREMENTS
-- ============================================
-- Stores measurements derived from detected objects with full auditability.
-- Every measurement includes source tracing for the zero-hallucination principle.

CREATE TABLE IF NOT EXISTS measurements (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),

    -- References (at least one should be set)
    detected_object_id UUID REFERENCES detected_objects(id) ON DELETE CASCADE,
    sector_id UUID REFERENCES sectors(id) ON DELETE SET NULL,

    -- Measurement details
    measurement_type TEXT NOT NULL,  -- "width", "height", "area", "perimeter", "count"
    value REAL NOT NULL,
    unit TEXT NOT NULL,  -- "m", "m2", "count"

    -- Auditability fields
    confidence REAL NOT NULL CHECK (confidence >= 0 AND confidence <= 1),
    method TEXT NOT NULL,  -- "vector_geometry", "bbox_scaled", "polygon_area", "arc_radius"
    scale_pixels_per_meter REAL,  -- Scale used for conversion

    -- Source tracing
    source_page INTEGER NOT NULL,
    source_bbox JSONB,  -- {x, y, width, height} for visual reference

    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- Indexes
CREATE INDEX IF NOT EXISTS idx_measurements_object ON measurements(detected_object_id);
CREATE INDEX IF NOT EXISTS idx_measurements_sector ON measurements(sector_id);
CREATE INDEX IF NOT EXISTS idx_measurements_type ON measurements(measurement_type);

COMMENT ON TABLE measurements IS 'Measurements with full auditability for zero-hallucination principle';
COMMENT ON COLUMN measurements.source_bbox IS 'Bounding box for visual source reference';


-- ============================================
-- SCALE CONTEXTS
-- ============================================
-- Stores scale calibrations for pixel-to-meter conversion.
-- Supports both automatic detection and user-provided calibration.

CREATE TABLE IF NOT EXISTS scale_contexts (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),

    -- Foreign key
    file_id UUID NOT NULL REFERENCES files(id) ON DELETE CASCADE,

    -- Scale information
    scale_string TEXT,  -- Human-readable: "1:100", "1:50"
    pixels_per_meter REAL NOT NULL,  -- Conversion factor

    -- Detection source
    detection_method TEXT NOT NULL,  -- "ocr_annotation", "dimension_line", "scale_bar", "user_input"
    confidence REAL NOT NULL CHECK (confidence >= 0 AND confidence <= 1),
    source_page INTEGER NOT NULL,
    source_bbox JSONB,  -- Where scale was detected

    -- For user-provided calibration
    user_reference_px REAL,  -- Length of reference in pixels
    user_reference_m REAL,   -- Known length of reference in meters

    -- Allow multiple calibrations per file, mark one as active
    is_active BOOLEAN DEFAULT TRUE,

    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- Indexes
CREATE INDEX IF NOT EXISTS idx_scale_contexts_file ON scale_contexts(file_id);
CREATE INDEX IF NOT EXISTS idx_scale_contexts_active ON scale_contexts(file_id, is_active) WHERE is_active = TRUE;

COMMENT ON TABLE scale_contexts IS 'Scale calibrations for pixel-to-meter conversion';
COMMENT ON COLUMN scale_contexts.is_active IS 'Only one scale context should be active per file';


-- ============================================
-- ANALYSIS RUNS
-- ============================================
-- Tracks analysis runs for grouping detected objects and measurements.

CREATE TABLE IF NOT EXISTS analysis_runs (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),

    -- Foreign key
    file_id UUID NOT NULL REFERENCES files(id) ON DELETE CASCADE,

    -- Analysis metadata
    status TEXT NOT NULL DEFAULT 'pending',  -- "pending", "processing", "completed", "failed"
    analysis_types TEXT[] NOT NULL DEFAULT ARRAY['full'],  -- Types requested

    -- Configuration
    confidence_threshold REAL DEFAULT 0.5,
    pages_analyzed INTEGER[],  -- NULL = all pages

    -- Results summary
    total_objects INTEGER DEFAULT 0,
    objects_by_type JSONB DEFAULT '{}',

    -- Timing
    started_at TIMESTAMPTZ,
    completed_at TIMESTAMPTZ,
    processing_time_ms INTEGER,

    -- Error handling
    error_message TEXT,
    warnings TEXT[],

    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- Indexes
CREATE INDEX IF NOT EXISTS idx_analysis_runs_file ON analysis_runs(file_id);
CREATE INDEX IF NOT EXISTS idx_analysis_runs_status ON analysis_runs(status);

COMMENT ON TABLE analysis_runs IS 'Tracks analysis runs and their results';


-- ============================================
-- HELPER FUNCTIONS
-- ============================================

-- Function to get the active scale context for a file
CREATE OR REPLACE FUNCTION get_active_scale(p_file_id UUID)
RETURNS TABLE (
    id UUID,
    scale_string TEXT,
    pixels_per_meter REAL,
    detection_method TEXT,
    confidence REAL
) AS $$
BEGIN
    RETURN QUERY
    SELECT
        sc.id,
        sc.scale_string,
        sc.pixels_per_meter,
        sc.detection_method,
        sc.confidence
    FROM scale_contexts sc
    WHERE sc.file_id = p_file_id AND sc.is_active = TRUE
    LIMIT 1;
END;
$$ LANGUAGE plpgsql;

COMMENT ON FUNCTION get_active_scale IS 'Returns the active scale context for a file';


-- Function to count objects by type within a sector
CREATE OR REPLACE FUNCTION count_objects_in_sector(
    p_sector_id UUID,
    p_object_type TEXT DEFAULT NULL
)
RETURNS TABLE (
    object_type TEXT,
    count BIGINT
) AS $$
BEGIN
    -- Note: This is a placeholder that returns 0.
    -- Full implementation requires point-in-polygon logic.
    RETURN QUERY
    SELECT
        COALESCE(p_object_type, 'all')::TEXT as object_type,
        0::BIGINT as count;
END;
$$ LANGUAGE plpgsql;

COMMENT ON FUNCTION count_objects_in_sector IS 'Counts objects within a sector (placeholder - needs point-in-polygon)';

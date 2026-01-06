/**
 * TypeScript types for SnapPlan API responses.
 * Aligned with backend Pydantic models.
 */

/** A single extracted cell with auditability metadata */
export interface ExtractedCell {
  value: string | number | null;
  raw: string;
  confidence: number;
  page: number;
  row_index: number;
  col_index: number;
}

/** A row in an extracted table - maps column names to cells */
export type ExtractedRow = Record<string, ExtractedCell>;

/** A single extracted table from a PDF page */
export interface ExtractedTable {
  page_number: number;
  table_index: number;
  headers: string[];
  normalized_headers: string[];
  rows: ExtractedRow[];
  row_count: number;
  extraction_method: string;
  confidence: number;
  warnings: string[];
}

/** Summary of extracted door data */
export interface ExtractionSummary {
  total_doors: number;
  by_type: Record<string, number>;
  by_fire_rating: Record<string, number>;
  dimensions: {
    widths: number[];
    heights: number[];
  };
}

/** Persistence layer result info */
export interface PersistenceInfo {
  supabase_enabled: boolean;
  success?: boolean;
  file_id?: string | null;
  extraction_id?: string | null;
  storage_path?: string | null;
  error?: string | null;
}

/** Full extraction response from the API */
export interface ExtractionResponse {
  extraction_id: string;
  source_file: string;
  extracted_at: string;
  tables: ExtractedTable[];
  total_rows: number;
  status: string;
  errors: string[];
  summary?: ExtractionSummary | null;
  persistence?: PersistenceInfo | null;
}

/** Parameters for the extract API call */
export interface ExtractParams {
  useSample: boolean;
  file?: File | null;
}

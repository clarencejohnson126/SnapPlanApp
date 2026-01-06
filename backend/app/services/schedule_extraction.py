"""
Schedule extraction service for SnapGrid.

Extracts structured table data from construction schedule PDFs (e.g., door lists).
Implements deterministic extraction with full auditability - NO hallucinated values.

Every extracted value traces back to a specific location in the source PDF.
"""

import re
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any, Optional
from uuid import uuid4

import pdfplumber

from .pdf_utils import validate_pdf_path


# German header mappings to normalized English field names
GERMAN_HEADER_MAP = {
    "pos": "pos",
    "pos.": "pos",
    "türnummer": "door_number",
    "tuernummer": "door_number",
    "tür": "door_number",
    "raum": "room",
    "typ": "type",
    "bs": "fire_rating",
    "b[m]": "width_m",
    "b [m]": "width_m",
    "breite": "width_m",
    "h[m]": "height_m",
    "h [m]": "height_m",
    "höhe": "height_m",
    "hoehe": "height_m",
    "bemerkung": "remarks",
    "bemerkungen": "remarks",
    "anmerkung": "remarks",
}


@dataclass
class ExtractedCell:
    """A single cell value with auditability metadata."""

    value: Any
    raw: str
    confidence: float = 1.0
    page: int = 0
    row_index: int = 0
    col_index: int = 0

    def to_dict(self) -> dict:
        return {
            "value": self.value,
            "raw": self.raw,
            "confidence": self.confidence,
            "page": self.page,
            "row_index": self.row_index,
            "col_index": self.col_index,
        }


@dataclass
class ExtractedTable:
    """A single extracted table with metadata."""

    page_number: int
    table_index: int
    headers: list[str]
    normalized_headers: list[str]
    rows: list[dict[str, ExtractedCell]]
    row_count: int
    extraction_method: str = "pdfplumber"
    confidence: float = 1.0
    warnings: list[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "page_number": self.page_number,
            "table_index": self.table_index,
            "headers": self.headers,
            "normalized_headers": self.normalized_headers,
            "rows": [
                {k: v.to_dict() for k, v in row.items()} for row in self.rows
            ],
            "row_count": self.row_count,
            "extraction_method": self.extraction_method,
            "confidence": self.confidence,
            "warnings": self.warnings,
        }


@dataclass
class ExtractionResult:
    """Complete extraction result with all tables and metadata."""

    extraction_id: str
    source_file: str
    extracted_at: str
    tables: list[ExtractedTable]
    total_rows: int
    status: str = "ok"
    errors: list[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "extraction_id": self.extraction_id,
            "source_file": self.source_file,
            "extracted_at": self.extracted_at,
            "tables": [t.to_dict() for t in self.tables],
            "total_rows": self.total_rows,
            "status": self.status,
            "errors": self.errors,
        }


def normalize_header(header: str) -> str:
    """
    Normalize a German header to a standardized English field name.

    Args:
        header: Raw header string from PDF

    Returns:
        Normalized field name
    """
    if not header:
        return "unknown"

    # Clean and lowercase
    clean = header.strip().lower()

    # Remove special characters except brackets
    clean = re.sub(r"[^\w\[\]\s]", "", clean)

    # Look up in mapping
    if clean in GERMAN_HEADER_MAP:
        return GERMAN_HEADER_MAP[clean]

    # Partial matches
    for german, english in GERMAN_HEADER_MAP.items():
        if german in clean or clean in german:
            return english

    return clean.replace(" ", "_")


def parse_german_decimal(value: str) -> Optional[float]:
    """
    Parse a German-format decimal number (comma as decimal separator).

    Args:
        value: String like "1,01" or "0,88"

    Returns:
        Float value or None if parsing fails
    """
    if not value or not isinstance(value, str):
        return None

    # Clean whitespace
    clean = value.strip()

    # Replace comma with period for German decimals
    clean = clean.replace(",", ".")

    try:
        return float(clean)
    except ValueError:
        return None


def is_data_row(row: list, headers: list) -> bool:
    """
    Determine if a row contains actual data vs. being a header or empty row.

    Args:
        row: List of cell values
        headers: Expected header names

    Returns:
        True if this appears to be a data row
    """
    if not row:
        return False

    # Count non-empty cells
    non_empty = sum(1 for cell in row if cell and str(cell).strip())

    if non_empty < 2:
        return False

    # Check if first cell looks like a position number
    first_cell = str(row[0]).strip() if row[0] else ""

    # Position numbers are typically integers
    if first_cell.isdigit():
        return True

    # Check if it matches header pattern (skip header rows)
    first_lower = first_cell.lower()
    if first_lower in ("pos", "pos.", "türnummer", "nr"):
        return False

    return non_empty >= 3


def extract_table_from_page(
    page: pdfplumber.page.Page,
    page_number: int,
    table_index: int = 0,
) -> Optional[ExtractedTable]:
    """
    Extract a single table from a PDF page.

    Args:
        page: pdfplumber page object
        page_number: 1-indexed page number
        table_index: Index of table on page (0-indexed)

    Returns:
        ExtractedTable or None if no valid table found
    """
    # Extract tables from page
    tables = page.extract_tables()

    if not tables or table_index >= len(tables):
        return None

    raw_table = tables[table_index]

    if not raw_table or len(raw_table) < 2:
        return None

    # First row should be headers
    raw_headers = [str(h).strip() if h else "" for h in raw_table[0]]

    # Normalize headers
    normalized = [normalize_header(h) for h in raw_headers]

    # Check if this looks like a schedule table (has expected columns)
    expected_cols = {"pos", "door_number", "room", "type"}
    found_cols = set(normalized)

    if not expected_cols.intersection(found_cols):
        # This might be a summary table, not the main schedule
        return None

    # Extract data rows
    extracted_rows = []
    warnings = []

    for row_idx, raw_row in enumerate(raw_table[1:], start=1):
        if not is_data_row(raw_row, raw_headers):
            continue

        row_data = {}
        for col_idx, (header, value) in enumerate(zip(normalized, raw_row)):
            raw_value = str(value).strip() if value else ""

            # Parse value based on column type
            if header in ("width_m", "height_m"):
                parsed = parse_german_decimal(raw_value)
                if parsed is None and raw_value:
                    warnings.append(
                        f"Could not parse decimal '{raw_value}' at row {row_idx}, col {col_idx}"
                    )
                final_value = parsed
            elif header == "pos":
                try:
                    final_value = int(raw_value) if raw_value else None
                except ValueError:
                    final_value = raw_value
            else:
                final_value = raw_value if raw_value else None

            row_data[header] = ExtractedCell(
                value=final_value,
                raw=raw_value,
                confidence=1.0 if raw_value else 0.0,
                page=page_number,
                row_index=row_idx,
                col_index=col_idx,
            )

        if row_data:
            extracted_rows.append(row_data)

    if not extracted_rows:
        return None

    return ExtractedTable(
        page_number=page_number,
        table_index=table_index,
        headers=raw_headers,
        normalized_headers=normalized,
        rows=extracted_rows,
        row_count=len(extracted_rows),
        extraction_method="pdfplumber",
        confidence=0.95,  # High confidence for clean table extraction
        warnings=warnings,
    )


def extract_schedules_from_pdf(path: str | Path) -> ExtractionResult:
    """
    Extract all schedule tables from a PDF file.

    This is the main entry point for schedule extraction. It processes
    each page, identifies tables, and returns structured data with
    full auditability.

    Args:
        path: Path to the PDF file

    Returns:
        ExtractionResult containing all extracted tables and metadata

    Example:
        >>> result = extract_schedules_from_pdf("Tuerenliste.pdf")
        >>> print(f"Found {result.total_rows} door entries")
        >>> for table in result.tables:
        ...     print(f"Page {table.page_number}: {table.row_count} rows")
    """
    extraction_id = str(uuid4())
    extracted_at = datetime.utcnow().isoformat() + "Z"
    errors = []
    tables = []

    try:
        path = validate_pdf_path(path)
    except (FileNotFoundError, ValueError) as e:
        return ExtractionResult(
            extraction_id=extraction_id,
            source_file=str(path),
            extracted_at=extracted_at,
            tables=[],
            total_rows=0,
            status="error",
            errors=[str(e)],
        )

    try:
        with pdfplumber.open(path) as pdf:
            for page_num, page in enumerate(pdf.pages, start=1):
                # Try to extract tables from each page
                # Most schedule PDFs have one main table per page
                table = extract_table_from_page(page, page_num, table_index=0)

                if table:
                    tables.append(table)

    except Exception as e:
        errors.append(f"PDF processing error: {str(e)}")
        return ExtractionResult(
            extraction_id=extraction_id,
            source_file=str(path),
            extracted_at=extracted_at,
            tables=tables,
            total_rows=sum(t.row_count for t in tables),
            status="error",
            errors=errors,
        )

    total_rows = sum(t.row_count for t in tables)

    return ExtractionResult(
        extraction_id=extraction_id,
        source_file=str(path),
        extracted_at=extracted_at,
        tables=tables,
        total_rows=total_rows,
        status="ok" if tables else "no_tables_found",
        errors=errors,
    )


def get_door_summary(result: ExtractionResult) -> dict:
    """
    Generate a summary of extracted door data.

    Args:
        result: ExtractionResult from extract_schedules_from_pdf

    Returns:
        Summary dictionary with counts by type, dimensions, etc.
    """
    summary = {
        "total_doors": result.total_rows,
        "by_type": {},
        "by_fire_rating": {},
        "dimensions": {
            "widths": [],
            "heights": [],
        },
    }

    for table in result.tables:
        for row in table.rows:
            # Count by type
            if "type" in row and row["type"].value:
                door_type = row["type"].value
                summary["by_type"][door_type] = summary["by_type"].get(door_type, 0) + 1

            # Count by fire rating
            if "fire_rating" in row and row["fire_rating"].value:
                rating = row["fire_rating"].value
                summary["by_fire_rating"][rating] = (
                    summary["by_fire_rating"].get(rating, 0) + 1
                )

            # Collect dimensions
            if "width_m" in row and row["width_m"].value:
                summary["dimensions"]["widths"].append(row["width_m"].value)

            if "height_m" in row and row["height_m"].value:
                summary["dimensions"]["heights"].append(row["height_m"].value)

    # Calculate unique dimensions
    summary["dimensions"]["unique_widths"] = sorted(
        set(summary["dimensions"]["widths"])
    )
    summary["dimensions"]["unique_heights"] = sorted(
        set(summary["dimensions"]["heights"])
    )

    return summary

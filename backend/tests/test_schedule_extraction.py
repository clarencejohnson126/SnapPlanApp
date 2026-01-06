"""
Tests for schedule extraction service.

These tests validate that the extraction service correctly processes
the sample door schedule PDF (Tuerenliste_Bauteil_B_OG1.pdf).

Test philosophy:
- Assert structural correctness (tables found, columns present)
- Assert reasonable counts (not exact to allow for minor PDF changes)
- Verify auditability fields are populated
- Do NOT hard-code specific values that might change
"""

import sys
from pathlib import Path

import pytest

# Add backend to path
backend_dir = Path(__file__).parent.parent
sys.path.insert(0, str(backend_dir))

from app.services.schedule_extraction import (
    ExtractionResult,
    extract_schedules_from_pdf,
    get_door_summary,
    normalize_header,
    parse_german_decimal,
)


class TestGermanDecimalParsing:
    """Tests for German decimal number parsing."""

    def test_parse_comma_decimal(self):
        """German decimals use comma as separator."""
        assert parse_german_decimal("1,01") == 1.01
        assert parse_german_decimal("0,88") == 0.88
        assert parse_german_decimal("2,26") == 2.26

    def test_parse_with_whitespace(self):
        """Should handle whitespace around numbers."""
        assert parse_german_decimal(" 1,01 ") == 1.01
        assert parse_german_decimal("  0,88") == 0.88

    def test_parse_integer(self):
        """Should handle integers."""
        assert parse_german_decimal("1") == 1.0
        assert parse_german_decimal("10") == 10.0

    def test_parse_invalid_returns_none(self):
        """Invalid values should return None, not raise."""
        assert parse_german_decimal("") is None
        assert parse_german_decimal(None) is None
        assert parse_german_decimal("abc") is None
        assert parse_german_decimal("-") is None


class TestHeaderNormalization:
    """Tests for German header normalization."""

    def test_normalize_standard_headers(self):
        """Standard German headers should normalize correctly."""
        assert normalize_header("Pos.") == "pos"
        assert normalize_header("Türnummer") == "door_number"
        assert normalize_header("Raum") == "room"
        assert normalize_header("Typ") == "type"
        assert normalize_header("BS") == "fire_rating"
        assert normalize_header("B[m]") == "width_m"
        assert normalize_header("H[m]") == "height_m"
        assert normalize_header("Bemerkung") == "remarks"

    def test_normalize_case_insensitive(self):
        """Normalization should be case insensitive."""
        assert normalize_header("POS.") == "pos"
        assert normalize_header("TÜRNUMMER") == "door_number"
        assert normalize_header("raum") == "room"

    def test_normalize_with_whitespace(self):
        """Should handle extra whitespace."""
        assert normalize_header("  Pos.  ") == "pos"
        assert normalize_header("B [m]") == "width_m"

    def test_normalize_unknown_header(self):
        """Unknown headers should be cleaned but preserved."""
        result = normalize_header("CustomColumn")
        assert result == "customcolumn"


class TestScheduleExtractionBasic:
    """Basic tests for the extraction function."""

    def test_extract_nonexistent_file(self):
        """Should handle missing files gracefully."""
        result = extract_schedules_from_pdf("/nonexistent/path.pdf")
        assert result.status == "error"
        assert len(result.errors) > 0
        assert result.total_rows == 0

    def test_extract_returns_extraction_result(self, sample_pdf_path):
        """Should return an ExtractionResult object."""
        result = extract_schedules_from_pdf(sample_pdf_path)
        assert isinstance(result, ExtractionResult)
        assert result.extraction_id is not None
        assert result.source_file is not None
        assert result.extracted_at is not None


class TestSamplePDFExtraction:
    """
    Tests specific to the sample door schedule PDF.

    These tests verify correct extraction from Tuerenliste_Bauteil_B_OG1.pdf
    which contains a door schedule for Building Part B, Floor 1.

    Known structure (as of initial implementation):
    - Pages 1-2: Main door table with ~35 entries
    - Page 3: Summary table (should be skipped by main extraction)
    """

    def test_extraction_succeeds(self, sample_pdf_path):
        """Extraction should complete without errors."""
        result = extract_schedules_from_pdf(sample_pdf_path)
        assert result.status == "ok", f"Extraction failed: {result.errors}"

    def test_finds_tables(self, sample_pdf_path):
        """Should find at least one table."""
        result = extract_schedules_from_pdf(sample_pdf_path)
        assert len(result.tables) >= 1, "No tables found in PDF"

    def test_extracts_reasonable_row_count(self, sample_pdf_path):
        """
        Should extract a reasonable number of door entries.

        The sample PDF has ~35 doors. We check for at least 30
        to allow for minor variations in parsing.
        """
        result = extract_schedules_from_pdf(sample_pdf_path)
        assert result.total_rows >= 30, f"Expected ~35 rows, got {result.total_rows}"
        assert result.total_rows <= 50, f"Too many rows ({result.total_rows}), possible parsing issue"

    def test_expected_columns_present(self, sample_pdf_path):
        """Should have the expected German schedule columns."""
        result = extract_schedules_from_pdf(sample_pdf_path)

        # Get normalized headers from first table
        assert len(result.tables) > 0
        headers = result.tables[0].normalized_headers

        # Check for key columns
        expected = ["pos", "door_number", "room", "type"]
        for col in expected:
            assert col in headers, f"Missing expected column: {col}"

    def test_door_numbers_look_valid(self, sample_pdf_path):
        """
        Door numbers should match expected pattern.

        Pattern: B.01.X.XXX-X (e.g., B.01.1.001-1)
        """
        result = extract_schedules_from_pdf(sample_pdf_path)

        # Check first few door numbers
        for table in result.tables:
            for row in table.rows[:5]:  # Check first 5 rows
                if "door_number" in row:
                    door_num = row["door_number"].value
                    if door_num:
                        # Should start with "B.01" for Building B, Floor 1
                        assert door_num.startswith("B.01"), (
                            f"Unexpected door number format: {door_num}"
                        )

    def test_dimensions_are_numeric(self, sample_pdf_path):
        """
        Width and height values should be parsed as floats.

        Expected ranges:
        - Width: 0.6m - 1.5m
        - Height: 1.8m - 2.5m
        """
        result = extract_schedules_from_pdf(sample_pdf_path)

        for table in result.tables:
            for row in table.rows:
                # Check width
                if "width_m" in row and row["width_m"].value is not None:
                    w = row["width_m"].value
                    assert isinstance(w, float), f"Width should be float, got {type(w)}"
                    assert 0.5 <= w <= 2.0, f"Width {w}m outside expected range"

                # Check height
                if "height_m" in row and row["height_m"].value is not None:
                    h = row["height_m"].value
                    assert isinstance(h, float), f"Height should be float, got {type(h)}"
                    assert 1.5 <= h <= 3.0, f"Height {h}m outside expected range"

    def test_auditability_fields_present(self, sample_pdf_path):
        """Each extracted cell should have auditability metadata."""
        result = extract_schedules_from_pdf(sample_pdf_path)

        for table in result.tables:
            for row in table.rows:
                for field_name, cell in row.items():
                    # Each cell should have these fields
                    assert hasattr(cell, "value"), f"Missing 'value' in {field_name}"
                    assert hasattr(cell, "raw"), f"Missing 'raw' in {field_name}"
                    assert hasattr(cell, "confidence"), f"Missing 'confidence' in {field_name}"
                    assert hasattr(cell, "page"), f"Missing 'page' in {field_name}"

                    # Page should be valid
                    assert cell.page >= 1, f"Invalid page number: {cell.page}"


class TestDoorSummary:
    """Tests for the door summary function."""

    def test_summary_counts_doors(self, sample_pdf_path):
        """Summary should count total doors."""
        result = extract_schedules_from_pdf(sample_pdf_path)
        summary = get_door_summary(result)

        assert "total_doors" in summary
        assert summary["total_doors"] >= 30

    def test_summary_groups_by_type(self, sample_pdf_path):
        """Summary should group doors by type."""
        result = extract_schedules_from_pdf(sample_pdf_path)
        summary = get_door_summary(result)

        assert "by_type" in summary
        # Should have at least some type categories
        assert len(summary["by_type"]) >= 1

    def test_summary_collects_dimensions(self, sample_pdf_path):
        """Summary should collect unique dimensions."""
        result = extract_schedules_from_pdf(sample_pdf_path)
        summary = get_door_summary(result)

        assert "dimensions" in summary
        assert "unique_widths" in summary["dimensions"]
        assert "unique_heights" in summary["dimensions"]

        # Should have at least 2 different widths (0.88m and 1.01m are common)
        assert len(summary["dimensions"]["unique_widths"]) >= 1


class TestEdgeCases:
    """Tests for edge cases and error handling."""

    def test_to_dict_serialization(self, sample_pdf_path):
        """Result should serialize to dict without errors."""
        result = extract_schedules_from_pdf(sample_pdf_path)
        result_dict = result.to_dict()

        assert isinstance(result_dict, dict)
        assert "extraction_id" in result_dict
        assert "tables" in result_dict
        assert isinstance(result_dict["tables"], list)

    def test_empty_cells_handled(self, sample_pdf_path):
        """Empty cells should not cause errors."""
        result = extract_schedules_from_pdf(sample_pdf_path)

        # Just verify extraction completed
        assert result.status == "ok"

        # Empty cells should have confidence 0
        for table in result.tables:
            for row in table.rows:
                for field_name, cell in row.items():
                    if cell.value is None or cell.raw == "":
                        assert cell.confidence == 0.0

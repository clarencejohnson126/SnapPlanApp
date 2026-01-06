"""
Tests for door gewerk service.

These tests validate that the door gewerk correctly processes
schedule extraction results and produces structured door lists.

Test philosophy:
- Test classification logic for different fire ratings
- Test summary aggregation
- Test integration with schedule extraction
- Verify auditability fields are populated
"""

import sys
from pathlib import Path

import pytest

# Add backend to path
backend_dir = Path(__file__).parent.parent
sys.path.insert(0, str(backend_dir))

from app.services.gewerke import (
    DoorCategory,
    DoorGewerkItem,
    DoorGewerkSummary,
    DoorGewerkResult,
    run_door_gewerk_from_schedule,
    _classify_door_category,
    _generate_gewerk_id,
    _generate_item_id,
)
from app.services.schedule_extraction import (
    ExtractionResult,
    ExtractedTable,
    ExtractedCell,
    extract_schedules_from_pdf,
)


class TestDoorCategoryClassification:
    """Tests for door category classification logic."""

    def test_classify_t30(self):
        """T30 fire rating should be classified as T30."""
        assert _classify_door_category("T30", None) == DoorCategory.T30
        assert _classify_door_category("t30", None) == DoorCategory.T30
        assert _classify_door_category("T-30", None) == DoorCategory.T30

    def test_classify_t90(self):
        """T90 fire rating should be classified as T90."""
        assert _classify_door_category("T90", None) == DoorCategory.T90
        assert _classify_door_category("t90", None) == DoorCategory.T90
        assert _classify_door_category("T-90", None) == DoorCategory.T90

    def test_classify_t90_takes_precedence(self):
        """T90 should take precedence over T30 if both present."""
        # Edge case: if somehow both T30 and T90 in combined string
        assert _classify_door_category("T90", "T30") == DoorCategory.T90

    def test_classify_dss_smoke_protection(self):
        """DSS/smoke protection doors should be classified as DSS."""
        assert _classify_door_category("DSS", None) == DoorCategory.DSS
        assert _classify_door_category("RS", None) == DoorCategory.DSS
        assert _classify_door_category("Rauchschutz", None) == DoorCategory.DSS
        assert _classify_door_category(None, "Dichtschliessend") == DoorCategory.DSS

    def test_classify_standard(self):
        """Doors with type but no special rating should be Standard."""
        assert _classify_door_category("", "Holztür") == DoorCategory.STANDARD
        assert _classify_door_category(None, "Standard") == DoorCategory.STANDARD
        assert _classify_door_category("Normal", None) == DoorCategory.STANDARD

    def test_classify_unknown(self):
        """Doors with no information should be Unknown."""
        assert _classify_door_category(None, None) == DoorCategory.UNKNOWN
        assert _classify_door_category("", "") == DoorCategory.UNKNOWN


class TestDoorGewerkDataModels:
    """Tests for door gewerk data models."""

    def test_door_gewerk_item_to_dict(self):
        """DoorGewerkItem should serialize to dict correctly."""
        item = DoorGewerkItem(
            item_id="door_12345678",
            position="1",
            door_number="T1.01",
            room="Flur",
            door_type="Holztür",
            fire_rating="T30",
            width_m=1.01,
            height_m=2.10,
            remarks="Feuerschutz",
            category=DoorCategory.T30,
            source_page=1,
            source_row_index=0,
            confidence=1.0,
        )
        d = item.to_dict()

        assert d["item_id"] == "door_12345678"
        assert d["door_number"] == "T1.01"
        assert d["category"] == "T30"
        assert d["width_m"] == 1.01
        assert d["source_page"] == 1

    def test_door_gewerk_summary_to_dict(self):
        """DoorGewerkSummary should serialize correctly."""
        summary = DoorGewerkSummary(
            total_doors=10,
            count_t30=3,
            count_t90=2,
            count_dss=1,
            count_standard=4,
            count_unknown=0,
            by_type={"Holztür": 5, "Stahltür": 5},
            by_fire_rating={"T30": 3, "T90": 2},
            by_category={"T30": 3, "T90": 2, "DSS": 1, "Standard": 4},
            unique_widths=[0.88, 1.01, 1.26],
            unique_heights=[2.01, 2.26],
        )
        d = summary.to_dict()

        assert d["total_doors"] == 10
        assert d["count_t30"] == 3
        assert len(d["unique_widths"]) == 3

    def test_door_gewerk_result_to_dict(self):
        """DoorGewerkResult should serialize completely."""
        result = DoorGewerkResult(
            gewerk_id="gew_123456789012",
            source_file="test.pdf",
            extraction_id="ext_123",
            processed_at="2024-01-01T00:00:00Z",
            status="ok",
        )
        d = result.to_dict()

        assert d["gewerk_id"] == "gew_123456789012"
        assert d["gewerk_type"] == "doors"
        assert d["status"] == "ok"
        assert "items" in d
        assert "summary" in d


class TestIdGeneration:
    """Tests for ID generation functions."""

    def test_gewerk_id_format(self):
        """Gewerk IDs should have correct format."""
        gid = _generate_gewerk_id()
        assert gid.startswith("gew_")
        assert len(gid) == 16  # gew_ + 12 hex chars

    def test_item_id_format(self):
        """Item IDs should have correct format."""
        item_id = _generate_item_id("door")
        assert item_id.startswith("door_")
        assert len(item_id) == 13  # door_ + 8 hex chars

    def test_item_id_custom_prefix(self):
        """Item IDs should use custom prefix."""
        item_id = _generate_item_id("drywall")
        assert item_id.startswith("drywall_")


class TestRunDoorGewerkFromSchedule:
    """Tests for run_door_gewerk_from_schedule function."""

    def _make_extraction_result(self, rows: list[dict]) -> ExtractionResult:
        """Helper to create a mock ExtractionResult."""
        extracted_rows = []
        for i, row in enumerate(rows):
            extracted_row = {}
            for key, value in row.items():
                extracted_row[key] = ExtractedCell(
                    value=value,
                    raw=str(value),
                    confidence=1.0,
                    page=1,
                    row_index=i,
                    col_index=0,
                )
            extracted_rows.append(extracted_row)

        table = ExtractedTable(
            page_number=1,
            table_index=0,
            headers=list(rows[0].keys()) if rows else [],
            normalized_headers=list(rows[0].keys()) if rows else [],
            rows=extracted_rows,
            row_count=len(rows),
        )

        return ExtractionResult(
            extraction_id="test_extraction_123",
            source_file="test_schedule.pdf",
            extracted_at="2024-01-01T00:00:00Z",
            tables=[table],
            total_rows=len(rows),
        )

    def test_empty_extraction(self):
        """Should handle empty extraction result."""
        extraction = ExtractionResult(
            extraction_id="test_empty",
            source_file="empty.pdf",
            extracted_at="2024-01-01T00:00:00Z",
            tables=[],
            total_rows=0,
        )
        result = run_door_gewerk_from_schedule(extraction)

        assert result.status == "ok"
        assert result.summary.total_doors == 0
        assert "No doors found" in result.warnings[0]

    def test_single_door_t30(self):
        """Should correctly process a single T30 door."""
        extraction = self._make_extraction_result([
            {
                "pos": "1",
                "door_number": "T1.01",
                "room": "Flur",
                "type": "Holztür",
                "fire_rating": "T30",
                "width_m": 1.01,
                "height_m": 2.10,
            }
        ])
        result = run_door_gewerk_from_schedule(extraction)

        assert result.status == "ok"
        assert len(result.items) == 1
        assert result.items[0].category == DoorCategory.T30
        assert result.summary.total_doors == 1
        assert result.summary.count_t30 == 1

    def test_multiple_doors_mixed_categories(self):
        """Should correctly classify multiple doors with different ratings."""
        extraction = self._make_extraction_result([
            {"type": "Standard", "fire_rating": "T30", "width_m": 1.01, "height_m": 2.10},
            {"type": "Standard", "fire_rating": "T90", "width_m": 1.26, "height_m": 2.26},
            {"type": "Standard", "fire_rating": "DSS", "width_m": 0.88, "height_m": 2.01},
            {"type": "Holztür", "fire_rating": "", "width_m": 1.01, "height_m": 2.10},
        ])
        result = run_door_gewerk_from_schedule(extraction)

        assert result.summary.total_doors == 4
        assert result.summary.count_t30 == 1
        assert result.summary.count_t90 == 1
        assert result.summary.count_dss == 1
        assert result.summary.count_standard == 1

    def test_unique_dimensions_collected(self):
        """Should collect unique width and height values."""
        extraction = self._make_extraction_result([
            {"type": "A", "width_m": 1.01, "height_m": 2.10},
            {"type": "B", "width_m": 1.01, "height_m": 2.26},
            {"type": "C", "width_m": 0.88, "height_m": 2.10},
            {"type": "D", "width_m": 1.26, "height_m": 2.26},
        ])
        result = run_door_gewerk_from_schedule(extraction)

        assert set(result.summary.unique_widths) == {0.88, 1.01, 1.26}
        assert set(result.summary.unique_heights) == {2.10, 2.26}

    def test_by_type_grouping(self):
        """Should group counts by door type."""
        extraction = self._make_extraction_result([
            {"type": "Holztür", "fire_rating": "T30"},
            {"type": "Holztür", "fire_rating": "T30"},
            {"type": "Stahltür", "fire_rating": "T90"},
        ])
        result = run_door_gewerk_from_schedule(extraction)

        assert result.summary.by_type.get("Holztür") == 2
        assert result.summary.by_type.get("Stahltür") == 1

    def test_auditability_fields_populated(self):
        """Should populate auditability fields."""
        extraction = self._make_extraction_result([
            {"pos": "1", "type": "Test", "fire_rating": "T30"}
        ])
        result = run_door_gewerk_from_schedule(extraction)

        item = result.items[0]
        assert item.source_page == 1
        assert item.source_row_index == 0
        assert item.confidence == 1.0
        assert item.raw_data is not None

    def test_unknown_category_warning(self):
        """Should warn when doors cannot be categorized."""
        extraction = self._make_extraction_result([
            {"pos": "1"},  # No type or fire rating
        ])
        result = run_door_gewerk_from_schedule(extraction)

        assert result.summary.count_unknown == 1
        assert any("could not be categorized" in w for w in result.warnings)


class TestDoorGewerkIntegration:
    """Integration tests using real PDF extraction."""

    def test_with_sample_pdf(self, sample_pdf_path):
        """Should process the sample door schedule PDF."""
        extraction = extract_schedules_from_pdf(str(sample_pdf_path))
        result = run_door_gewerk_from_schedule(extraction)

        # Should have processed successfully
        assert result.status == "ok"
        assert result.gewerk_type == "doors"
        assert result.extraction_id == extraction.extraction_id

        # Should have found doors
        assert result.summary.total_doors > 0
        assert len(result.items) == result.summary.total_doors

        # Should have some categorization
        total_categorized = (
            result.summary.count_t30
            + result.summary.count_t90
            + result.summary.count_dss
            + result.summary.count_standard
            + result.summary.count_unknown
        )
        assert total_categorized == result.summary.total_doors

        # All items should have valid categories
        for item in result.items:
            assert item.category in DoorCategory
            assert item.item_id.startswith("door_")

    def test_sample_pdf_has_dimensions(self, sample_pdf_path):
        """Sample PDF should have extractable dimensions."""
        extraction = extract_schedules_from_pdf(str(sample_pdf_path))
        result = run_door_gewerk_from_schedule(extraction)

        # Should have found some dimension data
        # (Sample door schedule has B[m] and H[m] columns)
        assert len(result.summary.unique_widths) > 0 or len(result.summary.unique_heights) > 0

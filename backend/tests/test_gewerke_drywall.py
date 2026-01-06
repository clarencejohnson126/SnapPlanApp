"""
Tests for drywall gewerk service.

These tests validate that the drywall gewerk correctly calculates
wall length and drywall area for sectors using vector measurement.

Test philosophy:
- Test data model serialization
- Test calculation logic with mocked segments
- Test integration with vector measurement
- Verify auditability fields are populated
"""

import sys
from pathlib import Path
from unittest.mock import patch, MagicMock

import pytest

# Add backend to path
backend_dir = Path(__file__).parent.parent
sys.path.insert(0, str(backend_dir))

from app.services.gewerke import (
    DrywallGewerkItem,
    DrywallGewerkSummary,
    DrywallGewerkResult,
    run_drywall_gewerk_for_sector,
    run_drywall_gewerk_for_sectors,
    _generate_gewerk_id,
    _generate_item_id,
)
from app.services.measurement_engine import Sector, MeasurementResult, generate_sector_id
from app.services.scale_calibration import ScaleContext
from app.services.vector_measurement import LineSegment, WallSegment


# =============================================================================
# Test Fixtures
# =============================================================================


@pytest.fixture
def simple_scale_context():
    """A scale context with 10 pixels per meter."""
    return ScaleContext(
        id="scale-test-123",
        file_id="test-file-123",
        scale_string="1:100",
        scale_factor=100.0,
        pixels_per_meter=10.0,
        detection_method="test",
        confidence=1.0,
        source_page=1,
    )


@pytest.fixture
def square_sector():
    """A 100x100 square sector centered at (50, 50)."""
    return Sector(
        sector_id=generate_sector_id(),
        file_id="test-file-123",
        page_number=1,
        name="Test Sector",
        polygon_points=[
            (0.0, 0.0),
            (100.0, 0.0),
            (100.0, 100.0),
            (0.0, 100.0),
        ],
        sector_type="room",
    )


@pytest.fixture
def sample_floor_plan_path():
    """Path to the sample floor plan PDF."""
    project_root = Path(__file__).parent.parent.parent
    return project_root / "sampleGrundrissBauplanGenie.pdf"


# =============================================================================
# Data Model Tests
# =============================================================================


class TestDrywallGewerkDataModels:
    """Tests for drywall gewerk data models."""

    def test_drywall_gewerk_item_to_dict(self):
        """DrywallGewerkItem should serialize to dict correctly."""
        item = DrywallGewerkItem(
            item_id="drywall_12345678",
            sector_id="sector-123",
            sector_name="Living Room",
            page_number=1,
            wall_length_m=25.5,
            wall_height_m=2.6,
            drywall_area_m2=66.3,
            wall_segment_count=12,
            measurement_ids=["meas-1", "meas-2"],
            scale_context_id="scale-123",
            confidence=1.0,
            assumptions=["wall_height_m: 2.60"],
        )
        d = item.to_dict()

        assert d["item_id"] == "drywall_12345678"
        assert d["sector_name"] == "Living Room"
        assert d["wall_length_m"] == 25.5
        assert d["wall_height_m"] == 2.6
        assert d["drywall_area_m2"] == 66.3
        assert d["wall_segment_count"] == 12
        assert len(d["measurement_ids"]) == 2

    def test_drywall_gewerk_summary_to_dict(self):
        """DrywallGewerkSummary should serialize correctly."""
        summary = DrywallGewerkSummary(
            total_sectors=3,
            total_wall_length_m=75.25,
            total_drywall_area_m2=195.65,
            average_wall_height_m=2.6,
        )
        d = summary.to_dict()

        assert d["total_sectors"] == 3
        assert d["total_wall_length_m"] == 75.25
        assert d["total_drywall_area_m2"] == 195.65
        assert d["average_wall_height_m"] == 2.6

    def test_drywall_gewerk_result_to_dict(self):
        """DrywallGewerkResult should serialize completely."""
        result = DrywallGewerkResult(
            gewerk_id="gew_123456789012",
            source_file="floor_plan.pdf",
            processed_at="2024-01-01T00:00:00Z",
            status="ok",
        )
        d = result.to_dict()

        assert d["gewerk_id"] == "gew_123456789012"
        assert d["gewerk_type"] == "drywall"
        assert d["status"] == "ok"
        assert "items" in d
        assert "summary" in d


# =============================================================================
# Validation Tests
# =============================================================================


class TestDrywallGewerkValidation:
    """Tests for input validation in drywall gewerk."""

    def test_negative_wall_height_returns_error(self, square_sector, simple_scale_context):
        """Should return error for negative wall height."""
        result = run_drywall_gewerk_for_sector(
            pdf_path="/nonexistent/test.pdf",
            sector=square_sector,
            scale_context=simple_scale_context,
            wall_height_m=-2.6,
        )

        assert result.status == "error"
        assert any("must be positive" in e for e in result.errors)

    def test_zero_wall_height_returns_error(self, square_sector, simple_scale_context):
        """Should return error for zero wall height."""
        result = run_drywall_gewerk_for_sector(
            pdf_path="/nonexistent/test.pdf",
            sector=square_sector,
            scale_context=simple_scale_context,
            wall_height_m=0.0,
        )

        assert result.status == "error"
        assert any("must be positive" in e for e in result.errors)

    def test_no_scale_returns_error(self, square_sector):
        """Should return error if scale context has no valid scale."""
        invalid_scale = ScaleContext(
            id="scale-invalid",
            file_id="test-file",
            pixels_per_meter=None,  # No scale
        )
        result = run_drywall_gewerk_for_sector(
            pdf_path="/nonexistent/test.pdf",
            sector=square_sector,
            scale_context=invalid_scale,
            wall_height_m=2.6,
        )

        assert result.status == "error"
        assert any("pixels_per_meter" in e for e in result.errors)


# =============================================================================
# Calculation Tests (with mocked vector extraction)
# =============================================================================


class TestDrywallGewerkCalculation:
    """Tests for drywall calculation logic with mocked extraction."""

    def _make_wall_segments(self, segments_data: list) -> list:
        """Helper to create WallSegment objects."""
        segments = []
        for i, (x1, y1, x2, y2) in enumerate(segments_data):
            line = LineSegment(
                x1=x1, y1=y1, x2=x2, y2=y2,
                page_number=1,
            )
            wall = WallSegment(
                segment_id=f"wall_test_{i:04d}",
                segment=line,
                kind="wall",
                confidence=1.0,
            )
            segments.append(wall)
        return segments

    @patch("app.services.gewerke.extract_wall_segments_from_page")
    def test_calculation_with_single_wall(
        self, mock_extract, square_sector, simple_scale_context
    ):
        """Should correctly calculate for a single wall segment."""
        # Create a 100px horizontal wall (10m at 10px/m scale)
        mock_extract.return_value = self._make_wall_segments([
            (10, 50, 90, 50),  # 80px long, inside square sector
        ])

        result = run_drywall_gewerk_for_sector(
            pdf_path="/test/path.pdf",
            sector=square_sector,
            scale_context=simple_scale_context,
            wall_height_m=2.6,
        )

        assert result.status == "ok"
        assert len(result.items) == 1

        item = result.items[0]
        # 80px at 10px/m = 8m wall length
        assert item.wall_length_m == pytest.approx(8.0, rel=0.01)
        # 8m * 2.6m height = 20.8 m2
        assert item.drywall_area_m2 == pytest.approx(20.8, rel=0.01)
        assert item.wall_height_m == 2.6

    @patch("app.services.gewerke.extract_wall_segments_from_page")
    def test_calculation_with_multiple_walls(
        self, mock_extract, square_sector, simple_scale_context
    ):
        """Should sum lengths from multiple wall segments."""
        # Create multiple walls inside the sector
        mock_extract.return_value = self._make_wall_segments([
            (10, 50, 90, 50),   # 80px horizontal
            (50, 10, 50, 90),   # 80px vertical
        ])

        result = run_drywall_gewerk_for_sector(
            pdf_path="/test/path.pdf",
            sector=square_sector,
            scale_context=simple_scale_context,
            wall_height_m=2.5,
        )

        assert result.status == "ok"
        item = result.items[0]

        # Total: 160px at 10px/m = 16m
        assert item.wall_length_m == pytest.approx(16.0, rel=0.01)
        # 16m * 2.5m = 40 m2
        assert item.drywall_area_m2 == pytest.approx(40.0, rel=0.01)

    @patch("app.services.gewerke.extract_wall_segments_from_page")
    def test_segments_outside_sector_excluded(
        self, mock_extract, square_sector, simple_scale_context
    ):
        """Segments outside the sector should not be counted."""
        # One inside, one completely outside
        mock_extract.return_value = self._make_wall_segments([
            (10, 50, 90, 50),     # Inside: 80px
            (200, 200, 300, 200),  # Outside: 100px
        ])

        result = run_drywall_gewerk_for_sector(
            pdf_path="/test/path.pdf",
            sector=square_sector,
            scale_context=simple_scale_context,
            wall_height_m=2.6,
        )

        assert result.status == "ok"
        item = result.items[0]

        # Only the inside segment counts: 80px = 8m
        assert item.wall_length_m == pytest.approx(8.0, rel=0.01)

    @patch("app.services.gewerke.extract_wall_segments_from_page")
    def test_no_segments_produces_zero(
        self, mock_extract, square_sector, simple_scale_context
    ):
        """Should handle pages with no wall segments."""
        mock_extract.return_value = []

        result = run_drywall_gewerk_for_sector(
            pdf_path="/test/path.pdf",
            sector=square_sector,
            scale_context=simple_scale_context,
            wall_height_m=2.6,
        )

        assert result.status == "ok"
        assert len(result.items) == 1
        assert result.items[0].wall_length_m == 0.0
        assert result.items[0].drywall_area_m2 == 0.0
        assert any("No wall segments" in w for w in result.warnings)


# =============================================================================
# Multi-Sector Tests
# =============================================================================


class TestDrywallGewerkMultipleSectors:
    """Tests for processing multiple sectors."""

    @patch("app.services.gewerke.extract_wall_segments_from_page")
    def test_multiple_sectors_aggregated(
        self, mock_extract, simple_scale_context
    ):
        """Should aggregate results from multiple sectors."""
        # Create two sectors
        sector1 = Sector(
            sector_id="sector-1",
            file_id="test-file",
            page_number=1,
            name="Room A",
            polygon_points=[(0, 0), (100, 0), (100, 100), (0, 100)],
        )
        sector2 = Sector(
            sector_id="sector-2",
            file_id="test-file",
            page_number=1,
            name="Room B",
            polygon_points=[(200, 0), (300, 0), (300, 100), (200, 100)],
        )

        # Mock returns walls in both sectors
        def mock_walls(path, page_number, dpi, min_length_px):
            line1 = LineSegment(x1=10, y1=50, x2=90, y2=50, page_number=1)
            line2 = LineSegment(x1=210, y1=50, x2=290, y2=50, page_number=1)
            return [
                WallSegment(segment_id="wall_1", segment=line1),
                WallSegment(segment_id="wall_2", segment=line2),
            ]

        mock_extract.side_effect = mock_walls

        result = run_drywall_gewerk_for_sectors(
            pdf_path="/test/path.pdf",
            sectors=[sector1, sector2],
            scale_context=simple_scale_context,
            wall_height_m=2.5,
        )

        assert result.status == "ok"
        assert len(result.items) == 2
        assert result.summary.total_sectors == 2

        # Each sector has 80px = 8m wall
        # Total: 16m wall length, 40 m2 area
        assert result.summary.total_wall_length_m == pytest.approx(16.0, rel=0.01)
        assert result.summary.total_drywall_area_m2 == pytest.approx(40.0, rel=0.01)


# =============================================================================
# Auditability Tests
# =============================================================================


class TestDrywallGewerkAuditability:
    """Tests for auditability fields in drywall gewerk."""

    @patch("app.services.gewerke.extract_wall_segments_from_page")
    def test_measurement_ids_populated(
        self, mock_extract, square_sector, simple_scale_context
    ):
        """Should populate measurement IDs for traceability."""
        line = LineSegment(x1=10, y1=50, x2=90, y2=50, page_number=1)
        mock_extract.return_value = [
            WallSegment(segment_id="wall_1", segment=line)
        ]

        result = run_drywall_gewerk_for_sector(
            pdf_path="/test/path.pdf",
            sector=square_sector,
            scale_context=simple_scale_context,
            wall_height_m=2.6,
        )

        item = result.items[0]
        assert len(item.measurement_ids) == 2  # wall_length + drywall_area
        assert all(mid.startswith("meas_") for mid in item.measurement_ids)

    @patch("app.services.gewerke.extract_wall_segments_from_page")
    def test_scale_context_id_preserved(
        self, mock_extract, square_sector, simple_scale_context
    ):
        """Should preserve scale context ID for traceability."""
        mock_extract.return_value = []

        result = run_drywall_gewerk_for_sector(
            pdf_path="/test/path.pdf",
            sector=square_sector,
            scale_context=simple_scale_context,
            wall_height_m=2.6,
        )

        item = result.items[0]
        assert item.scale_context_id == simple_scale_context.id

    @patch("app.services.gewerke.extract_wall_segments_from_page")
    def test_assumptions_populated(
        self, mock_extract, square_sector, simple_scale_context
    ):
        """Should include assumptions for transparency."""
        mock_extract.return_value = []

        result = run_drywall_gewerk_for_sector(
            pdf_path="/test/path.pdf",
            sector=square_sector,
            scale_context=simple_scale_context,
            wall_height_m=2.6,
        )

        item = result.items[0]
        assert len(item.assumptions) > 0
        # Should include wall height assumption
        assert any("wall_height_m" in a for a in item.assumptions)


# =============================================================================
# Integration Tests
# =============================================================================


class TestDrywallGewerkIntegration:
    """Integration tests using real PDF extraction (if available)."""

    @pytest.mark.skipif(
        not Path(__file__).parent.parent.parent.joinpath("sampleGrundrissBauplanGenie.pdf").exists(),
        reason="Sample floor plan PDF not found",
    )
    def test_with_sample_floor_plan(self, sample_floor_plan_path, simple_scale_context):
        """Should process a real floor plan PDF (if available)."""
        # Create a simple sector covering part of the page
        sector = Sector(
            sector_id=generate_sector_id(),
            file_id="test-file",
            page_number=1,
            name="Test Room",
            polygon_points=[
                (100, 100),
                (500, 100),
                (500, 400),
                (100, 400),
            ],
        )

        result = run_drywall_gewerk_for_sector(
            pdf_path=str(sample_floor_plan_path),
            sector=sector,
            scale_context=simple_scale_context,
            wall_height_m=2.6,
        )

        # Should complete without errors
        assert result.status == "ok"
        assert result.gewerk_type == "drywall"
        assert len(result.items) == 1

        # Should have valid measurements (even if zero)
        item = result.items[0]
        assert item.wall_length_m >= 0
        assert item.drywall_area_m2 >= 0
        assert item.wall_height_m == 2.6

"""
Tests for Vector Measurement Service

Tests for line extraction, wall segments, and sector-based measurements.
Part of Phase D implementation.
"""

import pytest
import math
from pathlib import Path
from unittest.mock import patch, MagicMock

from app.services.vector_measurement import (
    LineSegment,
    WallSegment,
    generate_wall_segment_id,
    extract_line_segments_from_page,
    extract_wall_segments_from_page,
    point_in_polygon,
    segment_in_polygon,
    compute_wall_length_in_sector_m,
    compute_drywall_area_in_sector_m2,
    FITZ_AVAILABLE,
)
from app.services.measurement_engine import (
    Sector,
    generate_sector_id,
)
from app.services.scale_calibration import ScaleContext


# =============================================================================
# Test Fixtures
# =============================================================================


@pytest.fixture
def simple_line_segment():
    """A horizontal line segment from (0,0) to (100,0)."""
    return LineSegment(
        x1=0.0,
        y1=0.0,
        x2=100.0,
        y2=0.0,
        page_number=1,
    )


@pytest.fixture
def diagonal_line_segment():
    """A diagonal line segment from (0,0) to (30,40) - length 50."""
    return LineSegment(
        x1=0.0,
        y1=0.0,
        x2=30.0,
        y2=40.0,
        page_number=1,
    )


@pytest.fixture
def simple_wall_segment(simple_line_segment):
    """A wall segment wrapping the simple line segment."""
    return WallSegment(
        segment_id="wall_test123",
        segment=simple_line_segment,
        kind="wall",
        confidence=1.0,
    )


@pytest.fixture
def square_sector():
    """A 100x100 square sector centered at (50, 50)."""
    return Sector(
        sector_id=generate_sector_id(),
        file_id="test-file-123",
        page_number=1,
        name="Test Square",
        polygon_points=[
            (0.0, 0.0),
            (100.0, 0.0),
            (100.0, 100.0),
            (0.0, 100.0),
        ],
    )


@pytest.fixture
def simple_scale_context():
    """A scale context with 10 pixels per meter."""
    return ScaleContext(
        id="scale-test-123",
        file_id="test-file-123",
        pixels_per_meter=10.0,
        scale_string="1:100",
        confidence=1.0,
        detection_method="test",
        source_page=1,
    )


@pytest.fixture
def sample_floor_plan_path():
    """Path to the sample floor plan PDF."""
    project_root = Path(__file__).parent.parent.parent
    return project_root / "sampleGrundrissBauplanGenie.pdf"


# =============================================================================
# LineSegment Tests
# =============================================================================


class TestLineSegment:
    """Tests for LineSegment dataclass."""

    def test_create_line_segment(self):
        """Test creating a basic line segment."""
        segment = LineSegment(
            x1=0.0,
            y1=0.0,
            x2=100.0,
            y2=0.0,
            page_number=1,
        )
        assert segment.x1 == 0.0
        assert segment.x2 == 100.0
        assert segment.page_number == 1

    def test_length_horizontal(self, simple_line_segment):
        """Test length calculation for horizontal line."""
        assert simple_line_segment.length_px == 100.0

    def test_length_vertical(self):
        """Test length calculation for vertical line."""
        segment = LineSegment(
            x1=50.0, y1=0.0,
            x2=50.0, y2=100.0,
            page_number=1,
        )
        assert segment.length_px == 100.0

    def test_length_diagonal(self, diagonal_line_segment):
        """Test length calculation for 3-4-5 triangle diagonal."""
        # sqrt(30^2 + 40^2) = sqrt(900 + 1600) = sqrt(2500) = 50
        assert diagonal_line_segment.length_px == 50.0

    def test_midpoint(self, simple_line_segment):
        """Test midpoint calculation."""
        mid = simple_line_segment.midpoint
        assert mid == (50.0, 0.0)

    def test_midpoint_diagonal(self, diagonal_line_segment):
        """Test midpoint for diagonal line."""
        mid = diagonal_line_segment.midpoint
        assert mid == (15.0, 20.0)

    def test_angle_horizontal(self, simple_line_segment):
        """Test angle for horizontal line."""
        assert simple_line_segment.angle_degrees == 0.0

    def test_angle_vertical(self):
        """Test angle for vertical line."""
        segment = LineSegment(
            x1=50.0, y1=0.0,
            x2=50.0, y2=100.0,
            page_number=1,
        )
        assert segment.angle_degrees == 90.0

    def test_angle_45_degrees(self):
        """Test angle for 45-degree line."""
        segment = LineSegment(
            x1=0.0, y1=0.0,
            x2=100.0, y2=100.0,
            page_number=1,
        )
        assert segment.angle_degrees == 45.0

    def test_to_dict(self, simple_line_segment):
        """Test serialization to dictionary."""
        d = simple_line_segment.to_dict()
        assert d["x1"] == 0.0
        assert d["x2"] == 100.0
        assert d["length_px"] == 100.0
        assert d["page_number"] == 1

    def test_from_dict(self):
        """Test deserialization from dictionary."""
        data = {
            "x1": 10.0,
            "y1": 20.0,
            "x2": 30.0,
            "y2": 40.0,
            "page_number": 2,
            "layer": "walls",
        }
        segment = LineSegment.from_dict(data)
        assert segment.x1 == 10.0
        assert segment.y2 == 40.0
        assert segment.page_number == 2
        assert segment.layer == "walls"

    def test_with_metadata(self):
        """Test line segment with metadata."""
        segment = LineSegment(
            x1=0.0, y1=0.0,
            x2=100.0, y2=0.0,
            page_number=1,
            layer="partition",
            stroke_width=2.5,
            color=(0.0, 0.0, 0.0),
            metadata={"source": "test"},
        )
        assert segment.layer == "partition"
        assert segment.stroke_width == 2.5
        assert segment.color == (0.0, 0.0, 0.0)


# =============================================================================
# WallSegment Tests
# =============================================================================


class TestWallSegment:
    """Tests for WallSegment dataclass."""

    def test_create_wall_segment(self, simple_line_segment):
        """Test creating a wall segment."""
        wall = WallSegment(
            segment_id="wall_123",
            segment=simple_line_segment,
            kind="wall",
            confidence=0.95,
        )
        assert wall.segment_id == "wall_123"
        assert wall.kind == "wall"
        assert wall.confidence == 0.95

    def test_length_from_segment(self, simple_wall_segment):
        """Test length property delegates to segment."""
        assert simple_wall_segment.length_px == 100.0

    def test_page_number_from_segment(self, simple_wall_segment):
        """Test page_number property delegates to segment."""
        assert simple_wall_segment.page_number == 1

    def test_to_dict(self, simple_wall_segment):
        """Test serialization to dictionary."""
        d = simple_wall_segment.to_dict()
        assert d["segment_id"] == "wall_test123"
        assert d["kind"] == "wall"
        assert d["length_px"] == 100.0
        assert "segment" in d

    def test_from_dict(self):
        """Test deserialization from dictionary."""
        data = {
            "segment_id": "wall_abc",
            "segment": {
                "x1": 0.0, "y1": 0.0,
                "x2": 50.0, "y2": 0.0,
                "page_number": 1,
            },
            "kind": "partition",
            "confidence": 0.8,
            "material": "drywall",
        }
        wall = WallSegment.from_dict(data)
        assert wall.segment_id == "wall_abc"
        assert wall.kind == "partition"
        assert wall.material == "drywall"
        assert wall.length_px == 50.0


class TestGenerateWallSegmentId:
    """Tests for wall segment ID generation."""

    def test_generates_unique_ids(self):
        """Test that generated IDs are unique."""
        ids = [generate_wall_segment_id() for _ in range(100)]
        assert len(set(ids)) == 100

    def test_id_format(self):
        """Test that IDs have expected format."""
        wall_id = generate_wall_segment_id()
        assert wall_id.startswith("wall_")
        assert len(wall_id) == 17  # "wall_" + 12 hex chars


# =============================================================================
# Point-in-Polygon Tests
# =============================================================================


class TestPointInPolygon:
    """Tests for point-in-polygon algorithm."""

    def test_point_inside_square(self):
        """Test point inside a square."""
        polygon = [(0, 0), (100, 0), (100, 100), (0, 100)]
        assert point_in_polygon(50, 50, polygon) is True

    def test_point_outside_square(self):
        """Test point outside a square."""
        polygon = [(0, 0), (100, 0), (100, 100), (0, 100)]
        assert point_in_polygon(150, 50, polygon) is False

    def test_point_on_edge(self):
        """Test point on edge - typically considered outside by ray casting."""
        polygon = [(0, 0), (100, 0), (100, 100), (0, 100)]
        # Edge cases depend on implementation
        # Just verify it doesn't crash
        result = point_in_polygon(50, 0, polygon)
        assert isinstance(result, bool)

    def test_point_at_corner(self):
        """Test point at corner."""
        polygon = [(0, 0), (100, 0), (100, 100), (0, 100)]
        result = point_in_polygon(0, 0, polygon)
        assert isinstance(result, bool)

    def test_triangle(self):
        """Test with triangular polygon."""
        polygon = [(0, 0), (100, 0), (50, 100)]
        assert point_in_polygon(50, 30, polygon) is True
        assert point_in_polygon(10, 90, polygon) is False

    def test_concave_polygon(self):
        """Test with L-shaped concave polygon."""
        # L-shape
        polygon = [
            (0, 0), (100, 0), (100, 50),
            (50, 50), (50, 100), (0, 100),
        ]
        # Inside the L
        assert point_in_polygon(25, 25, polygon) is True
        assert point_in_polygon(25, 75, polygon) is True
        # In the cut-out part
        assert point_in_polygon(75, 75, polygon) is False

    def test_insufficient_points(self):
        """Test with fewer than 3 points."""
        assert point_in_polygon(50, 50, []) is False
        assert point_in_polygon(50, 50, [(0, 0)]) is False
        assert point_in_polygon(50, 50, [(0, 0), (100, 100)]) is False


# =============================================================================
# Segment-in-Polygon Tests
# =============================================================================


class TestSegmentInPolygon:
    """Tests for segment-in-polygon checking."""

    def test_segment_fully_inside(self, square_sector):
        """Test segment with both endpoints inside."""
        segment = LineSegment(
            x1=20.0, y1=50.0,
            x2=80.0, y2=50.0,
            page_number=1,
        )
        assert segment_in_polygon(segment, square_sector.polygon_points) is True

    def test_segment_fully_outside(self, square_sector):
        """Test segment with both endpoints outside."""
        segment = LineSegment(
            x1=200.0, y1=50.0,
            x2=300.0, y2=50.0,
            page_number=1,
        )
        assert segment_in_polygon(segment, square_sector.polygon_points) is False

    def test_segment_one_endpoint_inside(self, square_sector):
        """Test segment with one endpoint inside."""
        segment = LineSegment(
            x1=50.0, y1=50.0,  # Inside
            x2=150.0, y2=50.0,  # Outside
            page_number=1,
        )
        # With require_both_endpoints=True (default), should be False
        assert segment_in_polygon(segment, square_sector.polygon_points, require_both_endpoints=True) is False
        # With require_both_endpoints=False, should be True
        assert segment_in_polygon(segment, square_sector.polygon_points, require_both_endpoints=False) is True


# =============================================================================
# Wall Length Calculation Tests
# =============================================================================


class TestComputeWallLengthInSectorM:
    """Tests for wall length calculation inside a sector."""

    def test_single_wall_inside_sector(self, square_sector, simple_scale_context):
        """Test with one wall fully inside the sector."""
        # Wall from (20, 50) to (80, 50) - length 60px
        wall = WallSegment(
            segment_id="wall_1",
            segment=LineSegment(
                x1=20.0, y1=50.0,
                x2=80.0, y2=50.0,
                page_number=1,
            ),
            kind="wall",
        )

        result = compute_wall_length_in_sector_m(
            wall_segments=[wall],
            sector=square_sector,
            scale_context=simple_scale_context,
        )

        # 60px / 10 px/m = 6m
        assert result.value == 6.0
        assert result.unit == "m"
        assert result.measurement_type == "sector_wall_length"
        assert "segment_count: 1" in result.assumptions

    def test_multiple_walls_inside_sector(self, square_sector, simple_scale_context):
        """Test with multiple walls inside the sector."""
        walls = [
            WallSegment(
                segment_id="wall_1",
                segment=LineSegment(x1=10.0, y1=50.0, x2=90.0, y2=50.0, page_number=1),  # 80px
                kind="wall",
            ),
            WallSegment(
                segment_id="wall_2",
                segment=LineSegment(x1=50.0, y1=10.0, x2=50.0, y2=90.0, page_number=1),  # 80px
                kind="wall",
            ),
        ]

        result = compute_wall_length_in_sector_m(
            wall_segments=walls,
            sector=square_sector,
            scale_context=simple_scale_context,
        )

        # 160px / 10 px/m = 16m
        assert result.value == 16.0
        assert "segment_count: 2" in result.assumptions

    def test_wall_outside_sector_excluded(self, square_sector, simple_scale_context):
        """Test that walls outside sector are excluded."""
        walls = [
            WallSegment(
                segment_id="wall_inside",
                segment=LineSegment(x1=20.0, y1=50.0, x2=80.0, y2=50.0, page_number=1),  # 60px inside
                kind="wall",
            ),
            WallSegment(
                segment_id="wall_outside",
                segment=LineSegment(x1=200.0, y1=50.0, x2=300.0, y2=50.0, page_number=1),  # outside
                kind="wall",
            ),
        ]

        result = compute_wall_length_in_sector_m(
            wall_segments=walls,
            sector=square_sector,
            scale_context=simple_scale_context,
        )

        # Only inside wall counted: 60px / 10 px/m = 6m
        assert result.value == 6.0
        assert "segment_count: 1" in result.assumptions

    def test_wall_on_different_page_excluded(self, square_sector, simple_scale_context):
        """Test that walls on different page are excluded."""
        wall = WallSegment(
            segment_id="wall_1",
            segment=LineSegment(x1=20.0, y1=50.0, x2=80.0, y2=50.0, page_number=2),  # Different page!
            kind="wall",
        )

        result = compute_wall_length_in_sector_m(
            wall_segments=[wall],
            sector=square_sector,
            scale_context=simple_scale_context,
        )

        assert result.value == 0.0
        assert "segment_count: 0" in result.assumptions

    def test_empty_wall_list(self, square_sector, simple_scale_context):
        """Test with no walls."""
        result = compute_wall_length_in_sector_m(
            wall_segments=[],
            sector=square_sector,
            scale_context=simple_scale_context,
        )

        assert result.value == 0.0
        assert result.unit == "m"

    def test_no_scale_raises_error(self, square_sector):
        """Test that missing scale raises ValueError."""
        scale = ScaleContext()  # No pixels_per_meter

        with pytest.raises(ValueError, match="valid pixels_per_meter"):
            compute_wall_length_in_sector_m(
                wall_segments=[],
                sector=square_sector,
                scale_context=scale,
            )

    def test_result_has_auditability_fields(self, square_sector, simple_scale_context):
        """Test that result includes all auditability fields."""
        wall = WallSegment(
            segment_id="wall_1",
            segment=LineSegment(x1=20.0, y1=50.0, x2=80.0, y2=50.0, page_number=1),
            kind="wall",
        )

        result = compute_wall_length_in_sector_m(
            wall_segments=[wall],
            sector=square_sector,
            scale_context=simple_scale_context,
        )

        assert result.file_id == square_sector.file_id
        assert result.page_number == square_sector.page_number
        assert result.sector_id == square_sector.sector_id
        assert result.scale_context_id == simple_scale_context.id
        assert result.method == "vector_geometry"
        assert len(result.assumptions) > 0


# =============================================================================
# Drywall Area Calculation Tests
# =============================================================================


class TestComputeDrywallAreaInSectorM2:
    """Tests for drywall area calculation."""

    def test_simple_drywall_area(self, square_sector, simple_scale_context):
        """Test drywall area calculation with known values."""
        # Wall of 100px at 10px/m = 10m wall length
        wall = WallSegment(
            segment_id="wall_1",
            segment=LineSegment(x1=10.0, y1=50.0, x2=90.0, y2=50.0, page_number=1),  # 80px
            kind="wall",
        )

        wall_height_m = 2.5

        result = compute_drywall_area_in_sector_m2(
            wall_segments=[wall],
            sector=square_sector,
            scale_context=simple_scale_context,
            wall_height_m=wall_height_m,
        )

        # 80px / 10 px/m = 8m wall length
        # 8m * 2.5m = 20 m²
        assert result.value == 20.0
        assert result.unit == "m2"
        assert result.measurement_type == "sector_drywall_area"
        assert f"wall_height_m: {wall_height_m:.2f}" in result.assumptions

    def test_multiple_walls_drywall_area(self, square_sector, simple_scale_context):
        """Test drywall area with multiple walls."""
        walls = [
            WallSegment(
                segment_id="wall_1",
                segment=LineSegment(x1=10.0, y1=50.0, x2=90.0, y2=50.0, page_number=1),  # 80px = 8m
                kind="wall",
            ),
            WallSegment(
                segment_id="wall_2",
                segment=LineSegment(x1=50.0, y1=10.0, x2=50.0, y2=90.0, page_number=1),  # 80px = 8m
                kind="wall",
            ),
        ]

        wall_height_m = 3.0

        result = compute_drywall_area_in_sector_m2(
            wall_segments=walls,
            sector=square_sector,
            scale_context=simple_scale_context,
            wall_height_m=wall_height_m,
        )

        # (8m + 8m) * 3m = 48 m²
        assert result.value == 48.0

    def test_zero_height_raises_error(self, square_sector, simple_scale_context):
        """Test that zero wall height raises ValueError."""
        with pytest.raises(ValueError, match="wall_height_m must be positive"):
            compute_drywall_area_in_sector_m2(
                wall_segments=[],
                sector=square_sector,
                scale_context=simple_scale_context,
                wall_height_m=0.0,
            )

    def test_negative_height_raises_error(self, square_sector, simple_scale_context):
        """Test that negative wall height raises ValueError."""
        with pytest.raises(ValueError, match="wall_height_m must be positive"):
            compute_drywall_area_in_sector_m2(
                wall_segments=[],
                sector=square_sector,
                scale_context=simple_scale_context,
                wall_height_m=-2.5,
            )

    def test_result_has_wall_length_in_assumptions(self, square_sector, simple_scale_context):
        """Test that result includes wall length in assumptions."""
        wall = WallSegment(
            segment_id="wall_1",
            segment=LineSegment(x1=10.0, y1=50.0, x2=90.0, y2=50.0, page_number=1),
            kind="wall",
        )

        result = compute_drywall_area_in_sector_m2(
            wall_segments=[wall],
            sector=square_sector,
            scale_context=simple_scale_context,
            wall_height_m=2.5,
        )

        # Check that wall length is documented
        wall_length_found = any("wall_length_m:" in a for a in result.assumptions)
        assert wall_length_found

    def test_empty_walls_returns_zero(self, square_sector, simple_scale_context):
        """Test that empty wall list returns zero area."""
        result = compute_drywall_area_in_sector_m2(
            wall_segments=[],
            sector=square_sector,
            scale_context=simple_scale_context,
            wall_height_m=2.5,
        )

        assert result.value == 0.0


# =============================================================================
# Vector Extraction Tests (with sample PDF if available)
# =============================================================================


class TestExtractLineSegmentsFromPage:
    """Tests for PDF line segment extraction."""

    @pytest.mark.skipif(not FITZ_AVAILABLE, reason="PyMuPDF not available")
    def test_extract_from_sample_pdf(self, sample_floor_plan_path):
        """Test extraction from sample floor plan PDF."""
        if not sample_floor_plan_path.exists():
            pytest.skip(f"Sample PDF not found: {sample_floor_plan_path}")

        segments = extract_line_segments_from_page(
            path=sample_floor_plan_path,
            page_number=1,
            dpi=150,
        )

        # Should return a list (may be empty if PDF is raster-only)
        assert isinstance(segments, list)
        # Log segment count for debugging
        print(f"Extracted {len(segments)} line segments from sample PDF")

    @pytest.mark.skipif(not FITZ_AVAILABLE, reason="PyMuPDF not available")
    def test_extract_returns_line_segments(self, sample_floor_plan_path):
        """Test that extraction returns LineSegment objects."""
        if not sample_floor_plan_path.exists():
            pytest.skip(f"Sample PDF not found: {sample_floor_plan_path}")

        segments = extract_line_segments_from_page(
            path=sample_floor_plan_path,
            page_number=1,
        )

        for segment in segments[:5]:  # Check first 5
            assert isinstance(segment, LineSegment)
            assert segment.page_number == 1

    @pytest.mark.skipif(not FITZ_AVAILABLE, reason="PyMuPDF not available")
    def test_file_not_found_raises_error(self):
        """Test that missing file raises FileNotFoundError."""
        with pytest.raises(FileNotFoundError):
            extract_line_segments_from_page(
                path="/nonexistent/file.pdf",
                page_number=1,
            )

    @pytest.mark.skipif(not FITZ_AVAILABLE, reason="PyMuPDF not available")
    def test_invalid_page_number_raises_error(self, sample_floor_plan_path):
        """Test that invalid page number raises ValueError."""
        if not sample_floor_plan_path.exists():
            pytest.skip(f"Sample PDF not found: {sample_floor_plan_path}")

        with pytest.raises(ValueError, match="Invalid page number"):
            extract_line_segments_from_page(
                path=sample_floor_plan_path,
                page_number=999,
            )

    def test_fitz_not_available_raises_import_error(self):
        """Test that missing PyMuPDF raises ImportError."""
        with patch("app.services.vector_measurement.FITZ_AVAILABLE", False):
            with pytest.raises(ImportError):
                extract_line_segments_from_page(
                    path="dummy.pdf",
                    page_number=1,
                )


class TestExtractWallSegmentsFromPage:
    """Tests for wall segment extraction."""

    @pytest.mark.skipif(not FITZ_AVAILABLE, reason="PyMuPDF not available")
    def test_extract_walls_from_sample_pdf(self, sample_floor_plan_path):
        """Test wall extraction from sample PDF."""
        if not sample_floor_plan_path.exists():
            pytest.skip(f"Sample PDF not found: {sample_floor_plan_path}")

        walls = extract_wall_segments_from_page(
            path=sample_floor_plan_path,
            page_number=1,
            dpi=150,
        )

        assert isinstance(walls, list)
        for wall in walls[:5]:  # Check first 5
            assert isinstance(wall, WallSegment)
            assert wall.kind == "wall"

    @pytest.mark.skipif(not FITZ_AVAILABLE, reason="PyMuPDF not available")
    def test_walls_have_unique_ids(self, sample_floor_plan_path):
        """Test that each wall has a unique ID."""
        if not sample_floor_plan_path.exists():
            pytest.skip(f"Sample PDF not found: {sample_floor_plan_path}")

        walls = extract_wall_segments_from_page(
            path=sample_floor_plan_path,
            page_number=1,
        )

        ids = [w.segment_id for w in walls]
        assert len(ids) == len(set(ids))


# =============================================================================
# Integration Tests
# =============================================================================


class TestIntegration:
    """Integration tests for the full vector measurement flow."""

    def test_full_wall_measurement_flow(self):
        """Test the complete flow from segments to measurement result."""
        # Create test data
        sector = Sector(
            sector_id="sect_integration",
            file_id="file_integration",
            page_number=1,
            name="Integration Test Room",
            polygon_points=[(0, 0), (1000, 0), (1000, 1000), (0, 1000)],
        )

        scale = ScaleContext(
            id="scale_integration",
            file_id="file_integration",
            pixels_per_meter=100.0,  # 100 px/m
            scale_string="1:100",
            confidence=1.0,
            detection_method="test",
            source_page=1,
        )

        # Create walls representing a room perimeter
        walls = [
            # North wall: 800px = 8m
            WallSegment(
                segment_id="wall_north",
                segment=LineSegment(x1=100, y1=100, x2=900, y2=100, page_number=1),
                kind="wall",
            ),
            # South wall: 800px = 8m
            WallSegment(
                segment_id="wall_south",
                segment=LineSegment(x1=100, y1=900, x2=900, y2=900, page_number=1),
                kind="wall",
            ),
            # West wall: 800px = 8m
            WallSegment(
                segment_id="wall_west",
                segment=LineSegment(x1=100, y1=100, x2=100, y2=900, page_number=1),
                kind="wall",
            ),
            # East wall: 800px = 8m
            WallSegment(
                segment_id="wall_east",
                segment=LineSegment(x1=900, y1=100, x2=900, y2=900, page_number=1),
                kind="wall",
            ),
        ]

        # Calculate wall length
        length_result = compute_wall_length_in_sector_m(
            wall_segments=walls,
            sector=sector,
            scale_context=scale,
        )

        # Total: 4 * 800px = 3200px = 32m
        assert length_result.value == 32.0
        assert length_result.unit == "m"

        # Calculate drywall area
        wall_height = 2.7  # Standard ceiling height
        area_result = compute_drywall_area_in_sector_m2(
            wall_segments=walls,
            sector=sector,
            scale_context=scale,
            wall_height_m=wall_height,
        )

        # 32m * 2.7m = 86.4 m²
        assert area_result.value == 86.4
        assert area_result.unit == "m2"

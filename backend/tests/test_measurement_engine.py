"""
Tests for measurement engine service.

These tests validate:
- Shoelace formula for polygon area calculation
- Perimeter calculation
- Sector data model functionality
- MeasurementResult data model functionality
- Unit conversions (pixels to meters)
"""

import sys
import math
from pathlib import Path
from datetime import datetime

import pytest

# Add backend to path
backend_dir = Path(__file__).parent.parent
sys.path.insert(0, str(backend_dir))

from app.services.measurement_engine import (
    Sector,
    MeasurementResult,
    SectorQueryResult,
    MeasurementType,
    MeasurementMethod,
    generate_measurement_id,
    generate_sector_id,
    shoelace_area_pixels,
    shoelace_perimeter_pixels,
    compute_sector_area_m2,
    compute_sector_perimeter_m,
)


class TestShoelaceAreaPixels:
    """Tests for shoelace formula polygon area calculation."""

    def test_unit_square(self):
        """A 1x1 square should have area 1."""
        square = [(0, 0), (1, 0), (1, 1), (0, 1)]
        area = shoelace_area_pixels(square)
        assert area == pytest.approx(1.0)

    def test_10x10_square(self):
        """A 10x10 square should have area 100."""
        square = [(0, 0), (10, 0), (10, 10), (0, 10)]
        area = shoelace_area_pixels(square)
        assert area == pytest.approx(100.0)

    def test_rectangle(self):
        """A 4x3 rectangle should have area 12."""
        rect = [(0, 0), (4, 0), (4, 3), (0, 3)]
        area = shoelace_area_pixels(rect)
        assert area == pytest.approx(12.0)

    def test_triangle(self):
        """A triangle with base 4 and height 3 should have area 6."""
        triangle = [(0, 0), (4, 0), (2, 3)]
        area = shoelace_area_pixels(triangle)
        assert area == pytest.approx(6.0)

    def test_clockwise_polygon(self):
        """Clockwise polygon should return positive area."""
        # Clockwise order
        square = [(0, 0), (0, 1), (1, 1), (1, 0)]
        area = shoelace_area_pixels(square)
        assert area == pytest.approx(1.0)
        assert area > 0

    def test_counterclockwise_polygon(self):
        """Counter-clockwise polygon should also return positive area."""
        # Counter-clockwise order
        square = [(0, 0), (1, 0), (1, 1), (0, 1)]
        area = shoelace_area_pixels(square)
        assert area == pytest.approx(1.0)
        assert area > 0

    def test_complex_polygon(self):
        """L-shaped polygon area calculation."""
        # L-shape: 3x3 square with 1x1 cut out from top-right
        l_shape = [(0, 0), (3, 0), (3, 2), (2, 2), (2, 3), (0, 3)]
        area = shoelace_area_pixels(l_shape)
        # 3*3 = 9 minus 1*1 = 1, total = 8
        assert area == pytest.approx(8.0)

    def test_raises_for_less_than_3_points(self):
        """Should raise ValueError for polygons with < 3 points."""
        with pytest.raises(ValueError, match="at least 3 points"):
            shoelace_area_pixels([(0, 0), (1, 1)])

        with pytest.raises(ValueError, match="at least 3 points"):
            shoelace_area_pixels([(0, 0)])

        with pytest.raises(ValueError, match="at least 3 points"):
            shoelace_area_pixels([])

    def test_floating_point_coordinates(self):
        """Should handle floating point coordinates."""
        square = [(0.5, 0.5), (2.5, 0.5), (2.5, 2.5), (0.5, 2.5)]
        area = shoelace_area_pixels(square)
        assert area == pytest.approx(4.0)

    def test_large_polygon(self):
        """Should handle large coordinate values."""
        square = [(1000, 1000), (2000, 1000), (2000, 2000), (1000, 2000)]
        area = shoelace_area_pixels(square)
        assert area == pytest.approx(1000000.0)


class TestShoelacePerimeterPixels:
    """Tests for polygon perimeter calculation."""

    def test_unit_square_perimeter(self):
        """A 1x1 square should have perimeter 4."""
        square = [(0, 0), (1, 0), (1, 1), (0, 1)]
        perimeter = shoelace_perimeter_pixels(square)
        assert perimeter == pytest.approx(4.0)

    def test_10x10_square_perimeter(self):
        """A 10x10 square should have perimeter 40."""
        square = [(0, 0), (10, 0), (10, 10), (0, 10)]
        perimeter = shoelace_perimeter_pixels(square)
        assert perimeter == pytest.approx(40.0)

    def test_rectangle_perimeter(self):
        """A 4x3 rectangle should have perimeter 14."""
        rect = [(0, 0), (4, 0), (4, 3), (0, 3)]
        perimeter = shoelace_perimeter_pixels(rect)
        assert perimeter == pytest.approx(14.0)

    def test_triangle_perimeter(self):
        """A 3-4-5 right triangle should have perimeter 12."""
        triangle = [(0, 0), (4, 0), (4, 3)]
        perimeter = shoelace_perimeter_pixels(triangle)
        # Sides: 4 + 3 + 5 = 12
        assert perimeter == pytest.approx(12.0)

    def test_raises_for_less_than_2_points(self):
        """Should raise ValueError for polygons with < 2 points."""
        with pytest.raises(ValueError, match="at least 2 points"):
            shoelace_perimeter_pixels([(0, 0)])

        with pytest.raises(ValueError, match="at least 2 points"):
            shoelace_perimeter_pixels([])


class TestComputeSectorAreaM2:
    """Tests for converting polygon area from pixels to square meters."""

    def test_100x100_px_at_100_ppm(self):
        """100x100 px square at 100 px/m should be 1 m²."""
        square = [(0, 0), (100, 0), (100, 100), (0, 100)]
        area_m2 = compute_sector_area_m2(square, pixels_per_meter=100)
        assert area_m2 == pytest.approx(1.0)

    def test_100x100_px_at_50_ppm(self):
        """100x100 px square at 50 px/m should be 4 m²."""
        square = [(0, 0), (100, 0), (100, 100), (0, 100)]
        area_m2 = compute_sector_area_m2(square, pixels_per_meter=50)
        assert area_m2 == pytest.approx(4.0)

    def test_200x200_px_at_100_ppm(self):
        """200x200 px square at 100 px/m should be 4 m²."""
        square = [(0, 0), (200, 0), (200, 200), (0, 200)]
        area_m2 = compute_sector_area_m2(square, pixels_per_meter=100)
        assert area_m2 == pytest.approx(4.0)

    def test_realistic_room_dimensions(self):
        """Realistic room: 400x300 px at 59.06 px/m (1:100 @ 150 DPI) = ~20.4 m²."""
        # 400 px / 59.06 = ~6.77 m
        # 300 px / 59.06 = ~5.08 m
        # 6.77 * 5.08 = ~34.4 m²
        room = [(0, 0), (400, 0), (400, 300), (0, 300)]
        area_m2 = compute_sector_area_m2(room, pixels_per_meter=59.055)
        expected = (400 * 300) / (59.055 ** 2)
        assert area_m2 == pytest.approx(expected, rel=0.01)

    def test_raises_for_zero_scale(self):
        """Should raise ValueError for zero or negative scale."""
        square = [(0, 0), (100, 0), (100, 100), (0, 100)]
        with pytest.raises(ValueError, match="must be positive"):
            compute_sector_area_m2(square, pixels_per_meter=0)

        with pytest.raises(ValueError, match="must be positive"):
            compute_sector_area_m2(square, pixels_per_meter=-1)


class TestComputeSectorPerimeterM:
    """Tests for converting polygon perimeter from pixels to meters."""

    def test_100x100_px_at_100_ppm(self):
        """100x100 px square at 100 px/m should have 4 m perimeter."""
        square = [(0, 0), (100, 0), (100, 100), (0, 100)]
        perimeter_m = compute_sector_perimeter_m(square, pixels_per_meter=100)
        assert perimeter_m == pytest.approx(4.0)

    def test_200x100_px_at_50_ppm(self):
        """200x100 px rectangle at 50 px/m should have 12 m perimeter."""
        rect = [(0, 0), (200, 0), (200, 100), (0, 100)]
        perimeter_m = compute_sector_perimeter_m(rect, pixels_per_meter=50)
        # (200+100)*2 = 600 px / 50 = 12 m
        assert perimeter_m == pytest.approx(12.0)

    def test_raises_for_zero_scale(self):
        """Should raise ValueError for zero or negative scale."""
        square = [(0, 0), (100, 0), (100, 100), (0, 100)]
        with pytest.raises(ValueError, match="must be positive"):
            compute_sector_perimeter_m(square, pixels_per_meter=0)


class TestSector:
    """Tests for Sector dataclass."""

    def test_to_dict_serialization(self):
        """to_dict should include all fields."""
        sector = Sector(
            sector_id="sect_abc123",
            file_id="file_xyz",
            page_number=1,
            name="Living Room",
            polygon_points=[(0, 0), (100, 0), (100, 100), (0, 100)],
            sector_type="room",
            area_m2=25.5,
            perimeter_m=20.0,
            metadata={"color": "blue"},
        )

        result = sector.to_dict()

        assert result["sector_id"] == "sect_abc123"
        assert result["file_id"] == "file_xyz"
        assert result["page_number"] == 1
        assert result["name"] == "Living Room"
        assert len(result["polygon_points"]) == 4
        assert result["sector_type"] == "room"
        assert result["area_m2"] == 25.5
        assert result["perimeter_m"] == 20.0
        assert result["metadata"]["color"] == "blue"

    def test_from_dict_deserialization(self):
        """from_dict should create valid Sector."""
        data = {
            "sector_id": "sect_abc123",
            "file_id": "file_xyz",
            "page_number": 1,
            "name": "Kitchen",
            "polygon_points": [[0, 0], [50, 0], [50, 50], [0, 50]],
            "sector_type": "room",
            "area_m2": 12.5,
            "created_at": "2024-01-15T10:30:00+00:00",
        }

        sector = Sector.from_dict(data)

        assert sector.sector_id == "sect_abc123"
        assert sector.file_id == "file_xyz"
        assert sector.name == "Kitchen"
        assert len(sector.polygon_points) == 4
        assert sector.polygon_points[0] == (0, 0)
        assert sector.created_at is not None

    def test_contains_point_inside(self):
        """contains_point should return True for point inside polygon."""
        sector = Sector(
            sector_id="test",
            file_id="test",
            page_number=1,
            name="Test",
            polygon_points=[(0, 0), (100, 0), (100, 100), (0, 100)],
        )

        assert sector.contains_point(50, 50) is True
        assert sector.contains_point(10, 10) is True
        assert sector.contains_point(99, 99) is True

    def test_contains_point_outside(self):
        """contains_point should return False for point outside polygon."""
        sector = Sector(
            sector_id="test",
            file_id="test",
            page_number=1,
            name="Test",
            polygon_points=[(0, 0), (100, 0), (100, 100), (0, 100)],
        )

        assert sector.contains_point(150, 50) is False
        assert sector.contains_point(-10, 50) is False
        assert sector.contains_point(50, 150) is False

    def test_contains_point_on_edge(self):
        """contains_point behavior for points on edge (implementation dependent)."""
        sector = Sector(
            sector_id="test",
            file_id="test",
            page_number=1,
            name="Test",
            polygon_points=[(0, 0), (100, 0), (100, 100), (0, 100)],
        )

        # Points on edge may be True or False depending on implementation
        # Just verify no exception is raised
        sector.contains_point(0, 50)
        sector.contains_point(50, 0)


class TestMeasurementResult:
    """Tests for MeasurementResult dataclass."""

    def test_to_dict_serialization(self):
        """to_dict should include all fields."""
        measurement = MeasurementResult(
            measurement_id="meas_123",
            measurement_type=MeasurementType.AREA.value,
            value=25.5,
            unit="m2",
            file_id="file_xyz",
            page_number=1,
            confidence=0.95,
            method=MeasurementMethod.POLYGON_AREA.value,
            assumptions=["pixels_per_meter=100"],
            source="Sector: Living Room",
            sector_id="sect_abc",
        )

        result = measurement.to_dict()

        assert result["measurement_id"] == "meas_123"
        assert result["measurement_type"] == "area"
        assert result["value"] == 25.5
        assert result["unit"] == "m2"
        assert result["file_id"] == "file_xyz"
        assert result["confidence"] == 0.95
        assert result["method"] == "polygon_area"
        assert "pixels_per_meter=100" in result["assumptions"]
        assert result["sector_id"] == "sect_abc"

    def test_from_dict_deserialization(self):
        """from_dict should create valid MeasurementResult."""
        data = {
            "measurement_id": "meas_456",
            "measurement_type": "width",
            "value": 0.9,
            "unit": "m",
            "file_id": "file_abc",
            "page_number": 2,
            "confidence": 0.8,
            "method": "bbox_scaled",
            "source_bbox": [10, 20, 100, 50],
        }

        measurement = MeasurementResult.from_dict(data)

        assert measurement.measurement_id == "meas_456"
        assert measurement.measurement_type == "width"
        assert measurement.value == 0.9
        assert measurement.source_bbox == (10, 20, 100, 50)


class TestIdGeneration:
    """Tests for ID generation functions."""

    def test_generate_measurement_id_format(self):
        """Measurement ID should have correct format."""
        mid = generate_measurement_id()
        assert mid.startswith("meas_")
        assert len(mid) > 5

    def test_generate_measurement_id_unique(self):
        """Measurement IDs should be unique."""
        ids = [generate_measurement_id() for _ in range(100)]
        assert len(set(ids)) == 100

    def test_generate_sector_id_format(self):
        """Sector ID should have correct format."""
        sid = generate_sector_id()
        assert sid.startswith("sect_")
        assert len(sid) > 5

    def test_generate_sector_id_unique(self):
        """Sector IDs should be unique."""
        ids = [generate_sector_id() for _ in range(100)]
        assert len(set(ids)) == 100


class TestMeasurementTypes:
    """Tests for MeasurementType and MeasurementMethod enums."""

    def test_measurement_types_exist(self):
        """All expected measurement types should exist."""
        assert MeasurementType.WIDTH.value == "width"
        assert MeasurementType.HEIGHT.value == "height"
        assert MeasurementType.AREA.value == "area"
        assert MeasurementType.PERIMETER.value == "perimeter"
        assert MeasurementType.COUNT.value == "count"

    def test_measurement_methods_exist(self):
        """All expected measurement methods should exist."""
        assert MeasurementMethod.VECTOR_GEOMETRY.value == "vector_geometry"
        assert MeasurementMethod.BBOX_SCALED.value == "bbox_scaled"
        assert MeasurementMethod.POLYGON_AREA.value == "polygon_area"
        assert MeasurementMethod.MANUAL.value == "manual"


class TestSectorQueryResult:
    """Tests for SectorQueryResult dataclass."""

    def test_to_dict_serialization(self):
        """to_dict should include all fields."""
        result = SectorQueryResult(
            sector_id="sect_123",
            sector_name="Living Room",
            query_type="door",
            total_count=3,
            objects=[{"id": "obj_1"}, {"id": "obj_2"}, {"id": "obj_3"}],
            summary={"total_width_m": 2.7},
        )

        data = result.to_dict()

        assert data["sector_id"] == "sect_123"
        assert data["sector_name"] == "Living Room"
        assert data["query_type"] == "door"
        assert data["total_count"] == 3
        assert len(data["objects"]) == 3
        assert data["summary"]["total_width_m"] == 2.7


class TestEdgeCases:
    """Tests for edge cases and boundary conditions."""

    def test_very_small_polygon(self):
        """Handle very small polygons without numerical issues."""
        tiny_square = [(0, 0), (0.001, 0), (0.001, 0.001), (0, 0.001)]
        area = shoelace_area_pixels(tiny_square)
        assert area == pytest.approx(0.000001, rel=0.01)

    def test_very_large_polygon(self):
        """Handle very large polygons without overflow."""
        huge_square = [(0, 0), (100000, 0), (100000, 100000), (0, 100000)]
        area = shoelace_area_pixels(huge_square)
        assert area == pytest.approx(10000000000.0)

    def test_negative_coordinates(self):
        """Handle polygons with negative coordinates."""
        square = [(-50, -50), (50, -50), (50, 50), (-50, 50)]
        area = shoelace_area_pixels(square)
        assert area == pytest.approx(10000.0)

    def test_concave_polygon(self):
        """Handle concave (non-convex) polygons."""
        # Star-like shape with concave parts
        star = [(0, 3), (1, 1), (3, 0), (1, -1), (0, -3), (-1, -1), (-3, 0), (-1, 1)]
        area = shoelace_area_pixels(star)
        # Just verify it returns a positive number without error
        assert area > 0

    def test_sector_with_empty_metadata(self):
        """Sector should handle empty metadata gracefully."""
        sector = Sector(
            sector_id="test",
            file_id="test",
            page_number=1,
            name="Test",
            polygon_points=[(0, 0), (1, 0), (1, 1)],
        )

        data = sector.to_dict()
        assert data["metadata"] == {}

    def test_measurement_with_none_values(self):
        """MeasurementResult should handle None optional values."""
        measurement = MeasurementResult(
            measurement_id="test",
            measurement_type="area",
            value=10.0,
            unit="m2",
            file_id="test",
            page_number=1,
        )

        data = measurement.to_dict()
        assert data["source_bbox"] is None
        assert data["sector_id"] is None
        assert data["object_id"] is None

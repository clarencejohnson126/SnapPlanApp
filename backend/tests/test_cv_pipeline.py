"""
Tests for CV pipeline service.

These tests validate:
- ObjectType enum and mappings
- BoundingBox dataclass functionality
- DetectedObject dataclass functionality
- DetectionResult dataclass functionality
- CV pipeline status checking
- Object detection (without requiring actual YOLO model)
"""

import sys
import tempfile
from pathlib import Path

import pytest

# Add backend to path
backend_dir = Path(__file__).parent.parent
sys.path.insert(0, str(backend_dir))

from app.services.cv_pipeline import (
    ObjectType,
    BoundingBox,
    DetectedObject,
    DetectionResult,
    CVPipelineStatus,
    generate_object_id,
    get_cv_pipeline_status,
    is_cv_pipeline_available,
    is_yolo_available,
    run_object_detection_on_page,
    _map_yolo_class_to_object_type,
    CV2_AVAILABLE,
    YOLO_AVAILABLE,
)
from app.core.config import Settings


class TestObjectType:
    """Tests for ObjectType enum."""

    def test_all_expected_types_exist(self):
        """All expected object types should exist."""
        assert ObjectType.DOOR.value == "door"
        assert ObjectType.WINDOW.value == "window"
        assert ObjectType.ROOM.value == "room"
        assert ObjectType.FIXTURE.value == "fixture"
        assert ObjectType.WALL.value == "wall"
        assert ObjectType.DIMENSION_LINE.value == "dimension_line"
        assert ObjectType.SCALE_ANNOTATION.value == "scale_annotation"
        assert ObjectType.STAIRS.value == "stairs"
        assert ObjectType.ELEVATOR.value == "elevator"
        assert ObjectType.COLUMN.value == "column"

    def test_enum_values_are_lowercase(self):
        """All enum values should be lowercase strings."""
        for obj_type in ObjectType:
            assert obj_type.value == obj_type.value.lower()


class TestBoundingBox:
    """Tests for BoundingBox dataclass."""

    def test_basic_creation(self):
        """BoundingBox should be created with correct values."""
        bbox = BoundingBox(x=10, y=20, width=100, height=50)
        assert bbox.x == 10
        assert bbox.y == 20
        assert bbox.width == 100
        assert bbox.height == 50

    def test_to_tuple(self):
        """to_tuple should return (x, y, width, height)."""
        bbox = BoundingBox(x=10, y=20, width=100, height=50)
        result = bbox.to_tuple()
        assert result == (10, 20, 100, 50)

    def test_to_dict(self):
        """to_dict should include all fields."""
        bbox = BoundingBox(x=10, y=20, width=100, height=50)
        result = bbox.to_dict()
        assert result["x"] == 10
        assert result["y"] == 20
        assert result["width"] == 100
        assert result["height"] == 50

    def test_center_property(self):
        """center should return the center point."""
        bbox = BoundingBox(x=0, y=0, width=100, height=50)
        center = bbox.center
        assert center == (50, 25)

    def test_center_with_offset(self):
        """center should account for x, y offset."""
        bbox = BoundingBox(x=10, y=20, width=100, height=50)
        center = bbox.center
        assert center == (60, 45)

    def test_area_property(self):
        """area should return width * height."""
        bbox = BoundingBox(x=0, y=0, width=100, height=50)
        assert bbox.area == 5000

    def test_contains_point_inside(self):
        """contains_point should return True for points inside."""
        bbox = BoundingBox(x=0, y=0, width=100, height=100)
        assert bbox.contains_point(50, 50) is True
        assert bbox.contains_point(0, 0) is True  # Top-left corner
        assert bbox.contains_point(100, 100) is True  # Bottom-right corner

    def test_contains_point_outside(self):
        """contains_point should return False for points outside."""
        bbox = BoundingBox(x=0, y=0, width=100, height=100)
        assert bbox.contains_point(150, 50) is False
        assert bbox.contains_point(-10, 50) is False
        assert bbox.contains_point(50, 150) is False

    def test_overlaps_true(self):
        """overlaps should return True for overlapping boxes."""
        bbox1 = BoundingBox(x=0, y=0, width=100, height=100)
        bbox2 = BoundingBox(x=50, y=50, width=100, height=100)
        assert bbox1.overlaps(bbox2) is True
        assert bbox2.overlaps(bbox1) is True

    def test_overlaps_false(self):
        """overlaps should return False for non-overlapping boxes."""
        bbox1 = BoundingBox(x=0, y=0, width=100, height=100)
        bbox2 = BoundingBox(x=200, y=0, width=100, height=100)
        assert bbox1.overlaps(bbox2) is False
        assert bbox2.overlaps(bbox1) is False

    def test_overlaps_adjacent(self):
        """Adjacent boxes (touching) are considered overlapping."""
        bbox1 = BoundingBox(x=0, y=0, width=100, height=100)
        bbox2 = BoundingBox(x=100, y=0, width=100, height=100)
        # Implementation counts touching as overlapping (edge case)
        assert bbox1.overlaps(bbox2) is True

    def test_overlaps_gap(self):
        """Boxes with gap between them should not overlap."""
        bbox1 = BoundingBox(x=0, y=0, width=100, height=100)
        bbox2 = BoundingBox(x=101, y=0, width=100, height=100)  # 1px gap
        assert bbox1.overlaps(bbox2) is False


class TestDetectedObject:
    """Tests for DetectedObject dataclass."""

    def test_basic_creation(self):
        """DetectedObject should be created with correct values."""
        bbox = BoundingBox(x=10, y=20, width=100, height=50)
        obj = DetectedObject(
            object_id="obj_123",
            object_type=ObjectType.DOOR,
            bbox=bbox,
            confidence=0.95,
            page_number=1,
        )

        assert obj.object_id == "obj_123"
        assert obj.object_type == ObjectType.DOOR
        assert obj.confidence == 0.95
        assert obj.page_number == 1
        assert obj.label is None
        assert obj.attributes == {}

    def test_with_optional_fields(self):
        """DetectedObject should handle optional fields."""
        bbox = BoundingBox(x=10, y=20, width=100, height=50)
        obj = DetectedObject(
            object_id="obj_456",
            object_type=ObjectType.DOOR,
            bbox=bbox,
            confidence=0.85,
            page_number=2,
            label="D-101",
            attributes={"fire_rating": "T30", "swing": "left"},
        )

        assert obj.label == "D-101"
        assert obj.attributes["fire_rating"] == "T30"
        assert obj.attributes["swing"] == "left"

    def test_to_dict(self):
        """to_dict should include all fields."""
        bbox = BoundingBox(x=10, y=20, width=100, height=50)
        obj = DetectedObject(
            object_id="obj_123",
            object_type=ObjectType.DOOR,
            bbox=bbox,
            confidence=0.95,
            page_number=1,
            label="D-101",
            attributes={"width_m": 0.9},
        )

        result = obj.to_dict()

        assert result["object_id"] == "obj_123"
        assert result["object_type"] == "door"  # Should be string value
        assert result["bbox"]["x"] == 10
        assert result["confidence"] == 0.95
        assert result["page_number"] == 1
        assert result["label"] == "D-101"
        assert result["attributes"]["width_m"] == 0.9


class TestDetectionResult:
    """Tests for DetectionResult dataclass."""

    def test_basic_creation(self):
        """DetectionResult should be created with correct values."""
        result = DetectionResult(
            document_id="doc_123",
            page_number=1,
            objects=[],
            processing_time_ms=150,
            model_version="yolov8n-blueprint",
        )

        assert result.document_id == "doc_123"
        assert result.page_number == 1
        assert len(result.objects) == 0
        assert result.processing_time_ms == 150
        assert result.model_version == "yolov8n-blueprint"
        assert result.warnings == []

    def test_with_objects(self):
        """DetectionResult should include detected objects."""
        bbox = BoundingBox(x=10, y=20, width=100, height=50)
        obj = DetectedObject(
            object_id="obj_1",
            object_type=ObjectType.DOOR,
            bbox=bbox,
            confidence=0.9,
            page_number=1,
        )

        result = DetectionResult(
            document_id="doc_123",
            page_number=1,
            objects=[obj],
        )

        assert len(result.objects) == 1
        assert result.objects[0].object_id == "obj_1"

    def test_object_counts(self):
        """object_counts should return counts by type."""
        bbox = BoundingBox(x=10, y=20, width=100, height=50)
        objects = [
            DetectedObject("obj_1", ObjectType.DOOR, bbox, 0.9, 1),
            DetectedObject("obj_2", ObjectType.DOOR, bbox, 0.85, 1),
            DetectedObject("obj_3", ObjectType.WINDOW, bbox, 0.95, 1),
        ]

        result = DetectionResult(
            document_id="doc_123",
            page_number=1,
            objects=objects,
        )

        counts = result.object_counts
        assert counts["door"] == 2
        assert counts["window"] == 1

    def test_to_dict(self):
        """to_dict should include all fields."""
        bbox = BoundingBox(x=10, y=20, width=100, height=50)
        obj = DetectedObject("obj_1", ObjectType.DOOR, bbox, 0.9, 1)

        result = DetectionResult(
            document_id="doc_123",
            page_number=1,
            objects=[obj],
            processing_time_ms=200,
            model_version="test-v1",
            warnings=["Low confidence detections"],
        )

        data = result.to_dict()

        assert data["document_id"] == "doc_123"
        assert data["page_number"] == 1
        assert len(data["objects"]) == 1
        assert data["processing_time_ms"] == 200
        assert data["model_version"] == "test-v1"
        assert "Low confidence" in data["warnings"][0]


class TestYoloClassMapping:
    """Tests for YOLO class name to ObjectType mapping."""

    def test_door_mapping(self):
        """door should map to DOOR."""
        assert _map_yolo_class_to_object_type("door") == ObjectType.DOOR
        assert _map_yolo_class_to_object_type("DOOR") == ObjectType.DOOR
        assert _map_yolo_class_to_object_type("Door") == ObjectType.DOOR

    def test_window_mapping(self):
        """window should map to WINDOW."""
        assert _map_yolo_class_to_object_type("window") == ObjectType.WINDOW

    def test_fixture_mappings(self):
        """Fixture types should map to FIXTURE."""
        assert _map_yolo_class_to_object_type("toilet") == ObjectType.FIXTURE
        assert _map_yolo_class_to_object_type("sink") == ObjectType.FIXTURE
        assert _map_yolo_class_to_object_type("bathtub") == ObjectType.FIXTURE
        assert _map_yolo_class_to_object_type("shower") == ObjectType.FIXTURE

    def test_dimension_line_mapping(self):
        """Dimension line variations should map correctly."""
        assert _map_yolo_class_to_object_type("dimension") == ObjectType.DIMENSION_LINE
        assert _map_yolo_class_to_object_type("dimension_line") == ObjectType.DIMENSION_LINE

    def test_unknown_class_returns_none(self):
        """Unknown classes should return None."""
        assert _map_yolo_class_to_object_type("unknown_class") is None
        assert _map_yolo_class_to_object_type("random_object") is None
        assert _map_yolo_class_to_object_type("") is None


class TestIdGeneration:
    """Tests for object ID generation."""

    def test_generate_object_id_format(self):
        """Object ID should have correct format."""
        oid = generate_object_id()
        assert oid.startswith("obj_")
        assert len(oid) > 4

    def test_generate_object_id_unique(self):
        """Object IDs should be unique."""
        ids = [generate_object_id() for _ in range(100)]
        assert len(set(ids)) == 100


class TestCVPipelineStatus:
    """Tests for CV pipeline status checking."""

    def test_status_to_dict(self):
        """Status should serialize to dict correctly."""
        status = CVPipelineStatus(
            cv_pipeline_enabled=True,
            opencv_installed=True,
            yolo_installed=True,
            yolo_model_configured=False,
            yolo_model_path=None,
            confidence_threshold=0.5,
        )

        data = status.to_dict()

        assert data["cv_pipeline_enabled"] is True
        assert data["opencv_installed"] is True
        assert data["yolo_installed"] is True
        assert data["yolo_model_configured"] is False
        assert data["yolo_model_path"] is None
        assert data["confidence_threshold"] == 0.5

    def test_get_cv_pipeline_status(self):
        """get_cv_pipeline_status should return valid status."""
        status = get_cv_pipeline_status()

        assert isinstance(status, CVPipelineStatus)
        assert isinstance(status.cv_pipeline_enabled, bool)
        assert isinstance(status.opencv_installed, bool)
        assert isinstance(status.yolo_installed, bool)

    def test_is_cv_pipeline_available(self):
        """is_cv_pipeline_available should return boolean."""
        result = is_cv_pipeline_available()
        assert isinstance(result, bool)

    def test_is_yolo_available_without_model(self):
        """is_yolo_available should return False without model configured."""
        # Without model path configured, should return False
        settings = Settings(yolo_model_path=None)
        result = is_yolo_available(settings)
        assert result is False


class TestRunObjectDetection:
    """Tests for object detection function."""

    def test_missing_image_returns_warning(self):
        """Detection should return warning for missing image."""
        result = run_object_detection_on_page(
            image_path="/nonexistent/path.png",
            document_id="doc_123",
            page_number=1,
        )

        assert len(result.objects) == 0
        assert len(result.warnings) > 0
        assert "not found" in result.warnings[0].lower()

    def test_no_yolo_configured_returns_warning(self):
        """Detection should return warning when YOLO not configured."""
        # Create a temporary image file
        with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as f:
            # Write minimal valid PNG header
            f.write(b"\x89PNG\r\n\x1a\n")
            temp_path = f.name

        try:
            # Run detection without YOLO configured
            settings = Settings(yolo_model_path=None)
            result = run_object_detection_on_page(
                image_path=temp_path,
                document_id="doc_123",
                page_number=1,
                settings=settings,
            )

            assert len(result.objects) == 0
            assert len(result.warnings) > 0
            assert "yolo" in result.warnings[0].lower() or "not configured" in result.warnings[0].lower()
        finally:
            Path(temp_path).unlink(missing_ok=True)

    def test_detection_returns_result_structure(self):
        """Detection should always return valid DetectionResult."""
        result = run_object_detection_on_page(
            image_path="/nonexistent/path.png",
            document_id="test_doc",
            page_number=2,
        )

        assert isinstance(result, DetectionResult)
        assert result.document_id == "test_doc"
        assert result.page_number == 2
        assert isinstance(result.objects, list)
        assert isinstance(result.warnings, list)


class TestEdgeCases:
    """Tests for edge cases and boundary conditions."""

    def test_zero_size_bounding_box(self):
        """BoundingBox with zero dimensions should work."""
        bbox = BoundingBox(x=10, y=20, width=0, height=0)
        assert bbox.area == 0
        assert bbox.center == (10, 20)

    def test_large_bounding_box(self):
        """Large bounding box coordinates should work."""
        bbox = BoundingBox(x=10000, y=20000, width=5000, height=3000)
        assert bbox.area == 15000000
        assert bbox.center == (12500, 21500)

    def test_negative_bounding_box_coordinates(self):
        """Negative coordinates should work (for relative positions)."""
        bbox = BoundingBox(x=-50, y=-30, width=100, height=60)
        assert bbox.center == (0, 0)

    def test_detection_result_empty_objects(self):
        """Empty detection result should have zero counts."""
        result = DetectionResult(
            document_id="test",
            page_number=1,
            objects=[],
        )

        assert result.object_counts == {}

    def test_detected_object_with_empty_attributes(self):
        """DetectedObject with empty attributes should serialize correctly."""
        bbox = BoundingBox(x=0, y=0, width=10, height=10)
        obj = DetectedObject(
            object_id="test",
            object_type=ObjectType.DOOR,
            bbox=bbox,
            confidence=0.5,
            page_number=1,
            attributes={},
        )

        data = obj.to_dict()
        assert data["attributes"] == {}


class TestDependencyChecks:
    """Tests for dependency availability checks."""

    def test_cv2_available_is_boolean(self):
        """CV2_AVAILABLE should be a boolean."""
        assert isinstance(CV2_AVAILABLE, bool)

    def test_yolo_available_is_boolean(self):
        """YOLO_AVAILABLE should be a boolean."""
        assert isinstance(YOLO_AVAILABLE, bool)

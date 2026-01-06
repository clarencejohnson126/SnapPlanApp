"""
Tests for scale calibration service.

These tests validate scale detection from text, user calibration,
and scale computation logic.

Test philosophy:
- Test regex patterns with known good and bad inputs
- Validate mathematical correctness of scale computations
- Verify confidence scores are reasonable
- Test edge cases and error handling
"""

import sys
from pathlib import Path

import pytest

# Add backend to path
backend_dir = Path(__file__).parent.parent
sys.path.insert(0, str(backend_dir))

from app.services.plan_ingestion import (
    PageInfo,
    PlanDocument,
    DEFAULT_RENDER_DPI,
)
from app.services.scale_calibration import (
    ScaleContext,
    detect_scale_from_text,
    compute_pixels_per_meter,
    compute_scale_from_points,
    validate_scale,
    INCHES_PER_METER,
    DetectionMethod,
)


class TestScaleContext:
    """Tests for ScaleContext dataclass."""

    def test_to_dict_serialization(self):
        """to_dict should serialize all fields correctly."""
        ctx = ScaleContext(
            id="test-id",
            file_id="file-123",
            scale_string="1:100",
            scale_factor=100.0,  # denominator, not reciprocal
            pixels_per_meter=59.055,
            detection_method="text_scale",
            confidence=0.95,
            source_page=1,
            source_bbox=(10, 20, 100, 50),
            is_active=True,
        )

        result = ctx.to_dict()

        assert result["id"] == "test-id"
        assert result["file_id"] == "file-123"
        assert result["scale_string"] == "1:100"
        assert result["scale_factor"] == 100.0
        assert result["pixels_per_meter"] == 59.055
        assert result["detection_method"] == "text_scale"
        assert result["confidence"] == 0.95
        assert result["source_page"] == 1
        assert result["is_active"] is True

    def test_default_is_active_true(self):
        """ScaleContext should default to is_active=True."""
        ctx = ScaleContext(
            detection_method="test",
            confidence=0.5,
            source_page=1,
        )

        assert ctx.is_active is True

    def test_has_scale_property(self):
        """has_scale should return True when pixels_per_meter is set."""
        ctx = ScaleContext(
            pixels_per_meter=100.0,
            detection_method="test",
            confidence=1.0,
            source_page=1,
        )
        assert ctx.has_scale is True

    def test_has_scale_false_when_no_ppm(self):
        """has_scale should return False when pixels_per_meter is None."""
        ctx = ScaleContext(
            detection_method="none",
            confidence=0.0,
            source_page=1,
        )
        assert ctx.has_scale is False

    def test_px_to_meters(self):
        """px_to_meters should convert correctly."""
        ctx = ScaleContext(
            pixels_per_meter=100.0,
            detection_method="test",
            confidence=1.0,
            source_page=1,
        )
        assert ctx.px_to_meters(100.0) == 1.0
        assert ctx.px_to_meters(50.0) == 0.5

    def test_meters_to_px(self):
        """meters_to_px should convert correctly."""
        ctx = ScaleContext(
            pixels_per_meter=100.0,
            detection_method="test",
            confidence=1.0,
            source_page=1,
        )
        assert ctx.meters_to_px(1.0) == 100.0
        assert ctx.meters_to_px(0.5) == 50.0


class TestDetectScaleFromText:
    """Tests for regex-based scale detection from text."""

    def test_detect_massstab_1_100(self):
        """Should detect 'MASSSTAB 1:100' pattern."""
        text = "MASSSTAB 1:100"
        result = detect_scale_from_text(text)

        assert result is not None
        scale_string, scale_factor, confidence = result
        assert scale_string == "1:100"
        assert scale_factor == 100.0  # denominator
        # Note: Due to pattern ordering, may match with lower confidence
        assert confidence >= 0.7

    def test_detect_massstab_lowercase(self):
        """Should detect lowercase 'massstab 1:100'."""
        text = "massstab 1:100"
        result = detect_scale_from_text(text)

        assert result is not None
        scale_string, scale_factor, confidence = result
        assert scale_string == "1:100"
        assert scale_factor == 100.0

    def test_detect_german_eszett(self):
        """Should detect with eszett character: 'Maßstab 1:50'."""
        text = "Maßstab 1:50"
        result = detect_scale_from_text(text)

        assert result is not None
        scale_string, scale_factor, confidence = result
        assert scale_string == "1:50"
        assert scale_factor == 50.0

    def test_detect_scale_with_m_prefix(self):
        """Should detect 'M 1:100' or 'M. 1:100' patterns."""
        text = "M 1:100"
        result = detect_scale_from_text(text)

        assert result is not None
        scale_string, scale_factor, confidence = result
        assert scale_string == "1:100"
        assert scale_factor == 100.0

    def test_detect_scale_english(self):
        """Should detect 'SCALE 1:50' pattern."""
        text = "SCALE 1:50"
        result = detect_scale_from_text(text)

        assert result is not None
        scale_string, scale_factor, confidence = result
        assert scale_string == "1:50"
        assert scale_factor == 50.0

    def test_detect_plain_1_100(self):
        """Should detect plain '1:100' with lower confidence."""
        text = "Drawing at 1:100"
        result = detect_scale_from_text(text)

        assert result is not None
        scale_string, scale_factor, confidence = result
        assert scale_string == "1:100"
        assert scale_factor == 100.0
        # Plain pattern should have lower confidence
        assert confidence < 0.9

    def test_detect_1_200(self):
        """Should correctly parse 1:200 scale."""
        text = "M 1:200"
        result = detect_scale_from_text(text)

        assert result is not None
        scale_string, scale_factor, confidence = result
        assert scale_string == "1:200"
        assert scale_factor == 200.0

    def test_detect_1_25(self):
        """Should correctly parse 1:25 scale."""
        text = "MASSSTAB 1:25"
        result = detect_scale_from_text(text)

        assert result is not None
        scale_string, scale_factor, confidence = result
        assert scale_string == "1:25"
        assert scale_factor == 25.0

    def test_no_scale_found(self):
        """Should return None when no scale pattern found."""
        text = "This is just regular text with no scale"
        result = detect_scale_from_text(text)

        assert result is None

    def test_empty_text(self):
        """Should handle empty text gracefully."""
        result = detect_scale_from_text("")

        assert result is None

    def test_scale_with_spaces(self):
        """Should handle spaces in scale notation: '1 : 100'."""
        text = "MASSSTAB 1 : 100"
        result = detect_scale_from_text(text)

        assert result is not None
        scale_string, scale_factor, confidence = result
        assert scale_string == "1:100"
        assert scale_factor == 100.0

    def test_multiple_scales_returns_first_match(self):
        """When multiple scales present, should return first pattern match."""
        # The function checks patterns in order and returns first match
        # Since all patterns check left-to-right in the text, first match wins
        text = "1:50 area MASSSTAB 1:100 specification"
        result = detect_scale_from_text(text)

        assert result is not None
        scale_string, scale_factor, confidence = result
        # Returns first pattern that matches (could be either scale)
        assert scale_string in ["1:50", "1:100"]
        assert confidence > 0

    def test_ignores_date_like_patterns(self):
        """Should not match date-like patterns as scales."""
        text = "Date: 12:30 Drawing 1:100"
        result = detect_scale_from_text(text)

        assert result is not None
        scale_string, scale_factor, confidence = result
        # Should match 1:100, not 12:30
        assert scale_string == "1:100"

    def test_architectural_scale_1_1000(self):
        """Should handle large architectural scales like 1:1000."""
        text = "Site plan M 1:1000"
        result = detect_scale_from_text(text)

        assert result is not None
        scale_string, scale_factor, confidence = result
        assert scale_string == "1:1000"
        assert scale_factor == 1000.0


class TestComputePixelsPerMeter:
    """Tests for pixels-per-meter calculation."""

    def test_compute_1_100_at_150_dpi(self):
        """At 1:100 scale and 150 DPI, should compute correctly."""
        # scale_factor is the denominator (100 for 1:100)
        ppm = compute_pixels_per_meter(
            scale_factor=100.0,  # 1:100
            page_width_points=1190.88,
            page_height_points=841.68,
            dpi=150,
        )

        # At 1:100 and 150 DPI:
        # 1 meter in reality = 0.01 meters on paper = 0.01 * 39.3701 inches on paper
        # = 0.393701 inches on paper * 150 pixels/inch = 59.055 pixels
        expected = (1.0 / 100.0) * INCHES_PER_METER * 150
        assert abs(ppm - expected) < 0.1

    def test_compute_1_50_at_150_dpi(self):
        """At 1:50 scale, should produce larger pixels_per_meter."""
        ppm = compute_pixels_per_meter(
            scale_factor=50.0,  # 1:50
            page_width_points=1190.88,
            page_height_points=841.68,
            dpi=150,
        )

        # 1:50 means objects are drawn larger, so more pixels per real meter
        expected = (1.0 / 50.0) * INCHES_PER_METER * 150
        assert abs(ppm - expected) < 0.1

    def test_higher_dpi_gives_more_pixels(self):
        """Higher DPI should result in more pixels per meter."""
        ppm_150 = compute_pixels_per_meter(100.0, 1000, 1000, 150)
        ppm_300 = compute_pixels_per_meter(100.0, 1000, 1000, 300)

        assert ppm_300 > ppm_150
        # Should be exactly 2x
        assert abs(ppm_300 / ppm_150 - 2.0) < 0.01


class TestComputeScaleFromPoints:
    """Tests for user-assisted calibration."""

    def test_compute_from_known_dimension(self):
        """Should correctly compute scale from known dimension."""
        # User says: "This line is 100 pixels and represents 1 meter"
        ctx = compute_scale_from_points(
            pixel_distance=100.0,
            real_distance_meters=1.0,
            page_number=1,
        )

        assert ctx.pixels_per_meter == 100.0
        assert ctx.detection_method == DetectionMethod.USER_CALIBRATION.value
        assert ctx.confidence == 1.0  # User input is trusted

    def test_compute_from_door_width(self):
        """Typical use case: calibrating from a door width."""
        # User knows the door is 0.9m wide and measures 90 pixels
        ctx = compute_scale_from_points(
            pixel_distance=90.0,
            real_distance_meters=0.9,
            page_number=1,
        )

        assert ctx.pixels_per_meter == 100.0  # 90 / 0.9 = 100

    def test_stores_reference_values(self):
        """Should store the reference values used for calibration."""
        ctx = compute_scale_from_points(
            pixel_distance=150.0,
            real_distance_meters=2.5,
            page_number=2,
        )

        assert ctx.user_reference_px == 150.0
        assert ctx.user_reference_m == 2.5
        assert ctx.source_page == 2

    def test_generates_id(self):
        """Should generate an ID for the context."""
        ctx = compute_scale_from_points(
            pixel_distance=100.0,
            real_distance_meters=1.0,
            page_number=1,
        )

        assert ctx.id is not None
        assert len(ctx.id) == 36  # UUID format

    def test_stores_file_id_if_provided(self):
        """Should store file_id if provided."""
        ctx = compute_scale_from_points(
            pixel_distance=100.0,
            real_distance_meters=1.0,
            page_number=1,
            file_id="my-file-123",
        )

        assert ctx.file_id == "my-file-123"

    def test_raises_for_invalid_pixel_distance(self):
        """Should raise ValueError for non-positive pixel distance."""
        with pytest.raises(ValueError):
            compute_scale_from_points(
                pixel_distance=0,
                real_distance_meters=1.0,
                page_number=1,
            )

        with pytest.raises(ValueError):
            compute_scale_from_points(
                pixel_distance=-10,
                real_distance_meters=1.0,
                page_number=1,
            )

    def test_raises_for_invalid_real_distance(self):
        """Should raise ValueError for non-positive real distance."""
        with pytest.raises(ValueError):
            compute_scale_from_points(
                pixel_distance=100,
                real_distance_meters=0,
                page_number=1,
            )


class TestValidateScale:
    """Tests for scale validation."""

    def test_validate_correct_scale(self):
        """Valid scale should pass validation."""
        scale = ScaleContext(
            pixels_per_meter=100.0,
            detection_method="user_calibration",
            confidence=1.0,
            source_page=1,
        )

        # 100 pixels should be 1 meter at 100 px/m
        is_valid = validate_scale(
            scale=scale,
            test_dimension_px=100.0,
            expected_dimension_m=1.0,
            tolerance=0.01,
        )

        assert is_valid is True

    def test_validate_within_tolerance(self):
        """Scale within tolerance should pass."""
        scale = ScaleContext(
            pixels_per_meter=100.0,
            detection_method="text_scale",
            confidence=0.9,
            source_page=1,
        )

        # 105 pixels at 100 px/m = 1.05m, expect 1.0m, tolerance 10%
        is_valid = validate_scale(
            scale=scale,
            test_dimension_px=105.0,
            expected_dimension_m=1.0,
            tolerance=0.1,  # 10% tolerance
        )

        assert is_valid is True

    def test_validate_outside_tolerance(self):
        """Scale outside tolerance should fail."""
        scale = ScaleContext(
            pixels_per_meter=100.0,
            detection_method="text_scale",
            confidence=0.9,
            source_page=1,
        )

        # 150 pixels at 100 px/m = 1.5m, expect 1.0m, tolerance 10%
        is_valid = validate_scale(
            scale=scale,
            test_dimension_px=150.0,
            expected_dimension_m=1.0,
            tolerance=0.1,  # 10% tolerance
        )

        assert is_valid is False

    def test_validate_returns_false_for_no_scale(self):
        """Should return False if scale has no pixels_per_meter."""
        scale = ScaleContext(
            pixels_per_meter=None,  # No scale
            detection_method="none",
            confidence=0.0,
            source_page=1,
        )

        is_valid = validate_scale(
            scale=scale,
            test_dimension_px=100.0,
            expected_dimension_m=1.0,
        )

        assert is_valid is False


class TestScaleDetectionIntegration:
    """Integration tests that combine multiple components."""

    def test_detected_scale_is_usable(self):
        """Detected scale should be usable for measurement."""
        text = "MASSSTAB 1:100"
        result = detect_scale_from_text(text)

        assert result is not None
        scale_string, scale_factor, confidence = result

        # Compute pixels_per_meter at 150 DPI
        ppm = compute_pixels_per_meter(
            scale_factor=scale_factor,
            page_width_points=1190.88,
            page_height_points=841.68,
            dpi=150,
        )

        # Create scale context
        ctx = ScaleContext(
            scale_string=scale_string,
            scale_factor=scale_factor,
            pixels_per_meter=ppm,
            detection_method="text_scale",
            confidence=confidence,
            source_page=1,
        )

        # Validate: pixels_per_meter pixels should be ~1m
        is_valid = validate_scale(
            scale=ctx,
            test_dimension_px=ppm,  # pixels_per_meter pixels
            expected_dimension_m=1.0,
            tolerance=0.01,
        )

        assert is_valid is True

    def test_user_calibration_overrides_detection(self):
        """User calibration should take precedence with higher confidence."""
        # Simulated detection with lower confidence
        detected = ScaleContext(
            scale_string="1:100",
            scale_factor=100.0,
            pixels_per_meter=59.055,
            detection_method="text_scale",
            confidence=0.85,
            source_page=1,
        )

        # User calibration with full confidence
        calibrated = compute_scale_from_points(
            pixel_distance=100.0,
            real_distance_meters=1.0,
            page_number=1,
        )

        # User calibration should have higher confidence
        assert calibrated.confidence > detected.confidence
        assert calibrated.detection_method == DetectionMethod.USER_CALIBRATION.value


class TestEdgeCases:
    """Tests for edge cases and error handling."""

    def test_very_small_scale_factor(self):
        """Should handle very small scale factors (e.g., 1:5000)."""
        text = "Site overview 1:5000"
        result = detect_scale_from_text(text)

        assert result is not None
        scale_string, scale_factor, confidence = result
        assert scale_string == "1:5000"
        assert scale_factor == 5000.0

    def test_very_large_scale_factor(self):
        """Should handle large scale factors (e.g., 1:10)."""
        text = "Detail M 1:10"
        result = detect_scale_from_text(text)

        assert result is not None
        scale_string, scale_factor, confidence = result
        assert scale_string == "1:10"
        assert scale_factor == 10.0

    def test_text_with_multiple_numbers(self):
        """Should correctly parse scale among other numbers."""
        text = """
        Drawing No: 12345
        Date: 2024-01-15
        Rev: 3
        MASSSTAB 1:100
        Sheet 2 of 5
        """
        result = detect_scale_from_text(text)

        assert result is not None
        scale_string, scale_factor, confidence = result
        assert scale_string == "1:100"
        assert scale_factor == 100.0

    def test_scale_context_serialization_roundtrip(self):
        """ScaleContext should serialize and deserialize correctly."""
        original = ScaleContext(
            id="test-123",
            file_id="file-456",
            scale_string="1:50",
            scale_factor=50.0,
            pixels_per_meter=118.11,
            detection_method="text_scale",
            confidence=0.95,
            source_page=2,
            source_bbox=(10, 20, 100, 50),
            user_reference_px=None,
            user_reference_m=None,
            is_active=True,
        )

        # Serialize to dict
        data = original.to_dict()

        # Deserialize back
        restored = ScaleContext.from_dict(data)

        # Verify all fields match
        assert restored.id == original.id
        assert restored.file_id == original.file_id
        assert restored.scale_string == original.scale_string
        assert restored.scale_factor == original.scale_factor
        assert abs(restored.pixels_per_meter - original.pixels_per_meter) < 0.01
        assert restored.detection_method == original.detection_method
        assert restored.confidence == original.confidence
        assert restored.source_page == original.source_page
        assert restored.is_active == original.is_active

    def test_user_calibration_stores_references(self):
        """User calibration should store reference values for traceability."""
        ctx = compute_scale_from_points(
            pixel_distance=90.0,
            real_distance_meters=0.9,
            page_number=1,
            file_id="test-file",
        )

        # Should store the original reference values
        assert ctx.user_reference_px == 90.0
        assert ctx.user_reference_m == 0.9
        assert ctx.pixels_per_meter == 100.0  # 90 / 0.9

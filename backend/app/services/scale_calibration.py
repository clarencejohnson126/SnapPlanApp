"""
Scale Calibration Service

Detects and calibrates scale factors for converting pixel measurements to real-world units.
Supports text-based scale detection and user-assisted calibration.

Part of the Aufmaß Engine - Phase B.
"""

from dataclasses import dataclass, field
from typing import Optional, Tuple, List, Dict, Any, Union
from enum import Enum
from pathlib import Path
import re
import uuid

from .plan_ingestion import (
    PlanDocument,
    PageInfo,
    extract_page_text,
    PDF_POINTS_PER_INCH,
)


class DetectionMethod(str, Enum):
    """Methods for scale detection."""

    TEXT_SCALE = "text_scale"  # Found "1:100", "M 1:50" in page text
    USER_CALIBRATION = "user_calibration"  # User-provided calibration
    DIMENSION_LINE = "dimension_line"  # Measured dimension line with known value
    SCALE_BAR = "scale_bar"  # Detected graphical scale bar
    NONE = "none"  # No scale detected


@dataclass
class ScaleContext:
    """
    Represents a detected or calibrated scale for pixel-to-meter conversion.

    The key relationship:
    - scale_factor: The architectural scale (e.g., 100 for 1:100)
    - pixels_per_meter: Depends on scale_factor, page size, and render DPI

    For a 1:100 scale drawing rendered at 150 DPI:
    - 1 meter in reality = 0.01 meters on paper = 0.01 * 39.37 inches on paper
    - At 150 DPI, that's 0.01 * 39.37 * 150 = 59.055 pixels per real meter
    """

    # Identification
    id: Optional[str] = None
    file_id: Optional[str] = None

    # Scale information
    scale_string: Optional[str] = None  # Human-readable: "1:100"
    scale_factor: Optional[float] = None  # The denominator: 100 for 1:100

    # Conversion factor (computed from scale_factor, page size, DPI)
    pixels_per_meter: Optional[float] = None

    # Detection metadata
    detection_method: str = DetectionMethod.NONE.value
    confidence: float = 0.0
    source_page: int = 1
    source_bbox: Optional[Tuple[float, float, float, float]] = None

    # Rendering context (needed to compute pixels_per_meter)
    page_width_points: Optional[float] = None
    page_height_points: Optional[float] = None
    render_dpi: int = 150

    # User calibration values (for traceability)
    user_reference_px: Optional[float] = None
    user_reference_m: Optional[float] = None

    # Active flag for database persistence
    is_active: bool = True

    # Traceability
    notes: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return {
            "id": self.id,
            "file_id": self.file_id,
            "scale_string": self.scale_string,
            "scale_factor": self.scale_factor,
            "pixels_per_meter": self.pixels_per_meter,
            "detection_method": self.detection_method,
            "confidence": self.confidence,
            "source_page": self.source_page,
            "source_bbox": list(self.source_bbox) if self.source_bbox else None,
            "page_width_points": self.page_width_points,
            "page_height_points": self.page_height_points,
            "render_dpi": self.render_dpi,
            "user_reference_px": self.user_reference_px,
            "user_reference_m": self.user_reference_m,
            "is_active": self.is_active,
            "notes": self.notes,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "ScaleContext":
        """Create ScaleContext from dictionary."""
        bbox = data.get("source_bbox")
        if bbox and isinstance(bbox, list):
            bbox = tuple(bbox)
        return cls(
            id=data.get("id"),
            file_id=data.get("file_id"),
            scale_string=data.get("scale_string"),
            scale_factor=data.get("scale_factor"),
            pixels_per_meter=data.get("pixels_per_meter"),
            detection_method=data.get("detection_method", DetectionMethod.NONE.value),
            confidence=data.get("confidence", 0.0),
            source_page=data.get("source_page", 1),
            source_bbox=bbox,
            page_width_points=data.get("page_width_points"),
            page_height_points=data.get("page_height_points"),
            render_dpi=data.get("render_dpi", 150),
            user_reference_px=data.get("user_reference_px"),
            user_reference_m=data.get("user_reference_m"),
            is_active=data.get("is_active", True),
            notes=data.get("notes", []),
        )

    def px_to_meters(self, px: float) -> float:
        """Convert pixel measurement to meters."""
        if self.pixels_per_meter is None or self.pixels_per_meter == 0:
            raise ValueError("Scale not calibrated - pixels_per_meter is not set")
        return px / self.pixels_per_meter

    def meters_to_px(self, meters: float) -> float:
        """Convert meters to pixel measurement."""
        if self.pixels_per_meter is None:
            raise ValueError("Scale not calibrated - pixels_per_meter is not set")
        return meters * self.pixels_per_meter

    @property
    def has_scale(self) -> bool:
        """Check if a valid scale is available."""
        return self.pixels_per_meter is not None and self.pixels_per_meter > 0


# Constants
METERS_PER_INCH = 0.0254
INCHES_PER_METER = 39.3701

# Common architectural scales
COMMON_SCALES: Dict[str, float] = {
    "1:1": 1.0,
    "1:2": 2.0,
    "1:5": 5.0,
    "1:10": 10.0,
    "1:20": 20.0,
    "1:25": 25.0,
    "1:50": 50.0,
    "1:100": 100.0,
    "1:200": 200.0,
    "1:250": 250.0,
    "1:500": 500.0,
    "1:1000": 1000.0,
}

# Regex patterns for scale detection
SCALE_PATTERNS = [
    # "M 1:100", "M1:100", "M. 1:100"
    r"[Mm]\.?\s*1\s*:\s*(\d+)",
    # "MASSSTAB 1:100", "Maßstab 1:100"
    r"[Mm][Aa][SsßẞSs][Ss][Tt][Aa][Bb]\s*1\s*:\s*(\d+)",
    # "SCALE 1:100"
    r"[Ss][Cc][Aa][Ll][Ee]\s*1\s*:\s*(\d+)",
    # Plain "1:100" (but be careful - this matches many things)
    r"(?<![0-9])1\s*:\s*(\d+)(?![0-9])",
]


def parse_scale_from_text(text: str) -> Optional[Tuple[str, float]]:
    """
    Parse a scale expression from text.

    Args:
        text: Text that may contain a scale expression

    Returns:
        Tuple of (scale_string, scale_factor) or None if not found.
        scale_factor is the denominator (e.g., 100 for "1:100")
    """
    for pattern in SCALE_PATTERNS:
        match = re.search(pattern, text)
        if match:
            denominator = int(match.group(1))
            # Validate it's a reasonable architectural scale
            if denominator >= 1 and denominator <= 10000:
                scale_string = f"1:{denominator}"
                return (scale_string, float(denominator))
    return None


def detect_scale_from_text(page_text: str) -> Optional[Tuple[str, float, float]]:
    """
    Try to parse typical scale expressions from page text.

    Searches for patterns like:
    - 'M 1:100'
    - 'M 1 : 50'
    - 'Maßstab 1:100'
    - '1:200'

    Args:
        page_text: Text content of a PDF page

    Returns:
        Tuple of (scale_string, scale_factor, confidence) or None if not found.
        Confidence is higher for more explicit patterns (e.g., "Maßstab 1:100")
    """
    # Try patterns in order of specificity (more specific = higher confidence)
    patterns_with_confidence = [
        (r"[Mm][Aa][SsßẞSs][Ss][Tt][Aa][Bb]\s*1\s*:\s*(\d+)", 0.95),  # MASSSTAB/Maßstab
        (r"[Ss][Cc][Aa][Ll][Ee]\s*1\s*:\s*(\d+)", 0.90),  # SCALE
        (r"[Mm]\.?\s*1\s*:\s*(\d+)", 0.85),  # M 1:100
        (r"(?<![0-9/])1\s*:\s*(\d+)(?![0-9])", 0.70),  # Plain 1:100
    ]

    for pattern, confidence in patterns_with_confidence:
        match = re.search(pattern, page_text)
        if match:
            denominator = int(match.group(1))
            # Validate it's a reasonable architectural scale
            if denominator >= 1 and denominator <= 10000:
                scale_string = f"1:{denominator}"
                return (scale_string, float(denominator), confidence)

    return None


def compute_pixels_per_meter(
    scale_factor: float,
    page_width_points: float,
    page_height_points: float,
    dpi: int,
) -> float:
    """
    Compute pixels per real-world meter given scale and rendering parameters.

    The calculation:
    1. At scale 1:N, 1 meter real = 1/N meters on paper
    2. 1/N meters on paper = (1/N) * 39.3701 inches on paper
    3. At DPI resolution, that's (1/N) * 39.3701 * DPI pixels

    Args:
        scale_factor: The scale denominator (e.g., 100 for 1:100)
        page_width_points: Page width in PDF points (72 pt/inch)
        page_height_points: Page height in PDF points
        dpi: Rendering DPI

    Returns:
        Pixels per real-world meter
    """
    if scale_factor <= 0:
        raise ValueError("scale_factor must be positive")

    # 1 meter real = (1/scale_factor) meters on paper
    # = (1/scale_factor) * INCHES_PER_METER inches on paper
    # = (1/scale_factor) * INCHES_PER_METER * dpi pixels
    pixels_per_meter = (1.0 / scale_factor) * INCHES_PER_METER * dpi

    return pixels_per_meter


def infer_scale_string(pixels_per_meter: float, dpi: int) -> Optional[str]:
    """
    Try to infer a standard scale string from pixels_per_meter.

    Args:
        pixels_per_meter: The computed pixels per meter ratio
        dpi: The rendering DPI

    Returns:
        A standard scale string like "1:100" if close match, else None
    """
    for scale_string, scale_factor in COMMON_SCALES.items():
        expected_ppm = compute_pixels_per_meter(scale_factor, 0, 0, dpi)
        # Allow 5% tolerance
        if abs(pixels_per_meter - expected_ppm) / expected_ppm < 0.05:
            return scale_string
    return None


def detect_scale_from_page(
    file_path: Union[str, Path],
    page_number: int,
    page_info: PageInfo,
    file_id: Optional[str] = None,
) -> ScaleContext:
    """
    Detect scale from a single PDF page using text extraction.

    Args:
        file_path: Path to the PDF file
        page_number: Page number to analyze (1-indexed)
        page_info: PageInfo for the page (contains dimensions, DPI)
        file_id: Optional file ID for tracking

    Returns:
        ScaleContext with detected scale or no-scale result
    """
    ctx_id = str(uuid.uuid4())

    # Extract text from page
    try:
        page_text = extract_page_text(file_path, page_number)
    except Exception as e:
        return ScaleContext(
            id=ctx_id,
            file_id=file_id,
            detection_method=DetectionMethod.NONE.value,
            confidence=0.0,
            source_page=page_number,
            page_width_points=page_info.width_points,
            page_height_points=page_info.height_points,
            render_dpi=page_info.dpi,
            notes=[f"Failed to extract text: {e}"],
        )

    # Try to detect scale from text
    result = detect_scale_from_text(page_text)

    if result is None:
        return ScaleContext(
            id=ctx_id,
            file_id=file_id,
            detection_method=DetectionMethod.NONE.value,
            confidence=0.0,
            source_page=page_number,
            page_width_points=page_info.width_points,
            page_height_points=page_info.height_points,
            render_dpi=page_info.dpi,
            notes=["No scale expression found in page text"],
        )

    scale_string, scale_factor, confidence = result

    # Compute pixels_per_meter
    pixels_per_meter = compute_pixels_per_meter(
        scale_factor,
        page_info.width_points,
        page_info.height_points,
        page_info.dpi,
    )

    return ScaleContext(
        id=ctx_id,
        file_id=file_id,
        scale_string=scale_string,
        scale_factor=scale_factor,
        pixels_per_meter=pixels_per_meter,
        detection_method=DetectionMethod.TEXT_SCALE.value,
        confidence=confidence,
        source_page=page_number,
        page_width_points=page_info.width_points,
        page_height_points=page_info.height_points,
        render_dpi=page_info.dpi,
        notes=[f"Detected from text: {scale_string}"],
    )


def detect_scale_from_document(
    document: PlanDocument,
    search_pages: Optional[List[int]] = None,
) -> ScaleContext:
    """
    Detect scale from a document, searching specified pages.

    Searches pages in order and returns the first high-confidence result,
    or the best result if no high-confidence match is found.

    Args:
        document: PlanDocument with page information
        search_pages: Specific pages to search (default: all pages)

    Returns:
        ScaleContext with detected scale or no-scale result
    """
    if search_pages is None:
        search_pages = list(range(1, document.total_pages + 1))

    best_result: Optional[ScaleContext] = None
    best_confidence = 0.0

    for page_num in search_pages:
        page_info = document.get_page(page_num)
        if page_info is None:
            continue

        result = detect_scale_from_page(
            document.file_path,
            page_num,
            page_info,
            document.file_id,
        )

        # Return immediately if high confidence
        if result.confidence >= 0.9:
            return result

        # Track best result
        if result.confidence > best_confidence:
            best_result = result
            best_confidence = result.confidence

    # Return best result or a no-scale result
    if best_result is not None:
        return best_result

    return ScaleContext(
        id=str(uuid.uuid4()),
        file_id=document.file_id,
        detection_method=DetectionMethod.NONE.value,
        confidence=0.0,
        source_page=1,
        notes=["No scale detected in any searched page"],
    )


def compute_scale_from_points(
    pixel_distance: float,
    real_distance_meters: float,
    page_number: int = 1,
    page_info: Optional[PageInfo] = None,
    file_id: Optional[str] = None,
) -> ScaleContext:
    """
    User-assisted scale calibration from a known reference dimension.

    Given a measured pixel distance (between two points on the rendered page)
    and a known real-world distance in meters, compute a ScaleContext.

    Args:
        pixel_distance: Distance in pixels between two reference points
        real_distance_meters: Known real-world distance in meters
        page_number: Page number where reference is located
        page_info: Optional PageInfo for the page
        file_id: Optional file ID for tracking

    Returns:
        ScaleContext calibrated from user input

    Raises:
        ValueError: If pixel_distance or real_distance_meters is invalid
    """
    if pixel_distance <= 0:
        raise ValueError("pixel_distance must be positive")
    if real_distance_meters <= 0:
        raise ValueError("real_distance_meters must be positive")

    # Compute pixels per meter directly from the reference
    pixels_per_meter = pixel_distance / real_distance_meters

    # Try to infer standard scale string
    dpi = page_info.dpi if page_info else 150
    scale_string = infer_scale_string(pixels_per_meter, dpi)

    # Compute scale_factor if we have a scale_string
    scale_factor = None
    if scale_string:
        scale_factor = COMMON_SCALES.get(scale_string)

    return ScaleContext(
        id=str(uuid.uuid4()),
        file_id=file_id,
        scale_string=scale_string,
        scale_factor=scale_factor,
        pixels_per_meter=pixels_per_meter,
        detection_method=DetectionMethod.USER_CALIBRATION.value,
        confidence=1.0,  # User input is definitive
        source_page=page_number,
        page_width_points=page_info.width_points if page_info else None,
        page_height_points=page_info.height_points if page_info else None,
        render_dpi=dpi,
        user_reference_px=pixel_distance,
        user_reference_m=real_distance_meters,
        notes=[
            f"User calibration: {pixel_distance:.2f}px = {real_distance_meters:.4f}m",
            f"Computed: {pixels_per_meter:.2f} pixels/meter",
        ],
    )


def validate_scale(
    scale: ScaleContext,
    test_dimension_px: float,
    expected_dimension_m: float,
    tolerance: float = 0.05,
) -> bool:
    """
    Validate a scale calibration against a known dimension.

    Args:
        scale: ScaleContext to validate
        test_dimension_px: Pixel length of test reference
        expected_dimension_m: Expected length in meters
        tolerance: Acceptable relative error (default 5%)

    Returns:
        True if scale is accurate within tolerance
    """
    if not scale.has_scale:
        return False

    computed_m = scale.px_to_meters(test_dimension_px)
    relative_error = abs(computed_m - expected_dimension_m) / expected_dimension_m

    return relative_error <= tolerance


# Async wrappers for API compatibility
async def detect_scale(
    document: PlanDocument,
    search_pages: Optional[List[int]] = None,
) -> ScaleContext:
    """
    Async wrapper for detect_scale_from_document.

    Attempts automatic scale detection from document annotations.
    """
    return detect_scale_from_document(document, search_pages)


async def calibrate_from_reference(
    document: PlanDocument,
    known_dimension_px: float,
    known_dimension_m: float,
    page_number: int = 1,
    bbox: Optional[Tuple[float, float, float, float]] = None,
) -> ScaleContext:
    """
    Async wrapper for user-assisted scale calibration.

    Args:
        document: PlanDocument being calibrated
        known_dimension_px: Length in pixels of the reference
        known_dimension_m: Actual length in meters of the reference
        page_number: Page where reference is located
        bbox: Optional bounding box of the reference element

    Returns:
        ScaleContext calibrated from user input
    """
    page_info = document.get_page(page_number)

    result = compute_scale_from_points(
        pixel_distance=known_dimension_px,
        real_distance_meters=known_dimension_m,
        page_number=page_number,
        page_info=page_info,
        file_id=document.file_id,
    )

    if bbox:
        result.source_bbox = bbox

    return result

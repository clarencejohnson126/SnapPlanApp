"""
Wall Opening Door Detector

Production-grade door detection using wall opening analysis.
This is a paradigm shift from "arc + line matching" to "detect gaps in walls".

Key insight: A door is fundamentally a WALL OPENING, not an arc+line pattern.
The arc symbol is optional - many CAD exports don't preserve it as a smooth arc.

Detection Pipeline:
1. Render PDF page at high DPI (400-600)
2. Extract wall mask using morphological operations
3. Detect openings (gaps) in walls as door candidates
4. Apply hatch suppression to filter false positives
5. Context validation (wall adjacency, plausible width)
6. Optional: YOLO hints to boost confidence

Reference: ChatGPT guidance on production floor plan parsing
"""

import logging
import math
import tempfile
import os
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import List, Optional, Dict, Any, Tuple, Set
import uuid

logger = logging.getLogger(__name__)


class DetectionMode(Enum):
    """
    Detection sensitivity modes for different blueprint types.

    - STRICT: High precision, fewer false positives. Best for clean CAD drawings.
    - BALANCED: Good balance for most blueprints. Recommended default.
    - SENSITIVE: High recall, may have more false positives. For complex drawings.
    """
    STRICT = "strict"      # DPI 150, conf 0.3 - clean floor plans
    BALANCED = "balanced"  # DPI 100, conf 0.1 - works for most cases
    SENSITIVE = "sensitive"  # DPI 100, conf 0.08 - catches more, more FPs


# Mode configurations
DETECTION_MODE_CONFIGS = {
    DetectionMode.STRICT: {"dpi": 150, "confidence": 0.3},
    DetectionMode.BALANCED: {"dpi": 100, "confidence": 0.1},
    DetectionMode.SENSITIVE: {"dpi": 100, "confidence": 0.08},
}

# Optional imports
try:
    import cv2
    import numpy as np
    CV2_AVAILABLE = True
except ImportError:
    CV2_AVAILABLE = False
    logger.warning("OpenCV not available - wall opening detection disabled")

try:
    import fitz
    FITZ_AVAILABLE = True
except ImportError:
    FITZ_AVAILABLE = False
    logger.warning("PyMuPDF not available - PDF rendering disabled")


@dataclass
class WallOpening:
    """
    Represents a detected wall opening (potential door location).
    """
    opening_id: str
    page_number: int
    # Position in pixels (at render DPI)
    center_x: float
    center_y: float
    width_px: float
    # Orientation
    angle_degrees: float  # 0=horizontal, 90=vertical
    # Wall context
    wall_thickness_px: float
    # Measurements (if scale known)
    width_m: Optional[float] = None
    # Validation
    confidence: float = 0.5
    is_door: bool = False
    detection_signals: List[str] = field(default_factory=list)
    # Metadata
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "opening_id": self.opening_id,
            "page_number": self.page_number,
            "center_x": self.center_x,
            "center_y": self.center_y,
            "width_px": self.width_px,
            "angle_degrees": self.angle_degrees,
            "wall_thickness_px": self.wall_thickness_px,
            "width_m": self.width_m,
            "confidence": self.confidence,
            "is_door": self.is_door,
            "detection_signals": self.detection_signals,
            "metadata": self.metadata,
        }


@dataclass
class DoorDetectionResult:
    """Result from wall-opening-based door detection."""
    page_number: int
    doors: List[WallOpening] = field(default_factory=list)
    total_openings_analyzed: int = 0
    wall_mask_generated: bool = False
    hatch_regions_filtered: int = 0
    processing_time_ms: int = 0
    warnings: List[str] = field(default_factory=list)
    debug_images: Dict[str, str] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "page_number": self.page_number,
            "door_count": len(self.doors),
            "doors": [d.to_dict() for d in self.doors],
            "total_openings_analyzed": self.total_openings_analyzed,
            "wall_mask_generated": self.wall_mask_generated,
            "hatch_regions_filtered": self.hatch_regions_filtered,
            "processing_time_ms": self.processing_time_ms,
            "warnings": self.warnings,
            "by_width": self._group_by_width(),
        }

    def _group_by_width(self) -> Dict[str, int]:
        """Group doors by width category."""
        groups: Dict[str, int] = {}
        for door in self.doors:
            if door.width_m:
                # Round to nearest 0.1m
                width_key = f"{round(door.width_m, 1):.1f}"
                groups[width_key] = groups.get(width_key, 0) + 1
        return groups


def generate_opening_id() -> str:
    """Generate a unique opening ID."""
    return f"opening_{uuid.uuid4().hex[:8]}"


def render_pdf_page_high_dpi(
    pdf_path: str,
    page_number: int = 1,
    dpi: int = 400,
    output_path: Optional[str] = None,
) -> str:
    """
    Render a PDF page at high DPI for wall detection.

    High DPI (400-600) is critical for:
    - Accurate wall stroke detection
    - Proper morphological operations
    - Fine-grained opening detection

    Args:
        pdf_path: Path to PDF file
        page_number: 1-indexed page number
        dpi: Render resolution (400-600 recommended)
        output_path: Optional output path

    Returns:
        Path to rendered PNG image
    """
    if not FITZ_AVAILABLE:
        raise ImportError("PyMuPDF required for PDF rendering")

    doc = fitz.open(pdf_path)
    try:
        page_idx = page_number - 1
        if page_idx < 0 or page_idx >= len(doc):
            raise ValueError(f"Invalid page {page_number}")

        page = doc[page_idx]
        zoom = dpi / 72.0
        mat = fitz.Matrix(zoom, zoom)
        pix = page.get_pixmap(matrix=mat)

        if output_path is None:
            fd, output_path = tempfile.mkstemp(suffix=".png")
            os.close(fd)

        pix.save(output_path)
        logger.info(f"Rendered page {page_number} at {dpi} DPI: {pix.width}x{pix.height}")

        return output_path
    finally:
        doc.close()


def extract_wall_mask(
    image_path: str,
    wall_thickness_range: Tuple[int, int] = (8, 40),
    min_wall_length: int = 100,
    debug_output_dir: Optional[str] = None,
) -> Tuple[Any, Dict[str, Any]]:
    """
    Extract wall mask from rendered floor plan image.

    REFINED STRATEGY (v2):
    1. Detect thick strokes only (walls are thicker than detail lines)
    2. Use distance transform to find stroke thickness
    3. Keep only strokes within wall thickness range
    4. Filter by length (walls are long, symbols are short)

    Args:
        image_path: Path to rendered floor plan image
        wall_thickness_range: Expected wall thickness in pixels (min, max)
        min_wall_length: Minimum wall segment length in pixels
        debug_output_dir: Optional directory for debug images

    Returns:
        Tuple of (wall_mask, debug_info)
        wall_mask: Binary image where 255=wall, 0=not wall
    """
    if not CV2_AVAILABLE:
        raise ImportError("OpenCV required for wall detection")

    img = cv2.imread(image_path)
    if img is None:
        raise ValueError(f"Failed to load image: {image_path}")

    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    h, w = gray.shape

    # Step 1: Binary threshold (walls are dark lines on light background)
    _, binary = cv2.threshold(gray, 200, 255, cv2.THRESH_BINARY_INV)

    # Step 2: Use distance transform to find stroke thickness
    dist_transform = cv2.distanceTransform(binary, cv2.DIST_L2, 5)

    # Step 3: Filter by stroke thickness
    # Walls have consistent thickness in the expected range
    min_thick, max_thick = wall_thickness_range
    half_min = min_thick / 2
    half_max = max_thick / 2

    # Skeleton to find stroke centerlines
    # The distance at skeleton points = half of stroke thickness
    thick_strokes = np.zeros_like(binary)
    thick_strokes[(dist_transform >= half_min) & (dist_transform <= half_max)] = 255

    # Step 4: Reconstruct walls from thick stroke centerlines
    # Dilate by the detected thickness
    kernel_size = int(max_thick)
    kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (kernel_size, kernel_size))
    wall_candidate = cv2.dilate(thick_strokes, kernel, iterations=1)

    # Intersect with original binary to clean up
    wall_candidate = cv2.bitwise_and(wall_candidate, binary)

    # Step 5: Connected component filtering by size AND aspect ratio
    num_labels, labels, stats, centroids = cv2.connectedComponentsWithStats(
        wall_candidate, connectivity=8
    )

    wall_mask = np.zeros_like(binary)
    min_wall_area = min_wall_length * min_thick  # Minimum area for a wall segment

    for i in range(1, num_labels):
        area = stats[i, cv2.CC_STAT_AREA]
        width = stats[i, cv2.CC_STAT_WIDTH]
        height = stats[i, cv2.CC_STAT_HEIGHT]

        # Walls are elongated - filter by aspect ratio
        aspect = max(width, height) / max(1, min(width, height))

        # Keep if: large enough AND elongated (not square furniture)
        if area >= min_wall_area and (aspect >= 3.0 or area > 5000):
            wall_mask[labels == i] = 255

    # Step 6: Morphological cleanup
    # Close small gaps in walls (from text/symbols overlapping)
    close_kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (5, 5))
    wall_mask = cv2.morphologyEx(wall_mask, cv2.MORPH_CLOSE, close_kernel)

    debug_info = {
        "original_shape": gray.shape,
        "num_components": num_labels - 1,
        "wall_pixels": int(np.sum(wall_mask > 0)),
        "coverage_pct": float(np.sum(wall_mask > 0) / (h * w) * 100),
    }

    # Save debug images if requested
    if debug_output_dir:
        os.makedirs(debug_output_dir, exist_ok=True)
        cv2.imwrite(os.path.join(debug_output_dir, "1_gray.png"), gray)
        cv2.imwrite(os.path.join(debug_output_dir, "2_binary.png"), binary)
        cv2.imwrite(os.path.join(debug_output_dir, "3_dist_transform.png"),
                    (dist_transform * 10).astype(np.uint8))
        cv2.imwrite(os.path.join(debug_output_dir, "4_thick_strokes.png"), thick_strokes)
        cv2.imwrite(os.path.join(debug_output_dir, "5_wall_mask.png"), wall_mask)
        debug_info["debug_dir"] = debug_output_dir

    return wall_mask, debug_info


def detect_hatch_regions(
    image_path: str,
    angle_tolerance: float = 5.0,
    min_hatch_lines: int = 5,
) -> List[Tuple[int, int, int, int]]:
    """
    Detect hatched regions (diagonal line patterns).

    Hatching creates false positives because:
    - Diagonal lines look like door panels
    - Regular spacing mimics door widths

    We detect hatching by finding regions with:
    - Many parallel lines at consistent angles (typically 45°)
    - Regular spacing between lines

    Args:
        image_path: Path to rendered image
        angle_tolerance: Tolerance for parallel line detection
        min_hatch_lines: Minimum lines to classify as hatching

    Returns:
        List of bounding boxes (x, y, w, h) for hatch regions
    """
    if not CV2_AVAILABLE:
        return []

    img = cv2.imread(image_path, cv2.IMREAD_GRAYSCALE)
    if img is None:
        return []

    # Edge detection for line finding
    edges = cv2.Canny(img, 50, 150, apertureSize=3)

    # Hough line detection
    lines = cv2.HoughLinesP(
        edges,
        rho=1,
        theta=np.pi/180,
        threshold=30,
        minLineLength=20,
        maxLineGap=5
    )

    if lines is None or len(lines) < min_hatch_lines:
        return []

    # Group lines by angle
    angle_groups: Dict[int, List[Tuple[int, int, int, int]]] = {}

    for line in lines:
        x1, y1, x2, y2 = line[0]
        angle = math.degrees(math.atan2(y2 - y1, x2 - x1))
        # Normalize to 0-180
        if angle < 0:
            angle += 180

        # Bucket by angle
        bucket = int(angle / angle_tolerance) * int(angle_tolerance)
        if bucket not in angle_groups:
            angle_groups[bucket] = []
        angle_groups[bucket].append((x1, y1, x2, y2))

    # Find groups that look like hatching (45° or 135°)
    hatch_regions = []
    hatch_angles = [45, 135]

    for target_angle in hatch_angles:
        for bucket, group_lines in angle_groups.items():
            if abs(bucket - target_angle) < angle_tolerance * 2:
                if len(group_lines) >= min_hatch_lines:
                    # Compute bounding box of this hatch group
                    all_x = []
                    all_y = []
                    for x1, y1, x2, y2 in group_lines:
                        all_x.extend([x1, x2])
                        all_y.extend([y1, y2])

                    x_min, x_max = min(all_x), max(all_x)
                    y_min, y_max = min(all_y), max(all_y)

                    # Expand slightly
                    margin = 20
                    x_min = max(0, x_min - margin)
                    y_min = max(0, y_min - margin)
                    x_max = min(img.shape[1], x_max + margin)
                    y_max = min(img.shape[0], y_max + margin)

                    hatch_regions.append((x_min, y_min, x_max - x_min, y_max - y_min))

    logger.info(f"Detected {len(hatch_regions)} hatch regions")
    return hatch_regions


def find_wall_openings(
    wall_mask: Any,
    min_opening_px: int = 20,
    max_opening_px: int = 300,
    min_wall_context_px: int = 30,
    page_number: int = 1,
) -> List[WallOpening]:
    """
    Find openings (gaps) in the wall mask using contour analysis.

    REFINED STRATEGY (v2):
    1. Find wall contours
    2. Analyze contour for indentations (openings)
    3. Validate opening has wall on both sides
    4. Filter by opening size

    Args:
        wall_mask: Binary wall mask (255=wall)
        min_opening_px: Minimum opening width in pixels
        max_opening_px: Maximum opening width in pixels
        min_wall_context_px: Minimum wall length on each side of opening
        page_number: Page number for ID generation

    Returns:
        List of WallOpening objects
    """
    if not CV2_AVAILABLE:
        return []

    openings: List[WallOpening] = []
    h, w = wall_mask.shape

    # Use morphological skeleton to find wall centerlines
    # This gives cleaner detection than raw mask scanning
    try:
        skeleton = cv2.ximgproc.thinning(wall_mask)
    except AttributeError:
        # Fallback: simple erosion-based skeleton
        skeleton = wall_mask.copy()
        erode_kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (3, 3))
        for _ in range(5):
            eroded = cv2.erode(skeleton, erode_kernel)
            skeleton = cv2.subtract(skeleton, eroded)

    # Find line segments in skeleton using Hough transform
    lines = cv2.HoughLinesP(
        skeleton,
        rho=1,
        theta=np.pi/180,
        threshold=50,
        minLineLength=min_wall_context_px * 2,
        maxLineGap=max_opening_px + 20  # Allow gaps up to door size
    )

    if lines is None:
        logger.info("No wall lines detected")
        return []

    # Group lines by orientation (horizontal vs vertical)
    horizontal_lines = []  # Angle near 0° or 180°
    vertical_lines = []    # Angle near 90°

    for line in lines:
        x1, y1, x2, y2 = line[0]
        angle = abs(math.degrees(math.atan2(y2 - y1, x2 - x1)))

        if angle < 15 or angle > 165:
            horizontal_lines.append((x1, y1, x2, y2))
        elif 75 < angle < 105:
            vertical_lines.append((x1, y1, x2, y2))

    # Find collinear gaps in horizontal lines (vertical openings / doors in H walls)
    openings.extend(_find_collinear_gaps(
        horizontal_lines, "horizontal",
        min_opening_px, max_opening_px, min_wall_context_px,
        page_number, h, w
    ))

    # Find collinear gaps in vertical lines (horizontal openings / doors in V walls)
    openings.extend(_find_collinear_gaps(
        vertical_lines, "vertical",
        min_opening_px, max_opening_px, min_wall_context_px,
        page_number, h, w
    ))

    logger.info(f"Found {len(openings)} wall openings from line analysis")
    return openings


def _find_collinear_gaps(
    lines: List[Tuple[int, int, int, int]],
    orientation: str,
    min_gap: int,
    max_gap: int,
    min_context: int,
    page_number: int,
    img_h: int,
    img_w: int,
) -> List[WallOpening]:
    """
    Find gaps between collinear line segments.

    A door opening appears as a gap between two wall segments
    that would otherwise be a single continuous wall.
    """
    openings = []

    if len(lines) < 2:
        return openings

    # Sort lines by position
    if orientation == "horizontal":
        # Group by Y position (row), sort by X
        # Lines on same row are candidates for gaps
        tolerance = 20  # Y tolerance for "same row"
        position_key = lambda l: (l[1] + l[3]) / 2  # Average Y
        extent_key = lambda l: (min(l[0], l[2]), max(l[0], l[2]))  # X range
    else:
        # Group by X position (column), sort by Y
        tolerance = 20
        position_key = lambda l: (l[0] + l[2]) / 2  # Average X
        extent_key = lambda l: (min(l[1], l[3]), max(l[1], l[3]))  # Y range

    # Group lines by position
    lines_sorted = sorted(lines, key=position_key)

    # Find groups of lines at similar positions
    groups: List[List[Tuple[int, int, int, int]]] = []
    current_group = [lines_sorted[0]]
    current_pos = position_key(lines_sorted[0])

    for line in lines_sorted[1:]:
        pos = position_key(line)
        if abs(pos - current_pos) <= tolerance:
            current_group.append(line)
        else:
            if len(current_group) >= 2:
                groups.append(current_group)
            current_group = [line]
            current_pos = pos

    if len(current_group) >= 2:
        groups.append(current_group)

    # For each group, find gaps between segments
    for group in groups:
        # Sort by extent (start position)
        segments = sorted([extent_key(l) for l in group], key=lambda s: s[0])

        for i in range(len(segments) - 1):
            end_of_first = segments[i][1]
            start_of_second = segments[i + 1][0]
            gap = start_of_second - end_of_first

            if min_gap <= gap <= max_gap:
                # Check segment lengths meet minimum context
                len_first = segments[i][1] - segments[i][0]
                len_second = segments[i + 1][1] - segments[i + 1][0]

                if len_first >= min_context and len_second >= min_context:
                    # Valid opening found
                    gap_center = end_of_first + gap / 2
                    line_pos = position_key(group[0])

                    if orientation == "horizontal":
                        center_x = gap_center
                        center_y = line_pos
                        angle = 0
                    else:
                        center_x = line_pos
                        center_y = gap_center
                        angle = 90

                    opening = WallOpening(
                        opening_id=generate_opening_id(),
                        page_number=page_number,
                        center_x=center_x,
                        center_y=center_y,
                        width_px=float(gap),
                        angle_degrees=angle,
                        wall_thickness_px=10.0,  # Estimate
                        detection_signals=[
                            f"{orientation}_wall",
                            "collinear_gap",
                            f"context_L{len_first}_R{len_second}"
                        ],
                    )
                    openings.append(opening)

    return openings


def filter_openings_in_hatch(
    openings: List[WallOpening],
    hatch_regions: List[Tuple[int, int, int, int]],
) -> List[WallOpening]:
    """
    Remove openings that fall within hatched regions.

    Hatching (diagonal fill patterns) creates many false positive
    door detections. This filter removes them.
    """
    if not hatch_regions:
        return openings

    filtered = []
    for opening in openings:
        in_hatch = False
        for (hx, hy, hw, hh) in hatch_regions:
            if (hx <= opening.center_x <= hx + hw and
                hy <= opening.center_y <= hy + hh):
                in_hatch = True
                break

        if not in_hatch:
            filtered.append(opening)

    removed = len(openings) - len(filtered)
    if removed > 0:
        logger.info(f"Filtered {removed} openings in hatch regions")

    return filtered


def validate_door_openings(
    openings: List[WallOpening],
    pixels_per_meter: float,
    min_door_width_m: float = 0.60,
    max_door_width_m: float = 2.20,
    standard_widths: List[float] = None,
) -> List[WallOpening]:
    """
    Validate openings as potential doors based on width.

    Standard door widths (DIN 18101):
    - 0.625m (62.5cm) - narrow WC doors
    - 0.755m (75.5cm) - standard interior
    - 0.885m (88.5cm) - wider interior
    - 1.01m (101cm) - double doors
    - 1.26m, 1.51m - wide double doors

    Args:
        openings: List of wall openings to validate
        pixels_per_meter: Scale factor
        min_door_width_m: Minimum valid door width
        max_door_width_m: Maximum valid door width
        standard_widths: List of standard door widths for snapping
    """
    if standard_widths is None:
        # DIN 18101 standard widths
        standard_widths = [0.625, 0.755, 0.885, 1.01, 1.135, 1.26, 1.385, 1.51, 1.76, 2.01]

    validated = []

    for opening in openings:
        # Calculate width in meters
        width_m = opening.width_px / pixels_per_meter
        opening.width_m = width_m

        # Check if within valid range
        if min_door_width_m <= width_m <= max_door_width_m:
            opening.is_door = True

            # Calculate confidence based on proximity to standard widths
            min_deviation = min(abs(width_m - std) for std in standard_widths)

            if min_deviation < 0.05:  # Within 5cm of standard
                opening.confidence = 0.9
                opening.detection_signals.append("standard_width")
            elif min_deviation < 0.10:  # Within 10cm
                opening.confidence = 0.75
                opening.detection_signals.append("near_standard_width")
            else:
                opening.confidence = 0.6
                opening.detection_signals.append("non_standard_width")

            # Categorize door type
            if width_m < 0.70:
                opening.metadata["door_type"] = "narrow"
            elif width_m < 0.95:
                opening.metadata["door_type"] = "standard"
            elif width_m < 1.30:
                opening.metadata["door_type"] = "wide"
            else:
                opening.metadata["door_type"] = "double"

            validated.append(opening)

    logger.info(f"Validated {len(validated)} door openings from {len(openings)} candidates")
    return validated


def deduplicate_openings(
    openings: List[WallOpening],
    distance_threshold_px: float = 50,
) -> List[WallOpening]:
    """
    Remove duplicate detections of the same opening.

    Due to scanning from multiple directions, we may detect
    the same opening multiple times. Keep the one with highest confidence.
    """
    if len(openings) <= 1:
        return openings

    # Sort by confidence (descending)
    sorted_openings = sorted(openings, key=lambda x: x.confidence, reverse=True)

    kept: List[WallOpening] = []
    used: Set[str] = set()

    for opening in sorted_openings:
        if opening.opening_id in used:
            continue

        # Check distance to already-kept openings
        is_duplicate = False
        for kept_opening in kept:
            dist = math.sqrt(
                (opening.center_x - kept_opening.center_x) ** 2 +
                (opening.center_y - kept_opening.center_y) ** 2
            )
            if dist < distance_threshold_px:
                is_duplicate = True
                break

        if not is_duplicate:
            kept.append(opening)
            used.add(opening.opening_id)

    removed = len(openings) - len(kept)
    if removed > 0:
        logger.info(f"Deduplicated {removed} openings")

    return kept


def detect_doors_from_wall_openings(
    pdf_path: str,
    page_number: int = 1,
    scale: int = 100,
    dpi: int = 400,
    min_door_width_m: float = 0.60,
    max_door_width_m: float = 2.20,
    debug_output_dir: Optional[str] = None,
) -> DoorDetectionResult:
    """
    Main entry point: Detect doors using wall opening analysis.

    This is the new paradigm for door detection:
    1. Render PDF at high DPI
    2. Extract wall mask
    3. Find openings in walls
    4. Filter hatch regions
    5. Validate as doors
    6. Deduplicate

    Args:
        pdf_path: Path to PDF file
        page_number: Page number (1-indexed)
        scale: Drawing scale denominator (100 for 1:100)
        dpi: Render DPI (400-600 recommended)
        min_door_width_m: Minimum door width
        max_door_width_m: Maximum door width
        debug_output_dir: Optional directory for debug images

    Returns:
        DoorDetectionResult with validated doors
    """
    import time
    start_time = time.time()

    warnings: List[str] = []
    debug_images: Dict[str, str] = {}

    if not CV2_AVAILABLE:
        return DoorDetectionResult(
            page_number=page_number,
            warnings=["OpenCV not available"],
        )

    if not FITZ_AVAILABLE:
        return DoorDetectionResult(
            page_number=page_number,
            warnings=["PyMuPDF not available"],
        )

    # Calculate pixels per meter
    # At 1:100 scale, 1m real = 1cm on paper = 0.01m on paper
    # At dpi resolution: 0.01m * (dpi/0.0254) pixels = 0.01/0.0254 * dpi
    METERS_PER_INCH = 0.0254
    paper_meters_per_real_meter = 1.0 / scale
    inches_per_paper_meter = 1.0 / METERS_PER_INCH
    pixels_per_meter = paper_meters_per_real_meter * inches_per_paper_meter * dpi

    logger.info(f"Scale 1:{scale} at {dpi} DPI → {pixels_per_meter:.2f} px/m")

    # Step 1: Render PDF page
    try:
        image_path = render_pdf_page_high_dpi(pdf_path, page_number, dpi)
        if debug_output_dir:
            debug_images["rendered"] = image_path
    except Exception as e:
        return DoorDetectionResult(
            page_number=page_number,
            warnings=[f"Failed to render PDF: {e}"],
        )

    try:
        # Step 2: Extract wall mask
        wall_mask, mask_info = extract_wall_mask(
            image_path,
            debug_output_dir=debug_output_dir,
        )

        if wall_mask is None or np.sum(wall_mask) == 0:
            warnings.append("No walls detected in image")
            return DoorDetectionResult(
                page_number=page_number,
                wall_mask_generated=False,
                warnings=warnings,
            )

        # Calculate opening size range
        min_opening_px = int(min_door_width_m * pixels_per_meter)
        max_opening_px = int(max_door_width_m * pixels_per_meter)

        # Step 3: Find wall openings
        openings = find_wall_openings(
            wall_mask,
            min_opening_px=min_opening_px,
            max_opening_px=max_opening_px,
            page_number=page_number,
        )

        total_openings = len(openings)

        # Step 4: Detect and filter hatch regions
        hatch_regions = detect_hatch_regions(image_path)
        hatch_filtered = len(hatch_regions)

        if hatch_regions:
            openings = filter_openings_in_hatch(openings, hatch_regions)

        # Step 5: Validate as doors
        doors = validate_door_openings(
            openings,
            pixels_per_meter=pixels_per_meter,
            min_door_width_m=min_door_width_m,
            max_door_width_m=max_door_width_m,
        )

        # Step 6: Deduplicate
        doors = deduplicate_openings(doors)

        processing_time_ms = int((time.time() - start_time) * 1000)

        return DoorDetectionResult(
            page_number=page_number,
            doors=doors,
            total_openings_analyzed=total_openings,
            wall_mask_generated=True,
            hatch_regions_filtered=hatch_filtered,
            processing_time_ms=processing_time_ms,
            warnings=warnings,
            debug_images=debug_images,
        )

    finally:
        # Clean up temp image unless debugging
        if not debug_output_dir and os.path.exists(image_path):
            try:
                os.remove(image_path)
            except Exception:
                pass


def detect_doors_yolo_primary(
    pdf_path: str,
    page_number: int = 1,
    scale: int = 100,
    dpi: Optional[int] = None,
    confidence_threshold: Optional[float] = None,
    use_wall_opening_validation: bool = False,
    mode: Optional[DetectionMode] = None,
) -> DoorDetectionResult:
    """
    Production door detection using YOLO as primary detector.

    This is the recommended approach for production use:
    1. YOLO runs first (fast, accurate for floor plans)
    2. Wall opening detection validates/supplements YOLO (if enabled)
    3. Results are merged and deduplicated

    Args:
        pdf_path: Path to PDF file
        page_number: Page number (1-indexed)
        scale: Drawing scale (100 for 1:100)
        dpi: Render DPI for YOLO (auto-selected based on mode if not provided)
        confidence_threshold: YOLO confidence threshold (auto-selected if not provided)
        use_wall_opening_validation: Whether to run wall opening as validation
        mode: Detection mode (STRICT, BALANCED, SENSITIVE). Defaults to BALANCED.

    Returns:
        DoorDetectionResult with detected doors
    """
    import time
    from .cv_pipeline import (
        is_yolo_available,
        render_pdf_page_to_image,
        run_object_detection_on_page,
        ObjectType,
    )
    from ..core.config import get_settings

    start_time = time.time()
    warnings: List[str] = []
    all_doors: List[WallOpening] = []

    settings = get_settings()

    # Apply detection mode if parameters not explicitly provided
    if mode is None:
        mode = DetectionMode.BALANCED

    mode_config = DETECTION_MODE_CONFIGS[mode]
    if dpi is None:
        dpi = mode_config["dpi"]
    if confidence_threshold is None:
        confidence_threshold = mode_config["confidence"]

    logger.info(f"Door detection: mode={mode.value}, dpi={dpi}, conf={confidence_threshold}")

    # Calculate pixels per meter for the given DPI
    METERS_PER_INCH = 0.0254
    paper_meters_per_real_meter = 1.0 / scale
    inches_per_paper_meter = 1.0 / METERS_PER_INCH
    pixels_per_meter = paper_meters_per_real_meter * inches_per_paper_meter * dpi

    # Step 1: Run YOLO detection (primary)
    yolo_doors: List[WallOpening] = []
    if is_yolo_available(settings):
        try:
            image_path = render_pdf_page_to_image(pdf_path, page_number, dpi)

            try:
                result = run_object_detection_on_page(
                    image_path=image_path,
                    document_id=Path(pdf_path).stem,
                    page_number=page_number,
                    object_types=[ObjectType.DOOR],
                    confidence_threshold=confidence_threshold,
                    settings=settings,
                )

                # Convert YOLO detections to WallOpening format
                for obj in result.objects:
                    # YOLO bbox captures the entire door symbol area, not just the door panel
                    # Empirical observation: bbox is about 3-4x the actual door width
                    # - bbox includes: swing arc, door panel, annotations, padding
                    # - actual door width ≈ bbox_min * 0.27
                    bbox_min = min(obj.bbox.width, obj.bbox.height)

                    # Estimate door width from YOLO bbox
                    # Calibrated: 260px bbox → 0.885m door → multiplier = 0.27
                    width_px = bbox_min * 0.27
                    width_m = width_px / pixels_per_meter

                    # Snap to nearest standard door width (DIN 18101)
                    # Standard single leaf doors: 625, 755, 885, 1010mm
                    # Standard double doors: 1260, 1510, 1760, 2010mm
                    standard_widths = [0.625, 0.755, 0.885, 1.01, 1.26, 1.51, 1.76, 2.01]
                    closest_std = min(standard_widths, key=lambda s: abs(s - width_m))

                    # Snap if within reasonable tolerance (10cm for single, 15cm for double)
                    tolerance = 0.10 if closest_std <= 1.1 else 0.15
                    if abs(closest_std - width_m) < tolerance:
                        width_m = closest_std

                    # Determine door type
                    if width_m < 0.70:
                        door_type = "narrow"
                    elif width_m < 0.95:
                        door_type = "standard"
                    elif width_m < 1.30:
                        door_type = "wide"
                    else:
                        door_type = "double"

                    door = WallOpening(
                        opening_id=generate_opening_id(),
                        page_number=page_number,
                        center_x=obj.bbox.center[0],
                        center_y=obj.bbox.center[1],
                        width_px=width_px,
                        angle_degrees=0,
                        wall_thickness_px=10,
                        width_m=width_m,
                        confidence=obj.confidence,
                        is_door=True,
                        detection_signals=["yolo_primary"],
                        metadata={
                            "door_type": door_type,
                            "yolo_class": obj.attributes.get("yolo_class"),
                            "bbox": obj.bbox.to_dict(),
                            "bbox_min_px": bbox_min,
                            "raw_width_m": bbox_min / pixels_per_meter,
                        },
                    )
                    yolo_doors.append(door)

                logger.info(f"YOLO detected {len(yolo_doors)} doors")

            finally:
                if os.path.exists(image_path):
                    os.remove(image_path)

        except Exception as e:
            logger.warning(f"YOLO detection failed: {e}")
            warnings.append(f"YOLO failed: {str(e)}")

    else:
        warnings.append("YOLO not available - using wall opening detection only")

    all_doors.extend(yolo_doors)

    # Step 2: Wall opening detection (validation/supplement)
    if use_wall_opening_validation and len(yolo_doors) < 3:
        # Only run wall opening if YOLO found few doors
        try:
            wall_result = detect_doors_from_wall_openings(
                pdf_path=pdf_path,
                page_number=page_number,
                scale=scale,
                dpi=300,  # Higher DPI for wall detection
            )

            # Add wall-opening doors that aren't duplicates of YOLO
            for wo_door in wall_result.doors:
                is_duplicate = False
                for yolo_door in yolo_doors:
                    dist = math.sqrt(
                        (wo_door.center_x - yolo_door.center_x) ** 2 +
                        (wo_door.center_y - yolo_door.center_y) ** 2
                    )
                    # Scale check: wall opening runs at 300 DPI, YOLO at 150
                    scaled_dist = dist / 2  # Approximate scaling
                    if scaled_dist < 100:
                        is_duplicate = True
                        break

                if not is_duplicate:
                    wo_door.detection_signals.append("wall_opening_supplement")
                    wo_door.confidence *= 0.8  # Lower confidence for wall-only detections
                    all_doors.append(wo_door)

            logger.info(f"Wall opening added {len(all_doors) - len(yolo_doors)} supplemental doors")

        except Exception as e:
            logger.warning(f"Wall opening detection failed: {e}")
            warnings.append(f"Wall opening failed: {str(e)}")

    processing_time_ms = int((time.time() - start_time) * 1000)

    return DoorDetectionResult(
        page_number=page_number,
        doors=all_doors,
        total_openings_analyzed=len(all_doors),
        wall_mask_generated=use_wall_opening_validation,
        hatch_regions_filtered=0,
        processing_time_ms=processing_time_ms,
        warnings=warnings,
    )


def detect_doors_with_yolo_hints(
    pdf_path: str,
    page_number: int = 1,
    scale: int = 100,
    dpi: int = 400,
    yolo_results: Optional[List[Dict[str, Any]]] = None,
) -> DoorDetectionResult:
    """
    Enhanced door detection using YOLO as hint engine.

    DEPRECATED: Use detect_doors_yolo_primary instead.
    This function is kept for backwards compatibility.

    Strategy:
    1. Run wall opening detection
    2. Boost confidence for openings near YOLO detections
    3. Add YOLO-only detections with lower confidence

    This combines the precision of wall opening detection
    with the pattern recognition of ML models.
    """
    # First, run wall opening detection
    result = detect_doors_from_wall_openings(
        pdf_path=pdf_path,
        page_number=page_number,
        scale=scale,
        dpi=dpi,
    )

    if yolo_results is None or len(yolo_results) == 0:
        return result

    # Boost confidence for wall openings near YOLO detections
    for door in result.doors:
        for yolo_det in yolo_results:
            yolo_cx = yolo_det.get("center_x", 0)
            yolo_cy = yolo_det.get("center_y", 0)

            dist = math.sqrt(
                (door.center_x - yolo_cx) ** 2 +
                (door.center_y - yolo_cy) ** 2
            )

            # If YOLO detection is nearby, boost confidence
            if dist < 100:  # Within 100 pixels
                door.confidence = min(0.95, door.confidence + 0.15)
                door.detection_signals.append("yolo_confirmed")
                door.metadata["yolo_distance"] = dist
                break

    return result


# Export main functions
__all__ = [
    "DetectionMode",
    "DETECTION_MODE_CONFIGS",
    "WallOpening",
    "DoorDetectionResult",
    "detect_doors_yolo_primary",  # Recommended production function
    "detect_doors_from_wall_openings",
    "detect_doors_with_yolo_hints",
    "render_pdf_page_high_dpi",
    "extract_wall_mask",
    "find_wall_openings",
    "detect_hatch_regions",
    "filter_openings_in_hatch",
    "validate_door_openings",
]

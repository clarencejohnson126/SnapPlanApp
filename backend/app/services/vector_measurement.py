"""
Vector Measurement Service

Extracts and measures vector geometry from CAD-style PDFs.
Supports wall segments, line extraction, and length/area calculations.

Part of the Aufmaß Engine - Phase D implementation.
"""

from dataclasses import dataclass, field
from pathlib import Path
from typing import List, Optional, Dict, Any, Tuple, Union
import math
import uuid
import logging

logger = logging.getLogger(__name__)

# Try to import PyMuPDF for vector extraction
try:
    import fitz
    FITZ_AVAILABLE = True
except ImportError:
    FITZ_AVAILABLE = False
    logger.warning("PyMuPDF (fitz) not available - vector extraction disabled")


@dataclass
class LineSegment:
    """
    Represents a line segment extracted from a PDF page.

    Coordinates are in the PDF's page coordinate system (same as rendered images).
    """
    x1: float
    y1: float
    x2: float
    y2: float
    page_number: int
    layer: Optional[str] = None
    stroke_width: Optional[float] = None
    color: Optional[Tuple[float, ...]] = None
    metadata: Dict[str, Any] = field(default_factory=dict)

    @property
    def length_px(self) -> float:
        """Calculate the length of the segment in pixels."""
        return math.sqrt((self.x2 - self.x1) ** 2 + (self.y2 - self.y1) ** 2)

    @property
    def midpoint(self) -> Tuple[float, float]:
        """Calculate the midpoint of the segment."""
        return ((self.x1 + self.x2) / 2, (self.y1 + self.y2) / 2)

    @property
    def angle_degrees(self) -> float:
        """Calculate the angle of the segment in degrees (0-180)."""
        angle_rad = math.atan2(self.y2 - self.y1, self.x2 - self.x1)
        angle_deg = math.degrees(angle_rad)
        # Normalize to 0-180 range (lines have no direction)
        if angle_deg < 0:
            angle_deg += 180
        return angle_deg

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return {
            "x1": self.x1,
            "y1": self.y1,
            "x2": self.x2,
            "y2": self.y2,
            "page_number": self.page_number,
            "layer": self.layer,
            "stroke_width": self.stroke_width,
            "color": list(self.color) if self.color else None,
            "length_px": self.length_px,
            "metadata": self.metadata,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "LineSegment":
        """Create LineSegment from dictionary."""
        color = data.get("color")
        if color and isinstance(color, list):
            color = tuple(color)
        return cls(
            x1=data["x1"],
            y1=data["y1"],
            x2=data["x2"],
            y2=data["y2"],
            page_number=data.get("page_number", 1),
            layer=data.get("layer"),
            stroke_width=data.get("stroke_width"),
            color=color,
            metadata=data.get("metadata", {}),
        )


@dataclass
class WallSegment:
    """
    Represents a wall segment candidate extracted from a PDF.

    WallSegments wrap LineSegments and add classification metadata.
    """
    segment_id: str
    segment: LineSegment
    kind: str = "wall"  # "wall", "partition", "exterior", etc.
    confidence: float = 1.0
    material: Optional[str] = None  # "drywall", "concrete", "brick", etc.
    thickness_m: Optional[float] = None
    metadata: Dict[str, Any] = field(default_factory=dict)

    @property
    def length_px(self) -> float:
        """Get length from underlying segment."""
        return self.segment.length_px

    @property
    def page_number(self) -> int:
        """Get page number from underlying segment."""
        return self.segment.page_number

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return {
            "segment_id": self.segment_id,
            "segment": self.segment.to_dict(),
            "kind": self.kind,
            "confidence": self.confidence,
            "material": self.material,
            "thickness_m": self.thickness_m,
            "length_px": self.length_px,
            "metadata": self.metadata,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "WallSegment":
        """Create WallSegment from dictionary."""
        return cls(
            segment_id=data.get("segment_id", generate_wall_segment_id()),
            segment=LineSegment.from_dict(data["segment"]),
            kind=data.get("kind", "wall"),
            confidence=data.get("confidence", 1.0),
            material=data.get("material"),
            thickness_m=data.get("thickness_m"),
            metadata=data.get("metadata", {}),
        )


def generate_wall_segment_id() -> str:
    """Generate a unique wall segment ID."""
    return f"wall_{uuid.uuid4().hex[:12]}"


def extract_line_segments_from_page(
    path: Union[str, Path],
    page_number: int,
    dpi: int = 150,
    min_length_px: float = 5.0,
) -> List[LineSegment]:
    """
    Extract line segments from a PDF page using PyMuPDF.

    Uses the PDF's vector graphics data (paths, lines, polylines).
    Coordinates are scaled to match rendered image coordinates at the given DPI.

    Args:
        path: Path to the PDF file
        page_number: Page number (1-indexed)
        dpi: DPI for coordinate scaling (should match render DPI)
        min_length_px: Minimum segment length to include (filters noise)

    Returns:
        List of LineSegment objects

    Raises:
        ImportError: If PyMuPDF is not available
        FileNotFoundError: If PDF file doesn't exist
        ValueError: If page number is invalid
    """
    if not FITZ_AVAILABLE:
        raise ImportError("PyMuPDF (fitz) is required for vector extraction")

    path = Path(path)
    if not path.exists():
        raise FileNotFoundError(f"PDF file not found: {path}")

    segments: List[LineSegment] = []

    doc = fitz.open(str(path))
    try:
        # PyMuPDF uses 0-indexed pages
        page_idx = page_number - 1
        if page_idx < 0 or page_idx >= len(doc):
            raise ValueError(f"Invalid page number {page_number}, document has {len(doc)} pages")

        page = doc[page_idx]

        # Get scaling factor from PDF points to rendered pixels
        # PDF is 72 points per inch, we render at 'dpi' pixels per inch
        scale = dpi / 72.0

        # Method 1: Get drawings (vector paths)
        drawings = page.get_drawings()

        for drawing in drawings:
            # Each drawing contains items describing path operations
            items = drawing.get("items", [])
            stroke_color = drawing.get("color")  # Stroke color
            stroke_width = drawing.get("width", 1.0)

            # Track current position for path construction
            current_point = None

            for item in items:
                # item is a tuple like ('l', p1, p2) for line or ('m', p) for moveto
                if len(item) < 2:
                    continue

                cmd = item[0]

                if cmd == "m":  # moveto
                    current_point = item[1]

                elif cmd == "l":  # lineto
                    p1 = item[1]
                    p2 = item[2]

                    # Scale coordinates to rendered DPI
                    x1 = p1.x * scale
                    y1 = p1.y * scale
                    x2 = p2.x * scale
                    y2 = p2.y * scale

                    # Calculate length
                    length = math.sqrt((x2 - x1) ** 2 + (y2 - y1) ** 2)

                    if length >= min_length_px:
                        segment = LineSegment(
                            x1=x1,
                            y1=y1,
                            x2=x2,
                            y2=y2,
                            page_number=page_number,
                            stroke_width=stroke_width * scale if stroke_width else None,
                            color=stroke_color,
                            metadata={
                                "source": "drawing",
                                "original_width": stroke_width,
                            },
                        )
                        segments.append(segment)

                    current_point = p2

                elif cmd == "re":  # rectangle - extract as 4 lines
                    rect = item[1]  # fitz.Rect

                    # Scale rectangle coordinates
                    x0 = rect.x0 * scale
                    y0 = rect.y0 * scale
                    x1 = rect.x1 * scale
                    y1 = rect.y1 * scale

                    # Create 4 line segments for the rectangle
                    rect_segments = [
                        (x0, y0, x1, y0),  # Top
                        (x1, y0, x1, y1),  # Right
                        (x1, y1, x0, y1),  # Bottom
                        (x0, y1, x0, y0),  # Left
                    ]

                    for rx1, ry1, rx2, ry2 in rect_segments:
                        length = math.sqrt((rx2 - rx1) ** 2 + (ry2 - ry1) ** 2)
                        if length >= min_length_px:
                            segment = LineSegment(
                                x1=rx1,
                                y1=ry1,
                                x2=rx2,
                                y2=ry2,
                                page_number=page_number,
                                stroke_width=stroke_width * scale if stroke_width else None,
                                color=stroke_color,
                                metadata={
                                    "source": "rectangle",
                                    "original_width": stroke_width,
                                },
                            )
                            segments.append(segment)

                elif cmd == "c":  # Bezier curve - approximate with line from start to end
                    # item = ('c', p1, p2, p3, p4) - cubic bezier
                    if len(item) >= 4:
                        p1 = item[1]  # Start point
                        p4 = item[-1]  # End point

                        x1 = p1.x * scale
                        y1 = p1.y * scale
                        x2 = p4.x * scale
                        y2 = p4.y * scale

                        length = math.sqrt((x2 - x1) ** 2 + (y2 - y1) ** 2)

                        if length >= min_length_px:
                            segment = LineSegment(
                                x1=x1,
                                y1=y1,
                                x2=x2,
                                y2=y2,
                                page_number=page_number,
                                stroke_width=stroke_width * scale if stroke_width else None,
                                color=stroke_color,
                                metadata={
                                    "source": "curve_approx",
                                    "original_cmd": "bezier",
                                },
                            )
                            segments.append(segment)

                        current_point = p4

        logger.info(f"Extracted {len(segments)} line segments from page {page_number}")

    finally:
        doc.close()

    return segments


def extract_wall_segments_from_page(
    path: Union[str, Path],
    page_number: int,
    dpi: int = 150,
    min_length_px: float = 10.0,
    filter_by_angle: bool = False,
) -> List[WallSegment]:
    """
    Extract wall segment candidates from a PDF page.

    For now, all line segments are treated as wall candidates.
    Future versions will filter by:
    - Layer names (e.g., "walls", "partitions")
    - Stroke width thresholds
    - Color coding
    - Angle filters (horizontal/vertical only)

    Args:
        path: Path to the PDF file
        page_number: Page number (1-indexed)
        dpi: DPI for coordinate scaling
        min_length_px: Minimum segment length (walls are typically longer)
        filter_by_angle: If True, only include horizontal/vertical lines

    Returns:
        List of WallSegment objects
    """
    line_segments = extract_line_segments_from_page(
        path=path,
        page_number=page_number,
        dpi=dpi,
        min_length_px=min_length_px,
    )

    wall_segments: List[WallSegment] = []

    for line in line_segments:
        # TODO: Add filtering logic based on:
        # - Layer names (when available in metadata)
        # - Stroke width (thicker lines = walls)
        # - Color (walls often have specific colors)

        # Optional: Filter by angle (horizontal or vertical only)
        if filter_by_angle:
            angle = line.angle_degrees
            # Allow horizontal (0° or 180°) and vertical (90°) with 5° tolerance
            is_horizontal = angle < 5 or angle > 175
            is_vertical = 85 < angle < 95
            if not (is_horizontal or is_vertical):
                continue

        wall = WallSegment(
            segment_id=generate_wall_segment_id(),
            segment=line,
            kind="wall",
            confidence=1.0,  # TODO: Adjust based on heuristics
            metadata={
                "classification": "all_lines_as_walls",
                "note": "Phase D: No filtering applied yet",
            },
        )
        wall_segments.append(wall)

    logger.info(f"Created {len(wall_segments)} wall segments from {len(line_segments)} lines")

    return wall_segments


def point_in_polygon(
    x: float,
    y: float,
    polygon_points: List[Tuple[float, float]],
) -> bool:
    """
    Check if a point is inside a polygon using ray casting algorithm.

    Args:
        x: X coordinate of the point
        y: Y coordinate of the point
        polygon_points: List of (x, y) vertices of the polygon

    Returns:
        True if point is inside the polygon
    """
    n = len(polygon_points)
    if n < 3:
        return False

    inside = False
    j = n - 1

    for i in range(n):
        xi, yi = polygon_points[i]
        xj, yj = polygon_points[j]

        if ((yi > y) != (yj > y)) and (x < (xj - xi) * (y - yi) / (yj - yi) + xi):
            inside = not inside

        j = i

    return inside


def segment_in_polygon(
    segment: LineSegment,
    polygon_points: List[Tuple[float, float]],
    require_both_endpoints: bool = True,
) -> bool:
    """
    Check if a line segment is inside (or intersects) a polygon.

    Args:
        segment: The line segment to check
        polygon_points: List of (x, y) vertices of the polygon
        require_both_endpoints: If True, both endpoints must be inside.
                               If False, at least one endpoint inside counts.

    Returns:
        True if segment is inside/intersects the polygon
    """
    p1_inside = point_in_polygon(segment.x1, segment.y1, polygon_points)
    p2_inside = point_in_polygon(segment.x2, segment.y2, polygon_points)

    if require_both_endpoints:
        return p1_inside and p2_inside
    else:
        # TODO: Add proper line-polygon intersection for partial segments
        return p1_inside or p2_inside


def compute_wall_length_in_sector_m(
    *,
    wall_segments: List[WallSegment],
    sector: "Sector",  # Forward reference
    scale_context: "ScaleContext",  # Forward reference
    require_both_endpoints: bool = True,
) -> "MeasurementResult":  # Forward reference
    """
    Compute total wall length in meters for wall segments inside a sector.

    Sums the length of all wall segments where both endpoints (or at least one,
    depending on require_both_endpoints) are inside the sector polygon.

    Args:
        wall_segments: List of WallSegment objects to consider
        sector: Sector with polygon defining the area of interest
        scale_context: ScaleContext with pixels_per_meter for conversion
        require_both_endpoints: If True, both endpoints must be inside sector

    Returns:
        MeasurementResult with total wall length in meters

    Raises:
        ValueError: If scale_context has no valid pixels_per_meter
    """
    # Import here to avoid circular dependency
    from .measurement_engine import MeasurementResult, generate_measurement_id, MeasurementMethod

    if not scale_context.has_scale:
        raise ValueError("ScaleContext must have valid pixels_per_meter")

    pixels_per_meter = scale_context.pixels_per_meter

    # Filter segments inside sector and sum lengths
    total_length_px = 0.0
    segment_count = 0
    included_segment_ids: List[str] = []

    for wall in wall_segments:
        # Check if segment is on the same page as sector
        if wall.page_number != sector.page_number:
            continue

        if segment_in_polygon(
            wall.segment,
            sector.polygon_points,
            require_both_endpoints=require_both_endpoints,
        ):
            total_length_px += wall.length_px
            segment_count += 1
            included_segment_ids.append(wall.segment_id)

    # Convert to meters
    total_length_m = total_length_px / pixels_per_meter

    return MeasurementResult(
        measurement_id=generate_measurement_id(),
        measurement_type="sector_wall_length",
        value=round(total_length_m, 4),
        unit="m",
        file_id=sector.file_id,
        page_number=sector.page_number,
        confidence=1.0,  # Deterministic calculation
        method=MeasurementMethod.VECTOR_GEOMETRY.value,
        assumptions=[
            f"pixels_per_meter: {pixels_per_meter:.2f}",
            f"segment_count: {segment_count}",
            f"require_both_endpoints: {require_both_endpoints}",
            "All line segments treated as walls (no layer filtering)",
        ],
        source=f"Sector: {sector.name}",
        sector_id=sector.sector_id,
        scale_context_id=scale_context.id,
    )


def compute_drywall_area_in_sector_m2(
    *,
    wall_segments: List[WallSegment],
    sector: "Sector",  # Forward reference
    scale_context: "ScaleContext",  # Forward reference
    wall_height_m: float,
    require_both_endpoints: bool = True,
) -> "MeasurementResult":  # Forward reference
    """
    Compute approximate drywall area in m² for a sector.

    Simple formula: drywall_area = total_wall_length * wall_height

    This assumes:
    - All wall segments are drywall (no filtering by material)
    - Wall height is constant throughout the sector
    - Both sides of walls are counted (multiply by 2 if needed externally)

    Args:
        wall_segments: List of WallSegment objects to consider
        sector: Sector with polygon defining the area of interest
        scale_context: ScaleContext with pixels_per_meter for conversion
        wall_height_m: Wall height in meters (user-provided)
        require_both_endpoints: If True, both endpoints must be inside sector

    Returns:
        MeasurementResult with drywall area in m²

    Raises:
        ValueError: If scale_context has no valid pixels_per_meter
        ValueError: If wall_height_m is not positive
    """
    # Import here to avoid circular dependency
    from .measurement_engine import MeasurementResult, generate_measurement_id, MeasurementMethod

    if wall_height_m <= 0:
        raise ValueError(f"wall_height_m must be positive, got {wall_height_m}")

    # First compute wall length
    wall_length_result = compute_wall_length_in_sector_m(
        wall_segments=wall_segments,
        sector=sector,
        scale_context=scale_context,
        require_both_endpoints=require_both_endpoints,
    )

    # Calculate drywall area
    total_wall_length_m = wall_length_result.value
    drywall_area_m2 = total_wall_length_m * wall_height_m

    # Extract segment count from wall length assumptions
    segment_count = 0
    for assumption in wall_length_result.assumptions:
        if assumption.startswith("segment_count:"):
            segment_count = int(assumption.split(":")[1].strip())
            break

    return MeasurementResult(
        measurement_id=generate_measurement_id(),
        measurement_type="sector_drywall_area",
        value=round(drywall_area_m2, 4),
        unit="m2",
        file_id=sector.file_id,
        page_number=sector.page_number,
        confidence=1.0,  # Deterministic calculation
        method=MeasurementMethod.VECTOR_GEOMETRY.value,
        assumptions=[
            f"wall_length_m: {total_wall_length_m:.4f}",
            f"wall_height_m: {wall_height_m:.2f}",
            f"pixels_per_meter: {scale_context.pixels_per_meter:.2f}",
            f"segment_count: {segment_count}",
            "All wall segments treated as drywall",
            "Single-sided area (multiply by 2 for both sides)",
            "Constant wall height assumed",
        ],
        source=f"Sector: {sector.name}",
        sector_id=sector.sector_id,
        scale_context_id=scale_context.id,
    )


@dataclass
class DoorSymbol:
    """
    Represents a detected door symbol from vector graphics.

    Door symbols in floor plans typically consist of:
    - An arc (quarter circle showing swing direction)
    - A leaf line (the door panel itself)
    """
    door_id: str
    page_number: int
    # Arc geometry
    arc_center: Tuple[float, float]
    arc_radius_px: float
    arc_start_angle: float
    arc_end_angle: float
    # Leaf line geometry
    leaf_line: Optional[LineSegment] = None
    # Measurements
    width_m: Optional[float] = None
    # Metadata
    label: Optional[str] = None
    confidence: float = 0.8
    detection_method: str = "arc_pattern"
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "door_id": self.door_id,
            "page_number": self.page_number,
            "arc_center": list(self.arc_center),
            "arc_radius_px": self.arc_radius_px,
            "arc_start_angle": self.arc_start_angle,
            "arc_end_angle": self.arc_end_angle,
            "leaf_line": self.leaf_line.to_dict() if self.leaf_line else None,
            "width_m": self.width_m,
            "label": self.label,
            "confidence": self.confidence,
            "detection_method": self.detection_method,
            "metadata": self.metadata,
        }


def generate_door_id() -> str:
    """Generate a unique door symbol ID."""
    return f"door_{uuid.uuid4().hex[:8]}"


def generate_window_id() -> str:
    """Generate a unique window symbol ID."""
    return f"window_{uuid.uuid4().hex[:8]}"


@dataclass
class WindowSymbol:
    """
    Represents a detected window symbol from vector graphics.

    Windows in floor plans are detected by:
    - Parallel lines (frame/mullions) without nearby arcs
    - Typical spacing of 5-15cm between lines
    - No swing arc (distinguishes from doors)
    """
    window_id: str
    page_number: int
    # Frame geometry
    center: Tuple[float, float]
    width_px: float
    height_px: float
    angle_degrees: float
    # Lines that form the window
    line1: Optional[LineSegment] = None
    line2: Optional[LineSegment] = None
    # Measurements
    width_m: Optional[float] = None
    height_m: Optional[float] = None
    area_m2: Optional[float] = None
    # Metadata
    label: Optional[str] = None
    confidence: float = 0.7
    detection_method: str = "parallel_lines"
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "window_id": self.window_id,
            "page_number": self.page_number,
            "center": list(self.center),
            "width_px": self.width_px,
            "height_px": self.height_px,
            "angle_degrees": self.angle_degrees,
            "line1": self.line1.to_dict() if self.line1 else None,
            "line2": self.line2.to_dict() if self.line2 else None,
            "width_m": self.width_m,
            "height_m": self.height_m,
            "area_m2": self.area_m2,
            "label": self.label,
            "confidence": self.confidence,
            "detection_method": self.detection_method,
            "metadata": self.metadata,
        }


def _is_roof_plan_page(page: Any, filename: str = "") -> bool:
    """
    Detect if a page is a roof plan (Dachgeschoss).

    Roof plans have arc patterns that look like doors but aren't:
    - Drainage flow arcs
    - Compass/north arrows
    - HVAC equipment symbols
    - Roof hatch symbols

    Returns True if the page appears to be a roof plan.
    """
    # Keywords indicating a roof plan
    roof_keywords = [
        "dachgeschoss", "dach", "dachdraufsicht", "dachaufsicht",
        "roof", "rooftop", "attic",
        "dachhaut", "dachfläche", "flachdach",
    ]

    # Check filename
    filename_lower = filename.lower()
    for keyword in roof_keywords:
        if keyword in filename_lower:
            return True

    # Check page text
    try:
        page_text = page.get_text().lower()
        for keyword in roof_keywords:
            if keyword in page_text:
                return True
    except Exception:
        pass

    return False


def _analyze_bezier_arc(p1: Any, p2: Any, p3: Any, p4: Any) -> Optional[Dict[str, Any]]:
    """
    Analyze a cubic Bezier curve to determine if it's approximately a quarter circle.

    Returns arc properties if it looks like a quarter circle, None otherwise.
    """
    # Get coordinates
    x1, y1 = p1.x, p1.y
    x2, y2 = p2.x, p2.y
    x3, y3 = p3.x, p3.y
    x4, y4 = p4.x, p4.y

    # Calculate approximate center (midpoint of start-end diagonal)
    # For a quarter circle, the center should be at one of the corners
    chord_length = math.sqrt((x4 - x1) ** 2 + (y4 - y1) ** 2)

    if chord_length < 5:  # Too small
        return None

    # For a quarter circle, chord = radius * sqrt(2)
    approx_radius = chord_length / math.sqrt(2)

    # Estimate center by finding the corner point
    # The center of a quarter arc is equidistant from both endpoints
    # Try different corner positions
    candidates = [
        (x1, y4),  # Bottom-left or top-right
        (x4, y1),  # Top-left or bottom-right
    ]

    best_center = None
    best_error = float('inf')

    for cx, cy in candidates:
        d1 = math.sqrt((x1 - cx) ** 2 + (y1 - cy) ** 2)
        d4 = math.sqrt((x4 - cx) ** 2 + (y4 - cy) ** 2)
        error = abs(d1 - d4)

        if error < best_error and d1 > 5:  # Minimum radius threshold
            best_error = error
            best_center = (cx, cy)
            approx_radius = (d1 + d4) / 2

    if best_center is None or best_error > approx_radius * 0.3:  # Allow 30% error
        return None

    # Calculate angles
    start_angle = math.degrees(math.atan2(y1 - best_center[1], x1 - best_center[0]))
    end_angle = math.degrees(math.atan2(y4 - best_center[1], x4 - best_center[0]))

    # Normalize angles
    if start_angle < 0:
        start_angle += 360
    if end_angle < 0:
        end_angle += 360

    # Check if it's approximately a quarter circle (90 degrees)
    angle_diff = abs(end_angle - start_angle)
    if angle_diff > 180:
        angle_diff = 360 - angle_diff

    if 70 < angle_diff < 110:  # Allow some tolerance for quarter circle
        return {
            "center": best_center,
            "radius": approx_radius,
            "start_angle": start_angle,
            "end_angle": end_angle,
            "arc_angle": angle_diff,
        }

    return None


def extract_door_symbols_from_page(
    path: Union[str, Path],
    page_number: int,
    dpi: int = 150,
    min_door_width_m: float = 0.5,  # Minimum realistic door width
    max_door_width_m: float = 2.5,  # Maximum realistic door width
    pixels_per_meter: Optional[float] = None,  # Required for filtering
) -> List[DoorSymbol]:
    """
    Extract door symbols from a PDF page by detecting arc patterns.

    Door symbols in architectural drawings typically consist of:
    - A quarter-circle arc (showing door swing)
    - A straight line (the door leaf) with length matching arc radius

    Args:
        path: Path to the PDF file
        page_number: Page number (1-indexed)
        dpi: DPI for coordinate scaling
        min_door_width_m: Minimum realistic door width in meters (default 0.5m)
        max_door_width_m: Maximum realistic door width in meters (default 2.5m)
        pixels_per_meter: Scale factor for filtering by real-world size

    Returns:
        List of detected DoorSymbol objects
    """
    if not FITZ_AVAILABLE:
        raise ImportError("PyMuPDF (fitz) is required for door detection")

    path = Path(path)
    if not path.exists():
        raise FileNotFoundError(f"PDF file not found: {path}")

    # Calculate pixel thresholds from real-world dimensions
    if pixels_per_meter:
        min_radius_px = min_door_width_m * pixels_per_meter
        max_radius_px = max_door_width_m * pixels_per_meter
    else:
        # Fallback to pixel-based thresholds (less accurate)
        min_radius_px = 20.0
        max_radius_px = 200.0

    doors: List[DoorSymbol] = []
    arcs: List[Dict[str, Any]] = []
    lines: List[LineSegment] = []

    doc = fitz.open(str(path))
    try:
        page_idx = page_number - 1
        if page_idx < 0 or page_idx >= len(doc):
            raise ValueError(f"Invalid page number {page_number}")

        page = doc[page_idx]
        scale = dpi / 72.0

        # Detect roof plans for stricter validation
        is_roof_plan = _is_roof_plan_page(page, str(path))
        if is_roof_plan:
            logger.info(f"Page {page_number} detected as roof plan - applying stricter door validation")

        drawings = page.get_drawings()

        for drawing in drawings:
            items = drawing.get("items", [])

            for item in items:
                if len(item) < 2:
                    continue

                cmd = item[0]

                # Detect Bezier curves (potential arcs)
                if cmd == "c" and len(item) >= 4:
                    p1, p2, p3, p4 = item[1], item[2], item[3], item[4] if len(item) > 4 else item[3]
                    arc_info = _analyze_bezier_arc(p1, p2, p3, p4)

                    if arc_info:
                        center_x = arc_info["center"][0] * scale
                        center_y = arc_info["center"][1] * scale
                        radius = arc_info["radius"] * scale

                        # Filter by realistic door size
                        if min_radius_px <= radius <= max_radius_px:
                            arcs.append({
                                "center": (center_x, center_y),
                                "radius": radius,
                                "start_angle": arc_info["start_angle"],
                                "end_angle": arc_info["end_angle"],
                            })

                # Collect line segments (for matching with arcs)
                elif cmd == "l":
                    p1 = item[1]
                    p2 = item[2]

                    x1 = p1.x * scale
                    y1 = p1.y * scale
                    x2 = p2.x * scale
                    y2 = p2.y * scale

                    length = math.sqrt((x2 - x1) ** 2 + (y2 - y1) ** 2)

                    # Only collect lines that could be door leaves
                    if min_radius_px <= length <= max_radius_px:
                        lines.append(LineSegment(
                            x1=x1, y1=y1, x2=x2, y2=y2,
                            page_number=page_number,
                        ))

        logger.info(f"Found {len(arcs)} potential arcs and {len(lines)} lines on page {page_number}")

        # Match arcs with nearby lines of similar length
        used_arcs = set()
        used_lines = set()

        # Roof plans need stricter matching to filter false positives
        # (drainage arcs, compass arrows, HVAC symbols look like doors)
        if is_roof_plan:
            max_center_dist_ratio = 0.25  # Line must be close to arc center (25% of radius)
            max_length_diff_ratio = 0.20  # Length must match well (20%)
            base_confidence = 0.70  # Lower confidence for roof plan doors
        else:
            max_center_dist_ratio = 0.6   # Normal: line within 60% of radius from center
            max_length_diff_ratio = 0.3   # Normal: length within 30%
            base_confidence = 0.85

        for i, arc in enumerate(arcs):
            if i in used_arcs:
                continue

            center = arc["center"]
            radius = arc["radius"]

            # Find a line that:
            # 1. Has one endpoint near the arc center
            # 2. Has length similar to arc radius
            best_line = None
            best_line_idx = None
            best_score = float('inf')

            for j, line in enumerate(lines):
                if j in used_lines:
                    continue

                # Check if one endpoint is near the arc center
                dist_to_p1 = math.sqrt((line.x1 - center[0]) ** 2 + (line.y1 - center[1]) ** 2)
                dist_to_p2 = math.sqrt((line.x2 - center[0]) ** 2 + (line.y2 - center[1]) ** 2)
                min_dist = min(dist_to_p1, dist_to_p2)

                # Check length match
                length_diff = abs(line.length_px - radius) / radius

                # Score based on proximity and length match
                if min_dist < radius * max_center_dist_ratio and length_diff < max_length_diff_ratio:
                    score = min_dist + length_diff * radius
                    if score < best_score:
                        best_score = score
                        best_line = line
                        best_line_idx = j

            # Only create door symbol if we have a matching leaf line
            # This filters out window arcs and other non-door symbols
            if best_line is not None:
                door = DoorSymbol(
                    door_id=generate_door_id(),
                    page_number=page_number,
                    arc_center=center,
                    arc_radius_px=radius,
                    arc_start_angle=arc["start_angle"],
                    arc_end_angle=arc["end_angle"],
                    leaf_line=best_line,
                    confidence=base_confidence,
                    metadata={"arc_index": i, "line_index": best_line_idx, "is_roof_plan": is_roof_plan},
                )
                doors.append(door)

                used_arcs.add(i)
                used_lines.add(best_line_idx)

        # NOTE: We no longer accept standalone arcs without matching leaf lines
        # This greatly reduces false positives from windows and other arc symbols

        logger.info(f"Detected {len(doors)} door symbols on page {page_number}")

    finally:
        doc.close()

    return doors


def measure_doors_on_page(
    path: Union[str, Path],
    page_number: int,
    pixels_per_meter: float,
    dpi: int = 150,
    min_door_width_m: float = 0.62,  # Minimum door width (62cm filters out windows, keeps WC doors)
    max_door_width_m: float = 2.0,  # Maximum single door width (includes wide doors up to 2m)
) -> List[DoorSymbol]:
    """
    Extract and measure door symbols from a PDF page.

    Only detects doors within realistic size range to filter false positives.

    Args:
        path: Path to the PDF file
        page_number: Page number (1-indexed)
        pixels_per_meter: Scale factor for converting pixels to meters
        dpi: DPI for coordinate scaling
        min_door_width_m: Minimum door width to detect (default 0.6m)
        max_door_width_m: Maximum door width to detect (default 2.0m)

    Returns:
        List of DoorSymbol objects with width_m calculated
    """
    doors = extract_door_symbols_from_page(
        path=path,
        page_number=page_number,
        dpi=dpi,
        min_door_width_m=min_door_width_m,
        max_door_width_m=max_door_width_m,
        pixels_per_meter=pixels_per_meter,
    )

    for door in doors:
        # Door width = arc radius in meters
        door.width_m = door.arc_radius_px / pixels_per_meter

    return doors


def extract_window_symbols_from_page(
    path: Union[str, Path],
    page_number: int,
    dpi: int = 150,
    min_window_width_m: float = 0.4,
    max_window_width_m: float = 3.5,
    pixels_per_meter: Optional[float] = None,
    door_centers: Optional[List[Tuple[float, float]]] = None,
) -> List[WindowSymbol]:
    """
    Extract window symbols from a PDF page.

    Windows are detected as parallel lines that:
    - Are 5-15cm apart (frame thickness)
    - Have length 0.4m - 3.5m
    - Are NOT near any door arcs

    Args:
        path: Path to the PDF file
        page_number: Page number (1-indexed)
        dpi: DPI for coordinate scaling
        min_window_width_m: Minimum window width (default 0.4m)
        max_window_width_m: Maximum window width (default 3.5m)
        pixels_per_meter: Scale factor for filtering
        door_centers: List of door arc centers to exclude

    Returns:
        List of WindowSymbol objects
    """
    if not FITZ_AVAILABLE:
        raise ImportError("PyMuPDF (fitz) is required for window detection")

    path = Path(path)
    if not path.exists():
        raise FileNotFoundError(f"PDF file not found: {path}")

    if door_centers is None:
        door_centers = []

    # Calculate pixel thresholds
    if pixels_per_meter:
        min_length_px = min_window_width_m * pixels_per_meter
        max_length_px = max_window_width_m * pixels_per_meter
        # Window frame spacing: 8-12cm (tighter range for accuracy)
        min_spacing_px = 0.08 * pixels_per_meter
        max_spacing_px = 0.12 * pixels_per_meter
        # Exclude area around doors (80cm radius)
        door_exclusion_px = 0.8 * pixels_per_meter
        # Minimum length for window (0.65m to filter small openings/vents)
        min_length_px = max(min_length_px, 0.65 * pixels_per_meter)
    else:
        min_length_px = 40.0
        max_length_px = 300.0
        min_spacing_px = 8.0
        max_spacing_px = 12.0
        door_exclusion_px = 80.0

    windows: List[WindowSymbol] = []
    lines: List[Dict[str, Any]] = []

    doc = fitz.open(str(path))
    try:
        page_idx = page_number - 1
        if page_idx < 0 or page_idx >= len(doc):
            raise ValueError(f"Invalid page number {page_number}")

        page = doc[page_idx]
        scale = dpi / 72.0

        drawings = page.get_drawings()

        # Collect all suitable lines
        for drawing in drawings:
            for item in drawing.get("items", []):
                if len(item) < 3:
                    continue

                cmd = item[0]
                if cmd == "l":  # Line segment
                    p1 = item[1]
                    p2 = item[2]

                    x1 = p1.x * scale
                    y1 = p1.y * scale
                    x2 = p2.x * scale
                    y2 = p2.y * scale

                    length = math.sqrt((x2 - x1) ** 2 + (y2 - y1) ** 2)

                    if min_length_px <= length <= max_length_px:
                        angle = math.atan2(y2 - y1, x2 - x1)
                        cx = (x1 + x2) / 2
                        cy = (y1 + y2) / 2

                        # Check if near a door
                        near_door = False
                        for door_c in door_centers:
                            dist = math.sqrt((cx - door_c[0]) ** 2 + (cy - door_c[1]) ** 2)
                            if dist < door_exclusion_px:
                                near_door = True
                                break

                        if not near_door:
                            lines.append({
                                "x1": x1, "y1": y1,
                                "x2": x2, "y2": y2,
                                "length": length,
                                "angle": angle,
                                "center": (cx, cy),
                            })

        # Find parallel line pairs (window frames)
        used = set()
        angle_tolerance = 0.05  # ~3 degrees (stricter parallel requirement)
        detected_centers = []  # For deduplication

        for i, line1 in enumerate(lines):
            if i in used:
                continue

            for j, line2 in enumerate(lines):
                if j <= i or j in used:
                    continue

                # Check parallel (similar angle)
                angle_diff = abs(line1["angle"] - line2["angle"])
                if angle_diff > angle_tolerance and abs(angle_diff - math.pi) > angle_tolerance:
                    continue

                # Similar length (within 20%)
                len_ratio = min(line1["length"], line2["length"]) / max(line1["length"], line2["length"])
                if len_ratio < 0.8:
                    continue

                # Distance between centers (perpendicular to line direction)
                dx = line2["center"][0] - line1["center"][0]
                dy = line2["center"][1] - line1["center"][1]

                # Project onto perpendicular
                perp_angle = line1["angle"] + math.pi / 2
                perp_dist = abs(dx * math.cos(perp_angle) + dy * math.sin(perp_angle))

                # Check spacing is window-like
                if not (min_spacing_px <= perp_dist <= max_spacing_px):
                    continue

                # Centers should be aligned (along the line direction)
                para_dist = abs(dx * math.cos(line1["angle"]) + dy * math.sin(line1["angle"]))
                if para_dist > line1["length"] * 0.2:  # Allow 20% offset
                    continue

                # Found window candidate
                cx = (line1["center"][0] + line2["center"][0]) / 2
                cy = (line1["center"][1] + line2["center"][1]) / 2
                width_px = (line1["length"] + line2["length"]) / 2
                height_px = perp_dist

                # Angle filter: windows should be roughly horizontal or vertical
                # Normalize angle to 0-180 range
                window_angle = math.degrees(line1["angle"]) % 180
                # Check if roughly horizontal (0° or 180°) or vertical (90°)
                angle_tolerance_deg = 15  # Allow ±15° from horizontal/vertical
                is_horizontal = window_angle < angle_tolerance_deg or window_angle > (180 - angle_tolerance_deg)
                is_vertical = abs(window_angle - 90) < angle_tolerance_deg
                if not (is_horizontal or is_vertical):
                    continue

                # Deduplication: skip if too close to existing detection
                min_separation = width_px * 0.3  # 30% of width
                too_close = False
                for prev_cx, prev_cy in detected_centers:
                    if math.sqrt((cx - prev_cx) ** 2 + (cy - prev_cy) ** 2) < min_separation:
                        too_close = True
                        break
                if too_close:
                    continue

                detected_centers.append((cx, cy))

                # Calculate measurements
                width_m = width_px / pixels_per_meter if pixels_per_meter else None
                height_m = height_px / pixels_per_meter if pixels_per_meter else None

                windows.append(WindowSymbol(
                    window_id=generate_window_id(),
                    page_number=page_number,
                    center=(cx, cy),
                    width_px=width_px,
                    height_px=height_px,
                    angle_degrees=math.degrees(line1["angle"]),
                    line1=LineSegment(
                        x1=line1["x1"], y1=line1["y1"],
                        x2=line1["x2"], y2=line1["y2"],
                        page_number=page_number
                    ),
                    line2=LineSegment(
                        x1=line2["x1"], y1=line2["y1"],
                        x2=line2["x2"], y2=line2["y2"],
                        page_number=page_number
                    ),
                    width_m=width_m,
                    height_m=height_m,
                    confidence=0.7,
                ))

                used.add(i)
                used.add(j)
                break

        logger.info(f"Detected {len(windows)} windows on page {page_number}")

    finally:
        doc.close()

    return windows


def measure_windows_on_page(
    path: Union[str, Path],
    page_number: int,
    pixels_per_meter: float,
    dpi: int = 150,
    min_window_width_m: float = 0.4,
    max_window_width_m: float = 3.5,
) -> List[WindowSymbol]:
    """
    Extract and measure window symbols from a PDF page.

    Automatically excludes areas near detected doors to avoid false positives.

    Args:
        path: Path to the PDF file
        page_number: Page number (1-indexed)
        pixels_per_meter: Scale factor for real measurements
        dpi: DPI for coordinate scaling
        min_window_width_m: Minimum window width (default 0.4m)
        max_window_width_m: Maximum window width (default 3.5m)

    Returns:
        List of WindowSymbol objects with measurements
    """
    # First, detect doors to exclude their areas
    doors = extract_door_symbols_from_page(
        path=path,
        page_number=page_number,
        dpi=dpi,
        pixels_per_meter=pixels_per_meter,
    )
    door_centers = [door.arc_center for door in doors]

    # Now detect windows, excluding door areas
    windows = extract_window_symbols_from_page(
        path=path,
        page_number=page_number,
        dpi=dpi,
        min_window_width_m=min_window_width_m,
        max_window_width_m=max_window_width_m,
        pixels_per_meter=pixels_per_meter,
        door_centers=door_centers,
    )

    # Calculate area for each window
    for window in windows:
        if window.width_m and window.height_m:
            window.area_m2 = window.width_m * window.height_m

    return windows


def generate_room_id() -> str:
    """Generate a unique room ID."""
    return f"room_{uuid.uuid4().hex[:8]}"


@dataclass
class RoomPolygon:
    """
    Represents a detected room from floor plan analysis.
    """
    room_id: str
    page_number: int
    name: Optional[str]
    polygon_points: List[Tuple[float, float]]
    centroid: Tuple[float, float]
    area_px: float
    area_m2: Optional[float] = None
    perimeter_px: float = 0.0
    perimeter_m: Optional[float] = None
    room_type: Optional[str] = None  # "living", "bedroom", "bathroom", etc.
    confidence: float = 0.7
    detection_method: str = "text_region"
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "room_id": self.room_id,
            "page_number": self.page_number,
            "name": self.name,
            "polygon_points": [list(p) for p in self.polygon_points],
            "centroid": list(self.centroid),
            "area_px": self.area_px,
            "area_m2": self.area_m2,
            "perimeter_px": self.perimeter_px,
            "perimeter_m": self.perimeter_m,
            "room_type": self.room_type,
            "confidence": self.confidence,
            "detection_method": self.detection_method,
            "metadata": self.metadata,
        }


def extract_room_labels_from_page(
    path: Union[str, Path],
    page_number: int,
    dpi: int = 150,
) -> List[Dict[str, Any]]:
    """
    Extract room labels and area annotations from a PDF page.

    German floor plans typically have labels like:
    - "Wohnzimmer 25,5 m²"
    - "Schlafzimmer"
    - "Bad 8,2 m²"
    - "B.01.1.017 Vorraum AZ"

    Returns:
        List of room labels with text, position, and parsed area if available
    """
    import re

    if not FITZ_AVAILABLE:
        raise ImportError("PyMuPDF (fitz) is required for room detection")

    path = Path(path)
    if not path.exists():
        raise FileNotFoundError(f"PDF file not found: {path}")

    labels = []
    scale = dpi / 72.0

    doc = fitz.open(str(path))
    try:
        page_idx = page_number - 1
        if page_idx < 0 or page_idx >= len(doc):
            raise ValueError(f"Invalid page number {page_number}")

        page = doc[page_idx]

        # Use blocks method - more reliable for m² annotations
        text_blocks = page.get_text("blocks")

        for block in text_blocks:
            if len(block) < 5 or not isinstance(block[4], str):
                continue

            text = block[4].strip().replace('\n', ' ')
            if not text or len(text) < 2:
                continue

            x0, y0, x1, y1 = block[0], block[1], block[2], block[3]

            # Parse area annotations (German format: "25,5 m²" or "25.5 m2")
            area_match = re.search(r'(\d+[,.]?\d*)\s*m[²2]', text, re.IGNORECASE)
            parsed_area = None
            if area_match:
                area_str = area_match.group(1).replace(',', '.')
                try:
                    parsed_area = float(area_str)
                except ValueError:
                    pass

            # Room type detection from German keywords
            room_type = None
            text_lower = text.lower()
            if any(kw in text_lower for kw in ['wohn', 'living']):
                room_type = 'living'
            elif any(kw in text_lower for kw in ['schlaf', 'bedroom']):
                room_type = 'bedroom'
            elif any(kw in text_lower for kw in ['bad', 'wc', 'toilet', 'dusch']):
                room_type = 'bathroom'
            elif any(kw in text_lower for kw in ['küche', 'kitchen', 'koch']):
                room_type = 'kitchen'
            elif any(kw in text_lower for kw in ['flur', 'gang', 'corridor', 'diele', 'vorraum']):
                room_type = 'corridor'
            elif any(kw in text_lower for kw in ['balkon', 'terras', 'loggia']):
                room_type = 'balcony'
            elif any(kw in text_lower for kw in ['abstell', 'lager', 'storage']):
                room_type = 'storage'
            elif any(kw in text_lower for kw in ['büro', 'office', 'arbeit']):
                room_type = 'office'
            elif any(kw in text_lower for kw in ['treppe', 'trh', 'stair']):
                room_type = 'stairwell'

            # Scale coordinates
            cx = ((x0 + x1) / 2) * scale
            cy = ((y0 + y1) / 2) * scale

            labels.append({
                "text": text,
                "center": (cx, cy),
                "bbox": (x0 * scale, y0 * scale, x1 * scale, y1 * scale),
                "parsed_area_m2": parsed_area,
                "room_type": room_type,
            })

        logger.info(f"Found {len(labels)} text labels on page {page_number}")

    finally:
        doc.close()

    return labels


def detect_rooms_from_page(
    path: Union[str, Path],
    page_number: int,
    pixels_per_meter: float,
    dpi: int = 150,
    min_room_area_m2: float = 2.0,
    max_room_area_m2: float = 500.0,
) -> List[RoomPolygon]:
    """
    Detect rooms from a PDF page using wall segment analysis.

    Strategy:
    1. Extract room labels with positions
    2. Find closed polygons near each label using flood fill regions
    3. Calculate areas and validate against label annotations

    For MVP, returns rectangular approximations based on nearby walls.

    Args:
        path: Path to the PDF file
        page_number: Page number (1-indexed)
        pixels_per_meter: Scale factor
        dpi: DPI for rendering
        min_room_area_m2: Minimum room area (filters closets, etc.)
        max_room_area_m2: Maximum room area (filters whole-floor detections)

    Returns:
        List of RoomPolygon objects
    """
    if not FITZ_AVAILABLE:
        raise ImportError("PyMuPDF (fitz) is required for room detection")

    # Get room labels
    labels = extract_room_labels_from_page(path, page_number, dpi)

    # Filter to likely room labels (have area annotation or room type)
    room_labels = [
        lbl for lbl in labels
        if lbl.get("parsed_area_m2") is not None or lbl.get("room_type") is not None
    ]

    rooms: List[RoomPolygon] = []

    for label in room_labels:
        cx, cy = label["center"]
        parsed_area = label.get("parsed_area_m2")
        room_type = label.get("room_type")
        text = label.get("text", "")

        # If we have a parsed area, create a square approximation
        if parsed_area and parsed_area >= min_room_area_m2 and parsed_area <= max_room_area_m2:
            # Convert m² to pixels
            area_px = parsed_area * (pixels_per_meter ** 2)

            # Approximate as square
            side_px = math.sqrt(area_px)
            half_side = side_px / 2

            # Create rectangular polygon centered on label
            polygon = [
                (cx - half_side, cy - half_side),
                (cx + half_side, cy - half_side),
                (cx + half_side, cy + half_side),
                (cx - half_side, cy + half_side),
            ]

            perimeter_px = 4 * side_px

            rooms.append(RoomPolygon(
                room_id=generate_room_id(),
                page_number=page_number,
                name=text,
                polygon_points=polygon,
                centroid=(cx, cy),
                area_px=area_px,
                area_m2=parsed_area,
                perimeter_px=perimeter_px,
                perimeter_m=4 * math.sqrt(parsed_area),
                room_type=room_type,
                confidence=0.8 if parsed_area else 0.5,
                detection_method="area_annotation",
                metadata={
                    "original_label": text,
                    "approximation": "square",
                }
            ))

    logger.info(f"Detected {len(rooms)} rooms on page {page_number}")
    return rooms


def measure_rooms_on_page(
    path: Union[str, Path],
    page_number: int,
    pixels_per_meter: float,
    dpi: int = 150,
) -> Dict[str, Any]:
    """
    Extract room information from a page including areas.

    Returns a summary with:
    - Total rooms detected
    - Total area
    - Individual room details
    - Room type breakdown

    Args:
        path: Path to the PDF file
        page_number: Page number (1-indexed)
        pixels_per_meter: Scale factor
        dpi: DPI

    Returns:
        Dictionary with room measurement summary
    """
    rooms = detect_rooms_from_page(
        path=path,
        page_number=page_number,
        pixels_per_meter=pixels_per_meter,
        dpi=dpi,
    )

    total_area = sum(r.area_m2 or 0 for r in rooms)

    # Group by type
    by_type: Dict[str, List[RoomPolygon]] = {}
    for room in rooms:
        room_type = room.room_type or "unknown"
        if room_type not in by_type:
            by_type[room_type] = []
        by_type[room_type].append(room)

    type_summary = {
        rtype: {
            "count": len(rlist),
            "total_area_m2": sum(r.area_m2 or 0 for r in rlist),
        }
        for rtype, rlist in by_type.items()
    }

    return {
        "page_number": page_number,
        "total_rooms": len(rooms),
        "total_area_m2": total_area,
        "rooms": [r.to_dict() for r in rooms],
        "by_type": type_summary,
    }


# Re-export for convenience
__all__ = [
    "LineSegment",
    "WallSegment",
    "DoorSymbol",
    "WindowSymbol",
    "RoomPolygon",
    "generate_wall_segment_id",
    "generate_door_id",
    "generate_window_id",
    "generate_room_id",
    "extract_line_segments_from_page",
    "extract_wall_segments_from_page",
    "extract_door_symbols_from_page",
    "extract_window_symbols_from_page",
    "extract_room_labels_from_page",
    "detect_rooms_from_page",
    "measure_doors_on_page",
    "measure_windows_on_page",
    "measure_rooms_on_page",
    "point_in_polygon",
    "segment_in_polygon",
    "compute_wall_length_in_sector_m",
    "compute_drywall_area_in_sector_m2",
    "FITZ_AVAILABLE",
]

"""
Measurement Engine Service

Geometric measurements, area calculations, and sector-based queries.
Part of the Aufmaß Engine - Phase C implementation (sectors, area calculation).
"""

from dataclasses import dataclass, field
from datetime import datetime
from typing import List, Tuple, Optional, Dict, Any
import uuid
import math
from enum import Enum


class MeasurementType(str, Enum):
    """Types of measurements that can be performed."""

    WIDTH = "width"
    HEIGHT = "height"
    LENGTH = "length"
    AREA = "area"
    PERIMETER = "perimeter"
    COUNT = "count"


class MeasurementMethod(str, Enum):
    """Methods used to derive measurements."""

    VECTOR_GEOMETRY = "vector_geometry"  # From PDF vector paths
    BBOX_SCALED = "bbox_scaled"  # From bounding box with scale
    POLYGON_AREA = "polygon_area"  # Calculated from polygon vertices
    ARC_RADIUS = "arc_radius"  # Door width from swing arc
    LINE_LENGTH = "line_length"  # Direct line measurement
    MANUAL = "manual"  # User-provided measurement


@dataclass
class Sector:
    """
    Represents a sector/zone for area calculations and queries.

    Sectors can be rooms, zones, floors, or any defined area.
    Used for queries like "Count windows in Apartment 3".

    Fields:
        sector_id: Unique identifier for this sector
        file_id: The file/document this sector belongs to
        page_number: Page number where sector is defined
        name: Human-readable name (e.g., "Living Room", "Zone A")
        polygon_points: List of (x, y) vertices in pixel coordinates
        sector_type: Classification ("room", "zone", "floor")
        area_m2: Calculated area in square meters (populated after measurement)
        perimeter_m: Calculated perimeter in meters (populated after measurement)
        created_at: When this sector was created
        metadata: Additional attributes (color, tags, etc.)
    """

    sector_id: str
    file_id: str
    page_number: int
    name: str
    polygon_points: List[Tuple[float, float]]  # Closed polygon vertices
    sector_type: Optional[str] = None  # "room", "zone", "floor"
    area_m2: Optional[float] = None
    perimeter_m: Optional[float] = None
    created_at: Optional[datetime] = None
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return {
            "sector_id": self.sector_id,
            "file_id": self.file_id,
            "page_number": self.page_number,
            "name": self.name,
            "polygon_points": [list(p) for p in self.polygon_points],
            "sector_type": self.sector_type,
            "area_m2": self.area_m2,
            "perimeter_m": self.perimeter_m,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "metadata": self.metadata,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "Sector":
        """Create Sector from dictionary."""
        created_at = None
        if data.get("created_at"):
            if isinstance(data["created_at"], datetime):
                created_at = data["created_at"]
            else:
                created_at = datetime.fromisoformat(data["created_at"].replace("Z", "+00:00"))

        return cls(
            sector_id=data.get("sector_id") or data.get("id", ""),
            file_id=data.get("file_id", ""),
            page_number=data.get("page_number", 1),
            name=data.get("name", ""),
            polygon_points=[tuple(p) for p in data.get("polygon_points", [])],
            sector_type=data.get("sector_type"),
            area_m2=data.get("area_m2"),
            perimeter_m=data.get("perimeter_m"),
            created_at=created_at,
            metadata=data.get("metadata") or data.get("attributes", {}),
        )

    def contains_point(self, x: float, y: float) -> bool:
        """
        Check if a point is inside this sector using ray casting algorithm.

        Args:
            x: X coordinate of the point
            y: Y coordinate of the point

        Returns:
            True if point is inside the polygon
        """
        n = len(self.polygon_points)
        if n < 3:
            return False

        inside = False
        j = n - 1

        for i in range(n):
            xi, yi = self.polygon_points[i]
            xj, yj = self.polygon_points[j]

            if ((yi > y) != (yj > y)) and (x < (xj - xi) * (y - yi) / (yj - yi) + xi):
                inside = not inside

            j = i

        return inside


@dataclass
class MeasurementResult:
    """
    Result of a measurement operation with full auditability.

    Every measurement includes source tracing for zero-hallucination principle.

    Fields:
        measurement_id: Unique identifier for this measurement
        measurement_type: Type of measurement (area, width, height, etc.)
        value: The measured value
        unit: Unit of measurement ("m", "m2", "count")
        file_id: Source file/document
        page_number: Source page number
        confidence: Confidence score (0.0 to 1.0)
        method: How the measurement was derived
        assumptions: List of assumptions made during measurement
        source: Description of the source (sector name, object type, etc.)
        sector_id: Optional sector this measurement belongs to
        object_id: Optional detected object this measurement is for
        scale_context_id: Scale context used for conversion
        source_bbox: Bounding box of source in pixels (x, y, w, h)
        created_at: When this measurement was created
    """

    measurement_id: str
    measurement_type: str  # "area", "width", "height", "perimeter", "count"
    value: float
    unit: str  # "m", "m2", "count"
    file_id: str
    page_number: int
    confidence: float = 1.0
    method: str = MeasurementMethod.POLYGON_AREA.value
    assumptions: List[str] = field(default_factory=list)
    source: Optional[str] = None  # "Sector: Living Room", "Door: D-101"
    sector_id: Optional[str] = None
    object_id: Optional[str] = None
    scale_context_id: Optional[str] = None
    source_bbox: Optional[Tuple[float, float, float, float]] = None
    created_at: Optional[datetime] = None

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return {
            "measurement_id": self.measurement_id,
            "measurement_type": self.measurement_type,
            "value": self.value,
            "unit": self.unit,
            "file_id": self.file_id,
            "page_number": self.page_number,
            "confidence": self.confidence,
            "method": self.method,
            "assumptions": self.assumptions,
            "source": self.source,
            "sector_id": self.sector_id,
            "object_id": self.object_id,
            "scale_context_id": self.scale_context_id,
            "source_bbox": list(self.source_bbox) if self.source_bbox else None,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "MeasurementResult":
        """Create MeasurementResult from dictionary."""
        created_at = None
        if data.get("created_at"):
            if isinstance(data["created_at"], datetime):
                created_at = data["created_at"]
            else:
                created_at = datetime.fromisoformat(data["created_at"].replace("Z", "+00:00"))

        source_bbox = None
        if data.get("source_bbox"):
            source_bbox = tuple(data["source_bbox"])

        return cls(
            measurement_id=data.get("measurement_id") or data.get("id", ""),
            measurement_type=data.get("measurement_type", ""),
            value=data.get("value", 0.0),
            unit=data.get("unit", ""),
            file_id=data.get("file_id", ""),
            page_number=data.get("page_number") or data.get("source_page", 1),
            confidence=data.get("confidence", 1.0),
            method=data.get("method", ""),
            assumptions=data.get("assumptions", []),
            source=data.get("source"),
            sector_id=data.get("sector_id"),
            object_id=data.get("object_id") or data.get("detected_object_id"),
            scale_context_id=data.get("scale_context_id"),
            source_bbox=source_bbox,
            created_at=created_at,
        )


@dataclass
class SectorQueryResult:
    """Result of querying objects within a sector."""

    sector_id: str
    sector_name: str
    query_type: str
    total_count: int
    objects: List[Dict[str, Any]]
    measurements: List[MeasurementResult] = field(default_factory=list)
    summary: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return {
            "sector_id": self.sector_id,
            "sector_name": self.sector_name,
            "query_type": self.query_type,
            "total_count": self.total_count,
            "objects": self.objects,
            "measurements": [m.to_dict() for m in self.measurements],
            "summary": self.summary,
        }


def generate_measurement_id() -> str:
    """Generate a unique measurement ID."""
    return f"meas_{uuid.uuid4().hex[:12]}"


def generate_sector_id() -> str:
    """Generate a unique sector ID."""
    return f"sect_{uuid.uuid4().hex[:12]}"


async def measure_object(
    obj: "DetectedObject",  # noqa: F821 - forward reference
    scale: "ScaleContext",  # noqa: F821 - forward reference
) -> MeasurementResult:
    """
    Calculate real-world dimensions from a detected object.

    Uses the bounding box and scale context to estimate dimensions.
    For more accurate measurements, use vector geometry when available.

    Args:
        obj: DetectedObject with bounding box
        scale: ScaleContext for pixel-to-meter conversion

    Returns:
        MeasurementResult with calculated dimensions

    Raises:
        NotImplementedError: Phase D implementation pending
    """
    # TODO: Phase D implementation
    # 1. Get bounding box dimensions in pixels
    # 2. Convert to meters using scale.px_to_meters()
    # 3. For doors: use arc radius if available in attributes
    # 4. Calculate confidence based on scale confidence and detection confidence
    raise NotImplementedError("Phase D implementation - object measurement pending")


def shoelace_area_pixels(polygon_points: List[Tuple[float, float]]) -> float:
    """
    Calculate the area of a polygon in pixel² using the Shoelace formula.

    The Shoelace formula (also known as Gauss's area formula):
    A = 0.5 * |Σ(x_i * y_{i+1} - x_{i+1} * y_i)|

    This is a pure geometric calculation - no unit conversion.

    Args:
        polygon_points: List of (x, y) vertices in any coordinate system.
                       Must have at least 3 points.
                       Polygon is automatically closed.

    Returns:
        Area in squared units (same as input coordinate units).
        Always returns positive value (absolute).

    Raises:
        ValueError: If polygon has fewer than 3 points.
    """
    n = len(polygon_points)
    if n < 3:
        raise ValueError(f"Polygon must have at least 3 points, got {n}")

    # Shoelace formula
    area = 0.0
    for i in range(n):
        j = (i + 1) % n  # Wrap around to close the polygon
        xi, yi = polygon_points[i]
        xj, yj = polygon_points[j]
        area += xi * yj
        area -= xj * yi

    return abs(area) / 2.0


def shoelace_perimeter_pixels(polygon_points: List[Tuple[float, float]]) -> float:
    """
    Calculate the perimeter of a polygon in pixels.

    Sums the Euclidean distance between consecutive vertices.

    Args:
        polygon_points: List of (x, y) vertices in pixel coordinates.
                       Must have at least 2 points for any perimeter.
                       Polygon is automatically closed.

    Returns:
        Perimeter in pixels.

    Raises:
        ValueError: If polygon has fewer than 2 points.
    """
    n = len(polygon_points)
    if n < 2:
        raise ValueError(f"Polygon must have at least 2 points, got {n}")

    perimeter = 0.0
    for i in range(n):
        j = (i + 1) % n  # Wrap around to close the polygon
        xi, yi = polygon_points[i]
        xj, yj = polygon_points[j]
        distance = math.sqrt((xj - xi) ** 2 + (yj - yi) ** 2)
        perimeter += distance

    return perimeter


def compute_sector_area_m2(
    polygon_points: List[Tuple[float, float]],
    pixels_per_meter: float,
) -> float:
    """
    Compute sector area in square meters from polygon points and scale.

    Uses the Shoelace formula for polygon area calculation, then
    converts from pixels² to meters² using the scale factor.

    Conversion: area_m2 = area_pixels / (pixels_per_meter²)

    Args:
        polygon_points: List of (x, y) vertices in pixel coordinates.
        pixels_per_meter: Scale factor from calibration.

    Returns:
        Area in square meters.

    Raises:
        ValueError: If polygon has fewer than 3 points or scale is invalid.
    """
    if pixels_per_meter <= 0:
        raise ValueError(f"pixels_per_meter must be positive, got {pixels_per_meter}")

    area_pixels = shoelace_area_pixels(polygon_points)
    area_m2 = area_pixels / (pixels_per_meter ** 2)

    return area_m2


def compute_sector_perimeter_m(
    polygon_points: List[Tuple[float, float]],
    pixels_per_meter: float,
) -> float:
    """
    Compute sector perimeter in meters from polygon points and scale.

    Args:
        polygon_points: List of (x, y) vertices in pixel coordinates.
        pixels_per_meter: Scale factor from calibration.

    Returns:
        Perimeter in meters.

    Raises:
        ValueError: If polygon has fewer than 2 points or scale is invalid.
    """
    if pixels_per_meter <= 0:
        raise ValueError(f"pixels_per_meter must be positive, got {pixels_per_meter}")

    perimeter_pixels = shoelace_perimeter_pixels(polygon_points)
    perimeter_m = perimeter_pixels / pixels_per_meter

    return perimeter_m


async def calculate_polygon_area(
    polygon_points: List[Tuple[float, float]],
    scale: "ScaleContext",  # noqa: F821 - forward reference
) -> float:
    """
    Calculate area of a polygon in square meters using Shoelace formula.

    Args:
        polygon_points: List of (x, y) vertices in pixel coordinates
        scale: ScaleContext for pixel-to-meter conversion

    Returns:
        Area in square meters
    """
    if scale.pixels_per_meter is None:
        raise ValueError("ScaleContext must have pixels_per_meter set")

    return compute_sector_area_m2(polygon_points, scale.pixels_per_meter)


async def calculate_polygon_perimeter(
    polygon_points: List[Tuple[float, float]],
    scale: "ScaleContext",  # noqa: F821 - forward reference
) -> float:
    """
    Calculate perimeter of a polygon in meters.

    Args:
        polygon_points: List of (x, y) vertices in pixel coordinates
        scale: ScaleContext for pixel-to-meter conversion

    Returns:
        Perimeter in meters
    """
    if scale.pixels_per_meter is None:
        raise ValueError("ScaleContext must have pixels_per_meter set")

    return compute_sector_perimeter_m(polygon_points, scale.pixels_per_meter)


async def calculate_sector_area(
    sector: Sector,
    scale: "ScaleContext",  # noqa: F821 - forward reference
) -> float:
    """
    Calculate area of a sector in square meters.

    Updates the sector's area_m2 field in place.

    Args:
        sector: Sector with polygon points
        scale: ScaleContext for conversion

    Returns:
        Area in square meters
    """
    area = await calculate_polygon_area(sector.polygon_points, scale)
    sector.area_m2 = area
    return area


async def calculate_sector_perimeter(
    sector: Sector,
    scale: "ScaleContext",  # noqa: F821 - forward reference
) -> float:
    """
    Calculate perimeter of a sector in meters.

    Updates the sector's perimeter_m field in place.

    Args:
        sector: Sector with polygon points
        scale: ScaleContext for conversion

    Returns:
        Perimeter in meters
    """
    perimeter = await calculate_polygon_perimeter(sector.polygon_points, scale)
    sector.perimeter_m = perimeter
    return perimeter


async def query_sector(
    sector: Sector,
    objects: List["DetectedObject"],  # noqa: F821 - forward reference
    query_type: "ObjectType",  # noqa: F821 - forward reference
    include_measurements: bool = True,
    scale: Optional["ScaleContext"] = None,  # noqa: F821 - forward reference
) -> SectorQueryResult:
    """
    Query objects within a sector.

    Example queries:
    - "How many doors in Apartment 3?"
    - "What's the total window count in Zone B?"
    - "List all fixtures in the bathroom"

    Args:
        sector: Sector to query within
        objects: All detected objects to filter
        query_type: Type of objects to count/list
        include_measurements: Whether to include measurements for each object
        scale: ScaleContext for measurements (required if include_measurements=True)

    Returns:
        SectorQueryResult with objects and optional measurements

    Raises:
        NotImplementedError: Phase E implementation pending
    """
    # TODO: Phase E implementation
    # 1. Filter objects by type
    # 2. Filter objects by sector containment (point-in-polygon)
    # 3. Optionally calculate measurements for each object
    # 4. Generate summary statistics
    raise NotImplementedError("Phase E implementation - sector queries pending")


async def calculate_material_quantity(
    sector: Sector,
    material_type: str,
    scale: "ScaleContext",  # noqa: F821 - forward reference
) -> Dict[str, Any]:
    """
    Calculate material quantities for a sector.

    Supported material types:
    - "flooring": Area calculation excluding wet rooms
    - "drywall": Wall area calculation
    - "ceiling": Ceiling area (same as floor area)
    - "paint": Wall area for painting

    Args:
        sector: Sector to calculate for
        material_type: Type of material to calculate
        scale: ScaleContext for conversion

    Returns:
        Dictionary with quantity and unit

    Raises:
        NotImplementedError: Phase E implementation pending
    """
    # TODO: Phase E implementation
    # 1. Calculate base area from sector polygon
    # 2. Apply material-specific adjustments
    # 3. Return quantity with unit
    raise NotImplementedError("Phase E implementation - material quantities pending")

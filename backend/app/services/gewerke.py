"""
Gewerke (Trade Modules) Service for SnapGrid.

Trade-specific quantity takeoff logic that sits on top of existing extraction
and measurement services.

Current Gewerke:
- DOORS (Türen): Parse door schedules and produce structured door lists
- DRYWALL (Trockenbau): Calculate wall length and drywall area for sectors

Every result includes full auditability back to source documents.
"""

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple
from uuid import uuid4

from .schedule_extraction import ExtractionResult, ExtractedCell, extract_schedules_from_pdf
from .vector_measurement import (
    WallSegment,
    extract_wall_segments_from_page,
    compute_wall_length_in_sector_m,
    compute_drywall_area_in_sector_m2,
)
from .measurement_engine import Sector, MeasurementResult
from .scale_calibration import ScaleContext


# =============================================================================
# Door Gewerk Data Models
# =============================================================================


class DoorCategory(str, Enum):
    """Standard door categories based on fire rating and type."""
    T30 = "T30"       # 30-minute fire-rated
    T90 = "T90"       # 90-minute fire-rated
    DSS = "DSS"       # Smoke protection (Dichtschließend/Rauchschutz)
    STANDARD = "Standard"  # No special rating
    UNKNOWN = "Unknown"


@dataclass
class DoorGewerkItem:
    """
    A single door entry from the door schedule.

    Normalized and enriched with category classification.
    """
    item_id: str
    position: Optional[str] = None  # Position number in schedule
    door_number: Optional[str] = None
    room: Optional[str] = None
    door_type: Optional[str] = None  # Raw type from schedule
    fire_rating: Optional[str] = None  # e.g., "T30", "T90", "RS"
    width_m: Optional[float] = None
    height_m: Optional[float] = None
    remarks: Optional[str] = None
    category: DoorCategory = DoorCategory.UNKNOWN

    # Auditability
    source_page: int = 0
    source_row_index: int = 0
    confidence: float = 1.0
    raw_data: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "item_id": self.item_id,
            "position": self.position,
            "door_number": self.door_number,
            "room": self.room,
            "door_type": self.door_type,
            "fire_rating": self.fire_rating,
            "width_m": self.width_m,
            "height_m": self.height_m,
            "remarks": self.remarks,
            "category": self.category.value,
            "source_page": self.source_page,
            "source_row_index": self.source_row_index,
            "confidence": self.confidence,
            "raw_data": self.raw_data,
        }


@dataclass
class DoorGewerkSummary:
    """
    Summary statistics for the door gewerk.
    """
    total_doors: int = 0
    count_t30: int = 0
    count_t90: int = 0
    count_dss: int = 0
    count_standard: int = 0
    count_unknown: int = 0

    # Grouped counts
    by_type: Dict[str, int] = field(default_factory=dict)
    by_fire_rating: Dict[str, int] = field(default_factory=dict)
    by_category: Dict[str, int] = field(default_factory=dict)

    # Dimensions
    unique_widths: List[float] = field(default_factory=list)
    unique_heights: List[float] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "total_doors": self.total_doors,
            "count_t30": self.count_t30,
            "count_t90": self.count_t90,
            "count_dss": self.count_dss,
            "count_standard": self.count_standard,
            "count_unknown": self.count_unknown,
            "by_type": self.by_type,
            "by_fire_rating": self.by_fire_rating,
            "by_category": self.by_category,
            "unique_widths": self.unique_widths,
            "unique_heights": self.unique_heights,
        }


@dataclass
class DoorGewerkResult:
    """
    Complete result from the door gewerk.
    """
    gewerk_id: str
    gewerk_type: str = "doors"
    source_file: str = ""
    extraction_id: str = ""
    processed_at: str = ""
    status: str = "ok"

    items: List[DoorGewerkItem] = field(default_factory=list)
    summary: DoorGewerkSummary = field(default_factory=DoorGewerkSummary)

    errors: List[str] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "gewerk_id": self.gewerk_id,
            "gewerk_type": self.gewerk_type,
            "source_file": self.source_file,
            "extraction_id": self.extraction_id,
            "processed_at": self.processed_at,
            "status": self.status,
            "items": [item.to_dict() for item in self.items],
            "summary": self.summary.to_dict(),
            "errors": self.errors,
            "warnings": self.warnings,
        }


# =============================================================================
# Drywall Gewerk Data Models
# =============================================================================


@dataclass
class DrywallGewerkItem:
    """
    Drywall measurement for a single sector.
    """
    item_id: str
    sector_id: str
    sector_name: str
    page_number: int

    # Measurements
    wall_length_m: float
    wall_height_m: float
    drywall_area_m2: float

    # Segment details
    wall_segment_count: int = 0

    # Auditability
    measurement_ids: List[str] = field(default_factory=list)
    scale_context_id: Optional[str] = None
    confidence: float = 1.0
    assumptions: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "item_id": self.item_id,
            "sector_id": self.sector_id,
            "sector_name": self.sector_name,
            "page_number": self.page_number,
            "wall_length_m": self.wall_length_m,
            "wall_height_m": self.wall_height_m,
            "drywall_area_m2": self.drywall_area_m2,
            "wall_segment_count": self.wall_segment_count,
            "measurement_ids": self.measurement_ids,
            "scale_context_id": self.scale_context_id,
            "confidence": self.confidence,
            "assumptions": self.assumptions,
        }


@dataclass
class DrywallGewerkSummary:
    """
    Summary statistics for the drywall gewerk.
    """
    total_sectors: int = 0
    total_wall_length_m: float = 0.0
    total_drywall_area_m2: float = 0.0
    average_wall_height_m: float = 0.0

    def to_dict(self) -> Dict[str, Any]:
        return {
            "total_sectors": self.total_sectors,
            "total_wall_length_m": round(self.total_wall_length_m, 4),
            "total_drywall_area_m2": round(self.total_drywall_area_m2, 4),
            "average_wall_height_m": round(self.average_wall_height_m, 2),
        }


@dataclass
class DrywallGewerkResult:
    """
    Complete result from the drywall gewerk.
    """
    gewerk_id: str
    gewerk_type: str = "drywall"
    source_file: str = ""
    processed_at: str = ""
    status: str = "ok"

    items: List[DrywallGewerkItem] = field(default_factory=list)
    summary: DrywallGewerkSummary = field(default_factory=DrywallGewerkSummary)

    errors: List[str] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "gewerk_id": self.gewerk_id,
            "gewerk_type": self.gewerk_type,
            "source_file": self.source_file,
            "processed_at": self.processed_at,
            "status": self.status,
            "items": [item.to_dict() for item in self.items],
            "summary": self.summary.to_dict(),
            "errors": self.errors,
            "warnings": self.warnings,
        }


# =============================================================================
# Door Gewerk Functions
# =============================================================================


def _classify_door_category(
    fire_rating: Optional[str],
    door_type: Optional[str],
) -> DoorCategory:
    """
    Classify a door into a category based on fire rating and type.

    Priority:
    1. T30/T90 from fire_rating
    2. DSS (smoke protection) patterns
    3. Standard if no special markers
    """
    # Normalize inputs
    fr = (fire_rating or "").upper().strip()
    dt = (door_type or "").upper().strip()
    combined = f"{fr} {dt}"

    # Check for T90 first (more restrictive)
    if "T90" in combined or "T-90" in combined:
        return DoorCategory.T90

    # Check for T30
    if "T30" in combined or "T-30" in combined:
        return DoorCategory.T30

    # Check for smoke protection (DSS = Dichtschließend, RS = Rauchschutz)
    if any(marker in combined for marker in ["DSS", "RS", "RAUCHSCHUTZ", "DICHTSCHLIESSEND"]):
        return DoorCategory.DSS

    # If we have some type info but no fire rating, it's standard
    if door_type or fire_rating:
        return DoorCategory.STANDARD

    return DoorCategory.UNKNOWN


def _extract_cell_value(cell: Optional[ExtractedCell]) -> Any:
    """Safely extract value from a cell."""
    if cell is None:
        return None
    return cell.value


def _generate_gewerk_id() -> str:
    """Generate a unique gewerk ID."""
    return f"gew_{uuid4().hex[:12]}"


def _generate_item_id(prefix: str = "item") -> str:
    """Generate a unique item ID."""
    return f"{prefix}_{uuid4().hex[:8]}"


def run_door_gewerk_from_schedule(
    extraction_result: ExtractionResult,
) -> DoorGewerkResult:
    """
    Transform a schedule ExtractionResult into a structured DoorGewerkResult.

    This function:
    1. Iterates through all extracted table rows
    2. Maps normalized headers to door attributes
    3. Classifies each door by category (T30, T90, DSS, Standard)
    4. Computes summary statistics

    Args:
        extraction_result: Result from extract_schedules_from_pdf()

    Returns:
        DoorGewerkResult with structured door list and summary
    """
    result = DoorGewerkResult(
        gewerk_id=_generate_gewerk_id(),
        source_file=extraction_result.source_file,
        extraction_id=extraction_result.extraction_id,
        processed_at=datetime.utcnow().isoformat() + "Z",
    )

    # Track summary data
    widths: List[float] = []
    heights: List[float] = []
    by_type: Dict[str, int] = {}
    by_fire_rating: Dict[str, int] = {}
    by_category: Dict[str, int] = {}

    # Process each table and row
    for table in extraction_result.tables:
        for row_idx, row in enumerate(table.rows):
            # Extract values from normalized headers
            position = _extract_cell_value(row.get("pos"))
            door_number = _extract_cell_value(row.get("door_number"))
            room = _extract_cell_value(row.get("room"))
            door_type = _extract_cell_value(row.get("type"))
            fire_rating = _extract_cell_value(row.get("fire_rating"))
            width_m = _extract_cell_value(row.get("width_m"))
            height_m = _extract_cell_value(row.get("height_m"))
            remarks = _extract_cell_value(row.get("remarks"))

            # Classify category
            category = _classify_door_category(fire_rating, door_type)

            # Build raw_data for auditability
            raw_data = {
                k: v.to_dict() if hasattr(v, 'to_dict') else str(v)
                for k, v in row.items()
            }

            # Create door item
            item = DoorGewerkItem(
                item_id=_generate_item_id("door"),
                position=str(position) if position else None,
                door_number=str(door_number) if door_number else None,
                room=str(room) if room else None,
                door_type=str(door_type) if door_type else None,
                fire_rating=str(fire_rating) if fire_rating else None,
                width_m=float(width_m) if width_m else None,
                height_m=float(height_m) if height_m else None,
                remarks=str(remarks) if remarks else None,
                category=category,
                source_page=table.page_number,
                source_row_index=row_idx,
                confidence=table.confidence,
                raw_data=raw_data,
            )
            result.items.append(item)

            # Update summary tracking
            if door_type:
                dt_str = str(door_type)
                by_type[dt_str] = by_type.get(dt_str, 0) + 1

            if fire_rating:
                fr_str = str(fire_rating)
                by_fire_rating[fr_str] = by_fire_rating.get(fr_str, 0) + 1

            cat_str = category.value
            by_category[cat_str] = by_category.get(cat_str, 0) + 1

            if width_m:
                widths.append(float(width_m))
            if height_m:
                heights.append(float(height_m))

    # Build summary
    result.summary = DoorGewerkSummary(
        total_doors=len(result.items),
        count_t30=by_category.get(DoorCategory.T30.value, 0),
        count_t90=by_category.get(DoorCategory.T90.value, 0),
        count_dss=by_category.get(DoorCategory.DSS.value, 0),
        count_standard=by_category.get(DoorCategory.STANDARD.value, 0),
        count_unknown=by_category.get(DoorCategory.UNKNOWN.value, 0),
        by_type=by_type,
        by_fire_rating=by_fire_rating,
        by_category=by_category,
        unique_widths=sorted(set(widths)),
        unique_heights=sorted(set(heights)),
    )

    # Add warnings if needed
    if result.summary.count_unknown > 0:
        result.warnings.append(
            f"{result.summary.count_unknown} doors could not be categorized"
        )

    if result.summary.total_doors == 0:
        result.warnings.append("No doors found in schedule")

    # Copy errors from extraction
    result.errors = extraction_result.errors.copy()
    if extraction_result.status != "ok":
        result.status = "partial"

    return result


async def run_door_gewerk_from_pdf(
    pdf_path: str,
) -> DoorGewerkResult:
    """
    Run the full door gewerk pipeline from a PDF file.

    This is a convenience wrapper that:
    1. Extracts schedules from the PDF
    2. Transforms to door gewerk result

    Args:
        pdf_path: Path to the door schedule PDF

    Returns:
        DoorGewerkResult with structured door list and summary
    """
    # Extract schedules
    extraction = extract_schedules_from_pdf(pdf_path)

    # Transform to gewerk result
    return run_door_gewerk_from_schedule(extraction)


# =============================================================================
# Drywall Gewerk Functions
# =============================================================================


def run_drywall_gewerk_for_sector(
    *,
    pdf_path: str,
    sector: Sector,
    scale_context: ScaleContext,
    wall_height_m: float,
    render_dpi: int = 150,
    min_segment_length_px: float = 5.0,
) -> DrywallGewerkResult:
    """
    Calculate drywall area for a single sector.

    This function:
    1. Extracts wall segments from the PDF page
    2. Filters to segments within the sector polygon
    3. Computes wall length using scale context
    4. Computes drywall area = wall_length * wall_height

    Args:
        pdf_path: Path to the floor plan PDF
        sector: Sector polygon defining the area of interest
        scale_context: Scale context for pixel-to-meter conversion
        wall_height_m: Wall height in meters (user-provided)
        render_dpi: DPI for PDF rendering (default 150)
        min_segment_length_px: Minimum segment length to include

    Returns:
        DrywallGewerkResult with single item and summary

    Raises:
        ValueError: If wall_height_m is not positive
        ValueError: If scale_context has no valid pixels_per_meter
    """
    result = DrywallGewerkResult(
        gewerk_id=_generate_gewerk_id(),
        source_file=str(pdf_path),
        processed_at=datetime.utcnow().isoformat() + "Z",
    )

    # Validate inputs
    if wall_height_m <= 0:
        result.status = "error"
        result.errors.append(f"wall_height_m must be positive, got {wall_height_m}")
        return result

    if not scale_context.has_scale:
        result.status = "error"
        result.errors.append("ScaleContext must have valid pixels_per_meter")
        return result

    try:
        # Extract wall segments from the page
        wall_segments = extract_wall_segments_from_page(
            path=pdf_path,
            page_number=sector.page_number,
            dpi=render_dpi,
            min_length_px=min_segment_length_px,
        )

        if not wall_segments:
            result.warnings.append(f"No wall segments found on page {sector.page_number}")

        # Compute wall length in sector
        wall_length_result = compute_wall_length_in_sector_m(
            wall_segments=wall_segments,
            sector=sector,
            scale_context=scale_context,
            require_both_endpoints=True,
        )

        # Compute drywall area
        drywall_area_result = compute_drywall_area_in_sector_m2(
            wall_segments=wall_segments,
            sector=sector,
            scale_context=scale_context,
            wall_height_m=wall_height_m,
            require_both_endpoints=True,
        )

        # Extract segment count from assumptions
        segment_count = 0
        for assumption in wall_length_result.assumptions:
            if assumption.startswith("segment_count:"):
                segment_count = int(assumption.split(":")[1].strip())
                break

        # Build item
        item = DrywallGewerkItem(
            item_id=_generate_item_id("drywall"),
            sector_id=sector.sector_id,
            sector_name=sector.name,
            page_number=sector.page_number,
            wall_length_m=wall_length_result.value,
            wall_height_m=wall_height_m,
            drywall_area_m2=drywall_area_result.value,
            wall_segment_count=segment_count,
            measurement_ids=[
                wall_length_result.measurement_id,
                drywall_area_result.measurement_id,
            ],
            scale_context_id=scale_context.id,
            confidence=min(wall_length_result.confidence, drywall_area_result.confidence),
            assumptions=drywall_area_result.assumptions,
        )
        result.items.append(item)

        # Build summary
        result.summary = DrywallGewerkSummary(
            total_sectors=1,
            total_wall_length_m=wall_length_result.value,
            total_drywall_area_m2=drywall_area_result.value,
            average_wall_height_m=wall_height_m,
        )

    except Exception as e:
        result.status = "error"
        result.errors.append(str(e))

    return result


def run_drywall_gewerk_for_sectors(
    *,
    pdf_path: str,
    sectors: List[Sector],
    scale_context: ScaleContext,
    wall_height_m: float,
    render_dpi: int = 150,
    min_segment_length_px: float = 5.0,
) -> DrywallGewerkResult:
    """
    Calculate drywall area for multiple sectors.

    Aggregates results across all sectors into a single result.

    Args:
        pdf_path: Path to the floor plan PDF
        sectors: List of Sector polygons
        scale_context: Scale context for pixel-to-meter conversion
        wall_height_m: Wall height in meters (user-provided)
        render_dpi: DPI for PDF rendering (default 150)
        min_segment_length_px: Minimum segment length to include

    Returns:
        DrywallGewerkResult with items for each sector and aggregated summary
    """
    result = DrywallGewerkResult(
        gewerk_id=_generate_gewerk_id(),
        source_file=str(pdf_path),
        processed_at=datetime.utcnow().isoformat() + "Z",
    )

    total_length = 0.0
    total_area = 0.0

    for sector in sectors:
        sector_result = run_drywall_gewerk_for_sector(
            pdf_path=pdf_path,
            sector=sector,
            scale_context=scale_context,
            wall_height_m=wall_height_m,
            render_dpi=render_dpi,
            min_segment_length_px=min_segment_length_px,
        )

        # Aggregate items
        result.items.extend(sector_result.items)
        result.warnings.extend(sector_result.warnings)
        result.errors.extend(sector_result.errors)

        # Aggregate totals
        for item in sector_result.items:
            total_length += item.wall_length_m
            total_area += item.drywall_area_m2

    # Build aggregated summary
    result.summary = DrywallGewerkSummary(
        total_sectors=len(sectors),
        total_wall_length_m=total_length,
        total_drywall_area_m2=total_area,
        average_wall_height_m=wall_height_m,
    )

    if result.errors:
        result.status = "partial" if result.items else "error"

    return result


# =============================================================================
# Exports
# =============================================================================


__all__ = [
    # Door Gewerk
    "DoorCategory",
    "DoorGewerkItem",
    "DoorGewerkSummary",
    "DoorGewerkResult",
    "run_door_gewerk_from_schedule",
    "run_door_gewerk_from_pdf",
    # Drywall Gewerk
    "DrywallGewerkItem",
    "DrywallGewerkSummary",
    "DrywallGewerkResult",
    "run_drywall_gewerk_for_sector",
    "run_drywall_gewerk_for_sectors",
]

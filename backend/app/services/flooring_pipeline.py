"""
Flooring Pipeline Service

Geometry-first pipeline for flooring area extraction from blueprints.
Routes to Vector or Raster pipeline based on input type.

Design principle: Deterministic geometry extraction first, AI only as helper.
"""

from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import List, Optional, Dict, Any, Tuple
import logging
import tempfile
import time

logger = logging.getLogger(__name__)

# Local imports
from .input_router import (
    analyze_input,
    InputAnalysis,
    InputType,
    ProcessingPipeline,
)
from .scale_calibration import (
    ScaleContext,
    detect_scale_from_text,
    compute_pixels_per_meter,
    DetectionMethod,
)


class PipelineMethod(str, Enum):
    """Processing method used for extraction."""
    VECTOR = "vector"
    RASTER = "raster"
    TEXT_EXTRACTION = "text_extraction"
    HYBRID = "hybrid"
    FAILED = "failed"


@dataclass
class RoomPolygon:
    """Represents a detected room polygon."""
    id: str
    points: List[Tuple[float, float]]  # [(x, y), ...]
    area_px: float
    area_m2: Optional[float] = None
    perimeter_px: float = 0.0
    perimeter_m: Optional[float] = None
    confidence: float = 1.0
    label: Optional[str] = None
    page_number: int = 1
    source: str = "unknown"  # "vector", "contour", etc.

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return {
            "id": self.id,
            "points": self.points,
            "area_px": self.area_px,
            "area_m2": self.area_m2,
            "perimeter_px": self.perimeter_px,
            "perimeter_m": self.perimeter_m,
            "confidence": self.confidence,
            "label": self.label,
            "page_number": self.page_number,
            "source": self.source,
        }


@dataclass
class FlooringResult:
    """Result from flooring area extraction."""

    # Summary
    total_area_m2: Optional[float] = None
    total_area_px: float = 0.0
    room_count: int = 0

    # Individual rooms
    rooms: List[RoomPolygon] = field(default_factory=list)

    # Scale information
    scale: Optional[ScaleContext] = None

    # Diagnostics
    pipeline_used: PipelineMethod = PipelineMethod.FAILED
    processing_time_ms: float = 0.0
    page_number: int = 1
    warnings: List[str] = field(default_factory=list)

    # Traceability
    input_analysis: Optional[InputAnalysis] = None

    # Status
    needs_user_confirmation: bool = False
    confirmation_reason: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return {
            "total_area_m2": self.total_area_m2,
            "total_area_px": self.total_area_px,
            "room_count": self.room_count,
            "rooms": [r.to_dict() for r in self.rooms],
            "scale": self.scale.to_dict() if self.scale else None,
            "pipeline_used": self.pipeline_used.value,
            "processing_time_ms": self.processing_time_ms,
            "page_number": self.page_number,
            "warnings": self.warnings,
            "needs_user_confirmation": self.needs_user_confirmation,
            "confirmation_reason": self.confirmation_reason,
        }


def analyze_flooring(
    file_path: str,
    page_number: int = 1,
    scale: Optional[int] = None,  # User-provided scale (e.g., 100 for 1:100)
    dpi: int = 300,
) -> FlooringResult:
    """
    Main entry point for flooring area extraction.

    Routes to appropriate pipeline based on input type:
    - Vector PDF → Vector Pipeline (preferred)
    - Scanned PDF / Photo → Raster Pipeline

    Args:
        file_path: Path to PDF or image file
        page_number: Page to analyze (1-indexed)
        scale: Optional user-provided scale (e.g., 100 for 1:100)
        dpi: Render DPI for image processing

    Returns:
        FlooringResult with detected rooms and areas
    """
    start_time = time.time()
    result = FlooringResult(page_number=page_number)

    # Step 1: Analyze input type
    try:
        analysis = analyze_input(file_path)
        result.input_analysis = analysis

        if analysis.input_type == InputType.UNKNOWN:
            result.warnings.extend(analysis.warnings)
            result.pipeline_used = PipelineMethod.FAILED
            return result

    except Exception as e:
        logger.error(f"Input analysis failed: {e}")
        result.warnings.append(f"Input analysis failed: {str(e)}")
        result.pipeline_used = PipelineMethod.FAILED
        return result

    # Step 2: Route to appropriate pipeline
    try:
        if analysis.input_type == InputType.CAD_WITH_TEXT:
            # Best case: German CAD PDF with annotations
            # Try text extraction first (NRF values)
            result = _try_text_extraction(file_path, page_number, result)

            if result.room_count == 0:
                # Fall back to vector pipeline
                result = _run_vector_pipeline(file_path, page_number, dpi, scale, result)

        elif analysis.input_type == InputType.CAD_NO_TEXT:
            # Vector PDF without annotations - use geometry
            result = _run_vector_pipeline(file_path, page_number, dpi, scale, result)

        elif analysis.input_type in [InputType.SCANNED_PDF, InputType.PHOTO]:
            # Raster input - use OpenCV contour detection
            result = _run_raster_pipeline(file_path, page_number, dpi, scale, result)

        else:
            # Unknown - try hybrid
            result = _run_hybrid_pipeline(file_path, page_number, dpi, scale, result)

    except Exception as e:
        logger.error(f"Pipeline execution failed: {e}")
        result.warnings.append(f"Pipeline failed: {str(e)}")
        result.pipeline_used = PipelineMethod.FAILED

    # Step 3: Apply scale if available
    if result.scale and result.scale.has_scale and result.rooms:
        _apply_scale_to_rooms(result)
    elif not result.scale or not result.scale.has_scale:
        result.needs_user_confirmation = True
        result.confirmation_reason = "Scale not detected - manual calibration required"
        result.warnings.append("No scale detected. Provide scale for m² conversion.")

    # Finalize
    result.processing_time_ms = (time.time() - start_time) * 1000

    return result


def _try_text_extraction(
    file_path: str,
    page_number: int,
    result: FlooringResult,
) -> FlooringResult:
    """
    Try to extract room areas from text annotations (NRF values).

    German CAD PDFs often have "NRF = 12,34 m²" annotations per room.
    """
    import re

    try:
        import fitz
    except ImportError:
        result.warnings.append("PyMuPDF not available for text extraction")
        return result

    try:
        doc = fitz.open(file_path)
        page = doc[page_number - 1]
        text = page.get_text()
        doc.close()

        # Pattern for NRF values: "NRF = 12,34 m²" or "NRF: 12.34m²"
        nrf_pattern = r'NRF\s*[=:]\s*([\d,\.]+)\s*m[²2]?'
        matches = re.findall(nrf_pattern, text, re.IGNORECASE)

        if matches:
            total_area = 0.0
            rooms = []

            for i, match in enumerate(matches):
                # Parse German number format (12,34 → 12.34)
                area_str = match.replace(',', '.')
                try:
                    area = float(area_str)
                    total_area += area

                    room = RoomPolygon(
                        id=f"room_{i+1}",
                        points=[],  # No geometry from text extraction
                        area_px=0,
                        area_m2=area,
                        confidence=0.95,
                        label=f"Room {i+1} (from NRF)",
                        page_number=page_number,
                        source="text_extraction",
                    )
                    rooms.append(room)

                except ValueError:
                    continue

            if rooms:
                result.rooms = rooms
                result.room_count = len(rooms)
                result.total_area_m2 = total_area
                result.pipeline_used = PipelineMethod.TEXT_EXTRACTION

                # Create scale context (not needed for text extraction, but for consistency)
                result.scale = ScaleContext(
                    scale_string="from_text",
                    detection_method="text_extraction",
                    confidence=0.95,
                )

                logger.info(f"Extracted {len(rooms)} rooms with total {total_area:.2f} m² from text")

    except Exception as e:
        logger.warning(f"Text extraction failed: {e}")
        result.warnings.append(f"Text extraction failed: {str(e)}")

    return result


def _run_vector_pipeline(
    file_path: str,
    page_number: int,
    dpi: int,
    user_scale: Optional[int],
    result: FlooringResult,
) -> FlooringResult:
    """
    Vector Pipeline: Extract room polygons from PDF vector geometry.

    Steps:
    1. Extract PDF vectors (lines, rectangles, curves)
    2. Render to image at target DPI
    3. Detect scale from text
    4. Use OpenCV to find enclosed regions (contours)
    5. Convert contours to polygons with area
    """
    from .room_polygon_detector import detect_room_polygons_from_pdf

    try:
        # Detect scale
        scale_context = _detect_or_create_scale(file_path, page_number, dpi, user_scale)
        result.scale = scale_context

        # Detect room polygons
        polygons = detect_room_polygons_from_pdf(
            file_path,
            page_number=page_number,
            dpi=dpi,
        )

        if polygons:
            result.rooms = polygons
            result.room_count = len(polygons)
            result.total_area_px = sum(p.area_px for p in polygons)
            result.pipeline_used = PipelineMethod.VECTOR

            logger.info(f"Vector pipeline: detected {len(polygons)} rooms")
        else:
            result.warnings.append("No room polygons detected from vectors")

    except Exception as e:
        logger.error(f"Vector pipeline failed: {e}")
        result.warnings.append(f"Vector pipeline failed: {str(e)}")
        result.pipeline_used = PipelineMethod.FAILED

    return result


def _run_raster_pipeline(
    file_path: str,
    page_number: int,
    dpi: int,
    user_scale: Optional[int],
    result: FlooringResult,
) -> FlooringResult:
    """
    Raster Pipeline: Extract room polygons from scanned/photo input.

    Steps:
    1. Render/load image
    2. Preprocess (denoise, enhance lines)
    3. Adaptive threshold
    4. Morphological closing to seal gaps
    5. Contour detection
    6. Filter contours by size/shape
    7. Convert to polygons
    """
    from .room_polygon_detector import detect_room_polygons_from_image

    try:
        # Detect scale
        scale_context = _detect_or_create_scale(file_path, page_number, dpi, user_scale)
        result.scale = scale_context

        # For raster input, we need more aggressive processing
        polygons = detect_room_polygons_from_image(
            file_path,
            page_number=page_number if file_path.lower().endswith('.pdf') else None,
            dpi=dpi,
            close_gaps=True,
        )

        if polygons:
            result.rooms = polygons
            result.room_count = len(polygons)
            result.total_area_px = sum(p.area_px for p in polygons)
            result.pipeline_used = PipelineMethod.RASTER

            # Raster pipeline is less reliable
            result.needs_user_confirmation = True
            result.confirmation_reason = "Raster input - please verify detected rooms"

            logger.info(f"Raster pipeline: detected {len(polygons)} rooms")
        else:
            result.warnings.append("No room polygons detected from raster")
            result.needs_user_confirmation = True
            result.confirmation_reason = "No rooms detected - manual selection required"

    except Exception as e:
        logger.error(f"Raster pipeline failed: {e}")
        result.warnings.append(f"Raster pipeline failed: {str(e)}")
        result.pipeline_used = PipelineMethod.FAILED

    return result


def _run_hybrid_pipeline(
    file_path: str,
    page_number: int,
    dpi: int,
    user_scale: Optional[int],
    result: FlooringResult,
) -> FlooringResult:
    """
    Hybrid Pipeline: Try vector first, fall back to raster.
    """
    # Try vector first
    result = _run_vector_pipeline(file_path, page_number, dpi, user_scale, result)

    if result.room_count == 0:
        # Fall back to raster
        result.warnings.append("Vector pipeline found no rooms, trying raster")
        result = _run_raster_pipeline(file_path, page_number, dpi, user_scale, result)

    if result.pipeline_used not in [PipelineMethod.FAILED]:
        result.pipeline_used = PipelineMethod.HYBRID

    return result


def _detect_or_create_scale(
    file_path: str,
    page_number: int,
    dpi: int,
    user_scale: Optional[int],
) -> ScaleContext:
    """
    Detect scale from PDF text or create from user input.
    """
    import fitz

    if user_scale:
        # User provided scale
        return _create_scale_context_from_user(file_path, page_number, dpi, user_scale)

    # Try to detect from text
    try:
        doc = fitz.open(file_path)
        page = doc[page_number - 1]
        page_text = page.get_text()
        page_width = page.rect.width
        page_height = page.rect.height
        doc.close()

        result = detect_scale_from_text(page_text)

        if result:
            scale_string, scale_factor, confidence = result
            pixels_per_meter = compute_pixels_per_meter(
                scale_factor, page_width, page_height, dpi
            )

            return ScaleContext(
                scale_string=scale_string,
                scale_factor=scale_factor,
                pixels_per_meter=pixels_per_meter,
                detection_method=DetectionMethod.TEXT_SCALE.value,
                confidence=confidence,
                source_page=page_number,
                page_width_points=page_width,
                page_height_points=page_height,
                render_dpi=dpi,
                notes=[f"Detected from text: {scale_string}"],
            )

    except Exception as e:
        logger.warning(f"Scale detection failed: {e}")

    # Return empty scale context
    return ScaleContext(
        render_dpi=dpi,
        source_page=page_number,
        detection_method=DetectionMethod.NONE.value,
        confidence=0.0,
        notes=["No scale detected - manual calibration required"],
    )


def _create_scale_context_from_user(
    file_path: str,
    page_number: int,
    dpi: int,
    user_scale: int,
) -> ScaleContext:
    """
    Create ScaleContext from user-provided scale.

    For 1:100 at 300 DPI:
    - 1 meter in reality = 0.01 m on paper = 0.3937 inches on paper
    - At 300 DPI = 0.3937 * 300 = 118.11 pixels per real meter
    """
    import fitz

    # Get page dimensions
    try:
        doc = fitz.open(file_path)
        page = doc[page_number - 1]
        page_width = page.rect.width  # in points (72 per inch)
        page_height = page.rect.height
        doc.close()
    except:
        page_width = 842  # A4 default
        page_height = 595

    # Calculate pixels per meter
    # 1 meter on paper at scale 1:S = 1/S meters = (1/S) * 39.3701 inches
    # At DPI = D pixels per inch → (1/S) * 39.3701 * D pixels per real meter
    INCHES_PER_METER = 39.3701
    pixels_per_meter = (1 / user_scale) * INCHES_PER_METER * dpi

    return ScaleContext(
        scale_string=f"1:{user_scale}",
        scale_factor=float(user_scale),
        pixels_per_meter=pixels_per_meter,
        detection_method="user_calibration",
        confidence=1.0,
        source_page=page_number,
        page_width_points=page_width,
        page_height_points=page_height,
        render_dpi=dpi,
        notes=[f"User-provided scale 1:{user_scale}"],
    )


def _apply_scale_to_rooms(result: FlooringResult) -> None:
    """
    Convert pixel areas to m² using the scale context.
    """
    if not result.scale or not result.scale.has_scale:
        return

    ppm = result.scale.pixels_per_meter
    ppm_sq = ppm * ppm  # pixels² per m²

    total_m2 = 0.0

    for room in result.rooms:
        if room.area_px > 0:
            room.area_m2 = room.area_px / ppm_sq
            total_m2 += room.area_m2

        if room.perimeter_px > 0:
            room.perimeter_m = room.perimeter_px / ppm

    result.total_area_m2 = total_m2

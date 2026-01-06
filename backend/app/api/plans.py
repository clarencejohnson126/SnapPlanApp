"""
Plans API Router

Endpoints for blueprint analysis, object detection, and measurement.
Part of the Aufmaß Engine - Phase B scale detection implemented.
"""

import tempfile
import time
import uuid
from pathlib import Path

from fastapi import APIRouter, UploadFile, File, HTTPException, Query
from pydantic import BaseModel, Field
from typing import List, Optional, Dict, Any
from enum import Enum

from ..services.plan_ingestion import (
    load_plan_document,
    render_page_to_image,
    extract_page_text,
    PlanDocument,
    PageInfo,
    DEFAULT_RENDER_DPI,
)
from ..services.scale_calibration import (
    ScaleContext,
    detect_scale_from_document,
    compute_scale_from_points,
)
from ..services.persistence import (
    store_scale_context,
    get_scale_context,
    list_scale_contexts,
    create_sector,
    get_sector,
    list_sectors as list_sectors_db,
    store_measurement,
)
from ..services.measurement_engine import (
    Sector,
    MeasurementResult,
    compute_sector_area_m2,
    compute_sector_perimeter_m,
    generate_sector_id,
    generate_measurement_id,
    MeasurementType,
    MeasurementMethod,
)
from ..services.cv_pipeline import (
    get_cv_pipeline_status,
    run_object_detection_on_page,
    store_detections,
    ObjectType,
)
from ..services.vector_measurement import (
    extract_wall_segments_from_page,
    compute_wall_length_in_sector_m,
    compute_drywall_area_in_sector_m2,
    FITZ_AVAILABLE,
)
from ..core.config import get_settings

router = APIRouter(prefix="/plans", tags=["Plan Analysis"])


# ============================================
# Enums
# ============================================


class AnalysisType(str, Enum):
    """Types of analysis that can be performed."""

    FULL = "full"  # Detect all object types
    DOORS_ONLY = "doors"
    WINDOWS_ONLY = "windows"
    ROOMS_ONLY = "rooms"
    FIXTURES_ONLY = "fixtures"


# ============================================
# Request Models
# ============================================


class AnalyzeRequest(BaseModel):
    """Request parameters for plan analysis."""

    analysis_types: List[AnalysisType] = Field(
        default=[AnalysisType.FULL],
        description="Types of objects to detect",
    )
    pages: Optional[List[int]] = Field(
        default=None,
        description="Specific pages to analyze (default: all)",
    )
    confidence_threshold: float = Field(
        default=0.5,
        ge=0.0,
        le=1.0,
        description="Minimum confidence for detections",
    )


class CalibrateRequest(BaseModel):
    """Request parameters for scale calibration."""

    analysis_id: str = Field(description="ID of the analysis to calibrate")
    known_dimension_px: float = Field(
        gt=0,
        description="Length in pixels of the reference element",
    )
    known_dimension_m: float = Field(
        gt=0,
        description="Actual length in meters of the reference element",
    )
    page_number: int = Field(
        default=1,
        ge=1,
        description="Page where reference is located",
    )


class MeasureRequest(BaseModel):
    """Request parameters for measurement."""

    analysis_id: str = Field(description="ID of the analysis to measure")
    object_ids: Optional[List[str]] = Field(
        default=None,
        description="Specific objects to measure (default: all)",
    )
    include_areas: bool = Field(
        default=True,
        description="Include area calculations for rooms",
    )


class SectorQueryRequest(BaseModel):
    """Request parameters for sector-based queries."""

    analysis_id: str = Field(description="ID of the analysis")
    sector_id: str = Field(description="ID of the sector to query")
    object_type: str = Field(description="Type of objects to count/list")
    include_measurements: bool = Field(
        default=True,
        description="Include measurements for each object",
    )


class ScaleDetectRequest(BaseModel):
    """Request parameters for scale detection from file_id."""

    file_id: str = Field(description="ID of the file to detect scale from")
    search_pages: Optional[List[int]] = Field(
        default=None,
        description="Pages to search for scale annotation (default: first 3)",
    )


class ScaleCalibrateRequest(BaseModel):
    """Request parameters for user-assisted scale calibration."""

    file_id: str = Field(description="ID of the file to calibrate")
    pixel_distance: float = Field(
        gt=0,
        description="Distance in pixels of the reference element",
    )
    real_distance_meters: float = Field(
        gt=0,
        description="Actual distance in meters of the reference element",
    )
    page_number: int = Field(
        default=1,
        ge=1,
        description="Page where reference is located",
    )
    source_bbox: Optional[Dict[str, float]] = Field(
        default=None,
        description="Bounding box of the reference element (x, y, width, height)",
    )


class CreateSectorRequest(BaseModel):
    """Request parameters for creating a sector."""

    file_id: str = Field(description="ID of the file this sector belongs to")
    page_number: int = Field(ge=1, description="Page number where sector is defined")
    name: str = Field(min_length=1, description="Name of the sector (e.g., 'Living Room')")
    points: List[List[float]] = Field(
        description="Polygon points as [[x1,y1], [x2,y2], ...] in pixel coordinates",
        min_length=3,
    )
    sector_type: Optional[str] = Field(
        default=None,
        description="Type of sector: 'room', 'zone', 'floor'",
    )
    metadata: Optional[Dict[str, Any]] = Field(
        default=None,
        description="Additional sector attributes",
    )


class MeasureSectorAreaRequest(BaseModel):
    """Request parameters for measuring sector area."""

    sector_id: str = Field(description="ID of the sector to measure")
    pixels_per_meter: Optional[float] = Field(
        default=None,
        gt=0,
        description="Scale factor. If not provided, uses file's active scale context.",
    )
    persist: bool = Field(
        default=True,
        description="Whether to persist the measurement result",
    )


class RunDetectionRequest(BaseModel):
    """Request parameters for running object detection."""

    file_id: str = Field(description="ID of the file to analyze")
    page_number: int = Field(ge=1, description="Page number to run detection on")
    image_path: str = Field(description="Path to the rendered page image")
    object_types: Optional[List[str]] = Field(
        default=None,
        description="Types of objects to detect (default: all)",
    )
    confidence_threshold: Optional[float] = Field(
        default=None,
        ge=0.0,
        le=1.0,
        description="Minimum detection confidence (default: from settings)",
    )
    persist: bool = Field(
        default=True,
        description="Whether to persist detection results",
    )


class SectorWallMeasurementRequest(BaseModel):
    """Request parameters for sector wall measurement (Phase D)."""

    file_id: str = Field(description="ID of the file containing the floor plan")
    page_number: int = Field(ge=1, description="Page number to extract walls from")
    sector_id: str = Field(description="ID of the sector to measure walls within")
    include_drywall_area: bool = Field(
        default=False,
        description="Whether to also calculate drywall area",
    )
    wall_height_m: Optional[float] = Field(
        default=None,
        gt=0,
        description="Wall height in meters (required if include_drywall_area=True)",
    )
    pdf_path: Optional[str] = Field(
        default=None,
        description="Path to the PDF file. If not provided, uses file_id to look up storage path.",
    )
    persist: bool = Field(
        default=True,
        description="Whether to persist the measurement results",
    )


# ============================================
# Response Models
# ============================================


class BoundingBoxResponse(BaseModel):
    """Bounding box in pixel coordinates."""

    x: float
    y: float
    width: float
    height: float


class DetectedObjectResponse(BaseModel):
    """A detected object in the blueprint."""

    object_id: str
    object_type: str
    bbox: BoundingBoxResponse
    confidence: float
    page_number: int
    label: Optional[str] = None
    attributes: Dict[str, Any] = Field(default_factory=dict)


class ScaleInfoResponse(BaseModel):
    """Detected or calibrated scale information."""

    scale_string: Optional[str] = None
    pixels_per_meter: Optional[float] = None
    detection_method: str
    confidence: float
    source_page: int


class ScaleContextResponse(BaseModel):
    """Full scale context with all details."""

    id: Optional[str] = None
    file_id: Optional[str] = None
    scale_string: Optional[str] = None
    scale_factor: Optional[float] = None
    pixels_per_meter: Optional[float] = None
    detection_method: str
    confidence: float
    source_page: int
    source_bbox: Optional[Dict[str, float]] = None
    user_reference_px: Optional[float] = None
    user_reference_m: Optional[float] = None
    is_active: bool = True
    has_scale: bool = True

    @classmethod
    def from_scale_context(cls, sc: ScaleContext) -> "ScaleContextResponse":
        """Create response from ScaleContext dataclass."""
        return cls(
            id=sc.id,
            file_id=sc.file_id,
            scale_string=sc.scale_string,
            scale_factor=sc.scale_factor,
            pixels_per_meter=sc.pixels_per_meter,
            detection_method=sc.detection_method,
            confidence=sc.confidence,
            source_page=sc.source_page,
            source_bbox=sc.source_bbox,
            user_reference_px=sc.user_reference_px,
            user_reference_m=sc.user_reference_m,
            is_active=sc.is_active,
            has_scale=sc.pixels_per_meter is not None,
        )

    @classmethod
    def no_scale(cls, file_id: str, source_page: int = 1) -> "ScaleContextResponse":
        """Create a 'no scale detected' response."""
        return cls(
            file_id=file_id,
            detection_method="none",
            confidence=0.0,
            source_page=source_page,
            has_scale=False,
        )


class AnalyzeResponse(BaseModel):
    """Response from plan analysis."""

    analysis_id: str
    document_id: str
    filename: str
    status: str  # "completed" | "partial" | "failed"
    total_pages: int
    total_objects: int
    objects_by_type: Dict[str, int]
    objects: List[DetectedObjectResponse]
    scale_detected: Optional[ScaleInfoResponse] = None
    processing_time_ms: int
    warnings: List[str] = Field(default_factory=list)


class MeasurementResponse(BaseModel):
    """A measurement result with full auditability."""

    measurement_id: str
    object_id: str
    measurement_type: str
    value: float
    unit: str
    confidence: float
    method: str
    source_page: int
    source_bbox: Optional[BoundingBoxResponse] = None


class MeasureResponse(BaseModel):
    """Response from measurement operation."""

    document_id: str
    analysis_id: str
    scale_used: ScaleInfoResponse
    measurements: List[MeasurementResponse]
    summary: Dict[str, Any] = Field(default_factory=dict)


class SectorResponse(BaseModel):
    """A sector/zone in the blueprint."""

    sector_id: str
    file_id: str
    page_number: int
    name: str
    polygon_points: List[List[float]]
    sector_type: Optional[str] = None
    area_m2: Optional[float] = None
    perimeter_m: Optional[float] = None
    created_at: Optional[str] = None
    metadata: Dict[str, Any] = Field(default_factory=dict)

    @classmethod
    def from_sector(cls, sector: Sector) -> "SectorResponse":
        """Create response from Sector dataclass."""
        return cls(
            sector_id=sector.sector_id,
            file_id=sector.file_id,
            page_number=sector.page_number,
            name=sector.name,
            polygon_points=[list(p) for p in sector.polygon_points],
            sector_type=sector.sector_type,
            area_m2=sector.area_m2,
            perimeter_m=sector.perimeter_m,
            created_at=sector.created_at.isoformat() if sector.created_at else None,
            metadata=sector.metadata,
        )


class SectorQueryResponse(BaseModel):
    """Response from sector query."""

    sector: SectorResponse
    query_type: str
    total_count: int
    objects: List[DetectedObjectResponse]
    measurements: List[MeasurementResponse] = Field(default_factory=list)
    summary: Dict[str, Any] = Field(default_factory=dict)


class MeasureSectorAreaResponse(BaseModel):
    """Response from sector area measurement."""

    sector_id: str
    sector_name: str
    area_m2: float
    perimeter_m: float
    area_pixels: float
    perimeter_pixels: float
    pixels_per_meter: float
    method: str
    confidence: float
    measurement_id: Optional[str] = None
    persisted: bool = False


class CVPipelineStatusResponse(BaseModel):
    """Status of the CV pipeline."""

    cv_pipeline_enabled: bool
    opencv_installed: bool
    yolo_installed: bool
    yolo_model_configured: bool
    yolo_model_path: Optional[str] = None
    confidence_threshold: float


class DetectionResponse(BaseModel):
    """Response from object detection."""

    document_id: str
    page_number: int
    objects: List[DetectedObjectResponse]
    object_counts: Dict[str, int]
    processing_time_ms: int
    model_version: str
    warnings: List[str] = Field(default_factory=list)
    analysis_id: Optional[str] = None
    persisted: bool = False
    persisted_count: int = 0


class MeasurementResultModel(BaseModel):
    """Measurement result with full auditability (mirrors MeasurementResult)."""

    measurement_id: str
    measurement_type: str
    value: float
    unit: str
    file_id: str
    page_number: int
    confidence: float = 1.0
    method: str
    assumptions: List[str] = Field(default_factory=list)
    source: Optional[str] = None
    sector_id: Optional[str] = None
    scale_context_id: Optional[str] = None

    @classmethod
    def from_measurement_result(cls, mr: MeasurementResult) -> "MeasurementResultModel":
        """Create response from MeasurementResult dataclass."""
        return cls(
            measurement_id=mr.measurement_id,
            measurement_type=mr.measurement_type,
            value=mr.value,
            unit=mr.unit,
            file_id=mr.file_id,
            page_number=mr.page_number,
            confidence=mr.confidence,
            method=mr.method,
            assumptions=mr.assumptions,
            source=mr.source,
            sector_id=mr.sector_id,
            scale_context_id=mr.scale_context_id,
        )


class SectorWallMeasurementResponse(BaseModel):
    """Response from sector wall measurement (Phase D)."""

    has_scale: bool
    reason: Optional[str] = None  # Reason if has_scale=False
    wall_length: Optional[MeasurementResultModel] = None
    drywall_area: Optional[MeasurementResultModel] = None
    wall_segment_count: int = 0
    sector_name: Optional[str] = None
    pixels_per_meter: Optional[float] = None
    persisted: bool = False
    warnings: List[str] = Field(default_factory=list)


# ============================================
# Endpoints
# ============================================


@router.post("/analyze", response_model=AnalyzeResponse)
async def analyze_plan(
    file: UploadFile = File(..., description="PDF blueprint to analyze"),
    analysis_types: str = Query(
        default="full",
        description="Comma-separated analysis types: full,doors,windows,rooms,fixtures",
    ),
    pages: Optional[str] = Query(
        default=None,
        description="Comma-separated page numbers (default: all)",
    ),
    confidence_threshold: float = Query(
        default=0.5,
        ge=0.0,
        le=1.0,
        description="Minimum detection confidence",
    ),
):
    """
    Upload a blueprint and detect objects.

    Analyzes the uploaded PDF to detect:
    - Doors (with fire ratings and swing direction)
    - Windows
    - Rooms (with polygon boundaries)
    - Fixtures (sinks, toilets, appliances)

    Returns detected objects with bounding boxes and confidence scores.
    Optionally attempts automatic scale detection.

    **Phase B/C Implementation Pending**
    """
    # TODO: Phase B - Ingest PDF with plan_ingestion
    # TODO: Phase B - Detect scale with scale_calibration
    # TODO: Phase C - Run object detection with cv_pipeline
    raise HTTPException(
        status_code=501,
        detail={
            "error": "Not Implemented",
            "message": "Phase B/C implementation pending - CV pipeline not yet available",
            "phase": "B/C",
        },
    )


@router.post("/calibrate", response_model=ScaleInfoResponse)
async def calibrate_scale(request: CalibrateRequest):
    """
    User-assisted scale calibration.

    Use when automatic scale detection fails or is inaccurate.
    Provide a known reference dimension (e.g., a dimension line with labeled value).

    **Phase B Implementation Pending**
    """
    # TODO: Phase B - Calibrate scale with scale_calibration
    raise HTTPException(
        status_code=501,
        detail={
            "error": "Not Implemented",
            "message": "Phase B implementation pending - scale calibration not yet available",
            "phase": "B",
        },
    )


@router.post("/measure", response_model=MeasureResponse)
async def measure_objects(request: MeasureRequest):
    """
    Calculate real-world measurements for detected objects.

    Requires a previous analysis_id from /analyze endpoint.
    Uses detected or calibrated scale to convert pixel measurements to meters.

    Returns:
    - Door widths and heights
    - Window dimensions
    - Room areas (m²) and perimeters

    **Phase D Implementation Pending**
    """
    # TODO: Phase D - Measure objects with measurement_engine
    raise HTTPException(
        status_code=501,
        detail={
            "error": "Not Implemented",
            "message": "Phase D implementation pending - measurement engine not yet available",
            "phase": "D",
        },
    )


@router.post("/query-sector", response_model=SectorQueryResponse)
async def query_sector(request: SectorQueryRequest):
    """
    Query objects within a specific sector/zone.

    Example queries:
    - "Count doors in Apartment 3"
    - "List windows in Zone B"
    - "Total fixtures in bathroom"

    Returns objects within the sector with optional measurements.

    **Phase E Implementation Pending**
    """
    # TODO: Phase E - Query sector with measurement_engine
    raise HTTPException(
        status_code=501,
        detail={
            "error": "Not Implemented",
            "message": "Phase E implementation pending - sector queries not yet available",
            "phase": "E",
        },
    )


@router.get("/analysis/{analysis_id}", response_model=AnalyzeResponse)
async def get_analysis(analysis_id: str):
    """
    Retrieve a previous analysis result.

    **Phase B Implementation Pending**
    """
    # TODO: Phase B - Retrieve from Supabase
    raise HTTPException(
        status_code=501,
        detail={
            "error": "Not Implemented",
            "message": "Phase B implementation pending - analysis retrieval not yet available",
            "phase": "B",
        },
    )


@router.get("/sectors/{analysis_id}", response_model=List[SectorResponse])
async def list_sectors(analysis_id: str):
    """
    List detected sectors/rooms for an analysis.

    **Phase E Implementation Pending**
    """
    # TODO: Phase E - Retrieve sectors from Supabase
    raise HTTPException(
        status_code=501,
        detail={
            "error": "Not Implemented",
            "message": "Phase E implementation pending - sector listing not yet available",
            "phase": "E",
        },
    )


# ============================================
# Scale Endpoints (Phase B)
# ============================================


@router.get("/scale/{file_id}", response_model=ScaleContextResponse)
async def get_scale(file_id: str):
    """
    Get the active scale context for a file.

    Returns the current scale calibration for the specified file.
    If no scale has been detected or calibrated, returns has_scale=false.
    """
    settings = get_settings()

    # Try to get from database first
    scale_context = get_scale_context(file_id=file_id, settings=settings)

    if scale_context:
        return ScaleContextResponse.from_scale_context(scale_context)

    # No scale context found
    return ScaleContextResponse.no_scale(file_id=file_id)


@router.post("/scale/detect", response_model=ScaleContextResponse)
async def detect_scale(
    file: UploadFile = File(..., description="PDF blueprint to detect scale from"),
    file_id: Optional[str] = Query(
        default=None,
        description="Optional file ID to associate with scale context",
    ),
    search_pages: Optional[str] = Query(
        default=None,
        description="Comma-separated page numbers to search (default: first 3)",
    ),
    persist: bool = Query(
        default=True,
        description="Whether to persist the detected scale to database",
    ),
):
    """
    Detect scale from an uploaded PDF blueprint.

    Searches for scale annotations like "M 1:100", "Maßstab 1:50", etc.
    in the specified pages (default: first 3 pages).

    Returns the detected scale context with confidence score.
    If no scale is detected, returns has_scale=false.
    """
    start_time = time.time()

    # Parse search_pages if provided
    pages_to_search = None
    if search_pages:
        try:
            pages_to_search = [int(p.strip()) for p in search_pages.split(",")]
        except ValueError:
            raise HTTPException(
                status_code=400,
                detail="Invalid page numbers. Use comma-separated integers.",
            )

    # Generate file_id if not provided
    if not file_id:
        file_id = str(uuid.uuid4())

    # Save uploaded file to temp location
    try:
        with tempfile.NamedTemporaryFile(delete=False, suffix=".pdf") as tmp:
            content = await file.read()
            tmp.write(content)
            tmp_path = tmp.name
    except Exception as e:
        raise HTTPException(
            status_code=400,
            detail=f"Failed to save uploaded file: {str(e)}",
        )

    try:
        # Load the document
        document = load_plan_document(tmp_path, file_id=file_id)

        # Detect scale
        scale_context = detect_scale_from_document(
            document=document,
            search_pages=pages_to_search,
        )

        # Persist if requested and scale was detected
        settings = get_settings()
        if persist and scale_context.pixels_per_meter is not None:
            store_result = store_scale_context(
                file_id=file_id,
                scale_context=scale_context,
                settings=settings,
            )
            if store_result.success:
                scale_context.id = store_result.scale_context_id

        return ScaleContextResponse.from_scale_context(scale_context)

    except FileNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    finally:
        # Clean up temp file
        Path(tmp_path).unlink(missing_ok=True)


@router.post("/scale/calibrate", response_model=ScaleContextResponse)
async def calibrate_scale(request: ScaleCalibrateRequest):
    """
    User-assisted scale calibration.

    Provide a known reference dimension (e.g., a door width that you know is 0.9m)
    to calibrate the scale for accurate measurements.

    This creates a new scale context with detection_method="user_input".
    """
    settings = get_settings()

    # Compute scale from user input
    scale_context = compute_scale_from_points(
        pixel_distance=request.pixel_distance,
        real_distance_meters=request.real_distance_meters,
        source_page=request.page_number,
        file_id=request.file_id,
        source_bbox=request.source_bbox,
    )

    # Persist the calibration
    store_result = store_scale_context(
        file_id=request.file_id,
        scale_context=scale_context,
        settings=settings,
    )

    if store_result.success:
        scale_context.id = store_result.scale_context_id

    return ScaleContextResponse.from_scale_context(scale_context)


@router.get("/scale/history/{file_id}", response_model=List[ScaleContextResponse])
async def get_scale_history(file_id: str):
    """
    Get all scale contexts for a file.

    Returns the full history of scale detections and calibrations,
    with the most recent first. The active scale is marked with is_active=true.
    """
    settings = get_settings()
    contexts = list_scale_contexts(file_id=file_id, settings=settings)

    return [ScaleContextResponse.from_scale_context(sc) for sc in contexts]


# ============================================
# Sector Endpoints (Phase C)
# ============================================


@router.post("/sectors", response_model=SectorResponse)
async def create_sector_endpoint(request: CreateSectorRequest):
    """
    Create a new sector (zone/room polygon).

    Define a polygon region on a page to enable area calculations
    and object queries within that region.
    """
    settings = get_settings()

    # Convert points to tuples
    polygon_points = [tuple(p) for p in request.points]

    # Create sector object
    sector = Sector(
        sector_id=generate_sector_id(),
        file_id=request.file_id,
        page_number=request.page_number,
        name=request.name,
        polygon_points=polygon_points,
        sector_type=request.sector_type,
        metadata=request.metadata or {},
    )

    # Persist to database
    result = create_sector(sector=sector, settings=settings)

    if result.success:
        sector.sector_id = result.sector_id

    return SectorResponse.from_sector(sector)


@router.get("/sectors/file/{file_id}", response_model=List[SectorResponse])
async def list_file_sectors(
    file_id: str,
    page_number: Optional[int] = Query(
        default=None,
        ge=1,
        description="Filter by page number",
    ),
):
    """
    List all sectors for a file.

    Optionally filter by page number.
    """
    settings = get_settings()
    sectors = list_sectors_db(
        file_id=file_id,
        page_number=page_number,
        settings=settings,
    )

    return [SectorResponse.from_sector(s) for s in sectors]


@router.get("/sectors/{sector_id}", response_model=SectorResponse)
async def get_sector_endpoint(sector_id: str):
    """
    Get a specific sector by ID.
    """
    settings = get_settings()
    sector = get_sector(sector_id=sector_id, settings=settings)

    if sector is None:
        raise HTTPException(status_code=404, detail=f"Sector not found: {sector_id}")

    return SectorResponse.from_sector(sector)


@router.post("/sectors/measure-area", response_model=MeasureSectorAreaResponse)
async def measure_sector_area(request: MeasureSectorAreaRequest):
    """
    Calculate the area and perimeter of a sector.

    Uses the shoelace formula for polygon area calculation.
    Requires a pixels_per_meter scale factor for conversion to real units.

    If pixels_per_meter is not provided, attempts to use the file's
    active scale context.
    """
    settings = get_settings()

    # Get the sector
    sector = get_sector(sector_id=request.sector_id, settings=settings)
    if sector is None:
        raise HTTPException(status_code=404, detail=f"Sector not found: {request.sector_id}")

    # Determine pixels_per_meter
    pixels_per_meter = request.pixels_per_meter
    scale_confidence = 1.0

    if pixels_per_meter is None:
        # Try to get from file's active scale context
        scale_context = get_scale_context(file_id=sector.file_id, settings=settings)
        if scale_context and scale_context.pixels_per_meter:
            pixels_per_meter = scale_context.pixels_per_meter
            scale_confidence = scale_context.confidence
        else:
            raise HTTPException(
                status_code=400,
                detail="No pixels_per_meter provided and no active scale context found for file",
            )

    # Import here to avoid issues
    from ..services.measurement_engine import shoelace_area_pixels, shoelace_perimeter_pixels

    # Calculate area and perimeter in pixels
    area_pixels = shoelace_area_pixels(sector.polygon_points)
    perimeter_pixels = shoelace_perimeter_pixels(sector.polygon_points)

    # Convert to real units
    area_m2 = compute_sector_area_m2(sector.polygon_points, pixels_per_meter)
    perimeter_m = compute_sector_perimeter_m(sector.polygon_points, pixels_per_meter)

    # Update sector with measurements
    sector.area_m2 = area_m2
    sector.perimeter_m = perimeter_m

    # Optionally persist measurement
    measurement_id = None
    persisted = False

    if request.persist:
        measurement = MeasurementResult(
            measurement_id=generate_measurement_id(),
            measurement_type=MeasurementType.AREA.value,
            value=area_m2,
            unit="m2",
            file_id=sector.file_id,
            page_number=sector.page_number,
            confidence=scale_confidence,
            method=MeasurementMethod.POLYGON_AREA.value,
            assumptions=[
                f"pixels_per_meter={pixels_per_meter}",
                f"polygon_vertices={len(sector.polygon_points)}",
            ],
            source=f"Sector: {sector.name}",
            sector_id=sector.sector_id,
        )

        result = store_measurement(measurement=measurement, settings=settings)
        if result.success:
            measurement_id = result.measurement_id
            persisted = True

    return MeasureSectorAreaResponse(
        sector_id=sector.sector_id,
        sector_name=sector.name,
        area_m2=area_m2,
        perimeter_m=perimeter_m,
        area_pixels=area_pixels,
        perimeter_pixels=perimeter_pixels,
        pixels_per_meter=pixels_per_meter,
        method=MeasurementMethod.POLYGON_AREA.value,
        confidence=scale_confidence,
        measurement_id=measurement_id,
        persisted=persisted,
    )


# ============================================
# CV Pipeline Endpoints (Phase C)
# ============================================


@router.get("/cv/status", response_model=CVPipelineStatusResponse)
async def cv_pipeline_status():
    """
    Get the current status of the CV pipeline.

    Returns information about what CV features are available:
    - OpenCV installation status
    - YOLO installation and configuration status
    - Current confidence threshold
    """
    status = get_cv_pipeline_status()
    return CVPipelineStatusResponse(
        cv_pipeline_enabled=status.cv_pipeline_enabled,
        opencv_installed=status.opencv_installed,
        yolo_installed=status.yolo_installed,
        yolo_model_configured=status.yolo_model_configured,
        yolo_model_path=status.yolo_model_path,
        confidence_threshold=status.confidence_threshold,
    )


@router.post("/cv/detect", response_model=DetectionResponse)
async def run_detection(request: RunDetectionRequest):
    """
    Run object detection on a page image.

    Requires YOLO to be configured (SNAPGRID_YOLO_MODEL_PATH).
    If YOLO is not configured, returns empty results with a warning.

    Objects detected depend on the trained YOLO model.
    """
    settings = get_settings()

    # Map object type strings to ObjectType enum
    object_types = None
    if request.object_types:
        object_types = []
        for type_str in request.object_types:
            try:
                object_types.append(ObjectType(type_str.lower()))
            except ValueError:
                pass  # Skip invalid types

    # Run detection
    result = run_object_detection_on_page(
        image_path=request.image_path,
        document_id=request.file_id,
        page_number=request.page_number,
        object_types=object_types,
        confidence_threshold=request.confidence_threshold,
        settings=settings,
    )

    # Convert objects to response format
    objects = []
    for obj in result.objects:
        objects.append(DetectedObjectResponse(
            object_id=obj.object_id,
            object_type=obj.object_type.value,
            bbox=BoundingBoxResponse(
                x=obj.bbox.x,
                y=obj.bbox.y,
                width=obj.bbox.width,
                height=obj.bbox.height,
            ),
            confidence=obj.confidence,
            page_number=obj.page_number,
            label=obj.label,
            attributes=obj.attributes,
        ))

    # Optionally persist
    analysis_id = None
    persisted = False
    persisted_count = 0

    if request.persist and len(result.objects) > 0:
        store_result = store_detections(
            result=result,
            file_id=request.file_id,
            settings=settings,
        )
        if store_result.get("success"):
            analysis_id = store_result.get("analysis_id")
            persisted = True
            persisted_count = store_result.get("stored_count", 0)

    return DetectionResponse(
        document_id=request.file_id,
        page_number=request.page_number,
        objects=objects,
        object_counts=result.object_counts,
        processing_time_ms=result.processing_time_ms,
        model_version=result.model_version,
        warnings=result.warnings,
        analysis_id=analysis_id,
        persisted=persisted,
        persisted_count=persisted_count,
    )


# ============================================
# Vector Measurement Endpoints (Phase D)
# ============================================


@router.post("/measure/sector-walls", response_model=SectorWallMeasurementResponse)
async def measure_sector_walls(request: SectorWallMeasurementRequest):
    """
    Measure total wall length and optionally drywall area within a sector.

    This endpoint:
    1. Loads the ScaleContext for the file (required for conversion)
    2. Loads the Sector by sector_id
    3. Extracts wall segments from the PDF using vector geometry
    4. Computes total wall length in meters for segments inside the sector
    5. Optionally computes drywall area (wall_length * wall_height)

    **Requirements:**
    - The file must have an active scale context (detected or calibrated)
    - A sector must be defined for the file/page
    - PDF file must be accessible (via pdf_path or file storage)

    **Returns:**
    - has_scale: Whether a valid scale was found
    - wall_length: Total wall length measurement in meters
    - drywall_area: Optional drywall area in m² (if include_drywall_area=True)
    """
    settings = get_settings()
    warnings: List[str] = []

    # Check if PyMuPDF is available
    if not FITZ_AVAILABLE:
        raise HTTPException(
            status_code=501,
            detail={
                "error": "PyMuPDF not available",
                "message": "Vector extraction requires PyMuPDF (fitz) to be installed",
            },
        )

    # Validate drywall parameters
    if request.include_drywall_area and request.wall_height_m is None:
        raise HTTPException(
            status_code=400,
            detail={
                "error": "Missing wall_height_m",
                "message": "wall_height_m is required when include_drywall_area=True",
            },
        )

    # 1. Get scale context for the file
    scale_context = get_scale_context(file_id=request.file_id, settings=settings)

    if scale_context is None or not scale_context.has_scale:
        return SectorWallMeasurementResponse(
            has_scale=False,
            reason="no_scale_context",
            warnings=["No active scale context found for file. Please detect or calibrate scale first."],
        )

    # 2. Get the sector
    sector = get_sector(sector_id=request.sector_id, settings=settings)

    if sector is None:
        raise HTTPException(
            status_code=404,
            detail=f"Sector not found: {request.sector_id}",
        )

    # Verify sector is for the same file and page
    if sector.file_id != request.file_id:
        raise HTTPException(
            status_code=400,
            detail=f"Sector belongs to file {sector.file_id}, not {request.file_id}",
        )

    if sector.page_number != request.page_number:
        warnings.append(
            f"Sector is on page {sector.page_number}, but request is for page {request.page_number}. "
            "No wall segments will match."
        )

    # 3. Determine PDF path
    pdf_path = request.pdf_path

    if pdf_path is None:
        # TODO: Look up storage path from Supabase using file_id
        # For now, require pdf_path to be provided
        raise HTTPException(
            status_code=400,
            detail={
                "error": "Missing pdf_path",
                "message": "pdf_path is required. Storage lookup by file_id not yet implemented.",
            },
        )

    # Verify PDF exists
    if not Path(pdf_path).exists():
        raise HTTPException(
            status_code=404,
            detail=f"PDF file not found: {pdf_path}",
        )

    # 4. Extract wall segments from the page
    try:
        wall_segments = extract_wall_segments_from_page(
            path=pdf_path,
            page_number=request.page_number,
            dpi=scale_context.render_dpi or 150,
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to extract wall segments: {str(e)}",
        )

    if len(wall_segments) == 0:
        warnings.append("No vector line segments found in PDF page. The PDF may be raster-only.")

    # 5. Compute wall length in sector
    wall_length_result = compute_wall_length_in_sector_m(
        wall_segments=wall_segments,
        sector=sector,
        scale_context=scale_context,
    )

    # 6. Optionally compute drywall area
    drywall_area_result = None
    if request.include_drywall_area and request.wall_height_m is not None:
        drywall_area_result = compute_drywall_area_in_sector_m2(
            wall_segments=wall_segments,
            sector=sector,
            scale_context=scale_context,
            wall_height_m=request.wall_height_m,
        )

    # 7. Persist measurements if requested
    persisted = False
    if request.persist:
        # Store wall length measurement
        result1 = store_measurement(measurement=wall_length_result, settings=settings)
        if result1.success:
            persisted = True

        # Store drywall area measurement
        if drywall_area_result is not None:
            result2 = store_measurement(measurement=drywall_area_result, settings=settings)
            # Only set persisted=True if both succeeded
            persisted = persisted and result2.success

    # Get segment count from assumptions
    segment_count = 0
    for assumption in wall_length_result.assumptions:
        if assumption.startswith("segment_count:"):
            segment_count = int(assumption.split(":")[1].strip())
            break

    return SectorWallMeasurementResponse(
        has_scale=True,
        wall_length=MeasurementResultModel.from_measurement_result(wall_length_result),
        drywall_area=MeasurementResultModel.from_measurement_result(drywall_area_result)
        if drywall_area_result else None,
        wall_segment_count=segment_count,
        sector_name=sector.name,
        pixels_per_meter=scale_context.pixels_per_meter,
        persisted=persisted,
        warnings=warnings,
    )


# ============================================
# General Endpoints
# ============================================


@router.get("/health")
async def plans_health():
    """Health check for the plans analysis service."""
    cv_status = get_cv_pipeline_status()

    return {
        "status": "ok",
        "service": "plans",
        "implementation_status": {
            "phase_a": "completed",  # Architecture & scaffolding
            "phase_b": "completed",  # Scale detection & calibration
            "phase_c": "completed",  # Sectors, area calculation, CV pipeline hooks
            "phase_d": "completed",  # Vector wall measurement
            "phase_e": "pending",  # Sector queries & material takeoff
        },
        "cv_pipeline_status": cv_status.to_dict(),
        "vector_extraction_available": FITZ_AVAILABLE,
        "available_endpoints": [
            "/api/v1/plans/health",
            "/api/v1/plans/scale/{file_id}",
            "/api/v1/plans/scale/detect",
            "/api/v1/plans/scale/calibrate",
            "/api/v1/plans/scale/history/{file_id}",
            "/api/v1/plans/sectors",
            "/api/v1/plans/sectors/file/{file_id}",
            "/api/v1/plans/sectors/{sector_id}",
            "/api/v1/plans/sectors/measure-area",
            "/api/v1/plans/cv/status",
            "/api/v1/plans/cv/detect",
            "/api/v1/plans/measure/sector-walls",
        ],
        "pending_endpoints": [
            "/api/v1/plans/analyze",
            "/api/v1/plans/measure",
            "/api/v1/plans/query-sector",
            "/api/v1/plans/analysis/{analysis_id}",
        ],
    }

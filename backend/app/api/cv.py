"""
Computer Vision API routes.

Provides endpoints for:
- Input analysis (determine PDF type)
- Roboflow CV detection (for scans/photos)
- Universal blueprint processing
"""

import shutil
import tempfile
from pathlib import Path
from typing import Any, Dict, List, Optional
from uuid import uuid4

from fastapi import APIRouter, File, HTTPException, Query, UploadFile
from pydantic import BaseModel, Field

from ..core.config import get_settings
from ..services.input_router import (
    InputType,
    ProcessingPipeline,
    InputAnalysis,
    analyze_input,
    route_to_pipeline,
)
from ..services.roboflow_service import (
    RoboflowModelType,
    RoboflowStatus,
    analyze_floor_plan,
    detect_doors,
    detect_rooms,
    detect_walls,
    get_roboflow_status,
    is_roboflow_available,
    run_inference_on_pdf_page,
)


router = APIRouter(prefix="/cv", tags=["computer-vision"])


# =============================================================================
# Response Models
# =============================================================================


class InputAnalysisResponse(BaseModel):
    """Response model for input analysis."""
    input_type: str
    recommended_pipeline: str
    has_text_layer: bool
    has_vector_layer: bool
    is_raster_only: bool
    detected_annotations: List[str]
    confidence: float
    warnings: List[str]


class CVStatusResponse(BaseModel):
    """Response model for CV pipeline status."""
    roboflow_available: bool
    sdk_installed: bool
    api_key_configured: bool
    models: Dict[str, str]
    yolo_available: bool
    opencv_installed: bool


class RoomDetectionResponse(BaseModel):
    """Response model for room detection."""
    room_count: int
    total_area_m2: float
    scale: str
    rooms: List[Dict[str, Any]]
    processing_time_ms: int
    warnings: List[str]


class WallDetectionResponse(BaseModel):
    """Response model for wall detection."""
    wall_count: int
    total_perimeter_m: float
    scale: str
    walls: List[Dict[str, Any]]
    processing_time_ms: int
    warnings: List[str]


class DoorDetectionResponse(BaseModel):
    """Response model for door detection."""
    door_count: int
    by_width: Dict[str, int]
    scale: str
    doors: List[Dict[str, Any]]
    processing_time_ms: int
    warnings: List[str]


class FloorPlanAnalysisResponse(BaseModel):
    """Response model for comprehensive floor plan analysis."""
    walls: Dict[str, Any]
    rooms: Dict[str, Any]
    doors: Dict[str, Any]
    summary: Dict[str, Any]
    processing_time_ms: int
    scale: str
    warnings: List[str]


# =============================================================================
# Status Endpoints
# =============================================================================


@router.get("/status", response_model=CVStatusResponse)
async def get_cv_status():
    """
    Get the status of CV pipeline components.

    Returns availability of:
    - Roboflow API (for scans/photos)
    - YOLO (for CAD PDFs)
    - OpenCV (for image processing)
    """
    settings = get_settings()
    roboflow_status = get_roboflow_status(settings)

    from ..services.cv_pipeline import is_yolo_available, CV2_AVAILABLE

    return CVStatusResponse(
        roboflow_available=roboflow_status.client_available,
        sdk_installed=roboflow_status.sdk_installed,
        api_key_configured=roboflow_status.api_key_configured,
        models=roboflow_status.models,
        yolo_available=is_yolo_available(settings),
        opencv_installed=CV2_AVAILABLE,
    )


# =============================================================================
# Input Analysis Endpoints
# =============================================================================


@router.post("/analyze-input", response_model=InputAnalysisResponse)
async def analyze_input_file(
    file: UploadFile = File(..., description="PDF or image file to analyze"),
):
    """
    Analyze an input file to determine its type and recommended processing pipeline.

    This endpoint helps decide whether to use:
    - Text extraction (for German CAD PDFs with annotations)
    - Vector + CV (for CAD PDFs without annotations)
    - Roboflow CV (for scanned PDFs and photos)

    **Input Types Detected:**
    - CAD PDF with German annotations (NRF, U, LH values)
    - CAD PDF without annotations
    - Scanned PDF (raster image)
    - Photo (JPG, PNG)
    """
    if not file.filename:
        raise HTTPException(status_code=400, detail="No filename provided")

    # Save uploaded file to temp location
    temp_dir = tempfile.mkdtemp()
    temp_path = Path(temp_dir) / file.filename

    try:
        with open(temp_path, "wb") as f:
            shutil.copyfileobj(file.file, f)

        # Analyze the input
        analysis = analyze_input(str(temp_path))

        return InputAnalysisResponse(
            input_type=analysis.input_type.value,
            recommended_pipeline=analysis.recommended_pipeline.value,
            has_text_layer=analysis.has_text_layer,
            has_vector_layer=analysis.has_vector_layer,
            is_raster_only=analysis.is_raster_only,
            detected_annotations=analysis.detected_annotations,
            confidence=analysis.confidence,
            warnings=analysis.warnings,
        )

    finally:
        shutil.rmtree(temp_dir, ignore_errors=True)


# =============================================================================
# Roboflow CV Detection Endpoints
# =============================================================================


@router.post("/detect/rooms", response_model=RoomDetectionResponse)
async def detect_rooms_cv(
    file: UploadFile = File(..., description="Floor plan PDF or image"),
    scale: int = Query(100, gt=0, description="Scale denominator (e.g., 100 for 1:100)"),
    page_number: int = Query(1, gt=0, description="Page number for PDFs"),
):
    """
    Detect rooms in a floor plan using Roboflow CV.

    **Best for:**
    - Scanned PDFs without text annotations
    - Photos of blueprints
    - International blueprints

    **Returns:**
    - Room boundaries with area (m²)
    - Total floor area
    """
    settings = get_settings()

    if not is_roboflow_available(settings):
        raise HTTPException(
            status_code=503,
            detail="Roboflow not available. Configure SNAPGRID_ROBOFLOW_API_KEY.",
        )

    if not file.filename:
        raise HTTPException(status_code=400, detail="No filename provided")

    temp_dir = tempfile.mkdtemp()
    temp_path = Path(temp_dir) / file.filename

    try:
        with open(temp_path, "wb") as f:
            shutil.copyfileobj(file.file, f)

        # Check if PDF or image
        suffix = temp_path.suffix.lower()

        if suffix == ".pdf":
            # Render PDF page to image first
            from ..services.cv_pipeline import render_pdf_page_to_image
            import os

            image_path = render_pdf_page_to_image(str(temp_path), page_number, dpi=150)
            try:
                result = detect_rooms(image_path, scale=scale, dpi=150, settings=settings)
            finally:
                if os.path.exists(image_path):
                    os.remove(image_path)
        else:
            result = detect_rooms(str(temp_path), scale=scale, dpi=150, settings=settings)

        return RoomDetectionResponse(
            room_count=result.get("room_count", 0),
            total_area_m2=result.get("total_area_m2", 0),
            scale=result.get("scale", f"1:{scale}"),
            rooms=result.get("rooms", []),
            processing_time_ms=result.get("processing_time_ms", 0),
            warnings=result.get("warnings", []),
        )

    finally:
        shutil.rmtree(temp_dir, ignore_errors=True)


@router.post("/detect/walls", response_model=WallDetectionResponse)
async def detect_walls_cv(
    file: UploadFile = File(..., description="Floor plan PDF or image"),
    scale: int = Query(100, gt=0, description="Scale denominator (e.g., 100 for 1:100)"),
    page_number: int = Query(1, gt=0, description="Page number for PDFs"),
):
    """
    Detect walls in a floor plan using Roboflow CV.

    **Best for:**
    - Drywall calculation from scanned PDFs
    - Wall perimeter measurement

    **Returns:**
    - Wall segments with perimeter (m)
    - Total wall perimeter
    """
    settings = get_settings()

    if not is_roboflow_available(settings):
        raise HTTPException(
            status_code=503,
            detail="Roboflow not available. Configure SNAPGRID_ROBOFLOW_API_KEY.",
        )

    if not file.filename:
        raise HTTPException(status_code=400, detail="No filename provided")

    temp_dir = tempfile.mkdtemp()
    temp_path = Path(temp_dir) / file.filename

    try:
        with open(temp_path, "wb") as f:
            shutil.copyfileobj(file.file, f)

        suffix = temp_path.suffix.lower()

        if suffix == ".pdf":
            from ..services.cv_pipeline import render_pdf_page_to_image
            import os

            image_path = render_pdf_page_to_image(str(temp_path), page_number, dpi=150)
            try:
                result = detect_walls(image_path, scale=scale, dpi=150, settings=settings)
            finally:
                if os.path.exists(image_path):
                    os.remove(image_path)
        else:
            result = detect_walls(str(temp_path), scale=scale, dpi=150, settings=settings)

        return WallDetectionResponse(
            wall_count=result.get("wall_count", 0),
            total_perimeter_m=result.get("total_perimeter_m", 0),
            scale=result.get("scale", f"1:{scale}"),
            walls=result.get("walls", []),
            processing_time_ms=result.get("processing_time_ms", 0),
            warnings=result.get("warnings", []),
        )

    finally:
        shutil.rmtree(temp_dir, ignore_errors=True)


@router.post("/detect/doors", response_model=DoorDetectionResponse)
async def detect_doors_cv(
    file: UploadFile = File(..., description="Floor plan PDF or image"),
    scale: int = Query(100, gt=0, description="Scale denominator (e.g., 100 for 1:100)"),
    page_number: int = Query(1, gt=0, description="Page number for PDFs"),
):
    """
    Detect doors in a floor plan using Roboflow CV.

    **Best for:**
    - Scanned PDFs without door labels
    - Photos of blueprints
    - International blueprints with different door symbols

    **Returns:**
    - Door locations with estimated width
    - Count by width
    """
    settings = get_settings()

    if not is_roboflow_available(settings):
        raise HTTPException(
            status_code=503,
            detail="Roboflow not available. Configure SNAPGRID_ROBOFLOW_API_KEY.",
        )

    if not file.filename:
        raise HTTPException(status_code=400, detail="No filename provided")

    temp_dir = tempfile.mkdtemp()
    temp_path = Path(temp_dir) / file.filename

    try:
        with open(temp_path, "wb") as f:
            shutil.copyfileobj(file.file, f)

        suffix = temp_path.suffix.lower()

        if suffix == ".pdf":
            from ..services.cv_pipeline import render_pdf_page_to_image
            import os

            image_path = render_pdf_page_to_image(str(temp_path), page_number, dpi=150)
            try:
                result = detect_doors(image_path, scale=scale, dpi=150, settings=settings)
            finally:
                if os.path.exists(image_path):
                    os.remove(image_path)
        else:
            result = detect_doors(str(temp_path), scale=scale, dpi=150, settings=settings)

        return DoorDetectionResponse(
            door_count=result.get("door_count", 0),
            by_width=result.get("by_width", {}),
            scale=result.get("scale", f"1:{scale}"),
            doors=result.get("doors", []),
            processing_time_ms=result.get("processing_time_ms", 0),
            warnings=result.get("warnings", []),
        )

    finally:
        shutil.rmtree(temp_dir, ignore_errors=True)


class ProductionDoorDetectionResponse(BaseModel):
    """Response model for production door detection (YOLO-primary)."""
    door_count: int
    by_width: Dict[str, int]
    by_type: Dict[str, int]
    scale: str
    detection_mode: str
    doors: List[Dict[str, Any]]
    processing_time_ms: int
    detection_method: str
    warnings: List[str]


@router.post("/detect/doors/production", response_model=ProductionDoorDetectionResponse)
async def detect_doors_production(
    file: UploadFile = File(..., description="Floor plan PDF"),
    scale: int = Query(100, gt=0, description="Scale denominator (e.g., 100 for 1:100, 50 for 1:50)"),
    page_number: int = Query(1, gt=0, description="Page number for PDFs"),
    mode: str = Query(
        "balanced",
        description="Detection mode: 'strict' (fewer FPs), 'balanced' (default), 'sensitive' (more detections)",
    ),
):
    """
    Production-grade door detection using YOLO as primary detector.

    **This is the recommended endpoint for production use.**

    Uses a trained YOLO model to detect door symbols in floor plans.
    Door widths are estimated from bounding box dimensions and snapped
    to standard DIN 18101 door widths when close.

    **Detection Modes:**
    - `strict`: High precision, fewer false positives. Best for clean floor plans (1:50 scale).
    - `balanced`: Good for most blueprints. Recommended default.
    - `sensitive`: Higher recall, may have more false positives. For complex/basement drawings.

    **Best for:**
    - German CAD PDFs (architectural floor plans)
    - PDF files with clear door symbols (arc + panel)
    - Scale 1:50 or 1:100 drawings

    **Standard Door Widths (DIN 18101):**
    - 0.625m (narrow, WC)
    - 0.755m (standard interior)
    - 0.885m (wider interior)
    - 1.01m (wide/accessible)
    - 1.26m, 1.51m (double doors)

    **Returns:**
    - Door count with confidence scores
    - Door locations and estimated widths
    - Breakdown by width and type (narrow/standard/wide/double)
    """
    if not file.filename:
        raise HTTPException(status_code=400, detail="No filename provided")

    # Validate file type
    suffix = Path(file.filename).suffix.lower()
    if suffix != ".pdf":
        raise HTTPException(
            status_code=400,
            detail="Only PDF files supported. Use /detect/doors for images.",
        )

    temp_dir = tempfile.mkdtemp()
    temp_path = Path(temp_dir) / file.filename

    try:
        with open(temp_path, "wb") as f:
            shutil.copyfileobj(file.file, f)

        # Map mode string to DetectionMode enum
        from ..services.wall_opening_detector import detect_doors_yolo_primary, DetectionMode

        mode_map = {
            "strict": DetectionMode.STRICT,
            "balanced": DetectionMode.BALANCED,
            "sensitive": DetectionMode.SENSITIVE,
        }
        detection_mode = mode_map.get(mode.lower(), DetectionMode.BALANCED)

        result = detect_doors_yolo_primary(
            pdf_path=str(temp_path),
            page_number=page_number,
            scale=scale,
            mode=detection_mode,
            use_wall_opening_validation=False,  # YOLO is sufficient
        )

        # Convert result to response format
        result_dict = result.to_dict()

        # Group by type
        by_type = {}
        for door in result.doors:
            door_type = door.metadata.get("door_type", "unknown")
            by_type[door_type] = by_type.get(door_type, 0) + 1

        return ProductionDoorDetectionResponse(
            door_count=len(result.doors),
            by_width=result_dict.get("by_width", {}),
            by_type=by_type,
            scale=f"1:{scale}",
            detection_mode=detection_mode.value,
            doors=[d.to_dict() for d in result.doors],
            processing_time_ms=result.processing_time_ms,
            detection_method="yolo_primary",
            warnings=result.warnings,
        )

    finally:
        shutil.rmtree(temp_dir, ignore_errors=True)


@router.post("/analyze", response_model=FloorPlanAnalysisResponse)
async def analyze_floor_plan_cv(
    file: UploadFile = File(..., description="Floor plan PDF or image"),
    scale: int = Query(100, gt=0, description="Scale denominator (e.g., 100 for 1:100)"),
    page_number: int = Query(1, gt=0, description="Page number for PDFs"),
):
    """
    Run comprehensive floor plan analysis using Roboflow CV.

    Detects walls, rooms, and doors in a single call.

    **Best for:**
    - Complete analysis of scanned blueprints
    - Quick overview of floor plan contents

    **Returns:**
    - Walls (perimeter in m)
    - Rooms (area in m²)
    - Doors (count and widths)
    - Summary statistics
    """
    settings = get_settings()

    if not is_roboflow_available(settings):
        raise HTTPException(
            status_code=503,
            detail="Roboflow not available. Configure SNAPGRID_ROBOFLOW_API_KEY.",
        )

    if not file.filename:
        raise HTTPException(status_code=400, detail="No filename provided")

    temp_dir = tempfile.mkdtemp()
    temp_path = Path(temp_dir) / file.filename

    try:
        with open(temp_path, "wb") as f:
            shutil.copyfileobj(file.file, f)

        suffix = temp_path.suffix.lower()

        if suffix == ".pdf":
            from ..services.cv_pipeline import render_pdf_page_to_image
            import os

            image_path = render_pdf_page_to_image(str(temp_path), page_number, dpi=150)
            try:
                result = analyze_floor_plan(image_path, scale=scale, dpi=150, settings=settings)
            finally:
                if os.path.exists(image_path):
                    os.remove(image_path)
        else:
            result = analyze_floor_plan(str(temp_path), scale=scale, dpi=150, settings=settings)

        return FloorPlanAnalysisResponse(
            walls=result.get("walls", {}),
            rooms=result.get("rooms", {}),
            doors=result.get("doors", {}),
            summary=result.get("summary", {}),
            processing_time_ms=result.get("processing_time_ms", 0),
            scale=result.get("scale", f"1:{scale}"),
            warnings=result.get("warnings", []),
        )

    finally:
        shutil.rmtree(temp_dir, ignore_errors=True)

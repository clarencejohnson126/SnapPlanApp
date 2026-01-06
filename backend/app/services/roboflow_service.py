"""
Roboflow CV Service

Integrates Roboflow's hosted models for blueprint analysis.
Supports scanned PDFs, photos, and international blueprints.

Models used:
- Floor Plan Segmentation (IIITBangalore) - Wall, door, window detection
- Room Segmentation Model - Room boundary detection
- Door Detection - Specialized door detection
- Wall-Floor Segmentation - Wall and floor area detection

API: https://detect.roboflow.com
Docs: https://docs.roboflow.com/deploy/hosted-api/native-hosted-api
"""

from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple
import logging
import time

from ..core.config import Settings, get_settings

logger = logging.getLogger(__name__)

# Check for inference-sdk
try:
    from inference_sdk import InferenceHTTPClient
    INFERENCE_SDK_AVAILABLE = True
except ImportError:
    INFERENCE_SDK_AVAILABLE = False
    logger.warning("inference-sdk not installed - run: pip install inference-sdk")

try:
    import cv2
    import numpy as np
    CV2_AVAILABLE = True
except ImportError:
    CV2_AVAILABLE = False
    logger.warning("OpenCV not installed - mask processing disabled")


class RoboflowModelType(Enum):
    """Types of Roboflow models for different detection tasks."""
    FLOOR_PLAN = "floor_plan"  # General floor plan segmentation
    ROOM_SEGMENTATION = "room_segmentation"  # Room boundary detection
    DOOR_DETECTION = "door_detection"  # Door detection
    WALL_FLOOR = "wall_floor"  # Wall and floor segmentation


@dataclass
class SegmentationMask:
    """Represents a segmentation mask from Roboflow."""
    class_name: str
    class_id: int
    confidence: float
    points: List[Tuple[float, float]]  # Polygon points
    area_px: float = 0.0
    perimeter_px: float = 0.0
    bbox: Optional[Dict[str, float]] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "class_name": self.class_name,
            "class_id": self.class_id,
            "confidence": self.confidence,
            "points": self.points,
            "area_px": self.area_px,
            "perimeter_px": self.perimeter_px,
            "bbox": self.bbox,
        }


@dataclass
class DetectionBox:
    """Represents a detection bounding box from Roboflow."""
    class_name: str
    class_id: int
    confidence: float
    x: float  # Center x
    y: float  # Center y
    width: float
    height: float

    @property
    def x1(self) -> float:
        """Top-left x coordinate."""
        return self.x - self.width / 2

    @property
    def y1(self) -> float:
        """Top-left y coordinate."""
        return self.y - self.height / 2

    @property
    def x2(self) -> float:
        """Bottom-right x coordinate."""
        return self.x + self.width / 2

    @property
    def y2(self) -> float:
        """Bottom-right y coordinate."""
        return self.y + self.height / 2

    @property
    def area_px(self) -> float:
        """Area in pixels."""
        return self.width * self.height

    def to_dict(self) -> Dict[str, Any]:
        return {
            "class_name": self.class_name,
            "class_id": self.class_id,
            "confidence": self.confidence,
            "x": self.x,
            "y": self.y,
            "width": self.width,
            "height": self.height,
            "area_px": self.area_px,
        }


@dataclass
class RoboflowResult:
    """Result from Roboflow inference."""
    model_id: str
    model_type: RoboflowModelType
    image_width: int
    image_height: int
    detections: List[DetectionBox] = field(default_factory=list)
    segmentations: List[SegmentationMask] = field(default_factory=list)
    processing_time_ms: int = 0
    raw_response: Optional[Dict] = None
    warnings: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "model_id": self.model_id,
            "model_type": self.model_type.value,
            "image_width": self.image_width,
            "image_height": self.image_height,
            "detections": [d.to_dict() for d in self.detections],
            "segmentations": [s.to_dict() for s in self.segmentations],
            "processing_time_ms": self.processing_time_ms,
            "warnings": self.warnings,
        }

    @property
    def detection_counts(self) -> Dict[str, int]:
        """Count detections by class."""
        counts = {}
        for det in self.detections:
            counts[det.class_name] = counts.get(det.class_name, 0) + 1
        return counts

    @property
    def segmentation_counts(self) -> Dict[str, int]:
        """Count segmentations by class."""
        counts = {}
        for seg in self.segmentations:
            counts[seg.class_name] = counts.get(seg.class_name, 0) + 1
        return counts


# Global inference client instance
_inference_client: Optional["InferenceHTTPClient"] = None


def get_roboflow_client(settings: Optional[Settings] = None) -> Optional["InferenceHTTPClient"]:
    """
    Get or initialize the Roboflow InferenceHTTPClient.

    Returns None if API key not configured or SDK not available.
    """
    global _inference_client

    if settings is None:
        settings = get_settings()

    if not INFERENCE_SDK_AVAILABLE:
        logger.debug("inference-sdk not installed")
        return None

    if not settings.roboflow_enabled:
        logger.debug("Roboflow not configured - API key missing")
        return None

    if _inference_client is not None:
        return _inference_client

    try:
        _inference_client = InferenceHTTPClient(
            api_url="https://detect.roboflow.com",
            api_key=settings.roboflow_api_key,
        )
        logger.info("Roboflow InferenceHTTPClient initialized")
        return _inference_client
    except Exception as e:
        logger.error(f"Failed to initialize Roboflow client: {e}")
        return None


def is_roboflow_available(settings: Optional[Settings] = None) -> bool:
    """Check if Roboflow is available and configured."""
    if settings is None:
        settings = get_settings()

    return settings.roboflow_enabled


def get_model_id(model_type: RoboflowModelType, settings: Optional[Settings] = None) -> str:
    """Get the model ID for a given model type."""
    if settings is None:
        settings = get_settings()

    model_map = {
        RoboflowModelType.FLOOR_PLAN: settings.roboflow_floor_plan_model,
        RoboflowModelType.ROOM_SEGMENTATION: settings.roboflow_room_segmentation_model,
        RoboflowModelType.DOOR_DETECTION: settings.roboflow_door_detection_model,
        RoboflowModelType.WALL_FLOOR: settings.roboflow_wall_floor_model,
    }
    return model_map.get(model_type, settings.roboflow_floor_plan_model)


def run_inference(
    image_path: str,
    model_type: RoboflowModelType = RoboflowModelType.FLOOR_PLAN,
    confidence_threshold: Optional[float] = None,
    settings: Optional[Settings] = None,
) -> RoboflowResult:
    """
    Run Roboflow inference on an image using inference-sdk.

    Args:
        image_path: Path to the image file
        model_type: Type of model to use
        confidence_threshold: Minimum confidence for detections
        settings: Optional Settings instance

    Returns:
        RoboflowResult with detections/segmentations
    """
    if settings is None:
        settings = get_settings()

    if confidence_threshold is None:
        confidence_threshold = settings.roboflow_confidence_threshold

    model_id = get_model_id(model_type, settings)
    start_time = time.time()

    # Check if image exists
    if not Path(image_path).exists():
        return RoboflowResult(
            model_id=model_id,
            model_type=model_type,
            image_width=0,
            image_height=0,
            warnings=[f"Image not found: {image_path}"],
        )

    if not INFERENCE_SDK_AVAILABLE:
        return RoboflowResult(
            model_id=model_id,
            model_type=model_type,
            image_width=0,
            image_height=0,
            warnings=["inference-sdk not installed - run: pip install inference-sdk"],
        )

    if not is_roboflow_available(settings):
        return RoboflowResult(
            model_id=model_id,
            model_type=model_type,
            image_width=0,
            image_height=0,
            warnings=["Roboflow not configured - set SNAPGRID_ROBOFLOW_API_KEY"],
        )

    try:
        # Get inference client
        client = get_roboflow_client(settings)
        if client is None:
            return RoboflowResult(
                model_id=model_id,
                model_type=model_type,
                image_width=0,
                image_height=0,
                warnings=["Failed to initialize Roboflow client"],
            )

        # Run inference using inference-sdk
        result = client.infer(image_path, model_id=model_id)
        processing_time = int((time.time() - start_time) * 1000)

        # Parse response (inference-sdk returns dict)
        return _parse_roboflow_response(
            response=result,
            model_id=model_id,
            model_type=model_type,
            confidence_threshold=confidence_threshold,
            processing_time_ms=processing_time,
        )

    except Exception as e:
        logger.error(f"Roboflow inference failed: {e}")
        return RoboflowResult(
            model_id=model_id,
            model_type=model_type,
            image_width=0,
            image_height=0,
            processing_time_ms=int((time.time() - start_time) * 1000),
            warnings=[f"Inference failed: {str(e)}"],
        )


def run_inference_on_pdf_page(
    pdf_path: str,
    page_number: int = 1,
    model_type: RoboflowModelType = RoboflowModelType.FLOOR_PLAN,
    dpi: int = 150,
    confidence_threshold: Optional[float] = None,
    settings: Optional[Settings] = None,
) -> RoboflowResult:
    """
    Run Roboflow inference on a PDF page.

    Args:
        pdf_path: Path to the PDF file
        page_number: Page number (1-indexed)
        model_type: Type of model to use
        dpi: Resolution for rendering
        confidence_threshold: Minimum confidence
        settings: Optional Settings instance

    Returns:
        RoboflowResult with detections/segmentations
    """
    from .cv_pipeline import render_pdf_page_to_image
    import os

    # Render PDF page to image
    try:
        image_path = render_pdf_page_to_image(pdf_path, page_number, dpi)
    except Exception as e:
        return RoboflowResult(
            model_id=get_model_id(model_type, settings),
            model_type=model_type,
            image_width=0,
            image_height=0,
            warnings=[f"Failed to render PDF page: {str(e)}"],
        )

    try:
        # Run inference on rendered image
        result = run_inference(
            image_path=image_path,
            model_type=model_type,
            confidence_threshold=confidence_threshold,
            settings=settings,
        )
        return result
    finally:
        # Clean up temp image
        if os.path.exists(image_path):
            os.remove(image_path)


def _parse_roboflow_response(
    response: Dict,
    model_id: str,
    model_type: RoboflowModelType,
    confidence_threshold: float,
    processing_time_ms: int,
) -> RoboflowResult:
    """Parse Roboflow API response into RoboflowResult."""

    # Get image dimensions
    image_width = response.get("image", {}).get("width", 0)
    image_height = response.get("image", {}).get("height", 0)

    detections = []
    segmentations = []
    warnings = []

    # Parse predictions
    predictions = response.get("predictions", [])

    for pred in predictions:
        confidence = pred.get("confidence", 0)

        # Skip low confidence predictions
        if confidence < confidence_threshold:
            continue

        class_name = pred.get("class", "unknown")
        class_id = pred.get("class_id", 0)

        # Check if it's a segmentation (has points) or detection (has bbox)
        points = pred.get("points", [])

        if points:
            # Segmentation mask
            polygon_points = [(p.get("x", 0), p.get("y", 0)) for p in points]

            # Calculate area and perimeter from polygon
            area_px, perimeter_px = _calculate_polygon_metrics(polygon_points)

            # Get bounding box
            x_coords = [p[0] for p in polygon_points]
            y_coords = [p[1] for p in polygon_points]
            bbox = {
                "x": min(x_coords),
                "y": min(y_coords),
                "width": max(x_coords) - min(x_coords),
                "height": max(y_coords) - min(y_coords),
            }

            segmentations.append(SegmentationMask(
                class_name=class_name,
                class_id=class_id,
                confidence=confidence,
                points=polygon_points,
                area_px=area_px,
                perimeter_px=perimeter_px,
                bbox=bbox,
            ))

        else:
            # Object detection box
            x = pred.get("x", 0)
            y = pred.get("y", 0)
            width = pred.get("width", 0)
            height = pred.get("height", 0)

            detections.append(DetectionBox(
                class_name=class_name,
                class_id=class_id,
                confidence=confidence,
                x=x,
                y=y,
                width=width,
                height=height,
            ))

    return RoboflowResult(
        model_id=model_id,
        model_type=model_type,
        image_width=image_width,
        image_height=image_height,
        detections=detections,
        segmentations=segmentations,
        processing_time_ms=processing_time_ms,
        raw_response=response,
        warnings=warnings,
    )


def _calculate_polygon_metrics(points: List[Tuple[float, float]]) -> Tuple[float, float]:
    """
    Calculate area and perimeter of a polygon.

    Uses the Shoelace formula for area and sum of edge lengths for perimeter.

    Args:
        points: List of (x, y) polygon vertices

    Returns:
        Tuple of (area, perimeter) in pixels
    """
    if len(points) < 3:
        return 0.0, 0.0

    # Calculate area using Shoelace formula
    n = len(points)
    area = 0.0
    perimeter = 0.0

    for i in range(n):
        j = (i + 1) % n
        x1, y1 = points[i]
        x2, y2 = points[j]

        # Shoelace contribution
        area += x1 * y2
        area -= x2 * y1

        # Edge length
        edge_length = ((x2 - x1) ** 2 + (y2 - y1) ** 2) ** 0.5
        perimeter += edge_length

    area = abs(area) / 2.0

    return area, perimeter


# =============================================================================
# High-Level Detection Functions
# =============================================================================


def detect_walls(
    image_path: str,
    scale: int = 100,
    dpi: int = 150,
    settings: Optional[Settings] = None,
) -> Dict[str, Any]:
    """
    Detect walls in a floor plan image.

    Args:
        image_path: Path to the image
        scale: Drawing scale (e.g., 100 for 1:100)
        dpi: Image DPI for scale conversion
        settings: Optional Settings instance

    Returns:
        Dict with wall detections and measurements
    """
    result = run_inference(
        image_path=image_path,
        model_type=RoboflowModelType.WALL_FLOOR,
        settings=settings,
    )

    # Filter for wall class
    wall_segments = [
        seg for seg in result.segmentations
        if "wall" in seg.class_name.lower()
    ]

    # Calculate meters from pixels
    INCHES_PER_METER = 39.3701
    pixels_per_meter = (1.0 / scale) * INCHES_PER_METER * dpi

    total_perimeter_px = sum(seg.perimeter_px for seg in wall_segments)
    total_perimeter_m = total_perimeter_px / pixels_per_meter if pixels_per_meter > 0 else 0

    return {
        "wall_count": len(wall_segments),
        "total_perimeter_px": total_perimeter_px,
        "total_perimeter_m": round(total_perimeter_m, 2),
        "scale": f"1:{scale}",
        "walls": [seg.to_dict() for seg in wall_segments],
        "processing_time_ms": result.processing_time_ms,
        "warnings": result.warnings,
    }


def detect_rooms(
    image_path: str,
    scale: int = 100,
    dpi: int = 150,
    settings: Optional[Settings] = None,
) -> Dict[str, Any]:
    """
    Detect rooms in a floor plan image.

    Args:
        image_path: Path to the image
        scale: Drawing scale (e.g., 100 for 1:100)
        dpi: Image DPI for scale conversion
        settings: Optional Settings instance

    Returns:
        Dict with room detections and measurements
    """
    result = run_inference(
        image_path=image_path,
        model_type=RoboflowModelType.ROOM_SEGMENTATION,
        settings=settings,
    )

    # Calculate meters from pixels
    INCHES_PER_METER = 39.3701
    pixels_per_meter = (1.0 / scale) * INCHES_PER_METER * dpi
    pixels_per_m2 = pixels_per_meter ** 2

    rooms = []
    total_area_m2 = 0.0

    for seg in result.segmentations:
        area_m2 = seg.area_px / pixels_per_m2 if pixels_per_m2 > 0 else 0
        perimeter_m = seg.perimeter_px / pixels_per_meter if pixels_per_meter > 0 else 0

        rooms.append({
            "class_name": seg.class_name,
            "confidence": seg.confidence,
            "area_px": seg.area_px,
            "area_m2": round(area_m2, 2),
            "perimeter_px": seg.perimeter_px,
            "perimeter_m": round(perimeter_m, 2),
            "bbox": seg.bbox,
        })
        total_area_m2 += area_m2

    return {
        "room_count": len(rooms),
        "total_area_m2": round(total_area_m2, 2),
        "scale": f"1:{scale}",
        "rooms": rooms,
        "processing_time_ms": result.processing_time_ms,
        "warnings": result.warnings,
    }


def detect_doors(
    image_path: str,
    scale: int = 100,
    dpi: int = 150,
    settings: Optional[Settings] = None,
) -> Dict[str, Any]:
    """
    Detect doors in a floor plan image.

    Args:
        image_path: Path to the image
        scale: Drawing scale (e.g., 100 for 1:100)
        dpi: Image DPI for scale conversion
        settings: Optional Settings instance

    Returns:
        Dict with door detections and measurements
    """
    result = run_inference(
        image_path=image_path,
        model_type=RoboflowModelType.DOOR_DETECTION,
        settings=settings,
    )

    # Calculate meters from pixels
    INCHES_PER_METER = 39.3701
    pixels_per_meter = (1.0 / scale) * INCHES_PER_METER * dpi

    doors = []
    width_counts = {}

    for det in result.detections:
        # Estimate door width from bounding box
        # Assume door is oriented along shorter dimension
        door_width_px = min(det.width, det.height)
        door_width_m = door_width_px / pixels_per_meter if pixels_per_meter > 0 else 0

        # Round to nearest 10cm for grouping
        width_key = f"{round(door_width_m * 10) / 10:.1f}"
        width_counts[width_key] = width_counts.get(width_key, 0) + 1

        doors.append({
            "class_name": det.class_name,
            "confidence": det.confidence,
            "x": det.x,
            "y": det.y,
            "width_px": det.width,
            "height_px": det.height,
            "estimated_width_m": round(door_width_m, 2),
        })

    return {
        "door_count": len(doors),
        "by_width": width_counts,
        "scale": f"1:{scale}",
        "doors": doors,
        "processing_time_ms": result.processing_time_ms,
        "warnings": result.warnings,
    }


def analyze_floor_plan(
    image_path: str,
    scale: int = 100,
    dpi: int = 150,
    settings: Optional[Settings] = None,
) -> Dict[str, Any]:
    """
    Run comprehensive floor plan analysis using multiple models.

    Args:
        image_path: Path to the image
        scale: Drawing scale (e.g., 100 for 1:100)
        dpi: Image DPI
        settings: Optional Settings instance

    Returns:
        Dict with complete analysis results
    """
    start_time = time.time()

    # Run all detections
    walls_result = detect_walls(image_path, scale, dpi, settings)
    rooms_result = detect_rooms(image_path, scale, dpi, settings)
    doors_result = detect_doors(image_path, scale, dpi, settings)

    total_time = int((time.time() - start_time) * 1000)

    # Combine warnings
    all_warnings = (
        walls_result.get("warnings", []) +
        rooms_result.get("warnings", []) +
        doors_result.get("warnings", [])
    )

    return {
        "walls": walls_result,
        "rooms": rooms_result,
        "doors": doors_result,
        "summary": {
            "total_rooms": rooms_result.get("room_count", 0),
            "total_doors": doors_result.get("door_count", 0),
            "total_floor_area_m2": rooms_result.get("total_area_m2", 0),
            "total_wall_perimeter_m": walls_result.get("total_perimeter_m", 0),
        },
        "processing_time_ms": total_time,
        "scale": f"1:{scale}",
        "warnings": list(set(all_warnings)),
    }


# =============================================================================
# Status and Diagnostics
# =============================================================================


@dataclass
class RoboflowStatus:
    """Status of Roboflow integration."""
    sdk_installed: bool
    api_key_configured: bool
    client_available: bool
    models: Dict[str, str]

    def to_dict(self) -> Dict[str, Any]:
        return {
            "sdk_installed": self.sdk_installed,
            "api_key_configured": self.api_key_configured,
            "client_available": self.client_available,
            "models": self.models,
        }


def get_roboflow_status(settings: Optional[Settings] = None) -> RoboflowStatus:
    """Get the current status of Roboflow integration."""
    if settings is None:
        settings = get_settings()

    return RoboflowStatus(
        sdk_installed=INFERENCE_SDK_AVAILABLE,
        api_key_configured=bool(settings.roboflow_api_key),
        client_available=get_roboflow_client(settings) is not None,
        models={
            "floor_plan": settings.roboflow_floor_plan_model,
            "room_segmentation": settings.roboflow_room_segmentation_model,
            "door_detection": settings.roboflow_door_detection_model,
            "wall_floor": settings.roboflow_wall_floor_model,
        },
    )

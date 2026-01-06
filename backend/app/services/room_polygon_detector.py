"""
Room Polygon Detector

Detects enclosed room regions from floor plan images using OpenCV.
Converts contours to polygons with area and perimeter calculations.

Part of the geometry-first flooring pipeline.
"""

from dataclasses import dataclass
from pathlib import Path
from typing import List, Optional, Tuple, Union
import logging
import uuid
import math

logger = logging.getLogger(__name__)

# Optional imports
try:
    import cv2
    import numpy as np
    CV2_AVAILABLE = True
except ImportError:
    CV2_AVAILABLE = False
    logger.warning("OpenCV not available - room detection disabled")

try:
    import fitz
    FITZ_AVAILABLE = True
except ImportError:
    FITZ_AVAILABLE = False
    logger.warning("PyMuPDF not available - PDF rendering disabled")


@dataclass
class RoomPolygon:
    """Represents a detected room polygon."""
    id: str
    points: List[Tuple[float, float]]
    area_px: float
    area_m2: Optional[float] = None
    perimeter_px: float = 0.0
    perimeter_m: Optional[float] = None
    confidence: float = 1.0
    label: Optional[str] = None
    page_number: int = 1
    source: str = "contour"

    def to_dict(self):
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


def render_pdf_page_to_image(
    pdf_path: Union[str, Path],
    page_number: int = 1,
    dpi: int = 300,
) -> Optional["np.ndarray"]:
    """
    Render a PDF page to a numpy array (image).

    Args:
        pdf_path: Path to PDF file
        page_number: 1-indexed page number
        dpi: Render resolution

    Returns:
        Numpy array (BGR format) or None on error
    """
    if not FITZ_AVAILABLE:
        raise ImportError("PyMuPDF required for PDF rendering")
    if not CV2_AVAILABLE:
        raise ImportError("OpenCV required for image processing")

    try:
        doc = fitz.open(str(pdf_path))
        page = doc[page_number - 1]

        # Render at specified DPI
        zoom = dpi / 72.0
        mat = fitz.Matrix(zoom, zoom)
        pix = page.get_pixmap(matrix=mat)

        # Convert to numpy array
        img_data = pix.samples
        width = pix.width
        height = pix.height
        channels = pix.n

        img = np.frombuffer(img_data, dtype=np.uint8).reshape(height, width, channels)

        # Convert to BGR for OpenCV (from RGB or RGBA)
        if channels == 4:
            img = cv2.cvtColor(img, cv2.COLOR_RGBA2BGR)
        elif channels == 3:
            img = cv2.cvtColor(img, cv2.COLOR_RGB2BGR)

        doc.close()
        return img

    except Exception as e:
        logger.error(f"Failed to render PDF: {e}")
        return None


def load_image(
    file_path: Union[str, Path],
    page_number: Optional[int] = None,
    dpi: int = 300,
) -> Optional["np.ndarray"]:
    """
    Load image from file (PDF or image format).

    Args:
        file_path: Path to image or PDF
        page_number: Page number if PDF (1-indexed)
        dpi: Render DPI for PDF

    Returns:
        Numpy array (BGR) or None
    """
    path = Path(file_path)

    if path.suffix.lower() == '.pdf':
        return render_pdf_page_to_image(path, page_number or 1, dpi)
    else:
        # Regular image
        if not CV2_AVAILABLE:
            raise ImportError("OpenCV required")
        return cv2.imread(str(path))


def preprocess_for_room_detection(
    img: "np.ndarray",
    enhance_lines: bool = True,
    denoise: bool = True,
) -> "np.ndarray":
    """
    Preprocess floor plan image for room detection.

    Steps:
    1. Convert to grayscale
    2. Optional denoising
    3. Adaptive threshold
    4. Optional line enhancement

    Returns:
        Binary image (white = background, black = lines)
    """
    if not CV2_AVAILABLE:
        raise ImportError("OpenCV required")

    # Convert to grayscale
    if len(img.shape) == 3:
        gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    else:
        gray = img.copy()

    # Denoise
    if denoise:
        gray = cv2.fastNlMeansDenoising(gray, h=10)

    # Adaptive threshold (works better for varying lighting)
    binary = cv2.adaptiveThreshold(
        gray,
        255,
        cv2.ADAPTIVE_THRESH_GAUSSIAN_C,
        cv2.THRESH_BINARY_INV,
        blockSize=21,
        C=5,
    )

    # Optional: enhance lines with morphological operations
    if enhance_lines:
        # Create a small kernel for line enhancement
        kernel = np.ones((2, 2), np.uint8)
        binary = cv2.dilate(binary, kernel, iterations=1)
        binary = cv2.erode(binary, kernel, iterations=1)

    return binary


def close_gaps_in_walls(
    binary: "np.ndarray",
    gap_size: int = 15,
) -> "np.ndarray":
    """
    Close small gaps in walls using morphological closing.

    This helps create complete room enclosures from broken wall lines.

    Args:
        binary: Binary image with walls as white pixels
        gap_size: Maximum gap size to close (in pixels)

    Returns:
        Binary image with gaps closed
    """
    if not CV2_AVAILABLE:
        raise ImportError("OpenCV required")

    # Use morphological closing (dilation followed by erosion)
    # Larger kernel = closes larger gaps but may merge separate rooms
    kernel = np.ones((gap_size, gap_size), np.uint8)

    closed = cv2.morphologyEx(binary, cv2.MORPH_CLOSE, kernel)

    # Also try horizontal and vertical closing separately
    # This preserves room corners better
    h_kernel = np.ones((1, gap_size), np.uint8)
    v_kernel = np.ones((gap_size, 1), np.uint8)

    h_closed = cv2.morphologyEx(closed, cv2.MORPH_CLOSE, h_kernel)
    v_closed = cv2.morphologyEx(h_closed, cv2.MORPH_CLOSE, v_kernel)

    return v_closed


def find_room_contours(
    binary: "np.ndarray",
    min_area_ratio: float = 0.005,  # At least 0.5% of image area
    max_area_ratio: float = 0.15,   # At most 15% of image area
    max_aspect_ratio: float = 4.0,  # Rooms shouldn't be too elongated
    min_solidity: float = 0.5,      # At least 50% filled (convex hull ratio)
    min_extent: float = 0.4,        # At least 40% of bounding box filled
) -> List["np.ndarray"]:
    """
    Find contours that likely represent rooms.

    Filters by:
    - Area ratio (rooms are typically 0.5-15% of floor plan)
    - Aspect ratio (rooms are roughly rectangular)
    - Solidity (area / convex_hull_area - rooms are mostly convex)
    - Extent (area / bounding_box_area - rooms fill their bbox)

    Args:
        binary: Binary image (walls as white)
        min_area_ratio: Minimum ratio of contour area to image area
        max_area_ratio: Maximum ratio of contour area to image area
        max_aspect_ratio: Maximum bounding box aspect ratio
        min_solidity: Minimum solidity (area / convex hull area)
        min_extent: Minimum extent (area / bounding box area)

    Returns:
        List of contour arrays
    """
    if not CV2_AVAILABLE:
        raise ImportError("OpenCV required")

    # Invert: we want to find enclosed white regions (rooms)
    # In our binary, walls are white, so invert to make rooms white
    inverted = cv2.bitwise_not(binary)

    # Find contours
    contours, hierarchy = cv2.findContours(
        inverted,
        cv2.RETR_CCOMP,  # Get 2-level hierarchy (external + holes)
        cv2.CHAIN_APPROX_SIMPLE,
    )

    if contours is None or len(contours) == 0:
        return []

    # Calculate image area for filtering
    img_area = binary.shape[0] * binary.shape[1]
    min_area = img_area * min_area_ratio
    max_area = img_area * max_area_ratio

    logger.info(f"Image area: {img_area:,} px, min room: {min_area:,.0f} px ({min_area_ratio*100}%), max room: {max_area:,.0f} px ({max_area_ratio*100}%)")

    # Filter contours
    room_contours = []
    stats = {"total": len(contours), "too_small": 0, "too_large": 0,
             "bad_aspect": 0, "bad_solidity": 0, "bad_extent": 0, "passed": 0}

    for i, contour in enumerate(contours):
        area = cv2.contourArea(contour)

        # Filter by area (most contours rejected here)
        if area < min_area:
            stats["too_small"] += 1
            continue
        if area > max_area:
            stats["too_large"] += 1
            continue

        # Filter by aspect ratio
        x, y, w, h = cv2.boundingRect(contour)
        aspect = max(w, h) / (min(w, h) + 1)
        if aspect > max_aspect_ratio:
            stats["bad_aspect"] += 1
            continue

        # Filter by solidity (area / convex hull area)
        # Rooms should be mostly convex - irregular shapes are likely noise
        hull = cv2.convexHull(contour)
        hull_area = cv2.contourArea(hull)
        if hull_area > 0:
            solidity = area / hull_area
            if solidity < min_solidity:
                stats["bad_solidity"] += 1
                continue

        # Filter by extent (area / bounding box area)
        # Rooms should fill most of their bounding box
        bbox_area = w * h
        if bbox_area > 0:
            extent = area / bbox_area
            if extent < min_extent:
                stats["bad_extent"] += 1
                continue

        room_contours.append(contour)
        stats["passed"] += 1

    logger.info(f"Contour filtering: {stats}")
    return room_contours


def simplify_contour(
    contour: "np.ndarray",
    epsilon_factor: float = 0.02,
) -> "np.ndarray":
    """
    Simplify contour to polygon with fewer points.

    Args:
        contour: OpenCV contour
        epsilon_factor: Approximation factor (higher = simpler)

    Returns:
        Simplified contour
    """
    if not CV2_AVAILABLE:
        raise ImportError("OpenCV required")

    perimeter = cv2.arcLength(contour, True)
    epsilon = epsilon_factor * perimeter
    simplified = cv2.approxPolyDP(contour, epsilon, True)

    return simplified


def contour_to_polygon(
    contour: "np.ndarray",
    page_number: int = 1,
    confidence: float = 1.0,
    source: str = "contour",
) -> RoomPolygon:
    """
    Convert OpenCV contour to RoomPolygon.

    Args:
        contour: OpenCV contour array
        page_number: Source page number
        confidence: Detection confidence
        source: Detection source label

    Returns:
        RoomPolygon with area and perimeter
    """
    if not CV2_AVAILABLE:
        raise ImportError("OpenCV required")

    # Simplify contour
    simplified = simplify_contour(contour)

    # Extract points
    points = [(float(pt[0][0]), float(pt[0][1])) for pt in simplified]

    # Calculate area and perimeter
    area_px = cv2.contourArea(contour)
    perimeter_px = cv2.arcLength(contour, True)

    return RoomPolygon(
        id=f"room_{uuid.uuid4().hex[:8]}",
        points=points,
        area_px=area_px,
        perimeter_px=perimeter_px,
        confidence=confidence,
        page_number=page_number,
        source=source,
    )


def detect_room_polygons_from_pdf(
    pdf_path: Union[str, Path],
    page_number: int = 1,
    dpi: int = 300,
    min_room_area_m2: float = 2.0,
    close_gaps: bool = True,
    gap_size: int = 15,
) -> List[RoomPolygon]:
    """
    Detect room polygons from a PDF page.

    Main entry point for vector pipeline.

    Args:
        pdf_path: Path to PDF file
        page_number: 1-indexed page number
        dpi: Render resolution
        min_room_area_m2: Approximate minimum room area (used for filtering)
        close_gaps: Whether to close gaps in walls
        gap_size: Gap closing kernel size

    Returns:
        List of RoomPolygon objects
    """
    # Render PDF to image
    img = render_pdf_page_to_image(pdf_path, page_number, dpi)
    if img is None:
        logger.error("Failed to render PDF")
        return []

    return _detect_rooms_from_image(
        img,
        page_number=page_number,
        dpi=dpi,
        min_room_area_m2=min_room_area_m2,
        close_gaps=close_gaps,
        gap_size=gap_size,
        source="vector_pdf",
    )


def detect_room_polygons_from_image(
    file_path: Union[str, Path],
    page_number: Optional[int] = None,
    dpi: int = 300,
    min_room_area_m2: float = 2.0,
    close_gaps: bool = True,
    gap_size: int = 20,
) -> List[RoomPolygon]:
    """
    Detect room polygons from an image file.

    Args:
        file_path: Path to image (or PDF)
        page_number: Page number if PDF
        dpi: Render DPI for PDF, assumed DPI for image
        min_room_area_m2: Approximate minimum room area
        close_gaps: Whether to close gaps
        gap_size: Gap closing kernel size

    Returns:
        List of RoomPolygon objects
    """
    img = load_image(file_path, page_number, dpi)
    if img is None:
        logger.error(f"Failed to load image: {file_path}")
        return []

    return _detect_rooms_from_image(
        img,
        page_number=page_number or 1,
        dpi=dpi,
        min_room_area_m2=min_room_area_m2,
        close_gaps=close_gaps,
        gap_size=gap_size,
        source="raster",
    )


def _detect_rooms_from_image(
    img: "np.ndarray",
    page_number: int = 1,
    dpi: int = 300,
    min_room_area_m2: float = 3.0,
    close_gaps: bool = True,
    gap_size: int = 8,
    source: str = "contour",
) -> List[RoomPolygon]:
    """
    Core room detection from image.

    Args:
        img: BGR image as numpy array
        page_number: Source page number
        dpi: Render DPI (for minimum area calculation)
        min_room_area_m2: Approximate minimum room area
        close_gaps: Whether to close gaps in walls
        gap_size: Gap closing kernel size
        source: Detection source label

    Returns:
        List of RoomPolygon objects
    """
    if not CV2_AVAILABLE:
        raise ImportError("OpenCV required for room detection")

    logger.info(f"Processing image: {img.shape[1]}x{img.shape[0]} pixels")

    # Step 1: Preprocess (skip denoising for CAD drawings - they're clean)
    binary = preprocess_for_room_detection(img, enhance_lines=True, denoise=False)

    # Step 2: Close gaps if requested
    if close_gaps:
        binary = close_gaps_in_walls(binary, gap_size=gap_size)

    # Step 3: Find contours with ratio-based filtering
    # Rooms typically occupy 0.5% to 15% of a floor plan image
    # For apartments: 3-8 rooms on a plan, so each room ~5-15% of plan area
    # For larger buildings: many rooms, so each room ~0.5-5% of plan area
    contours = find_room_contours(
        binary,
        min_area_ratio=0.005,   # At least 0.5% of image
        max_area_ratio=0.15,    # At most 15% of image
        max_aspect_ratio=4.0,   # Reasonable room proportions
        min_solidity=0.5,       # Rooms are mostly convex
        min_extent=0.4,         # Rooms fill their bounding box
    )

    # Step 4: Convert to RoomPolygon objects
    polygons = []
    for i, contour in enumerate(contours):
        polygon = contour_to_polygon(
            contour,
            page_number=page_number,
            confidence=0.75,  # Contour detection is moderately reliable
            source=source,
        )
        polygon.label = f"Room {i + 1}"
        polygons.append(polygon)

    # Sort by area (largest first)
    polygons.sort(key=lambda p: p.area_px, reverse=True)

    logger.info(f"Detected {len(polygons)} room polygons")
    return polygons


def crop_plan_region(
    img: "np.ndarray",
    margin_ratio: float = 0.05,
) -> Tuple["np.ndarray", Tuple[int, int, int, int]]:
    """
    Crop image to the main plan region, excluding title blocks and margins.

    Strategy:
    1. Find regions with high line density (the floor plan)
    2. Exclude sparse regions (margins, title blocks are often text-heavy but line-sparse)

    Args:
        img: Input image (BGR)
        margin_ratio: Extra margin to add around detected region

    Returns:
        Tuple of (cropped image, (x, y, width, height) of crop region)
    """
    if not CV2_AVAILABLE:
        raise ImportError("OpenCV required")

    # Convert to grayscale and threshold
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY) if len(img.shape) == 3 else img
    _, binary = cv2.threshold(gray, 240, 255, cv2.THRESH_BINARY_INV)

    # Find the bounding box of all non-white content
    coords = cv2.findNonZero(binary)
    if coords is None:
        return img, (0, 0, img.shape[1], img.shape[0])

    x, y, w, h = cv2.boundingRect(coords)

    # Add margin
    margin_x = int(w * margin_ratio)
    margin_y = int(h * margin_ratio)

    x = max(0, x - margin_x)
    y = max(0, y - margin_y)
    w = min(img.shape[1] - x, w + 2 * margin_x)
    h = min(img.shape[0] - y, h + 2 * margin_y)

    cropped = img[y:y+h, x:x+w]

    return cropped, (x, y, w, h)

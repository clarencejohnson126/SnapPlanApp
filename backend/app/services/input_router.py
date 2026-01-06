"""
Input Router Service

Detects the type of input (CAD PDF with text, CAD PDF without text, scanned PDF, photo)
and routes to the appropriate processing pipeline.

Input Types:
- CAD_WITH_TEXT: CAD-exported PDF with text annotations (NRF, U values) → Text extraction
- CAD_NO_TEXT: CAD-exported PDF without annotations → Vector + CV
- SCANNED_PDF: Scanned blueprint (raster image in PDF) → Roboflow CV
- PHOTO: Photo of blueprint (JPG, PNG) → Roboflow CV
"""

from dataclasses import dataclass
from enum import Enum
from pathlib import Path
from typing import Optional, Tuple, List
import logging
import re

logger = logging.getLogger(__name__)


class InputType(Enum):
    """Types of blueprint inputs that SnapGrid can process."""
    CAD_WITH_TEXT = "cad_with_text"  # German CAD PDFs with NRF/U annotations
    CAD_NO_TEXT = "cad_no_text"  # CAD PDFs with vectors but no text
    SCANNED_PDF = "scanned_pdf"  # Scanned blueprint (raster)
    PHOTO = "photo"  # Photo of blueprint (JPG, PNG, etc.)
    UNKNOWN = "unknown"


class ProcessingPipeline(Enum):
    """Processing pipelines available for different input types."""
    TEXT_EXTRACTION = "text_extraction"  # pdfplumber/PyMuPDF text extraction
    VECTOR_ANALYSIS = "vector_analysis"  # Vector geometry parsing + local YOLO
    ROBOFLOW_CV = "roboflow_cv"  # Roboflow API for CV
    HYBRID = "hybrid"  # Combination of methods


@dataclass
class InputAnalysis:
    """Result of analyzing an input file."""
    input_type: InputType
    recommended_pipeline: ProcessingPipeline
    has_text_layer: bool
    has_vector_layer: bool
    is_raster_only: bool
    text_sample: Optional[str] = None
    detected_annotations: List[str] = None
    confidence: float = 0.0
    warnings: List[str] = None

    def __post_init__(self):
        if self.detected_annotations is None:
            self.detected_annotations = []
        if self.warnings is None:
            self.warnings = []


def analyze_input(file_path: str) -> InputAnalysis:
    """
    Analyze an input file and determine its type and recommended processing pipeline.

    Args:
        file_path: Path to the input file (PDF, JPG, PNG, etc.)

    Returns:
        InputAnalysis with detected type and recommended pipeline
    """
    path = Path(file_path)

    if not path.exists():
        return InputAnalysis(
            input_type=InputType.UNKNOWN,
            recommended_pipeline=ProcessingPipeline.ROBOFLOW_CV,
            has_text_layer=False,
            has_vector_layer=False,
            is_raster_only=False,
            confidence=0.0,
            warnings=[f"File not found: {file_path}"],
        )

    suffix = path.suffix.lower()

    # Handle image files (photos)
    if suffix in ['.jpg', '.jpeg', '.png', '.tiff', '.tif', '.bmp', '.webp']:
        return InputAnalysis(
            input_type=InputType.PHOTO,
            recommended_pipeline=ProcessingPipeline.ROBOFLOW_CV,
            has_text_layer=False,
            has_vector_layer=False,
            is_raster_only=True,
            confidence=1.0,
        )

    # Handle PDF files
    if suffix == '.pdf':
        return _analyze_pdf(file_path)

    # Unknown file type
    return InputAnalysis(
        input_type=InputType.UNKNOWN,
        recommended_pipeline=ProcessingPipeline.ROBOFLOW_CV,
        has_text_layer=False,
        has_vector_layer=False,
        is_raster_only=False,
        confidence=0.0,
        warnings=[f"Unknown file type: {suffix}"],
    )


def _analyze_pdf(pdf_path: str) -> InputAnalysis:
    """
    Analyze a PDF file to determine if it's CAD (with/without text) or scanned.

    Detection strategy:
    1. Extract text - check for German annotations (NRF, U, LH, etc.)
    2. Check for vector content (drawing operators)
    3. Check for embedded images (raster content)
    """
    try:
        import fitz  # PyMuPDF
    except ImportError:
        return InputAnalysis(
            input_type=InputType.UNKNOWN,
            recommended_pipeline=ProcessingPipeline.ROBOFLOW_CV,
            has_text_layer=False,
            has_vector_layer=False,
            is_raster_only=False,
            confidence=0.0,
            warnings=["PyMuPDF not installed - cannot analyze PDF"],
        )

    try:
        doc = fitz.open(pdf_path)

        # Analyze first few pages (or all if < 5 pages)
        pages_to_check = min(len(doc), 5)

        total_text_chars = 0
        total_images = 0
        total_drawings = 0
        detected_annotations = []
        text_sample = ""

        # German architectural annotation patterns
        german_patterns = {
            'NRF': r'NRF\s*[=:]?\s*[\d,\.]+\s*m[²2]?',  # Net room area
            'U': r'U\s*[=:]?\s*[\d,\.]+\s*m(?![²2])',  # Perimeter
            'LH': r'LH\s*[=:]?\s*[\d,\.]+\s*m',  # Ceiling height
            'BGF': r'BGF\s*[=:]?\s*[\d,\.]+\s*m[²2]?',  # Gross floor area
            'ROOM_ID': r'B\.\d{2}\.\d\.\d{3}',  # Room ID pattern
            'DOOR_ID': r'B\.\d{2}\.\d\.\d{3}-\d+',  # Door ID pattern
            'FIRE_RATING': r'T\s*[39]0[-\s]?RS|DSS',  # Fire ratings
            'SCALE': r'M(?:aßstab)?\s*1\s*:\s*\d+',  # Scale annotation
        }

        for page_num in range(pages_to_check):
            page = doc[page_num]

            # Extract text
            text = page.get_text()
            total_text_chars += len(text)

            if not text_sample and text.strip():
                text_sample = text[:500]

            # Check for German annotation patterns
            for pattern_name, pattern in german_patterns.items():
                if re.search(pattern, text, re.IGNORECASE):
                    if pattern_name not in detected_annotations:
                        detected_annotations.append(pattern_name)

            # Count images (raster content)
            images = page.get_images()
            total_images += len(images)

            # Check for drawing operators (vector content)
            # Get the page's drawing commands
            drawings = page.get_drawings()
            total_drawings += len(drawings)

        doc.close()

        # Determine input type based on analysis
        has_text = total_text_chars > 100
        has_german_annotations = len(detected_annotations) >= 2
        has_vectors = total_drawings > 100
        has_significant_raster = total_images > 0 and total_drawings < 50

        # Classification logic
        if has_german_annotations and has_text:
            # CAD PDF with German text annotations - best case
            return InputAnalysis(
                input_type=InputType.CAD_WITH_TEXT,
                recommended_pipeline=ProcessingPipeline.TEXT_EXTRACTION,
                has_text_layer=True,
                has_vector_layer=has_vectors,
                is_raster_only=False,
                text_sample=text_sample,
                detected_annotations=detected_annotations,
                confidence=0.95,
            )

        elif has_vectors and not has_significant_raster:
            # CAD PDF without text - use vector + CV
            return InputAnalysis(
                input_type=InputType.CAD_NO_TEXT,
                recommended_pipeline=ProcessingPipeline.HYBRID,
                has_text_layer=has_text,
                has_vector_layer=True,
                is_raster_only=False,
                text_sample=text_sample if has_text else None,
                detected_annotations=detected_annotations,
                confidence=0.85,
                warnings=["No German annotations found - using vector + CV pipeline"],
            )

        elif has_significant_raster:
            # Scanned PDF - pure raster, needs Roboflow CV
            return InputAnalysis(
                input_type=InputType.SCANNED_PDF,
                recommended_pipeline=ProcessingPipeline.ROBOFLOW_CV,
                has_text_layer=has_text,  # OCR text layer may exist
                has_vector_layer=False,
                is_raster_only=True,
                text_sample=text_sample if has_text else None,
                confidence=0.90,
                warnings=["Scanned PDF detected - using Roboflow CV pipeline"],
            )

        else:
            # Fallback - use hybrid approach
            return InputAnalysis(
                input_type=InputType.CAD_NO_TEXT,
                recommended_pipeline=ProcessingPipeline.HYBRID,
                has_text_layer=has_text,
                has_vector_layer=has_vectors,
                is_raster_only=not has_vectors,
                text_sample=text_sample if has_text else None,
                detected_annotations=detected_annotations,
                confidence=0.70,
                warnings=["Unclear document type - using hybrid pipeline"],
            )

    except Exception as e:
        logger.error(f"Error analyzing PDF: {e}")
        return InputAnalysis(
            input_type=InputType.UNKNOWN,
            recommended_pipeline=ProcessingPipeline.ROBOFLOW_CV,
            has_text_layer=False,
            has_vector_layer=False,
            is_raster_only=False,
            confidence=0.0,
            warnings=[f"Error analyzing PDF: {str(e)}"],
        )


def get_pipeline_for_input(analysis: InputAnalysis) -> ProcessingPipeline:
    """
    Get the recommended processing pipeline for an analyzed input.

    Args:
        analysis: InputAnalysis from analyze_input()

    Returns:
        ProcessingPipeline to use
    """
    return analysis.recommended_pipeline


def should_use_roboflow(analysis: InputAnalysis) -> bool:
    """
    Check if Roboflow CV should be used for this input.

    Roboflow is recommended for:
    - Scanned PDFs (raster only)
    - Photos
    - CAD PDFs without German annotations (as fallback)

    Args:
        analysis: InputAnalysis from analyze_input()

    Returns:
        True if Roboflow should be used
    """
    return analysis.recommended_pipeline in [
        ProcessingPipeline.ROBOFLOW_CV,
        ProcessingPipeline.HYBRID,
    ]


def should_use_text_extraction(analysis: InputAnalysis) -> bool:
    """
    Check if text extraction should be used for this input.

    Text extraction is recommended for:
    - CAD PDFs with German annotations (NRF, U, LH values)

    Args:
        analysis: InputAnalysis from analyze_input()

    Returns:
        True if text extraction should be used
    """
    return (
        analysis.has_text_layer
        and len(analysis.detected_annotations) >= 2
    )


def route_to_pipeline(
    file_path: str,
    force_pipeline: Optional[ProcessingPipeline] = None,
) -> Tuple[InputAnalysis, ProcessingPipeline]:
    """
    Analyze input and route to appropriate pipeline.

    Args:
        file_path: Path to the input file
        force_pipeline: Optional pipeline to force (overrides auto-detection)

    Returns:
        Tuple of (InputAnalysis, ProcessingPipeline)
    """
    analysis = analyze_input(file_path)

    if force_pipeline is not None:
        return analysis, force_pipeline

    return analysis, analysis.recommended_pipeline

"""
Plan Ingestion Service

Handles PDF loading, page rendering, and metadata extraction for blueprint analysis.
Uses PyMuPDF (fitz) for PDF operations.

Part of the Aufmaß Engine - Phase B.
"""

from dataclasses import dataclass, field
from typing import List, Optional, Dict, Any, Union
from pathlib import Path
import uuid
import tempfile
import io

import fitz  # PyMuPDF
from PIL import Image


# Constants
PDF_POINTS_PER_INCH = 72.0
DEFAULT_RENDER_DPI = 150


@dataclass
class PageInfo:
    """Information about a single page in a plan document."""

    page_number: int  # 1-indexed
    width_points: float  # Width in PDF points (72 points = 1 inch)
    height_points: float  # Height in PDF points
    width_px: int  # Width in pixels at rendered DPI
    height_px: int  # Height in pixels at rendered DPI
    rotation: int  # Page rotation in degrees (0, 90, 180, 270)
    dpi: int = DEFAULT_RENDER_DPI
    rendered_path: Optional[str] = None  # Path to rendered PNG if saved

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return {
            "page_number": self.page_number,
            "width_points": self.width_points,
            "height_points": self.height_points,
            "width_px": self.width_px,
            "height_px": self.height_px,
            "rotation": self.rotation,
            "dpi": self.dpi,
            "rendered_path": self.rendered_path,
        }

    @property
    def width_inches(self) -> float:
        """Page width in inches."""
        return self.width_points / PDF_POINTS_PER_INCH

    @property
    def height_inches(self) -> float:
        """Page height in inches."""
        return self.height_points / PDF_POINTS_PER_INCH


@dataclass
class PlanDocument:
    """Represents an ingested plan document with page information."""

    file_id: str
    filename: str
    file_path: str
    total_pages: int
    pages: List[PageInfo] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return {
            "file_id": self.file_id,
            "filename": self.filename,
            "file_path": self.file_path,
            "total_pages": self.total_pages,
            "pages": [p.to_dict() for p in self.pages],
            "metadata": self.metadata,
        }

    def get_page(self, page_number: int) -> Optional[PageInfo]:
        """Get PageInfo for a specific page (1-indexed)."""
        for page in self.pages:
            if page.page_number == page_number:
                return page
        return None


def _calculate_pixel_dimensions(
    width_points: float,
    height_points: float,
    dpi: int,
) -> tuple[int, int]:
    """
    Calculate pixel dimensions from PDF points at a given DPI.

    Args:
        width_points: Width in PDF points
        height_points: Height in PDF points
        dpi: Dots per inch for rendering

    Returns:
        Tuple of (width_px, height_px)
    """
    scale = dpi / PDF_POINTS_PER_INCH
    width_px = int(width_points * scale)
    height_px = int(height_points * scale)
    return width_px, height_px


def load_plan_document(
    file_path: Union[str, Path],
    file_id: Optional[str] = None,
    dpi: int = DEFAULT_RENDER_DPI,
) -> PlanDocument:
    """
    Load a PDF document and extract page information.

    This is a synchronous function that opens the PDF, reads metadata,
    and builds a PlanDocument with PageInfo for each page.

    Args:
        file_path: Path to the PDF file
        file_id: Optional file ID (auto-generated if not provided)
        dpi: DPI to use for pixel dimension calculations

    Returns:
        PlanDocument with page information

    Raises:
        FileNotFoundError: If PDF file does not exist
        ValueError: If file is not a valid PDF
    """
    path = Path(file_path)
    if not path.exists():
        raise FileNotFoundError(f"PDF file not found: {file_path}")

    if file_id is None:
        file_id = str(uuid.uuid4())

    try:
        doc = fitz.open(str(path))
    except Exception as e:
        raise ValueError(f"Failed to open PDF: {e}") from e

    try:
        # Extract metadata
        metadata = {
            "title": doc.metadata.get("title", ""),
            "author": doc.metadata.get("author", ""),
            "subject": doc.metadata.get("subject", ""),
            "creator": doc.metadata.get("creator", ""),
            "producer": doc.metadata.get("producer", ""),
            "creation_date": doc.metadata.get("creationDate", ""),
            "mod_date": doc.metadata.get("modDate", ""),
            "format": doc.metadata.get("format", ""),
            "encryption": doc.metadata.get("encryption", None),
        }

        # Build page info list
        pages: List[PageInfo] = []
        for page_num in range(doc.page_count):
            page = doc[page_num]
            rect = page.rect  # Page rectangle in points

            width_points = rect.width
            height_points = rect.height
            rotation = page.rotation

            width_px, height_px = _calculate_pixel_dimensions(
                width_points, height_points, dpi
            )

            page_info = PageInfo(
                page_number=page_num + 1,  # 1-indexed
                width_points=width_points,
                height_points=height_points,
                width_px=width_px,
                height_px=height_px,
                rotation=rotation,
                dpi=dpi,
            )
            pages.append(page_info)

        plan_doc = PlanDocument(
            file_id=file_id,
            filename=path.name,
            file_path=str(path.absolute()),
            total_pages=doc.page_count,
            pages=pages,
            metadata=metadata,
        )

        return plan_doc

    finally:
        doc.close()


def render_page_to_image(
    file_path: Union[str, Path],
    page_number: int,
    dpi: int = DEFAULT_RENDER_DPI,
) -> Image.Image:
    """
    Render a single PDF page to a PIL Image.

    Args:
        file_path: Path to the PDF file
        page_number: Page number to render (1-indexed)
        dpi: Resolution for rendering

    Returns:
        PIL Image object

    Raises:
        FileNotFoundError: If PDF file does not exist
        ValueError: If page_number is out of range
    """
    path = Path(file_path)
    if not path.exists():
        raise FileNotFoundError(f"PDF file not found: {file_path}")

    doc = fitz.open(str(path))
    try:
        if page_number < 1 or page_number > doc.page_count:
            raise ValueError(
                f"Page {page_number} out of range. Document has {doc.page_count} pages."
            )

        page = doc[page_number - 1]  # Convert to 0-indexed

        # Create transformation matrix for DPI
        # PyMuPDF default is 72 DPI, so we scale accordingly
        scale = dpi / PDF_POINTS_PER_INCH
        matrix = fitz.Matrix(scale, scale)

        # Render page to pixmap
        pixmap = page.get_pixmap(matrix=matrix, alpha=False)

        # Convert to PIL Image
        img_data = pixmap.tobytes("png")
        img = Image.open(io.BytesIO(img_data))

        return img

    finally:
        doc.close()


def render_page_to_file(
    file_path: Union[str, Path],
    page_number: int,
    output_path: Optional[Union[str, Path]] = None,
    dpi: int = DEFAULT_RENDER_DPI,
) -> str:
    """
    Render a single PDF page to an image file.

    Args:
        file_path: Path to the PDF file
        page_number: Page number to render (1-indexed)
        output_path: Path for output image (auto-generated if not provided)
        dpi: Resolution for rendering

    Returns:
        Path to the rendered image file
    """
    img = render_page_to_image(file_path, page_number, dpi)

    if output_path is None:
        # Generate a temp file path
        output_path = Path(tempfile.gettempdir()) / f"page_{page_number}_{uuid.uuid4().hex[:8]}.png"

    output_path = Path(output_path)
    img.save(str(output_path), "PNG")

    return str(output_path)


def extract_page_text(
    file_path: Union[str, Path],
    page_number: int,
) -> str:
    """
    Extract text content from a PDF page.

    This is useful for scale detection (finding "1:100" annotations, etc.)

    Args:
        file_path: Path to the PDF file
        page_number: Page number to extract text from (1-indexed)

    Returns:
        Text content of the page

    Raises:
        FileNotFoundError: If PDF file does not exist
        ValueError: If page_number is out of range
    """
    path = Path(file_path)
    if not path.exists():
        raise FileNotFoundError(f"PDF file not found: {file_path}")

    doc = fitz.open(str(path))
    try:
        if page_number < 1 or page_number > doc.page_count:
            raise ValueError(
                f"Page {page_number} out of range. Document has {doc.page_count} pages."
            )

        page = doc[page_number - 1]
        text = page.get_text()

        return text

    finally:
        doc.close()


def extract_all_text(file_path: Union[str, Path]) -> Dict[int, str]:
    """
    Extract text content from all pages of a PDF.

    Args:
        file_path: Path to the PDF file

    Returns:
        Dictionary mapping page number (1-indexed) to text content
    """
    path = Path(file_path)
    if not path.exists():
        raise FileNotFoundError(f"PDF file not found: {file_path}")

    doc = fitz.open(str(path))
    try:
        result = {}
        for page_num in range(doc.page_count):
            page = doc[page_num]
            result[page_num + 1] = page.get_text()
        return result

    finally:
        doc.close()


def extract_metadata(file_path: Union[str, Path]) -> Dict[str, Any]:
    """
    Extract metadata from a PDF document.

    Args:
        file_path: Path to the PDF file

    Returns:
        Dictionary containing:
        - title: Document title if available
        - author: Document author if available
        - creation_date: Creation timestamp
        - page_count: Number of pages
        - page_sizes: List of (width, height) tuples in PDF points
    """
    path = Path(file_path)
    if not path.exists():
        raise FileNotFoundError(f"PDF file not found: {file_path}")

    doc = fitz.open(str(path))
    try:
        page_sizes = []
        for page_num in range(doc.page_count):
            page = doc[page_num]
            rect = page.rect
            page_sizes.append((rect.width, rect.height))

        return {
            "title": doc.metadata.get("title", ""),
            "author": doc.metadata.get("author", ""),
            "subject": doc.metadata.get("subject", ""),
            "creator": doc.metadata.get("creator", ""),
            "creation_date": doc.metadata.get("creationDate", ""),
            "page_count": doc.page_count,
            "page_sizes": page_sizes,
        }

    finally:
        doc.close()


# Async wrappers for API compatibility
async def ingest_plan(
    file_path: str,
    render_dpi: int = DEFAULT_RENDER_DPI,
    output_dir: Optional[str] = None,
) -> PlanDocument:
    """
    Async wrapper for load_plan_document.

    Loads a PDF blueprint and extracts page information.

    Args:
        file_path: Path to the PDF file
        render_dpi: Resolution for pixel dimension calculations
        output_dir: Not used in current implementation

    Returns:
        PlanDocument with page information
    """
    return load_plan_document(file_path, dpi=render_dpi)


async def render_page(
    file_path: str,
    page_number: int,
    dpi: int = DEFAULT_RENDER_DPI,
    output_path: Optional[str] = None,
) -> str:
    """
    Async wrapper for render_page_to_file.

    Renders a single page from a PDF to an image file.

    Args:
        file_path: Path to the PDF file
        page_number: Page number to render (1-indexed)
        dpi: Resolution for rendering
        output_path: Path for output image (auto-generated if not provided)

    Returns:
        Path to the rendered image file
    """
    return render_page_to_file(file_path, page_number, output_path, dpi)

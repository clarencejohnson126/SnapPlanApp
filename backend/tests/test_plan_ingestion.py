"""
Tests for plan ingestion service.

These tests validate PDF loading, page rendering, and metadata extraction
using PyMuPDF (fitz).

Test philosophy:
- Assert correct page dimensions and metadata
- Validate image rendering produces valid PIL images
- Verify text extraction returns strings
- Test error handling for invalid inputs
"""

import sys
import tempfile
from pathlib import Path

import pytest
from PIL import Image

# Add backend to path
backend_dir = Path(__file__).parent.parent
sys.path.insert(0, str(backend_dir))

from app.services.plan_ingestion import (
    PDF_POINTS_PER_INCH,
    DEFAULT_RENDER_DPI,
    PageInfo,
    PlanDocument,
    load_plan_document,
    render_page_to_image,
    render_page_to_file,
    extract_page_text,
    extract_all_text,
    extract_metadata,
    _calculate_pixel_dimensions,
)


class TestPixelDimensionCalculation:
    """Tests for pixel dimension calculation from PDF points."""

    def test_calculate_at_72_dpi(self):
        """At 72 DPI (PDF native), pixels should equal points."""
        width_px, height_px = _calculate_pixel_dimensions(72.0, 144.0, 72)
        assert width_px == 72
        assert height_px == 144

    def test_calculate_at_150_dpi(self):
        """At 150 DPI, pixels should scale proportionally."""
        # 72 points at 150 DPI = 72 * (150/72) = 150 pixels
        width_px, height_px = _calculate_pixel_dimensions(72.0, 72.0, 150)
        assert width_px == 150
        assert height_px == 150

    def test_calculate_letter_size_at_default_dpi(self):
        """Letter size (8.5x11 inches) should calculate correctly."""
        # Letter is 612 x 792 points (8.5 x 11 inches at 72 DPI)
        width_px, height_px = _calculate_pixel_dimensions(612.0, 792.0, DEFAULT_RENDER_DPI)

        # At 150 DPI: 8.5 * 150 = 1275, 11 * 150 = 1650
        expected_width = int(612 * (DEFAULT_RENDER_DPI / PDF_POINTS_PER_INCH))
        expected_height = int(792 * (DEFAULT_RENDER_DPI / PDF_POINTS_PER_INCH))

        assert width_px == expected_width
        assert height_px == expected_height


class TestPageInfo:
    """Tests for PageInfo dataclass."""

    def test_to_dict_includes_all_fields(self):
        """to_dict should include all PageInfo fields."""
        page = PageInfo(
            page_number=1,
            width_points=612.0,
            height_points=792.0,
            width_px=1275,
            height_px=1650,
            rotation=0,
            dpi=150,
            rendered_path="/tmp/page.png",
        )

        result = page.to_dict()

        assert result["page_number"] == 1
        assert result["width_points"] == 612.0
        assert result["height_points"] == 792.0
        assert result["width_px"] == 1275
        assert result["height_px"] == 1650
        assert result["rotation"] == 0
        assert result["dpi"] == 150
        assert result["rendered_path"] == "/tmp/page.png"

    def test_width_inches_property(self):
        """width_inches should convert points to inches."""
        page = PageInfo(
            page_number=1,
            width_points=612.0,  # 8.5 inches
            height_points=792.0,
            width_px=1275,
            height_px=1650,
            rotation=0,
        )

        assert abs(page.width_inches - 8.5) < 0.01

    def test_height_inches_property(self):
        """height_inches should convert points to inches."""
        page = PageInfo(
            page_number=1,
            width_points=612.0,
            height_points=792.0,  # 11 inches
            width_px=1275,
            height_px=1650,
            rotation=0,
        )

        assert abs(page.height_inches - 11.0) < 0.01


class TestPlanDocument:
    """Tests for PlanDocument dataclass."""

    def test_to_dict_serialization(self):
        """to_dict should serialize all fields correctly."""
        page = PageInfo(
            page_number=1,
            width_points=612.0,
            height_points=792.0,
            width_px=1275,
            height_px=1650,
            rotation=0,
        )

        doc = PlanDocument(
            file_id="test-id-123",
            filename="test.pdf",
            file_path="/path/to/test.pdf",
            total_pages=1,
            pages=[page],
            metadata={"title": "Test Document"},
        )

        result = doc.to_dict()

        assert result["file_id"] == "test-id-123"
        assert result["filename"] == "test.pdf"
        assert result["total_pages"] == 1
        assert len(result["pages"]) == 1
        assert result["metadata"]["title"] == "Test Document"

    def test_get_page_by_number(self):
        """get_page should return correct page for valid number."""
        pages = [
            PageInfo(page_number=1, width_points=612, height_points=792,
                    width_px=1275, height_px=1650, rotation=0),
            PageInfo(page_number=2, width_points=612, height_points=792,
                    width_px=1275, height_px=1650, rotation=0),
        ]

        doc = PlanDocument(
            file_id="test",
            filename="test.pdf",
            file_path="/test.pdf",
            total_pages=2,
            pages=pages,
        )

        page1 = doc.get_page(1)
        page2 = doc.get_page(2)

        assert page1 is not None
        assert page1.page_number == 1
        assert page2 is not None
        assert page2.page_number == 2

    def test_get_page_invalid_number_returns_none(self):
        """get_page should return None for invalid page number."""
        doc = PlanDocument(
            file_id="test",
            filename="test.pdf",
            file_path="/test.pdf",
            total_pages=1,
            pages=[PageInfo(page_number=1, width_points=612, height_points=792,
                           width_px=1275, height_px=1650, rotation=0)],
        )

        assert doc.get_page(0) is None
        assert doc.get_page(2) is None
        assert doc.get_page(99) is None


class TestLoadPlanDocument:
    """Tests for loading PDF documents."""

    def test_load_nonexistent_file_raises(self):
        """Loading a nonexistent file should raise FileNotFoundError."""
        with pytest.raises(FileNotFoundError):
            load_plan_document("/nonexistent/path.pdf")

    def test_load_invalid_pdf_raises(self):
        """Loading an invalid PDF should raise ValueError."""
        # Create a temp file with invalid content
        with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as f:
            f.write(b"This is not a valid PDF")
            temp_path = f.name

        try:
            with pytest.raises(ValueError):
                load_plan_document(temp_path)
        finally:
            Path(temp_path).unlink()

    def test_load_sample_pdf_succeeds(self, sample_pdf_path):
        """Loading the sample PDF should succeed."""
        doc = load_plan_document(sample_pdf_path)

        assert doc is not None
        assert doc.total_pages >= 1
        assert len(doc.pages) == doc.total_pages
        assert doc.filename == sample_pdf_path.name

    def test_load_with_custom_file_id(self, sample_pdf_path):
        """Custom file_id should be used when provided."""
        custom_id = "my-custom-id-123"
        doc = load_plan_document(sample_pdf_path, file_id=custom_id)

        assert doc.file_id == custom_id

    def test_load_auto_generates_file_id(self, sample_pdf_path):
        """file_id should be auto-generated when not provided."""
        doc = load_plan_document(sample_pdf_path)

        assert doc.file_id is not None
        # Should be a valid UUID format
        assert len(doc.file_id) == 36

    def test_load_page_dimensions_reasonable(self, sample_pdf_path):
        """Page dimensions should be reasonable for blueprints."""
        doc = load_plan_document(sample_pdf_path)

        for page in doc.pages:
            # PDF should have positive dimensions
            assert page.width_points > 0
            assert page.height_points > 0
            assert page.width_px > 0
            assert page.height_px > 0

            # Should be larger than a postage stamp
            assert page.width_inches > 1
            assert page.height_inches > 1

    def test_load_extracts_metadata(self, sample_pdf_path):
        """Loading should extract PDF metadata."""
        doc = load_plan_document(sample_pdf_path)

        # Metadata dict should exist
        assert doc.metadata is not None
        assert isinstance(doc.metadata, dict)


class TestRenderPageToImage:
    """Tests for rendering PDF pages to images."""

    def test_render_nonexistent_file_raises(self):
        """Rendering from nonexistent file should raise FileNotFoundError."""
        with pytest.raises(FileNotFoundError):
            render_page_to_image("/nonexistent/path.pdf", 1)

    def test_render_invalid_page_raises(self, sample_pdf_path):
        """Rendering invalid page number should raise ValueError."""
        with pytest.raises(ValueError):
            render_page_to_image(sample_pdf_path, 0)

        with pytest.raises(ValueError):
            render_page_to_image(sample_pdf_path, 9999)

    def test_render_returns_pil_image(self, sample_pdf_path):
        """Rendering should return a PIL Image object."""
        img = render_page_to_image(sample_pdf_path, 1)

        assert isinstance(img, Image.Image)
        assert img.width > 0
        assert img.height > 0

    def test_render_respects_dpi(self, sample_pdf_path):
        """Rendering at different DPIs should produce different sizes."""
        img_low = render_page_to_image(sample_pdf_path, 1, dpi=72)
        img_high = render_page_to_image(sample_pdf_path, 1, dpi=150)

        # Higher DPI should produce larger image
        assert img_high.width > img_low.width
        assert img_high.height > img_low.height


class TestRenderPageToFile:
    """Tests for rendering PDF pages to files."""

    def test_render_creates_file(self, sample_pdf_path):
        """Rendering should create an image file."""
        with tempfile.TemporaryDirectory() as tmpdir:
            output_path = Path(tmpdir) / "test_output.png"
            result_path = render_page_to_file(sample_pdf_path, 1, output_path)

            assert Path(result_path).exists()
            assert Path(result_path).suffix == ".png"

    def test_render_auto_generates_path(self, sample_pdf_path):
        """Rendering without output_path should auto-generate one."""
        result_path = render_page_to_file(sample_pdf_path, 1)

        try:
            assert Path(result_path).exists()
        finally:
            Path(result_path).unlink(missing_ok=True)


class TestExtractPageText:
    """Tests for text extraction from PDF pages."""

    def test_extract_nonexistent_file_raises(self):
        """Extracting from nonexistent file should raise FileNotFoundError."""
        with pytest.raises(FileNotFoundError):
            extract_page_text("/nonexistent/path.pdf", 1)

    def test_extract_invalid_page_raises(self, sample_pdf_path):
        """Extracting from invalid page should raise ValueError."""
        with pytest.raises(ValueError):
            extract_page_text(sample_pdf_path, 0)

    def test_extract_returns_string(self, sample_pdf_path):
        """Extraction should return a string."""
        text = extract_page_text(sample_pdf_path, 1)

        assert isinstance(text, str)


class TestExtractAllText:
    """Tests for extracting text from all pages."""

    def test_extract_all_returns_dict(self, sample_pdf_path):
        """Should return dict mapping page numbers to text."""
        result = extract_all_text(sample_pdf_path)

        assert isinstance(result, dict)
        assert len(result) >= 1

        # Keys should be page numbers (1-indexed)
        for page_num in result.keys():
            assert page_num >= 1


class TestExtractMetadata:
    """Tests for metadata extraction."""

    def test_extract_metadata_returns_dict(self, sample_pdf_path):
        """Should return a dictionary with standard metadata fields."""
        metadata = extract_metadata(sample_pdf_path)

        assert isinstance(metadata, dict)
        assert "page_count" in metadata
        assert "page_sizes" in metadata
        assert metadata["page_count"] >= 1

    def test_extract_metadata_page_sizes_list(self, sample_pdf_path):
        """page_sizes should be a list of (width, height) tuples."""
        metadata = extract_metadata(sample_pdf_path)

        assert isinstance(metadata["page_sizes"], list)
        assert len(metadata["page_sizes"]) == metadata["page_count"]

        for size in metadata["page_sizes"]:
            assert len(size) == 2
            assert size[0] > 0  # width
            assert size[1] > 0  # height

"""
PDF utility functions for SnapGrid.

Provides helpers for loading and inspecting PDF files.
"""

import os
from pathlib import Path
from typing import Optional

import pdfplumber


def validate_pdf_path(path: str | Path) -> Path:
    """
    Validate that a PDF file exists and is readable.

    Args:
        path: Path to the PDF file

    Returns:
        Validated Path object

    Raises:
        FileNotFoundError: If file doesn't exist
        ValueError: If file is not a PDF
    """
    path = Path(path)

    if not path.exists():
        raise FileNotFoundError(f"PDF file not found: {path}")

    if not path.suffix.lower() == ".pdf":
        raise ValueError(f"File is not a PDF: {path}")

    return path


def get_pdf_page_count(path: str | Path) -> int:
    """
    Get the number of pages in a PDF.

    Args:
        path: Path to the PDF file

    Returns:
        Number of pages
    """
    path = validate_pdf_path(path)

    with pdfplumber.open(path) as pdf:
        return len(pdf.pages)


def get_pdf_metadata(path: str | Path) -> dict:
    """
    Extract basic metadata from a PDF file.

    Args:
        path: Path to the PDF file

    Returns:
        Dictionary with PDF metadata
    """
    path = validate_pdf_path(path)

    with pdfplumber.open(path) as pdf:
        return {
            "filename": path.name,
            "path": str(path),
            "page_count": len(pdf.pages),
            "metadata": pdf.metadata or {},
        }

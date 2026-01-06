#!/usr/bin/env python3
"""
PDF to Training Images Converter for Roboflow

Converts PDF floor plans to PNG images suitable for Roboflow training.
Roboflow does NOT support PDF uploads - images must be PNG/JPG.

Usage:
    python pdf_to_training_images.py <input_folder> <output_folder> [--dpi 150]

Example:
    python pdf_to_training_images.py /path/to/pdfs /path/to/training_images --dpi 200
"""

import argparse
import sys
from pathlib import Path

try:
    import fitz  # PyMuPDF
except ImportError:
    print("ERROR: PyMuPDF not installed. Run: pip install PyMuPDF")
    sys.exit(1)


def convert_pdf_to_images(
    pdf_path: Path,
    output_folder: Path,
    dpi: int = 150,
    format: str = "png"
) -> list[Path]:
    """
    Convert all pages of a PDF to images.

    Args:
        pdf_path: Path to PDF file
        output_folder: Folder to save images
        dpi: Resolution (150-200 recommended for training)
        format: Output format (png or jpg)

    Returns:
        List of created image paths
    """
    output_folder.mkdir(parents=True, exist_ok=True)
    created_files = []

    doc = fitz.open(pdf_path)
    pdf_name = pdf_path.stem

    # Calculate zoom factor for desired DPI (PDF default is 72 DPI)
    zoom = dpi / 72
    mat = fitz.Matrix(zoom, zoom)

    for page_num in range(len(doc)):
        page = doc[page_num]
        pix = page.get_pixmap(matrix=mat)

        # Create output filename
        if len(doc) == 1:
            output_name = f"{pdf_name}.{format}"
        else:
            output_name = f"{pdf_name}_page{page_num + 1:02d}.{format}"

        output_path = output_folder / output_name

        # Save image
        if format.lower() == "jpg":
            pix.save(output_path, "jpeg")
        else:
            pix.save(output_path, "png")

        created_files.append(output_path)
        print(f"  Created: {output_path.name} ({pix.width}x{pix.height})")

    doc.close()
    return created_files


def process_folder(
    input_folder: Path,
    output_folder: Path,
    dpi: int = 150,
    format: str = "png"
) -> dict:
    """
    Process all PDFs in a folder.

    Returns:
        Summary of processed files
    """
    pdf_files = list(input_folder.glob("*.pdf")) + list(input_folder.glob("*.PDF"))

    if not pdf_files:
        print(f"No PDF files found in {input_folder}")
        return {"total_pdfs": 0, "total_images": 0}

    print(f"\nFound {len(pdf_files)} PDF files")
    print(f"Output folder: {output_folder}")
    print(f"DPI: {dpi}")
    print(f"Format: {format.upper()}")
    print("-" * 50)

    total_images = 0

    for pdf_path in sorted(pdf_files):
        print(f"\nProcessing: {pdf_path.name}")
        images = convert_pdf_to_images(pdf_path, output_folder, dpi, format)
        total_images += len(images)

    print("\n" + "=" * 50)
    print(f"DONE: {len(pdf_files)} PDFs → {total_images} images")
    print(f"Images saved to: {output_folder}")
    print("=" * 50)

    return {
        "total_pdfs": len(pdf_files),
        "total_images": total_images,
        "output_folder": str(output_folder)
    }


def main():
    parser = argparse.ArgumentParser(
        description="Convert PDF floor plans to images for Roboflow training"
    )
    parser.add_argument(
        "input_folder",
        type=Path,
        help="Folder containing PDF files"
    )
    parser.add_argument(
        "output_folder",
        type=Path,
        help="Folder to save converted images"
    )
    parser.add_argument(
        "--dpi",
        type=int,
        default=150,
        help="Image resolution (default: 150, recommended: 150-200)"
    )
    parser.add_argument(
        "--format",
        choices=["png", "jpg"],
        default="png",
        help="Output format (default: png)"
    )

    args = parser.parse_args()

    if not args.input_folder.exists():
        print(f"ERROR: Input folder not found: {args.input_folder}")
        sys.exit(1)

    process_folder(
        args.input_folder,
        args.output_folder,
        args.dpi,
        args.format
    )


if __name__ == "__main__":
    main()

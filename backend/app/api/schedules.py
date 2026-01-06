"""
Schedule extraction API routes.

Provides endpoints for extracting structured data from construction schedule PDFs.
"""

import shutil
import tempfile
from pathlib import Path
from typing import Optional
from uuid import uuid4

from fastapi import APIRouter, File, HTTPException, Query, UploadFile
from pydantic import BaseModel

from ..core.config import get_sample_pdf_path, get_settings, settings
from ..services.persistence import store_file_and_extraction
from ..services.schedule_extraction import (
    ExtractionResult,
    extract_schedules_from_pdf,
    get_door_summary,
)

router = APIRouter(prefix="/schedules", tags=["schedules"])


class PersistenceInfo(BaseModel):
    """Persistence layer result info."""

    supabase_enabled: bool
    success: bool = False
    file_id: Optional[str] = None
    extraction_id: Optional[str] = None
    storage_path: Optional[str] = None
    error: Optional[str] = None


class ExtractionResponse(BaseModel):
    """Response model for schedule extraction."""

    extraction_id: str
    source_file: str
    extracted_at: str
    tables: list[dict]
    total_rows: int
    status: str
    errors: list[str]
    summary: Optional[dict] = None
    persistence: Optional[PersistenceInfo] = None


class HealthResponse(BaseModel):
    """Health check response."""

    status: str
    service: str
    sample_pdf_available: bool


@router.get("/health", response_model=HealthResponse)
async def health_check():
    """
    Check if the schedule extraction service is healthy.

    Returns availability of sample PDF for testing.
    """
    sample_path = get_sample_pdf_path()
    return HealthResponse(
        status="ok",
        service="schedule-extraction",
        sample_pdf_available=sample_path.exists(),
    )


@router.post("/extract", response_model=ExtractionResponse)
async def extract_schedule(
    file: Optional[UploadFile] = File(None),
    use_sample: bool = Query(
        False,
        description="Use the built-in sample door schedule PDF (Tuerenliste_Bauteil_B_OG1.pdf)",
    ),
    include_summary: bool = Query(
        True,
        description="Include a summary of extracted data (counts by type, dimensions, etc.)",
    ),
    project_id: Optional[str] = Query(
        None,
        description="Optional project ID to associate the file with (for Supabase storage)",
    ),
):
    """
    Extract schedule data from a PDF file.

    You can either:
    - Upload a PDF file directly
    - Set `use_sample=true` to use the built-in sample door schedule

    Returns structured JSON with:
    - All extracted tables with row data
    - Auditability metadata (page numbers, confidence scores)
    - Optional summary statistics
    - Persistence info (if Supabase is configured)

    Example:
        ```bash
        # Using sample PDF
        curl -X POST "http://localhost:8000/api/v1/schedules/extract?use_sample=true"

        # Uploading a PDF
        curl -X POST "http://localhost:8000/api/v1/schedules/extract" \\
             -F "file=@my_schedule.pdf"

        # With project association (requires Supabase)
        curl -X POST "http://localhost:8000/api/v1/schedules/extract?project_id=uuid" \\
             -F "file=@my_schedule.pdf"
        ```
    """
    # Variables for persistence
    file_bytes: Optional[bytes] = None
    original_filename: str = ""

    # Determine which PDF to process
    if use_sample:
        pdf_path = get_sample_pdf_path()
        if not pdf_path.exists():
            raise HTTPException(
                status_code=404,
                detail=f"Sample PDF not found at {pdf_path}. Please ensure the file exists.",
            )
        original_filename = pdf_path.name
        # Read file bytes for persistence
        file_bytes = pdf_path.read_bytes()
    elif file:
        # Save uploaded file to temp location
        if not file.filename.lower().endswith(".pdf"):
            raise HTTPException(
                status_code=400,
                detail="Uploaded file must be a PDF",
            )

        original_filename = file.filename

        # Read file bytes for persistence
        file_bytes = await file.read()
        await file.seek(0)  # Reset for potential re-read

        # Create temp file
        temp_dir = Path(tempfile.mkdtemp())
        temp_path = temp_dir / f"{uuid4()}.pdf"

        try:
            with open(temp_path, "wb") as buffer:
                buffer.write(file_bytes)
            pdf_path = temp_path
        except Exception as e:
            raise HTTPException(
                status_code=500,
                detail=f"Failed to save uploaded file: {str(e)}",
            )
    else:
        raise HTTPException(
            status_code=400,
            detail="Either upload a PDF file or set use_sample=true",
        )

    # Perform extraction
    try:
        result = extract_schedules_from_pdf(pdf_path)
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Extraction failed: {str(e)}",
        )
    finally:
        # Clean up temp file if used
        if file and "temp_path" in locals():
            try:
                temp_path.unlink()
                temp_dir.rmdir()
            except:
                pass

    # Build response
    response_data = result.to_dict()

    if include_summary:
        response_data["summary"] = get_door_summary(result)

    # Persist to Supabase if configured
    persistence_result = store_file_and_extraction(
        file_bytes=file_bytes,
        original_filename=original_filename,
        extraction_result=result,
        extraction_type="schedule",
        project_id=project_id,
        settings=get_settings(),
    )

    response_data["persistence"] = persistence_result.to_dict()

    return ExtractionResponse(**response_data)


@router.get("/sample-info")
async def get_sample_info():
    """
    Get information about the sample PDF file.

    Useful for understanding what test data is available.
    """
    sample_path = get_sample_pdf_path()

    if not sample_path.exists():
        raise HTTPException(
            status_code=404,
            detail="Sample PDF not found",
        )

    return {
        "filename": sample_path.name,
        "path": str(sample_path),
        "exists": True,
        "size_bytes": sample_path.stat().st_size,
        "description": "Door schedule (Türenliste) for Building Part B, 1st Floor (OG1)",
        "expected_content": {
            "type": "door_schedule",
            "language": "German",
            "expected_columns": [
                "Pos.",
                "Türnummer",
                "Raum",
                "Typ",
                "BS",
                "B[m]",
                "H[m]",
                "Bemerkung",
            ],
        },
    }

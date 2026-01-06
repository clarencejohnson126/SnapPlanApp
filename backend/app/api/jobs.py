"""
Job Processing API for SnapGrid MVP.

Called by Supabase Edge Functions to process extraction jobs.
Implements zero-hallucination principle: all values must trace to source PDF.
"""

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, Field
from typing import Optional, List, Dict, Any
import tempfile
import shutil
import time
import logging
import re
import os

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/jobs", tags=["jobs"])


# =============================================================================
# Request/Response Models
# =============================================================================

class ProcessJobRequest(BaseModel):
    """Request to process an extraction job."""
    job_id: str = Field(..., description="UUID of the job to process")
    file_url: str = Field(..., description="Signed URL to download PDF from Supabase Storage")
    job_type: str = Field(default="area_text", description="Type of extraction: area_text, doors_text, etc.")
    config: Dict[str, Any] = Field(default_factory=dict, description="Processing configuration")


class RoomResult(BaseModel):
    """Individual room extraction result with full audit trail."""
    room_id: str = Field(..., description="Unique identifier for the room")
    room_name: Optional[str] = Field(None, description="Human-readable room name")
    room_type: Optional[str] = Field(None, description="Classified room type")

    # Measurements
    area_m2: float = Field(..., description="Area in square meters")
    perimeter_m: Optional[float] = Field(None, description="Perimeter in meters")
    ceiling_height_m: Optional[float] = Field(None, description="Ceiling height in meters")

    # Factor application
    area_factor: float = Field(default=1.0, description="Factor applied (0.5 for balcony)")
    effective_area_m2: float = Field(..., description="area_m2 * area_factor")

    # Audit trail (zero-hallucination principle)
    source_text: Optional[str] = Field(None, description="Raw text from PDF")
    source_page: int = Field(..., description="Page number (1-indexed)")
    source_bbox: Optional[Dict[str, float]] = Field(None, description="Bounding box {x, y, width, height}")
    confidence: float = Field(default=0.95, description="Extraction confidence")
    extraction_method: str = Field(default="text_extraction", description="Method used")


class JobResult(BaseModel):
    """Complete job processing result."""
    job_id: str
    status: str

    # Room results
    rooms: List[RoomResult]

    # Aggregates
    total_rooms: int
    total_area_m2: float
    total_effective_area_m2: float
    total_perimeter_m: float
    area_by_type: Dict[str, float]

    # Metadata
    processing_time_ms: int
    warnings: List[str] = Field(default_factory=list)


# =============================================================================
# Room Type Classification
# =============================================================================

# Rooms that get reduced factor (0.5 by default)
REDUCED_FACTOR_ROOM_TYPES = {"Balcony", "Terrace", "Loggia"}

def classify_room_type(room_name: Optional[str]) -> Optional[str]:
    """
    Classify room by name into standard types.

    German construction terms:
    - Balkon → Balcony (factor 0.5)
    - Terrasse → Terrace (factor 0.5)
    - Loggia → Loggia (factor 0.5)
    - TRH/Treppenhaus → Stairwell
    - WC/Toilette → WC
    - Flur/Gang → Corridor
    - Nutzungseinheit → Unit
    - etc.
    """
    if not room_name:
        return None

    name_lower = room_name.lower()

    # Factor 0.5 room types
    if 'balkon' in name_lower:
        return 'Balcony'
    elif 'terrasse' in name_lower:
        return 'Terrace'
    elif 'loggia' in name_lower:
        return 'Loggia'

    # Standard room types
    elif 'trh' in name_lower or 'treppenhaus' in name_lower:
        return 'Stairwell'
    elif 'wc' in name_lower or 'toilette' in name_lower:
        return 'WC'
    elif 'flur' in name_lower or 'gang' in name_lower or 'diele' in name_lower:
        return 'Corridor'
    elif 'nutzungseinheit' in name_lower or 'ne' == name_lower.strip():
        return 'Unit'
    elif 'büro' in name_lower or 'office' in name_lower:
        return 'Office'
    elif 'lager' in name_lower or 'abstellraum' in name_lower:
        return 'Storage'
    elif 'technik' in name_lower or 'haustechnik' in name_lower:
        return 'Technical'
    elif 'küche' in name_lower or 'kueche' in name_lower:
        return 'Kitchen'
    elif 'bad' in name_lower or 'dusche' in name_lower:
        return 'Bathroom'
    elif 'schlafzimmer' in name_lower or 'schlaf' in name_lower:
        return 'Bedroom'
    elif 'wohnzimmer' in name_lower or 'wohn' in name_lower:
        return 'Living Room'
    elif 'keller' in name_lower:
        return 'Basement'
    elif 'garage' in name_lower or 'stellplatz' in name_lower:
        return 'Garage'

    # Return original if no match
    return room_name


def parse_german_decimal(value: str) -> Optional[float]:
    """
    Parse German-format decimal (comma as separator).

    Examples:
        "12,34" → 12.34
        "1.234,56" → 1234.56 (thousand separator + decimal)
        "42.18" → 42.18 (already dot format)
    """
    if not value or not isinstance(value, str):
        return None

    clean = value.strip()

    # Check for German format with thousand separator (1.234,56)
    if '.' in clean and ',' in clean:
        # Assume dot is thousand separator, comma is decimal
        clean = clean.replace('.', '').replace(',', '.')
    elif ',' in clean:
        # Simple German decimal: 12,34 → 12.34
        clean = clean.replace(',', '.')

    try:
        return float(clean)
    except ValueError:
        return None


# =============================================================================
# Enhanced Text Extraction
# =============================================================================

def extract_nrf_with_context(page_text: str, page_number: int) -> List[Dict[str, Any]]:
    """
    Extract NRF (Netto-Raumfläche) values with context for audit trail.

    Patterns handled:
    - "NRF = 12,34 m²"
    - "NRF: 12.34m²"
    - "NRF  42,18 m2"
    - Multi-line: "NRF:" then "12,34 m²" on next line

    Also extracts:
    - U (Umfang/Perimeter): "U = 12,50 m"
    - LH (Lichte Höhe/Ceiling Height): "LH = 2,60 m"
    - Room labels near NRF values
    """
    results = []

    # Split into lines for context
    lines = page_text.split('\n')

    # Patterns
    nrf_pattern = r'NRF\s*[=:]\s*([\d,\.]+)\s*m[²2]?'
    nrf_value_only = r'^([\d,\.]+)\s*m[²2]?$'
    u_pattern = r'U\s*[=:]\s*([\d,\.]+)\s*m(?![²2])'
    lh_pattern = r'LH\s*[=:]\s*([\d,\.]+)\s*m(?![²2])'
    room_label_pattern = r'([A-Z]\.[\d\.]+(?:-\d+)?)\s*(?:TRH|Nutzungseinheit|Balkon|WC|Flur|[\w\s]+)?'

    i = 0
    room_counter = 0

    while i < len(lines):
        line = lines[i].strip()

        # Try to match NRF on same line
        nrf_match = re.search(nrf_pattern, line, re.IGNORECASE)

        if nrf_match:
            area_str = nrf_match.group(1)
            area = parse_german_decimal(area_str)

            if area is not None and 0 < area < 10000:  # Sanity check
                room_counter += 1

                # Look for room label in same line or nearby
                room_label = None
                room_name = None

                # Check same line for label
                label_match = re.search(room_label_pattern, line)
                if label_match:
                    room_label = label_match.group(1)
                    # Extract room name if present
                    remaining = line[label_match.end():].strip()
                    if remaining and not remaining.startswith('NRF'):
                        room_name = remaining.split('NRF')[0].strip()

                # Check previous line for label
                if not room_label and i > 0:
                    prev_line = lines[i-1].strip()
                    label_match = re.search(room_label_pattern, prev_line)
                    if label_match:
                        room_label = label_match.group(1)
                        room_name = prev_line.replace(room_label, '').strip()

                # Look for U (perimeter) and LH (height) nearby
                perimeter = None
                height = None

                # Search in surrounding lines (current, next, prev)
                search_text = ' '.join(lines[max(0, i-1):min(len(lines), i+3)])

                u_match = re.search(u_pattern, search_text, re.IGNORECASE)
                if u_match:
                    perimeter = parse_german_decimal(u_match.group(1))

                lh_match = re.search(lh_pattern, search_text, re.IGNORECASE)
                if lh_match:
                    height = parse_german_decimal(lh_match.group(1))

                results.append({
                    'room_id': room_label or f"room_{room_counter}",
                    'room_name': room_name or f"Room {room_counter}",
                    'area_m2': area,
                    'perimeter_m': perimeter,
                    'ceiling_height_m': height,
                    'source_text': line,
                    'source_page': page_number,
                    'confidence': 0.95,
                })

        # Handle split NRF (NRF: on one line, value on next)
        elif 'NRF' in line.upper() and re.search(r'NRF\s*[=:]?\s*$', line, re.IGNORECASE):
            # Check next line for value
            if i + 1 < len(lines):
                next_line = lines[i + 1].strip()
                val_match = re.match(nrf_value_only, next_line)
                if val_match:
                    area_str = val_match.group(1)
                    area = parse_german_decimal(area_str)

                    if area is not None and 0 < area < 10000:
                        room_counter += 1

                        results.append({
                            'room_id': f"room_{room_counter}",
                            'room_name': f"Room {room_counter}",
                            'area_m2': area,
                            'perimeter_m': None,
                            'ceiling_height_m': None,
                            'source_text': f"{line} {next_line}",
                            'source_page': page_number,
                            'confidence': 0.90,  # Slightly lower for split values
                        })
                        i += 1  # Skip next line

        i += 1

    return results


def extract_areas_from_pdf(file_path: str, page_number: int = 1) -> Dict[str, Any]:
    """
    Extract room areas from PDF text using NRF (Netto-Raumfläche) values.

    This is the PRIMARY method for German CAD PDFs with text annotations.
    Implements zero-hallucination principle: only extracts values actually present in PDF.
    """
    try:
        import fitz  # PyMuPDF
    except ImportError:
        return {
            'success': False,
            'error': 'PyMuPDF not installed',
            'rooms': [],
            'warnings': ['PyMuPDF (fitz) is required for PDF text extraction']
        }

    rooms = []
    warnings = []

    try:
        doc = fitz.open(file_path)

        if page_number > len(doc):
            return {
                'success': False,
                'error': f'Page {page_number} does not exist (document has {len(doc)} pages)',
                'rooms': [],
                'warnings': []
            }

        page = doc[page_number - 1]
        text = page.get_text()
        doc.close()

        # Extract NRF values with context
        extracted = extract_nrf_with_context(text, page_number)

        if extracted:
            for item in extracted:
                rooms.append(item)

            logger.info(f"Extracted {len(rooms)} rooms from page {page_number}")
        else:
            warnings.append(f"No NRF values found on page {page_number}")

        return {
            'success': True,
            'rooms': rooms,
            'warnings': warnings
        }

    except Exception as e:
        logger.error(f"PDF extraction failed: {e}")
        return {
            'success': False,
            'error': str(e),
            'rooms': [],
            'warnings': [f"Extraction error: {str(e)}"]
        }


# =============================================================================
# API Endpoints
# =============================================================================

@router.post("/process", response_model=JobResult)
async def process_job(request: ProcessJobRequest):
    """
    Process an extraction job.

    This endpoint:
    1. Downloads the PDF from the signed URL
    2. Runs text extraction (NRF values)
    3. Applies balcony factor if configured
    4. Returns structured results with audit trail

    Called by Supabase Edge Function after job creation.
    """
    start_time = time.time()
    warnings: List[str] = []

    # Create temp directory for PDF
    temp_dir = tempfile.mkdtemp()
    temp_path = os.path.join(temp_dir, "input.pdf")

    try:
        # Download PDF from signed URL
        import httpx

        async with httpx.AsyncClient(timeout=60.0) as client:
            response = await client.get(request.file_url)
            response.raise_for_status()

            with open(temp_path, 'wb') as f:
                f.write(response.content)

        logger.info(f"Downloaded PDF to {temp_path} ({os.path.getsize(temp_path)} bytes)")

        # Get config
        page_number = request.config.get("page_number", 1)
        balcony_factor = request.config.get("balcony_factor", 0.5)

        # Extract based on job type
        if request.job_type == "area_text":
            extraction_result = extract_areas_from_pdf(temp_path, page_number)
        else:
            raise HTTPException(
                status_code=400,
                detail=f"Unsupported job type: {request.job_type}. MVP only supports 'area_text'."
            )

        if not extraction_result['success']:
            raise HTTPException(
                status_code=500,
                detail=extraction_result.get('error', 'Extraction failed')
            )

        warnings.extend(extraction_result.get('warnings', []))

        # Build room results with classification and factors
        rooms: List[RoomResult] = []
        total_area = 0.0
        total_effective = 0.0
        total_perimeter = 0.0
        area_by_type: Dict[str, float] = {}

        for room_data in extraction_result['rooms']:
            # Classify room type
            room_type = classify_room_type(room_data.get('room_name'))

            # Determine factor based on room type
            factor = balcony_factor if room_type in REDUCED_FACTOR_ROOM_TYPES else 1.0

            area = room_data['area_m2']
            effective = area * factor
            perimeter = room_data.get('perimeter_m') or 0.0

            room_result = RoomResult(
                room_id=room_data['room_id'],
                room_name=room_data.get('room_name'),
                room_type=room_type,
                area_m2=area,
                perimeter_m=room_data.get('perimeter_m'),
                ceiling_height_m=room_data.get('ceiling_height_m'),
                area_factor=factor,
                effective_area_m2=effective,
                source_text=room_data.get('source_text'),
                source_page=room_data['source_page'],
                source_bbox=room_data.get('source_bbox'),
                confidence=room_data.get('confidence', 0.95),
                extraction_method="text_extraction",
            )
            rooms.append(room_result)

            # Aggregate
            total_area += area
            total_effective += effective
            total_perimeter += perimeter

            # Group by type
            if room_type:
                area_by_type[room_type] = area_by_type.get(room_type, 0) + effective

        processing_time = int((time.time() - start_time) * 1000)

        return JobResult(
            job_id=request.job_id,
            status="completed",
            rooms=rooms,
            total_rooms=len(rooms),
            total_area_m2=round(total_area, 2),
            total_effective_area_m2=round(total_effective, 2),
            total_perimeter_m=round(total_perimeter, 2),
            area_by_type={k: round(v, 2) for k, v in area_by_type.items()},
            processing_time_ms=processing_time,
            warnings=warnings,
        )

    except httpx.HTTPError as e:
        logger.error(f"Failed to download PDF: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to download PDF: {str(e)}")

    except Exception as e:
        logger.error(f"Job processing failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))

    finally:
        # Cleanup temp files
        shutil.rmtree(temp_dir, ignore_errors=True)


@router.get("/health")
async def health_check():
    """Health check endpoint for Edge Function verification."""
    return {"status": "healthy", "service": "jobs"}

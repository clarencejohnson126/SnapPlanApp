"""
Persistence layer for SnapGrid.

Handles storage of uploaded files and extraction results to Supabase.
All operations are conditional - if Supabase is not configured, they safely no-op.
"""

import logging
from dataclasses import dataclass
from datetime import datetime
from typing import Optional, List
from uuid import uuid4

from ..core.config import Settings, get_settings
from .schedule_extraction import ExtractionResult, get_door_summary
from .scale_calibration import ScaleContext
from .measurement_engine import Sector, MeasurementResult
from .supabase_client import get_supabase_client

logger = logging.getLogger(__name__)


@dataclass
class PersistenceResult:
    """Result of a persistence operation."""

    supabase_enabled: bool
    success: bool = False
    file_id: Optional[str] = None
    extraction_id: Optional[str] = None
    storage_path: Optional[str] = None
    error: Optional[str] = None

    def to_dict(self) -> dict:
        """Convert to dictionary for API response."""
        result = {
            "supabase_enabled": self.supabase_enabled,
        }
        if self.supabase_enabled:
            result.update({
                "success": self.success,
                "file_id": self.file_id,
                "extraction_id": self.extraction_id,
                "storage_path": self.storage_path,
            })
            if self.error:
                result["error"] = self.error
        return result


def store_file_and_extraction(
    *,
    file_bytes: bytes,
    original_filename: str,
    extraction_result: ExtractionResult,
    extraction_type: str = "schedule",
    project_id: Optional[str] = None,
    settings: Optional[Settings] = None,
) -> PersistenceResult:
    """
    Store uploaded file and extraction results to Supabase.

    If Supabase is not configured, returns a result with supabase_enabled=False.

    This function:
    1. Uploads the PDF to Supabase Storage
    2. Creates a row in the 'files' table
    3. Creates a row in the 'extractions' table with raw JSON + summary

    Args:
        file_bytes: Raw bytes of the uploaded PDF file
        original_filename: Original name of the uploaded file
        extraction_result: The extraction result to store
        extraction_type: Type of extraction (default: "schedule")
        project_id: Optional project ID to associate with the file
        settings: Optional Settings instance

    Returns:
        PersistenceResult with IDs and status
    """
    if settings is None:
        settings = get_settings()

    # Check if Supabase is enabled
    if not settings.supabase_enabled:
        logger.debug("Supabase not enabled, skipping persistence")
        return PersistenceResult(supabase_enabled=False)

    # Get Supabase client
    client = get_supabase_client(settings)
    if client is None:
        return PersistenceResult(
            supabase_enabled=True,
            success=False,
            error="Failed to initialize Supabase client"
        )

    # Generate IDs
    file_id = str(uuid4())
    extraction_id = str(uuid4())

    # Build storage path
    if project_id:
        storage_path = f"{project_id}/{file_id}/{original_filename}"
    else:
        storage_path = f"unassigned/{file_id}/{original_filename}"

    try:
        # 1. Upload file to Supabase Storage
        logger.info(f"Uploading file to storage: {storage_path}")
        storage_result = client.storage.from_(settings.supabase_bucket_name).upload(
            path=storage_path,
            file=file_bytes,
            file_options={"content-type": "application/pdf"}
        )

        # Check for upload errors
        if hasattr(storage_result, 'error') and storage_result.error:
            raise Exception(f"Storage upload failed: {storage_result.error}")

        # 2. Create file record
        logger.info(f"Creating file record: {file_id}")
        file_data = {
            "id": file_id,
            "project_id": project_id,
            "original_filename": original_filename,
            "storage_path": storage_path,
            "file_type": extraction_type,
            "file_size_bytes": len(file_bytes),
            "mime_type": "application/pdf",
        }

        file_insert = client.table("files").insert(file_data).execute()

        if hasattr(file_insert, 'error') and file_insert.error:
            raise Exception(f"File insert failed: {file_insert.error}")

        # 3. Create extraction record
        logger.info(f"Creating extraction record: {extraction_id}")

        # Prepare JSON data
        raw_result_json = extraction_result.to_dict()
        summary_json = get_door_summary(extraction_result)

        extraction_data = {
            "id": extraction_id,
            "file_id": file_id,
            "extraction_type": extraction_type,
            "status": "completed" if extraction_result.status == "ok" else "failed",
            "raw_result_json": raw_result_json,
            "summary_json": summary_json,
            "row_count": extraction_result.total_rows,
            "table_count": len(extraction_result.tables),
        }

        extraction_insert = client.table("extractions").insert(extraction_data).execute()

        if hasattr(extraction_insert, 'error') and extraction_insert.error:
            raise Exception(f"Extraction insert failed: {extraction_insert.error}")

        logger.info(f"Successfully stored file {file_id} and extraction {extraction_id}")

        return PersistenceResult(
            supabase_enabled=True,
            success=True,
            file_id=file_id,
            extraction_id=extraction_id,
            storage_path=storage_path,
        )

    except Exception as e:
        logger.error(f"Persistence failed: {e}")
        return PersistenceResult(
            supabase_enabled=True,
            success=False,
            error=str(e)
        )


def get_extraction_by_id(
    extraction_id: str,
    settings: Optional[Settings] = None,
) -> Optional[dict]:
    """
    Retrieve an extraction result by ID.

    Args:
        extraction_id: The extraction UUID
        settings: Optional Settings instance

    Returns:
        Extraction data dictionary or None if not found
    """
    if settings is None:
        settings = get_settings()

    if not settings.supabase_enabled:
        return None

    client = get_supabase_client(settings)
    if client is None:
        return None

    try:
        result = client.table("extractions").select("*").eq("id", extraction_id).execute()
        if result.data and len(result.data) > 0:
            return result.data[0]
        return None
    except Exception as e:
        logger.error(f"Failed to retrieve extraction {extraction_id}: {e}")
        return None


def list_extractions(
    limit: int = 10,
    offset: int = 0,
    settings: Optional[Settings] = None,
) -> list[dict]:
    """
    List recent extractions.

    Args:
        limit: Maximum number of results
        offset: Number of results to skip
        settings: Optional Settings instance

    Returns:
        List of extraction records
    """
    if settings is None:
        settings = get_settings()

    if not settings.supabase_enabled:
        return []

    client = get_supabase_client(settings)
    if client is None:
        return []

    try:
        result = (
            client.table("extractions")
            .select("id, file_id, extraction_type, status, row_count, table_count, created_at")
            .order("created_at", desc=True)
            .range(offset, offset + limit - 1)
            .execute()
        )
        return result.data or []
    except Exception as e:
        logger.error(f"Failed to list extractions: {e}")
        return []


# ============================================
# SCALE CONTEXT PERSISTENCE
# ============================================


@dataclass
class ScaleContextResult:
    """Result of a scale context persistence operation."""

    supabase_enabled: bool
    success: bool = False
    scale_context_id: Optional[str] = None
    error: Optional[str] = None

    def to_dict(self) -> dict:
        """Convert to dictionary for API response."""
        result = {
            "supabase_enabled": self.supabase_enabled,
        }
        if self.supabase_enabled:
            result.update({
                "success": self.success,
                "scale_context_id": self.scale_context_id,
            })
            if self.error:
                result["error"] = self.error
        return result


def store_scale_context(
    *,
    file_id: str,
    scale_context: ScaleContext,
    settings: Optional[Settings] = None,
) -> ScaleContextResult:
    """
    Store a scale context to Supabase.

    If this scale context is set as active, deactivates any other active
    scale contexts for the same file.

    Args:
        file_id: The file UUID this scale context belongs to
        scale_context: The ScaleContext to store
        settings: Optional Settings instance

    Returns:
        ScaleContextResult with ID and status
    """
    if settings is None:
        settings = get_settings()

    if not settings.supabase_enabled:
        logger.debug("Supabase not enabled, skipping scale context persistence")
        return ScaleContextResult(supabase_enabled=False)

    client = get_supabase_client(settings)
    if client is None:
        return ScaleContextResult(
            supabase_enabled=True,
            success=False,
            error="Failed to initialize Supabase client"
        )

    # Generate ID if not present
    scale_context_id = scale_context.id or str(uuid4())

    try:
        # If this scale context is active, deactivate others first
        if scale_context.is_active:
            logger.debug(f"Deactivating other scale contexts for file {file_id}")
            client.table("scale_contexts").update(
                {"is_active": False}
            ).eq("file_id", file_id).eq("is_active", True).execute()

        # Prepare scale context data
        scale_data = {
            "id": scale_context_id,
            "file_id": file_id,
            "scale_string": scale_context.scale_string,
            "pixels_per_meter": scale_context.pixels_per_meter,
            "detection_method": scale_context.detection_method,
            "confidence": scale_context.confidence,
            "source_page": scale_context.source_page,
            "source_bbox": scale_context.source_bbox,
            "user_reference_px": scale_context.user_reference_px,
            "user_reference_m": scale_context.user_reference_m,
            "is_active": scale_context.is_active,
        }

        logger.info(f"Storing scale context: {scale_context_id}")
        insert_result = client.table("scale_contexts").insert(scale_data).execute()

        if hasattr(insert_result, 'error') and insert_result.error:
            raise Exception(f"Scale context insert failed: {insert_result.error}")

        logger.info(f"Successfully stored scale context {scale_context_id}")

        return ScaleContextResult(
            supabase_enabled=True,
            success=True,
            scale_context_id=scale_context_id,
        )

    except Exception as e:
        logger.error(f"Failed to store scale context: {e}")
        return ScaleContextResult(
            supabase_enabled=True,
            success=False,
            error=str(e)
        )


def get_scale_context(
    *,
    file_id: str,
    page_number: Optional[int] = None,
    active_only: bool = True,
    settings: Optional[Settings] = None,
) -> Optional[ScaleContext]:
    """
    Retrieve a scale context for a file.

    Args:
        file_id: The file UUID
        page_number: Optional page number to filter by
        active_only: If True, only return active scale contexts
        settings: Optional Settings instance

    Returns:
        ScaleContext or None if not found
    """
    if settings is None:
        settings = get_settings()

    if not settings.supabase_enabled:
        return None

    client = get_supabase_client(settings)
    if client is None:
        return None

    try:
        query = client.table("scale_contexts").select("*").eq("file_id", file_id)

        if active_only:
            query = query.eq("is_active", True)

        if page_number is not None:
            query = query.eq("source_page", page_number)

        # Order by created_at desc to get most recent
        query = query.order("created_at", desc=True).limit(1)

        result = query.execute()

        if result.data and len(result.data) > 0:
            row = result.data[0]
            return ScaleContext(
                id=row.get("id"),
                file_id=row.get("file_id"),
                scale_string=row.get("scale_string"),
                scale_factor=_compute_scale_factor_from_string(row.get("scale_string")),
                pixels_per_meter=row.get("pixels_per_meter"),
                detection_method=row.get("detection_method"),
                confidence=row.get("confidence"),
                source_page=row.get("source_page"),
                source_bbox=row.get("source_bbox"),
                user_reference_px=row.get("user_reference_px"),
                user_reference_m=row.get("user_reference_m"),
                is_active=row.get("is_active", True),
            )
        return None

    except Exception as e:
        logger.error(f"Failed to retrieve scale context for file {file_id}: {e}")
        return None


def list_scale_contexts(
    *,
    file_id: str,
    settings: Optional[Settings] = None,
) -> List[ScaleContext]:
    """
    List all scale contexts for a file.

    Args:
        file_id: The file UUID
        settings: Optional Settings instance

    Returns:
        List of ScaleContext objects
    """
    if settings is None:
        settings = get_settings()

    if not settings.supabase_enabled:
        return []

    client = get_supabase_client(settings)
    if client is None:
        return []

    try:
        result = (
            client.table("scale_contexts")
            .select("*")
            .eq("file_id", file_id)
            .order("created_at", desc=True)
            .execute()
        )

        contexts = []
        for row in result.data or []:
            contexts.append(ScaleContext(
                id=row.get("id"),
                file_id=row.get("file_id"),
                scale_string=row.get("scale_string"),
                scale_factor=_compute_scale_factor_from_string(row.get("scale_string")),
                pixels_per_meter=row.get("pixels_per_meter"),
                detection_method=row.get("detection_method"),
                confidence=row.get("confidence"),
                source_page=row.get("source_page"),
                source_bbox=row.get("source_bbox"),
                user_reference_px=row.get("user_reference_px"),
                user_reference_m=row.get("user_reference_m"),
                is_active=row.get("is_active", True),
            ))
        return contexts

    except Exception as e:
        logger.error(f"Failed to list scale contexts for file {file_id}: {e}")
        return []


def _compute_scale_factor_from_string(scale_string: Optional[str]) -> Optional[float]:
    """
    Helper to compute scale factor from a scale string like "1:100".

    Args:
        scale_string: Scale string in format "1:N" or "1:N"

    Returns:
        Scale factor (e.g., 0.01 for 1:100) or None if cannot parse
    """
    if not scale_string:
        return None

    import re
    match = re.search(r"1\s*:\s*(\d+)", scale_string)
    if match:
        denominator = int(match.group(1))
        if denominator > 0:
            return 1.0 / denominator
    return None


# ============================================
# SECTOR PERSISTENCE
# ============================================


@dataclass
class SectorResult:
    """Result of a sector persistence operation."""

    supabase_enabled: bool
    success: bool = False
    sector_id: Optional[str] = None
    error: Optional[str] = None

    def to_dict(self) -> dict:
        """Convert to dictionary for API response."""
        result = {
            "supabase_enabled": self.supabase_enabled,
        }
        if self.supabase_enabled:
            result.update({
                "success": self.success,
                "sector_id": self.sector_id,
            })
            if self.error:
                result["error"] = self.error
        return result


def create_sector(
    *,
    sector: Sector,
    settings: Optional[Settings] = None,
) -> SectorResult:
    """
    Store a sector to Supabase.

    Args:
        sector: The Sector to store
        settings: Optional Settings instance

    Returns:
        SectorResult with ID and status
    """
    if settings is None:
        settings = get_settings()

    if not settings.supabase_enabled:
        logger.debug("Supabase not enabled, skipping sector persistence")
        return SectorResult(supabase_enabled=False)

    client = get_supabase_client(settings)
    if client is None:
        return SectorResult(
            supabase_enabled=True,
            success=False,
            error="Failed to initialize Supabase client"
        )

    # Use existing sector_id or generate new one
    sector_id = sector.sector_id or str(uuid4())

    try:
        sector_data = {
            "id": sector_id,
            "file_id": sector.file_id,
            "name": sector.name,
            "sector_type": sector.sector_type,
            "polygon_points": [list(p) for p in sector.polygon_points],
            "page_number": sector.page_number,
            "area_m2": sector.area_m2,
            "perimeter_m": sector.perimeter_m,
        }

        logger.info(f"Creating sector: {sector_id}")
        insert_result = client.table("sectors").insert(sector_data).execute()

        if hasattr(insert_result, 'error') and insert_result.error:
            raise Exception(f"Sector insert failed: {insert_result.error}")

        logger.info(f"Successfully created sector {sector_id}")

        return SectorResult(
            supabase_enabled=True,
            success=True,
            sector_id=sector_id,
        )

    except Exception as e:
        logger.error(f"Failed to create sector: {e}")
        return SectorResult(
            supabase_enabled=True,
            success=False,
            error=str(e)
        )


def get_sector(
    *,
    sector_id: str,
    settings: Optional[Settings] = None,
) -> Optional[Sector]:
    """
    Retrieve a sector by ID.

    Args:
        sector_id: The sector UUID
        settings: Optional Settings instance

    Returns:
        Sector or None if not found
    """
    if settings is None:
        settings = get_settings()

    if not settings.supabase_enabled:
        return None

    client = get_supabase_client(settings)
    if client is None:
        return None

    try:
        result = client.table("sectors").select("*").eq("id", sector_id).execute()

        if result.data and len(result.data) > 0:
            row = result.data[0]
            return Sector.from_dict({
                "sector_id": row.get("id"),
                "file_id": row.get("file_id"),
                "name": row.get("name"),
                "sector_type": row.get("sector_type"),
                "polygon_points": row.get("polygon_points", []),
                "page_number": row.get("page_number"),
                "area_m2": row.get("area_m2"),
                "perimeter_m": row.get("perimeter_m"),
                "created_at": row.get("created_at"),
            })
        return None

    except Exception as e:
        logger.error(f"Failed to retrieve sector {sector_id}: {e}")
        return None


def list_sectors(
    *,
    file_id: str,
    page_number: Optional[int] = None,
    settings: Optional[Settings] = None,
) -> List[Sector]:
    """
    List all sectors for a file.

    Args:
        file_id: The file UUID
        page_number: Optional page number to filter by
        settings: Optional Settings instance

    Returns:
        List of Sector objects
    """
    if settings is None:
        settings = get_settings()

    if not settings.supabase_enabled:
        return []

    client = get_supabase_client(settings)
    if client is None:
        return []

    try:
        query = client.table("sectors").select("*").eq("file_id", file_id)

        if page_number is not None:
            query = query.eq("page_number", page_number)

        query = query.order("created_at", desc=True)

        result = query.execute()

        sectors = []
        for row in result.data or []:
            sectors.append(Sector.from_dict({
                "sector_id": row.get("id"),
                "file_id": row.get("file_id"),
                "name": row.get("name"),
                "sector_type": row.get("sector_type"),
                "polygon_points": row.get("polygon_points", []),
                "page_number": row.get("page_number"),
                "area_m2": row.get("area_m2"),
                "perimeter_m": row.get("perimeter_m"),
                "created_at": row.get("created_at"),
            }))
        return sectors

    except Exception as e:
        logger.error(f"Failed to list sectors for file {file_id}: {e}")
        return []


def delete_sector(
    *,
    sector_id: str,
    settings: Optional[Settings] = None,
) -> bool:
    """
    Delete a sector by ID.

    Args:
        sector_id: The sector UUID
        settings: Optional Settings instance

    Returns:
        True if deleted successfully, False otherwise
    """
    if settings is None:
        settings = get_settings()

    if not settings.supabase_enabled:
        return False

    client = get_supabase_client(settings)
    if client is None:
        return False

    try:
        result = client.table("sectors").delete().eq("id", sector_id).execute()
        return True
    except Exception as e:
        logger.error(f"Failed to delete sector {sector_id}: {e}")
        return False


# ============================================
# MEASUREMENT PERSISTENCE
# ============================================


@dataclass
class MeasurementPersistResult:
    """Result of a measurement persistence operation."""

    supabase_enabled: bool
    success: bool = False
    measurement_id: Optional[str] = None
    error: Optional[str] = None

    def to_dict(self) -> dict:
        """Convert to dictionary for API response."""
        result = {
            "supabase_enabled": self.supabase_enabled,
        }
        if self.supabase_enabled:
            result.update({
                "success": self.success,
                "measurement_id": self.measurement_id,
            })
            if self.error:
                result["error"] = self.error
        return result


def store_measurement(
    *,
    measurement: MeasurementResult,
    settings: Optional[Settings] = None,
) -> MeasurementPersistResult:
    """
    Store a measurement result to Supabase.

    Args:
        measurement: The MeasurementResult to store
        settings: Optional Settings instance

    Returns:
        MeasurementPersistResult with ID and status
    """
    if settings is None:
        settings = get_settings()

    if not settings.supabase_enabled:
        logger.debug("Supabase not enabled, skipping measurement persistence")
        return MeasurementPersistResult(supabase_enabled=False)

    client = get_supabase_client(settings)
    if client is None:
        return MeasurementPersistResult(
            supabase_enabled=True,
            success=False,
            error="Failed to initialize Supabase client"
        )

    # Use existing measurement_id or generate new one
    measurement_id = measurement.measurement_id or str(uuid4())

    try:
        measurement_data = {
            "id": measurement_id,
            "detected_object_id": measurement.object_id,
            "sector_id": measurement.sector_id,
            "measurement_type": measurement.measurement_type,
            "value": measurement.value,
            "unit": measurement.unit,
            "confidence": measurement.confidence,
            "method": measurement.method,
            "scale_pixels_per_meter": None,  # We store this separately via scale_context_id
            "source_page": measurement.page_number,
            "source_bbox": list(measurement.source_bbox) if measurement.source_bbox else None,
        }

        logger.info(f"Storing measurement: {measurement_id}")
        insert_result = client.table("measurements").insert(measurement_data).execute()

        if hasattr(insert_result, 'error') and insert_result.error:
            raise Exception(f"Measurement insert failed: {insert_result.error}")

        logger.info(f"Successfully stored measurement {measurement_id}")

        return MeasurementPersistResult(
            supabase_enabled=True,
            success=True,
            measurement_id=measurement_id,
        )

    except Exception as e:
        logger.error(f"Failed to store measurement: {e}")
        return MeasurementPersistResult(
            supabase_enabled=True,
            success=False,
            error=str(e)
        )


def list_measurements(
    *,
    sector_id: Optional[str] = None,
    object_id: Optional[str] = None,
    page_number: Optional[int] = None,
    settings: Optional[Settings] = None,
) -> List[MeasurementResult]:
    """
    List measurements, optionally filtered.

    Args:
        sector_id: Optional sector ID to filter by
        object_id: Optional object ID to filter by
        page_number: Optional page number to filter by
        settings: Optional Settings instance

    Returns:
        List of MeasurementResult objects
    """
    if settings is None:
        settings = get_settings()

    if not settings.supabase_enabled:
        return []

    client = get_supabase_client(settings)
    if client is None:
        return []

    try:
        query = client.table("measurements").select("*")

        if sector_id is not None:
            query = query.eq("sector_id", sector_id)

        if object_id is not None:
            query = query.eq("detected_object_id", object_id)

        if page_number is not None:
            query = query.eq("source_page", page_number)

        query = query.order("created_at", desc=True)

        result = query.execute()

        measurements = []
        for row in result.data or []:
            measurements.append(MeasurementResult.from_dict({
                "measurement_id": row.get("id"),
                "measurement_type": row.get("measurement_type"),
                "value": row.get("value"),
                "unit": row.get("unit"),
                "file_id": "",  # Not stored directly in measurements table
                "page_number": row.get("source_page"),
                "confidence": row.get("confidence"),
                "method": row.get("method"),
                "sector_id": row.get("sector_id"),
                "object_id": row.get("detected_object_id"),
                "source_bbox": row.get("source_bbox"),
                "created_at": row.get("created_at"),
            }))
        return measurements

    except Exception as e:
        logger.error(f"Failed to list measurements: {e}")
        return []

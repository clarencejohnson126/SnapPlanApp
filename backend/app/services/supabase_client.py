"""
Supabase client integration for SnapGrid.

Provides a configured Supabase client for database and storage operations.
The client is only created if Supabase environment variables are set.

Required environment variables:
    SNAPGRID_SUPABASE_URL: Your Supabase project URL
    SNAPGRID_SUPABASE_SERVICE_KEY: Your Supabase service role key (for server-side operations)
    SNAPGRID_SUPABASE_BUCKET_NAME: Storage bucket name (default: "snapgrid-files")
"""

import logging
from functools import lru_cache
from typing import Optional

from ..core.config import Settings, get_settings

# Lazy import to avoid errors if supabase is not installed
_supabase_client = None
_supabase_import_error = None

try:
    from supabase import Client, create_client
except ImportError as e:
    _supabase_import_error = e
    Client = None
    create_client = None

logger = logging.getLogger(__name__)


class SupabaseNotConfiguredError(Exception):
    """Raised when Supabase operations are attempted without configuration."""
    pass


def get_supabase_client(settings: Optional[Settings] = None) -> Optional["Client"]:
    """
    Get a configured Supabase client instance.

    Returns None if:
        - Supabase is not configured (missing env vars)
        - The supabase-py package is not installed

    Args:
        settings: Optional Settings instance (uses global if not provided)

    Returns:
        Configured Supabase Client or None
    """
    global _supabase_client

    if settings is None:
        settings = get_settings()

    # Check if supabase package is available
    if _supabase_import_error is not None:
        logger.warning(
            "supabase-py package not installed. Install with: pip install supabase"
        )
        return None

    # Check if Supabase is configured
    if not settings.supabase_enabled:
        logger.debug(
            "Supabase not configured. Set SNAPGRID_SUPABASE_URL and "
            "SNAPGRID_SUPABASE_SERVICE_KEY to enable persistence."
        )
        return None

    # Create client if not already cached
    if _supabase_client is None:
        try:
            _supabase_client = create_client(
                settings.supabase_url,
                settings.supabase_service_key
            )
            logger.info(f"Supabase client initialized for {settings.supabase_url}")
        except Exception as e:
            logger.error(f"Failed to create Supabase client: {e}")
            return None

    return _supabase_client


def reset_supabase_client():
    """
    Reset the cached Supabase client.

    Useful for testing or when configuration changes.
    """
    global _supabase_client
    _supabase_client = None


def check_supabase_connection(settings: Optional[Settings] = None) -> dict:
    """
    Check if Supabase connection is working.

    Returns:
        Dictionary with connection status information
    """
    if settings is None:
        settings = get_settings()

    result = {
        "configured": settings.supabase_enabled,
        "connected": False,
        "bucket_name": settings.supabase_bucket_name,
        "error": None,
    }

    if not settings.supabase_enabled:
        result["error"] = "Supabase not configured (missing URL or service key)"
        return result

    client = get_supabase_client(settings)
    if client is None:
        result["error"] = "Failed to create Supabase client"
        return result

    # Try a simple query to verify connection
    try:
        # Check if we can access the storage
        client.storage.list_buckets()
        result["connected"] = True
    except Exception as e:
        result["error"] = str(e)

    return result

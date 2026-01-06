"""
Tests for Supabase persistence layer.

Uses mocks to avoid requiring a real Supabase connection.
"""

import pytest
from unittest.mock import MagicMock, patch
from datetime import datetime

from app.core.config import Settings
from app.services.persistence import (
    PersistenceResult,
    store_file_and_extraction,
    get_extraction_by_id,
    list_extractions,
)
from app.services.schedule_extraction import ExtractionResult, ExtractedTable, ExtractedCell


# ============================================================================
# Fixtures
# ============================================================================


@pytest.fixture
def mock_settings_enabled():
    """Settings with Supabase enabled."""
    settings = MagicMock(spec=Settings)
    settings.supabase_enabled = True
    settings.supabase_url = "https://test.supabase.co"
    settings.supabase_service_key = "test-key"
    settings.supabase_bucket_name = "test-bucket"
    return settings


@pytest.fixture
def mock_settings_disabled():
    """Settings with Supabase disabled."""
    settings = MagicMock(spec=Settings)
    settings.supabase_enabled = False
    settings.supabase_url = None
    settings.supabase_service_key = None
    settings.supabase_bucket_name = "snapgrid-files"
    return settings


@pytest.fixture
def sample_extraction_result():
    """Create a sample extraction result for testing."""
    table = ExtractedTable(
        page_number=1,
        table_index=0,
        headers=["Pos.", "Türnummer", "B[m]"],
        normalized_headers=["pos", "door_number", "width_m"],
        row_count=2,
        rows=[
            {
                "pos": ExtractedCell(value=1, raw="1", confidence=1.0, page=1, row_index=0, col_index=0),
                "door_number": ExtractedCell(value="B.01.1.001-1", raw="B.01.1.001-1", confidence=1.0, page=1, row_index=0, col_index=1),
                "width_m": ExtractedCell(value=1.01, raw="1,01", confidence=1.0, page=1, row_index=0, col_index=2),
            },
            {
                "pos": ExtractedCell(value=2, raw="2", confidence=1.0, page=1, row_index=1, col_index=0),
                "door_number": ExtractedCell(value="B.01.1.002-1", raw="B.01.1.002-1", confidence=1.0, page=1, row_index=1, col_index=1),
                "width_m": ExtractedCell(value=0.88, raw="0,88", confidence=1.0, page=1, row_index=1, col_index=2),
            },
        ],
    )
    return ExtractionResult(
        extraction_id="test-extraction-id",
        source_file="test.pdf",
        extracted_at="2025-12-21T12:00:00Z",
        tables=[table],
        total_rows=2,
    )


@pytest.fixture
def mock_supabase_client():
    """Create a mock Supabase client."""
    client = MagicMock()

    # Mock storage upload
    storage_bucket = MagicMock()
    storage_bucket.upload.return_value = MagicMock(error=None)
    client.storage.from_.return_value = storage_bucket

    # Mock table inserts
    table_result = MagicMock()
    table_result.error = None
    table_result.data = [{"id": "test-id"}]

    table_mock = MagicMock()
    table_mock.insert.return_value.execute.return_value = table_result
    table_mock.select.return_value.eq.return_value.execute.return_value = table_result
    table_mock.select.return_value.order.return_value.range.return_value.execute.return_value = table_result

    client.table.return_value = table_mock

    return client


# ============================================================================
# Tests - Supabase Disabled
# ============================================================================


class TestSupabaseDisabled:
    """Tests when Supabase is not configured."""

    def test_store_returns_disabled_result(self, mock_settings_disabled, sample_extraction_result):
        """When Supabase is disabled, store should return supabase_enabled=False."""
        result = store_file_and_extraction(
            file_bytes=b"fake pdf content",
            original_filename="test.pdf",
            extraction_result=sample_extraction_result,
            settings=mock_settings_disabled,
        )

        assert result.supabase_enabled is False
        assert result.file_id is None
        assert result.extraction_id is None

    def test_get_extraction_returns_none(self, mock_settings_disabled):
        """When Supabase is disabled, get_extraction_by_id returns None."""
        result = get_extraction_by_id("some-id", settings=mock_settings_disabled)
        assert result is None

    def test_list_extractions_returns_empty(self, mock_settings_disabled):
        """When Supabase is disabled, list_extractions returns empty list."""
        result = list_extractions(settings=mock_settings_disabled)
        assert result == []

    def test_persistence_result_to_dict_disabled(self):
        """PersistenceResult.to_dict() for disabled state."""
        result = PersistenceResult(supabase_enabled=False)
        data = result.to_dict()

        assert data == {"supabase_enabled": False}
        assert "success" not in data
        assert "file_id" not in data


# ============================================================================
# Tests - Supabase Enabled (Mocked)
# ============================================================================


class TestSupabaseEnabled:
    """Tests when Supabase is configured (using mocks)."""

    def test_store_success(
        self,
        mock_settings_enabled,
        sample_extraction_result,
        mock_supabase_client,
    ):
        """Successful storage should return file_id and extraction_id."""
        with patch("app.services.persistence.get_supabase_client", return_value=mock_supabase_client):
            result = store_file_and_extraction(
                file_bytes=b"fake pdf content",
                original_filename="test.pdf",
                extraction_result=sample_extraction_result,
                settings=mock_settings_enabled,
            )

        assert result.supabase_enabled is True
        assert result.success is True
        assert result.file_id is not None
        assert result.extraction_id is not None
        assert result.storage_path is not None
        assert result.error is None

    def test_store_with_project_id(
        self,
        mock_settings_enabled,
        sample_extraction_result,
        mock_supabase_client,
    ):
        """Storage path should include project_id when provided."""
        with patch("app.services.persistence.get_supabase_client", return_value=mock_supabase_client):
            result = store_file_and_extraction(
                file_bytes=b"fake pdf content",
                original_filename="test.pdf",
                extraction_result=sample_extraction_result,
                project_id="project-123",
                settings=mock_settings_enabled,
            )

        assert result.storage_path is not None
        assert "project-123" in result.storage_path

    def test_store_without_project_id(
        self,
        mock_settings_enabled,
        sample_extraction_result,
        mock_supabase_client,
    ):
        """Storage path should use 'unassigned' when no project_id."""
        with patch("app.services.persistence.get_supabase_client", return_value=mock_supabase_client):
            result = store_file_and_extraction(
                file_bytes=b"fake pdf content",
                original_filename="test.pdf",
                extraction_result=sample_extraction_result,
                settings=mock_settings_enabled,
            )

        assert result.storage_path is not None
        assert "unassigned" in result.storage_path

    def test_store_client_none_returns_error(self, mock_settings_enabled, sample_extraction_result):
        """When client initialization fails, should return error."""
        with patch("app.services.persistence.get_supabase_client", return_value=None):
            result = store_file_and_extraction(
                file_bytes=b"fake pdf content",
                original_filename="test.pdf",
                extraction_result=sample_extraction_result,
                settings=mock_settings_enabled,
            )

        assert result.supabase_enabled is True
        assert result.success is False
        assert result.error is not None

    def test_store_upload_failure(
        self,
        mock_settings_enabled,
        sample_extraction_result,
        mock_supabase_client,
    ):
        """Storage upload failure should be handled gracefully."""
        # Make upload raise an exception
        mock_supabase_client.storage.from_.return_value.upload.side_effect = Exception("Upload failed")

        with patch("app.services.persistence.get_supabase_client", return_value=mock_supabase_client):
            result = store_file_and_extraction(
                file_bytes=b"fake pdf content",
                original_filename="test.pdf",
                extraction_result=sample_extraction_result,
                settings=mock_settings_enabled,
            )

        assert result.supabase_enabled is True
        assert result.success is False
        assert "Upload failed" in result.error

    def test_persistence_result_to_dict_success(self):
        """PersistenceResult.to_dict() for successful state."""
        result = PersistenceResult(
            supabase_enabled=True,
            success=True,
            file_id="file-123",
            extraction_id="extraction-456",
            storage_path="project/file/test.pdf",
        )
        data = result.to_dict()

        assert data["supabase_enabled"] is True
        assert data["success"] is True
        assert data["file_id"] == "file-123"
        assert data["extraction_id"] == "extraction-456"
        assert data["storage_path"] == "project/file/test.pdf"
        assert "error" not in data

    def test_persistence_result_to_dict_error(self):
        """PersistenceResult.to_dict() for error state."""
        result = PersistenceResult(
            supabase_enabled=True,
            success=False,
            error="Something went wrong",
        )
        data = result.to_dict()

        assert data["supabase_enabled"] is True
        assert data["success"] is False
        assert data["error"] == "Something went wrong"


# ============================================================================
# Tests - Supabase Client Module
# ============================================================================


class TestSupabaseClient:
    """Tests for the supabase_client module."""

    def test_get_client_returns_none_when_disabled(self, mock_settings_disabled):
        """get_supabase_client returns None when Supabase is not configured."""
        from app.services.supabase_client import get_supabase_client

        result = get_supabase_client(mock_settings_disabled)
        assert result is None

    def test_check_connection_not_configured(self, mock_settings_disabled):
        """check_supabase_connection returns proper status when not configured."""
        from app.services.supabase_client import check_supabase_connection

        result = check_supabase_connection(mock_settings_disabled)

        assert result["configured"] is False
        assert result["connected"] is False
        assert result["error"] is not None


# ============================================================================
# Tests - API Integration
# ============================================================================


class TestAPIWithPersistence:
    """Tests for API endpoint with persistence integration."""

    def test_extract_response_includes_persistence(self, test_client, sample_pdf_path):
        """Extraction response should include persistence info."""
        response = test_client.post(
            "/api/v1/schedules/extract?use_sample=true"
        )

        assert response.status_code == 200
        data = response.json()

        # Persistence info should be present
        assert "persistence" in data
        persistence = data["persistence"]

        # When Supabase is not configured, supabase_enabled should be False
        assert "supabase_enabled" in persistence

    def test_extract_with_project_id_param(self, test_client, sample_pdf_path):
        """Endpoint should accept project_id parameter."""
        response = test_client.post(
            "/api/v1/schedules/extract?use_sample=true&project_id=test-project-123"
        )

        assert response.status_code == 200
        data = response.json()
        assert "persistence" in data

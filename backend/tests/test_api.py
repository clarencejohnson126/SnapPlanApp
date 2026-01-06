"""
Tests for FastAPI endpoints.

These tests verify the API layer works correctly.
"""

import sys
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

# Add backend to path
backend_dir = Path(__file__).parent.parent
sys.path.insert(0, str(backend_dir))

from app.main import app


@pytest.fixture
def client():
    """Create a test client for the FastAPI app."""
    return TestClient(app)


class TestRootEndpoints:
    """Tests for root-level endpoints."""

    def test_root_returns_info(self, client):
        """Root endpoint should return app info."""
        response = client.get("/")
        assert response.status_code == 200

        data = response.json()
        assert "name" in data
        assert data["name"] == "SnapGrid"
        assert "version" in data

    def test_health_check(self, client):
        """Health endpoint should return ok status."""
        response = client.get("/health")
        assert response.status_code == 200

        data = response.json()
        assert data["status"] == "ok"


class TestScheduleEndpoints:
    """Tests for schedule extraction endpoints."""

    def test_schedule_health(self, client):
        """Schedule service health check should work."""
        response = client.get("/api/v1/schedules/health")
        assert response.status_code == 200

        data = response.json()
        assert data["status"] == "ok"
        assert data["service"] == "schedule-extraction"

    def test_sample_info(self, client):
        """Should return info about sample PDF."""
        response = client.get("/api/v1/schedules/sample-info")

        # May be 404 if sample not found, or 200 if found
        if response.status_code == 200:
            data = response.json()
            assert "filename" in data
            assert "expected_content" in data

    def test_extract_requires_input(self, client):
        """Extract endpoint should require either file or use_sample."""
        response = client.post("/api/v1/schedules/extract")
        assert response.status_code == 400
        assert "Either upload a PDF file or set use_sample=true" in response.json()["detail"]

    def test_extract_with_sample(self, client, sample_pdf_path):
        """Should extract from sample PDF when use_sample=true."""
        response = client.post("/api/v1/schedules/extract?use_sample=true")

        if response.status_code == 404:
            pytest.skip("Sample PDF not found")

        assert response.status_code == 200

        data = response.json()
        assert data["status"] == "ok"
        assert "tables" in data
        assert "total_rows" in data
        assert data["total_rows"] >= 30  # Expected ~35 doors

    def test_extract_includes_summary(self, client, sample_pdf_path):
        """Should include summary when requested."""
        response = client.post(
            "/api/v1/schedules/extract?use_sample=true&include_summary=true"
        )

        if response.status_code == 404:
            pytest.skip("Sample PDF not found")

        assert response.status_code == 200

        data = response.json()
        assert "summary" in data
        assert data["summary"] is not None
        assert "total_doors" in data["summary"]

    def test_extract_response_structure(self, client, sample_pdf_path):
        """Response should have expected structure."""
        response = client.post("/api/v1/schedules/extract?use_sample=true")

        if response.status_code == 404:
            pytest.skip("Sample PDF not found")

        assert response.status_code == 200

        data = response.json()

        # Required fields
        assert "extraction_id" in data
        assert "source_file" in data
        assert "extracted_at" in data
        assert "tables" in data
        assert "total_rows" in data
        assert "status" in data
        assert "errors" in data

        # Table structure
        if data["tables"]:
            table = data["tables"][0]
            assert "page_number" in table
            assert "headers" in table
            assert "normalized_headers" in table
            assert "rows" in table
            assert "row_count" in table

            # Row structure
            if table["rows"]:
                row = table["rows"][0]
                # Each value should have auditability fields
                for field_name, cell in row.items():
                    assert "value" in cell
                    assert "raw" in cell
                    assert "confidence" in cell
                    assert "page" in cell

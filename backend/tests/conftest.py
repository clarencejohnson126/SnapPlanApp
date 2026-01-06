"""
Pytest configuration and fixtures for SnapGrid backend tests.
"""

import sys
from pathlib import Path

import pytest
from httpx import ASGITransport, AsyncClient
from starlette.testclient import TestClient

# Add backend to path for imports
backend_dir = Path(__file__).parent.parent
sys.path.insert(0, str(backend_dir))

from app.core.config import get_sample_pdf_path
from app.main import app


@pytest.fixture
def sample_pdf_path() -> Path:
    """Get path to the sample door schedule PDF."""
    path = get_sample_pdf_path()
    if not path.exists():
        pytest.skip(f"Sample PDF not found at {path}")
    return path


@pytest.fixture
def project_root() -> Path:
    """Get the project root directory."""
    return Path(__file__).parent.parent.parent


@pytest.fixture
def test_client() -> TestClient:
    """Synchronous test client for API tests."""
    return TestClient(app)

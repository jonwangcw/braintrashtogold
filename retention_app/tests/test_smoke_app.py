import pytest

fastapi = pytest.importorskip("fastapi")
pytest.importorskip("starlette")
pytest.importorskip("multipart")

from fastapi.testclient import TestClient

from app.main import app


def test_homepage_smoke():
    client = TestClient(app)
    response = client.get("/")
    assert response.status_code == 200

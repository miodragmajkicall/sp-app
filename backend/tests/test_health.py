import pytest
import httpx

BASE_URL = "http://localhost:8000"


@pytest.mark.live_api
def test_health():
    r = httpx.get(f"{BASE_URL}/health", timeout=5)
    assert r.status_code == 200
    assert r.json() == {"status": "ok"}


@pytest.mark.live_api
def test_db_health():
    r = httpx.get(f"{BASE_URL}/db/health", timeout=5)
    assert r.status_code == 200
    assert r.json() == {"db": "ok"}
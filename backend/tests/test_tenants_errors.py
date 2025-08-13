# backend/tests/test_tenants_errors.py
import time
import uuid
import httpx

BASE_URL = "http://localhost:8000"

def _create_tenant(code: str, name: str) -> str:
    r = httpx.post(f"{BASE_URL}/tenants", json={"code": code, "name": name}, timeout=5)
    assert r.status_code == 201
    return r.json()["id"]

def test_create_duplicate_code_returns_400_or_409():
    # prvo stvorimo tenant s unikatnim code-om
    code = f"dup{int(time.time())}"
    _ = _create_tenant(code, "First")

    # pokušamo ponovo s ISTIM code-om → mora pasti
    r = httpx.post(f"{BASE_URL}/tenants", json={"code": code, "name": "Second"}, timeout=5)
    assert r.status_code in (400, 409)
    # poruka može varirati zavisno od handlera/DB poruke:
    msg = r.json().get("detail", "").lower()
    assert ("code already exists" in msg) or ("duplicate key" in msg) or ("unique" in msg)

def test_get_nonexistent_returns_404():
    random_id = str(uuid.uuid4())
    r = httpx.get(f"{BASE_URL}/tenants/{random_id}", timeout=5)
    assert r.status_code == 404

def test_delete_nonexistent_returns_404():
    random_id = str(uuid.uuid4())
    r = httpx.delete(f"{BASE_URL}/tenants/{random_id}", timeout=5)
    assert r.status_code == 404

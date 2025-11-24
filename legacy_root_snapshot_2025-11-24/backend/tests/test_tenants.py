import httpx
from uuid import uuid4

BASE_URL = "http://localhost:8000"

def test_tenants_crud_flow():
    # --- CREATE ---
    code = "t-" + uuid4().hex[:6]
    payload = {"code": code, "name": "Test d.o.o."}
    r = httpx.post(f"{BASE_URL}/tenants", json=payload, timeout=5)
    assert r.status_code == 201
    created = r.json()
    tenant_id = created["id"]
    assert created["code"] == code
    assert created["name"] == "Test d.o.o."

    # --- LIST contains our tenant ---
    r = httpx.get(f"{BASE_URL}/tenants", timeout=5)
    assert r.status_code == 200
    items = r.json()
    assert any(t["id"] == tenant_id for t in items)

    # --- GET by id ---
    r = httpx.get(f"{BASE_URL}/tenants/{tenant_id}", timeout=5)
    assert r.status_code == 200
    assert r.json()["id"] == tenant_id

    # --- PATCH (update name) ---
    new_name = "Test d.o.o. (updated)"
    r = httpx.patch(f"{BASE_URL}/tenants/{tenant_id}", json={"name": new_name}, timeout=5)
    assert r.status_code == 200
    assert r.json()["name"] == new_name

    # --- DELETE ---
    r = httpx.delete(f"{BASE_URL}/tenants/{tenant_id}", timeout=5)
    assert r.status_code == 204

    # --- GET should now be 404 ---
    r = httpx.get(f"{BASE_URL}/tenants/{tenant_id}", timeout=5)
    assert r.status_code == 404

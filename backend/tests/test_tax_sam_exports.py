from __future__ import annotations

from fastapi.testclient import TestClient

from app.main import app


client = TestClient(app)


def test_sam_overview_export_csv_basic():
    """
    Osnovni smoke test za /sam/overview/{year}/export.

    Cilj:
    - endpoint radi (200 OK),
    - vraća CSV (text/csv),
    - header sadrži očekivane kolone.
    """
    year = 2025
    tenant_code = "t-demo"

    response = client.get(
        f"/sam/overview/{year}/export",
        headers={"X-Tenant-Code": tenant_code},
    )

    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/csv")

    body = response.text.splitlines()
    assert len(body) >= 1

    header = body[0]
    assert "section" in header
    assert "month" in header
    assert "month_label" in header
    assert "income_total" in header
    assert "total_due" in header


def test_tax_yearly_export_csv_basic():
    """
    Osnovni smoke test za /tax/yearly/export.

    Cilj:
    - endpoint radi (200 OK),
    - vraća CSV (text/csv),
    - header sadrži očekivane kolone.
    """
    year = 2025
    tenant_code = "t-demo"

    response = client.get(
        f"/tax/yearly/export?year={year}",
        headers={"X-Tenant-Code": tenant_code},
    )

    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/csv")

    body = response.text.splitlines()
    assert len(body) >= 2  # header + barem jedan red podataka

    header = body[0]
    assert "year" in header
    assert "tenant_code" in header
    assert "months_included" in header
    assert "total_income" in header
    assert "total_due" in header

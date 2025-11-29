# /home/miso/dev/sp-app/sp-app/backend/tests/test_reports_year_summary.py
from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def test_reports_year_summary_basic():
    response = client.get(
        "/reports/year-summary/2025",
        headers={"X-Tenant-Code": "t-demo"},
    )

    assert response.status_code == 200

    data = response.json()

    # Osnovni meta podaci
    assert data["year"] == 2025
    assert data["tenant_code"] == "t-demo"

    # Ključevi koje očekujemo u odgovoru
    for key in [
        "total_income",
        "total_expense",
        "profit",
        "taxable_base",
        "income_tax",
        "contributions_total",
        "total_due",
        "currency",
    ]:
        assert key in data

# /home/miso/dev/sp-app/sp-app/backend/tests/test_reports_cashflow_export.py
from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def test_reports_cashflow_export_csv_basic():
    response = client.get(
        "/reports/cashflow/2025/export",
        headers={"X-Tenant-Code": "t-demo"},
    )

    assert response.status_code == 200

    # Content-Type treba da bude text/csv (može imati charset suffix)
    content_type = response.headers.get("content-type", "")
    assert content_type.startswith("text/csv")

    # Content-Disposition sa očekivanim imenom fajla
    content_disposition = response.headers.get("content-disposition", "")
    assert 'attachment; filename="cashflow-t-demo-2025.csv"' in content_disposition

    # Tijelo CSV-a
    body = response.content.decode("utf-8")
    lines = [line for line in body.strip().splitlines() if line]

    # Header + 12 mjeseci
    assert len(lines) == 13
    assert lines[0] == "year,month,tenant_code,income,expense,profit,currency"

    # Prvi podatak (januar) – osnovna provjera formata
    first_data = lines[1].split(",")
    assert first_data[0] == "2025"           # year
    assert first_data[1].isdigit()          # month
    assert first_data[2] == "t-demo"        # tenant_code
    # income/expense/profit mogu biti "0" ili "0.00" – samo provjeravamo da postoje
    assert len(first_data) == 7

# /home/miso/dev/sp-app/sp-app/backend/tests/test_export_inspection.py

from fastapi.testclient import TestClient

from app.main import app
from app.routes import export as export_route

client = TestClient(app)


def _post_export(payload: dict):
    return client.post(
        "/export/inspection",
        headers={"X-Tenant-Code": "t-demo"},
        json=payload,
    )


def _valid_payload() -> dict:
    return {
        "from_date": "2025-01-01",
        "to_date": "2025-01-31",
        "include_outgoing_invoices_pdf": True,
        "include_input_invoices_pdf": True,
        "include_kpr_pdf": True,
        "include_promet_pdf": True,
        "include_cash_bank_pdf": True,
        "include_taxes_pdf": True,
    }


def test_export_inspection_is_not_implemented(monkeypatch):
    def fail_if_called(*args, **kwargs):
        raise AssertionError("Inspection export must fail before generation")

    monkeypatch.setattr(export_route, "ensure_tenant_exists", fail_if_called)
    monkeypatch.setattr(export_route, "_dummy_pdf", fail_if_called)
    monkeypatch.setattr(export_route.zipfile, "ZipFile", fail_if_called)

    payload = _valid_payload()
    response = _post_export(payload)

    assert response.status_code == 501
    assert response.json() == {
        "detail": (
            "Inspection ZIP export is not available because document generators "
            "are not implemented"
        )
    }

    # Content-Type
    content_type = response.headers.get("content-type", "")
    assert not content_type.startswith("application/zip")

    # Content-Disposition
    cd = response.headers.get("content-disposition", "")
    assert not cd

def test_export_inspection_requires_tenant_header():
    response = client.post(
        "/export/inspection",
        json=_valid_payload(),
    )

    assert response.status_code == 400
    assert response.json() == {"detail": "Missing X-Tenant-Code header"}


def test_export_inspection_rejects_invalid_date():
    payload = _valid_payload()
    payload["from_date"] = "not-a-date"

    response = _post_export(payload)

    assert response.status_code == 422


def test_export_inspection_reversed_period_is_not_implemented():
    payload = _valid_payload()
    payload["from_date"] = "2025-02-01"
    payload["to_date"] = "2025-01-01"

    response = _post_export(payload)

    assert response.status_code == 501

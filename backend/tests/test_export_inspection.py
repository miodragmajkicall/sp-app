# /home/miso/dev/sp-app/sp-app/backend/tests/test_export_inspection.py

from fastapi.testclient import TestClient
import zipfile
import io

from app.main import app

client = TestClient(app)


def _post_export(payload: dict):
    return client.post(
        "/export/inspection",
        headers={"X-Tenant-Code": "t-demo"},
        json=payload,
    )


def test_export_inspection_basic_zip():
    payload = {
        "from_date": "2025-01-01",
        "to_date": "2025-01-31",
        "include_outgoing_invoices_pdf": True,
        "include_input_invoices_pdf": True,
        "include_kpr_pdf": True,
        "include_promet_pdf": True,
        "include_cash_bank_pdf": True,
        "include_taxes_pdf": True,
    }

    response = _post_export(payload)

    assert response.status_code == 200

    # Content-Type
    content_type = response.headers.get("content-type", "")
    assert content_type.startswith("application/zip")

    # Content-Disposition
    cd = response.headers.get("content-disposition", "")
    assert 'attachment; filename="inspection-t-demo-2025-01-01_2025-01-31.zip"' in cd

    # ZIP sadržaj
    zf = zipfile.ZipFile(io.BytesIO(response.content))
    names = sorted(zf.namelist())

    assert names == sorted(
        [
            "01_invoices_outgoing/outgoing_invoices_2025-01-01_2025-01-31.pdf",
            "02_invoices_incoming/input_invoices_2025-01-01_2025-01-31.pdf",
            "03_kpr/KPR_2025-01-01_2025-01-31.pdf",
            "04_promet/knjiga_prometa_2025-01-01_2025-01-31.pdf",
            "05_cash_bank/cash_bank_2025-01-01_2025-01-31.pdf",
            "06_taxes/taxes_2025-01-01_2025-01-31.pdf",
        ]
    )


def test_export_inspection_with_exclusions():
    payload = {
        "from_date": "2025-01-01",
        "to_date": "2025-01-31",
        "include_outgoing_invoices_pdf": False,
        "include_input_invoices_pdf": True,
        "include_kpr_pdf": False,
        "include_promet_pdf": True,
        "include_cash_bank_pdf": False,
        "include_taxes_pdf": True,
    }

    response = _post_export(payload)
    assert response.status_code == 200

    zf = zipfile.ZipFile(io.BytesIO(response.content))
    names = zf.namelist()

    assert "01_invoices_outgoing/outgoing_invoices_2025-01-01_2025-01-31.pdf" not in names
    assert "03_kpr/KPR_2025-01-01_2025-01-31.pdf" not in names
    assert "05_cash_bank/cash_bank_2025-01-01_2025-01-31.pdf" not in names

    assert "02_invoices_incoming/input_invoices_2025-01-01_2025-01-31.pdf" in names
    assert "04_promet/knjiga_prometa_2025-01-01_2025-01-31.pdf" in names
    assert "06_taxes/taxes_2025-01-01_2025-01-31.pdf" in names


def test_export_inspection_invalid_period():
    payload = {
        "from_date": "2025-02-01",
        "to_date": "2025-01-01",
        "include_outgoing_invoices_pdf": True,
        "include_input_invoices_pdf": True,
        "include_kpr_pdf": True,
        "include_promet_pdf": True,
        "include_cash_bank_pdf": True,
        "include_taxes_pdf": True,
    }

    response = _post_export(payload)

    assert response.status_code == 400
    assert "from_date" in response.json().get("detail", "")

from __future__ import annotations

import csv
import re
from datetime import date
from decimal import Decimal
from io import BytesIO, StringIO
from uuid import uuid4

from fastapi.testclient import TestClient
from pypdf import PdfReader

from app.db import SessionLocal
from app.main import app
from app.models import TenantTaxProfileSettings
from app.schemas.kpr import KprRowItem
from app.services.pdf_kpr import KprPeriod, render_kpr_pdf
from app.tenant_security import ensure_tenant_exists
from tests.invoice_profile_helpers import save_complete_profile

client = TestClient(app)


def _post(path, headers, payload):
    response = client.post(path, headers=headers, json=payload)
    assert response.status_code == 201, response.text
    return response.json()


def _get(path, headers, params=None):
    response = client.get(path, headers=headers, params=params)
    assert response.status_code == 200, response.text
    return response


def _profile(tenant):
    with SessionLocal() as db:
        ensure_tenant_exists(db, tenant)
        db.add(TenantTaxProfileSettings(
            tenant_code=tenant, entity="RS", regime="pausal",
            scenario_key="rs_primary", has_additional_activity=False,
        ))
        db.commit()


def _projection(row):
    return (row["date"], row["kind"], row["source"],
            int(row["source_id"]), Decimal(str(row["amount"])),
            row["tax_treatment"], row["tax_deductible"])


def _summary(rows):
    income = sum((r[4] for r in rows if r[1] == "income"), Decimal(0))
    expense = sum((r[4] for r in rows if r[1] == "expense"), Decimal(0))
    return {"income": income, "expense": expense, "net": income - expense}


def _check_list(headers, params, selected, whole=None):
    data = _get("/kpr", headers, params).json()
    assert data["total"] == len(selected)
    assert [_projection(r) for r in data["items"]] == selected
    assert {k: Decimal(str(v)) for k, v in data["summary"].items()} == _summary(
        selected if whole is None else whole
    )
    return data


def _check_exports(headers, params, expected, other_tag):
    csv_response = _get("/kpr/export-excel", headers, params)
    assert csv_response.content.startswith(b"\xef\xbb\xbf")
    csv_text = csv_response.content.decode("utf-8-sig")
    rows = list(csv.reader(StringIO(csv_text, newline="")))
    assert len(rows[0]) == 12
    assert all(len(row) == 12 for row in rows)
    assert other_tag not in csv_text
    actual = [
        (r[0], "income" if r[1] == "PRIHOD" else "expense",
         r[10], int(r[11]), Decimal(r[6]), r[9] or None, r[8] == "DA")
        for r in rows[1:]
    ]
    assert actual == expected

    pdf_response = _get("/kpr/export", headers, params)
    assert pdf_response.content.startswith(b"%PDF-")
    reader = PdfReader(BytesIO(pdf_response.content))
    text = "\n".join(page.extract_text() or "" for page in reader.pages)
    ids = [
        (source, int(source_id))
        for source, source_id in re.findall(
            r"\b(invoice|input_invoice|cash)\s*/\s*(\d+)\b", text
        )
    ]
    assert ids == [(r[2], r[3]) for r in expected]
    assert other_tag not in text
    for amount in _summary(expected).values():
        assert f"{amount:.2f} BAM" in text


def test_kpr7_two_tenants_all_sources_exports():
    fixtures = []
    for scale in (1, 2):
        tenant = f"kpr7-{uuid4().hex[:12]}"
        headers = {"X-Tenant-Code": tenant}
        tag = f"KPR7-{uuid4().hex[:8]}"
        total = Decimal("117.00") * scale
        deductible = scale == 1
        save_complete_profile(client, headers)
        _profile(tenant)

        invoice = _post("/invoices", headers, {
            "invoice_number": f"K7-I-{uuid4().hex[:8]}",
            "issue_date": "2025-12-31", "due_date": "2026-01-10",
            "buyer_name": f"{tag} Buyer", "buyer_address": "Banja Luka",
            "items": [{"description": "KPR7 service", "quantity": "1",
                       "unit_price": str(Decimal(100) * scale), "vat_rate": "0.17"}],
        })
        incoming = _post("/input-invoices", headers, {
            "supplier_name": f"{tag} Supplier",
            "invoice_number": f"K7-U-{uuid4().hex[:8]}",
            "issue_date": "2025-12-20", "posting_date": "2025-12-20",
            "total_base": str(Decimal(100) * scale),
            "total_vat": str(Decimal(17) * scale),
            "total_amount": str(total), "is_tax_deductible": deductible,
            "note": f"{tag} input",
        })
        input_id = incoming["id"]
        payment = _post(f"/input-invoices/{input_id}/payment", headers, {
            "payment_date": "2026-01-02", "account": "bank",
        })
        cash = _post("/cash/", headers, {
            "entry_date": "2026-01-03", "kind": "expense",
            "amount": str(Decimal(5) * scale),
            "recognition_class": "business_activity",
            "tax_treatment": "nondeductible", "note": f"{tag} manual",
        })
        excluded = _post("/cash/", headers, {
            "entry_date": "2026-01-04", "kind": "expense", "amount": "999.00",
            "recognition_class": "cash_only", "note": f"{tag} excluded",
        })
        expected = [
            ("2025-12-31", "income", "invoice", invoice["id"], total, None, False),
            ("2026-01-02", "expense", "input_invoice", input_id, total, None, deductible),
            ("2026-01-03", "expense", "cash", cash["id"],
             Decimal(5) * scale, "nondeductible", False),
        ]
        fixtures.append((headers, tag, expected, payment["id"], excluded["id"]))

    for index, (headers, tag, expected, linked_id, excluded_id) in enumerate(fixtures):
        other_tag = fixtures[1 - index][1]
        data = _check_list(headers, {"limit": 100}, expected)
        assert other_tag not in str(data)
        assert ("cash", linked_id) not in {(r[2], r[3]) for r in expected}
        assert ("cash", excluded_id) not in {(r[2], r[3]) for r in expected}

        for offset in range(4):
            response = _get("/kpr", headers, {"limit": 1, "offset": offset}).json()
            assert response["total"] == 3
            assert [_projection(r) for r in response["items"]] == expected[offset:offset + 1]
            assert {k: Decimal(str(v)) for k, v in response["summary"].items()} == _summary(expected)
        _check_list(headers, {"kind": "income"}, expected[:1], expected)
        _check_list(headers, {"kind": "expense"}, expected[1:], expected)

        for params, selected in [
            ({"year": 2025}, expected[:1]),
            ({"year": 2025, "month": 12}, expected[:1]),
            ({"year": 2026}, expected[1:]),
            ({"year": 2026, "month": 1}, expected[1:]),
            ({"year": 2028}, []),
        ]:
            _check_list(headers, params, selected)
            _check_exports(headers, params, selected, other_tag)

        _check_list(headers, {"month": 12}, expected[:1])
        _check_list(headers, {"month": 1}, expected[1:])
        _check_exports(headers, {"year": 2026, "kind": "income", "limit": 1, "offset": 99},
                       expected[1:], other_tag)
        _check_list(headers, {"limit": 100}, expected)


def test_kpr7_pdf_long_row_and_document():
    document_number = "KPR7-" + "D" * 59
    tokens = [f"KPR7SEG{n:03d}" for n in range(320)]
    description = "KPR7-LONG-START\n" + " ".join(tokens) + "\nKPR7-LONG-END"
    assert len(document_number) == 64
    row = KprRowItem(
        date=date(2026, 9, 9), kind="expense", category="input_invoice",
        counterparty="KPR7 Long Supplier", document_number=document_number,
        description=description, amount=Decimal("117.00"), currency="BAM",
        tax_deductible=True, tax_treatment=None,
        source="input_invoice", source_id=987654321,
    )
    original = row.model_dump()
    pdf = render_kpr_pdf("kpr7-long-test", KprPeriod(2026, 9), [row])
    reader = PdfReader(BytesIO(pdf))
    pages = [page.extract_text() or "" for page in reader.pages]
    assert len(pages) > 1
    assert all("Stranica" in text for text in pages)
    assert all(float(page.mediabox.width) > float(page.mediabox.height) for page in reader.pages)
    text = "\n".join(pages)
    compact = "".join(text.split())
    assert document_number in compact
    assert compact.count("KPR7-LONG-START") == 1
    assert compact.count("KPR7-LONG-END") == 1
    assert re.findall(r"KPR7SEG\d{3}", compact) == tokens
    assert re.findall(r"\binput_invoice\s*/\s*(\d+)\b", text) == ["987654321"]
    assert "117.00 BAM" in text
    assert "-117.00 BAM" in text
    assert sum(line.strip() == "Neto rezultat" for line in text.splitlines()) == 1
    assert row.model_dump() == original

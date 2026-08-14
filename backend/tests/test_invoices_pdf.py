from __future__ import annotations

from contextlib import contextmanager
from datetime import date
from decimal import Decimal
from io import BytesIO
from pathlib import Path
import re
from types import SimpleNamespace
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient
from PIL import Image

from app.main import app
from app.db import get_session as _get_session_dep
from app.models import Invoice, TenantAsset, TenantProfileSettings
from app.routes import invoices as invoice_routes
from app.routes import settings as settings_routes
from app.services.pdf_invoice import LEGACY_ISSUER_MESSAGE, render_invoice_pdf
from tests.invoice_profile_helpers import save_complete_profile

client = TestClient(app)


@contextmanager
def _db_session_for_test():
    """
    Helper context manager za direktan rad sa DB u testovima.

    Koristimo isti get_session dependency kao i API, ali ga ovdje
    ručno "vozimо" kao generator:
    - next() -> Session
    - drugi next() će pokrenuti finally blok i zatvoriti sesiju.
    """
    gen = _get_session_dep()
    db = next(gen)
    try:
        yield db
    finally:
        try:
            next(gen)
        except StopIteration:
            pass


def _make_invoice_payload(
    invoice_number: str,
    buyer_name: str = "PDF Test Buyer",
) -> dict:
    """
    Helper za kreiranje minimalno validnog payload-a za fakturu.
    """
    return {
        "invoice_number": invoice_number,
        "issue_date": date(2088, 1, 15).isoformat(),
        "due_date": date(2088, 2, 15).isoformat(),
        "buyer_name": buyer_name,
        "buyer_address": "Test ulica 1, Banja Luka",
        "items": [
            {
                "description": "Test stavka 1",
                "quantity": "2",
                "unit_price": "10.00",
                "vat_rate": "0.17",
            },
            {
                "description": "Test stavka 2",
                "quantity": "1",
                "unit_price": "5.00",
                "vat_rate": "0.17",
            },
        ],
    }


def test_invoice_pdf_generation_happy_path() -> None:
    """
    Happy-path test za PDF generisanje fakture:

    - kreiramo fakturu za tenanta 'pdf-tenant-a',
    - pozivamo GET /invoices/{id}/pdf,
    - očekujemo:
        * 200 OK,
        * Content-Type: application/pdf,
        * Content-Disposition sa 'inline' i ispravnim imenom fajla,
        * PDF sadržaj počinje sa '%PDF-1.4' i sadrži osnovni tekst fakture.
    """
    tenant_code = "pdf-tenant-a"
    save_complete_profile(client, {"X-Tenant-Code": tenant_code})
    invoice_number = "PDF-INV-001"

    # 0) Očistimo potencijalne stare fakture sa istim brojem za ovog tenanta
    with _db_session_for_test() as db:
        db.query(Invoice).filter(
            Invoice.tenant_code == tenant_code,
            Invoice.invoice_number == invoice_number,
        ).delete()
        db.commit()

    # 1) Kreiramo fakturu
    create_resp = client.post(
        "/invoices",
        headers={"X-Tenant-Code": tenant_code},
        json=_make_invoice_payload(invoice_number),
    )
    assert create_resp.status_code == 201, create_resp.text

    invoice_data = create_resp.json()
    invoice_id = invoice_data["id"]
    assert invoice_data["invoice_number"] == invoice_number

    # 2) Preuzimamo PDF
    pdf_resp = client.get(
        f"/invoices/{invoice_id}/pdf",
        headers={"X-Tenant-Code": tenant_code},
    )
    assert pdf_resp.status_code == 200

    # Headeri
    ct = pdf_resp.headers.get("content-type", "")
    assert ct.startswith("application/pdf")

    cd = pdf_resp.headers.get("content-disposition", "")
    assert "inline" in cd
    assert f"invoice-{invoice_number}" in cd

    # Sadržaj PDF-a
    content = pdf_resp.content
    assert content.startswith(b"%PDF-1.4")
    # Provjerimo da se unutar PDF-a nalaze osnovni podaci iz fakture
    assert b"Faktura br:" in content
    assert invoice_number.encode("ascii") in content
    assert f"Tenant: {tenant_code}".encode("ascii") not in content
    assert b"Osnovica:" in content
    assert b"Ukupno:" in content


def test_invoice_pdf_not_accessible_for_other_tenant() -> None:
    """
    Sigurnosni test: faktura se ne smije moći preuzeti kao PDF
    sa drugim X-Tenant-Code header-om.

    - kreiramo fakturu za tenanta 'pdf-tenant-b',
    - pokušamo da preuzmemo PDF sa header-om drugog tenanta,
    - očekujemo 404 (Invoice not found).
    """
    tenant_owner = "pdf-tenant-b"
    other_tenant = "pdf-tenant-c"
    save_complete_profile(client, {"X-Tenant-Code": tenant_owner})
    invoice_number = "PDF-INV-002"

    # 0) Očistimo potencijalne stare fakture sa istim brojem za tenant_owner
    with _db_session_for_test() as db:
        db.query(Invoice).filter(
            Invoice.tenant_code == tenant_owner,
            Invoice.invoice_number == invoice_number,
        ).delete()
        db.commit()

    # 1) Kreiramo fakturu za tenant_owner
    create_resp = client.post(
        "/invoices",
        headers={"X-Tenant-Code": tenant_owner},
        json=_make_invoice_payload(invoice_number, buyer_name="PDF Buyer 2"),
    )
    assert create_resp.status_code == 201, create_resp.text

    invoice_data = create_resp.json()
    invoice_id = invoice_data["id"]

    # 2) Pokušavamo preuzeti PDF sa drugim tenant header-om
    pdf_resp = client.get(
        f"/invoices/{invoice_id}/pdf",
        headers={"X-Tenant-Code": other_tenant},
    )
    assert pdf_resp.status_code == 404
    body = pdf_resp.json()
    assert body.get("detail") == "Invoice not found"


def _item(description: str = "Test service", **overrides):
    values = {
        "description": description,
        "quantity": Decimal("2"),
        "unit_price": Decimal("10.00"),
        "discount_percent": Decimal("5.00"),
        "vat_rate": Decimal("0.17"),
        "base_amount": Decimal("19.00"),
        "vat_amount": Decimal("3.23"),
        "total_amount": Decimal("22.23"),
    }
    values.update(overrides)
    return SimpleNamespace(**values)


def _invoice(**overrides):
    values = {
        "invoice_number": "UNIT-PDF-1",
        "issue_date": date(2088, 1, 15),
        "due_date": date(2088, 2, 15),
        "buyer_name": "Business Buyer",
        "buyer_address": "Buyer address 1",
        "buyer_type": "BUSINESS",
        "buyer_tax_id": "4401111111111",
        "issuer_business_name": "Historical Issuer SP",
        "issuer_address": "Historical address 10",
        "issuer_tax_id": "4402222222222",
        "issuer_phone": "+387 51 111 222",
        "issuer_email": "office@historical.example",
        "issuer_bank_name": "Historical Bank",
        "issuer_bank_account": "555-111-222",
        "issuer_iban": "BA391290079401028494",
        "issuer_swift_bic": "HISTBA22",
        "total_base": Decimal("19.00"),
        "total_vat": Decimal("3.23"),
        "total_amount": Decimal("22.23"),
        "items": [_item()],
    }
    values.update(overrides)
    return SimpleNamespace(**values)


def _image_bytes(
    image_format: str,
    *,
    size: tuple[int, int] = (80, 40),
    color=(20, 100, 180, 255),
) -> bytes:
    mode = "RGBA" if image_format == "PNG" else "RGB"
    image = Image.new(mode, size, color)
    output = BytesIO()
    image.save(output, format=image_format)
    return output.getvalue()


def _pdf_text(pdf: bytes) -> bytes:
    return pdf


def _image_stream(pdf: bytes) -> bytes:
    match = re.search(
        rb"/Filter /DCTDecode /Length \d+ >>\nstream\n(.*?)\nendstream",
        pdf,
        re.DOTALL,
    )
    assert match is not None
    return match.group(1)


@pytest.fixture
def isolated_logo_storage(tmp_path: Path, monkeypatch):
    root = tmp_path / "tenant_assets"
    monkeypatch.setattr(settings_routes, "TENANT_ASSETS_ROOT", root)
    monkeypatch.setattr(invoice_routes, "TENANT_ASSETS_ROOT", root)
    return root


def _headers(prefix: str) -> dict[str, str]:
    return {"X-Tenant-Code": f"{prefix}-{uuid4().hex[:10]}"}


def _create_invoice(headers: dict[str, str], **payload_overrides) -> dict:
    save_complete_profile(client, headers)
    payload = _make_invoice_payload(f"PDF-{uuid4().hex[:12]}")
    payload.update(payload_overrides)
    response = client.post("/invoices", headers=headers, json=payload)
    assert response.status_code == 201, response.text
    return response.json()


def test_pdf_uses_complete_historical_issuer_and_no_demo_values() -> None:
    content = _pdf_text(render_invoice_pdf(_invoice()))
    for value in (
        b"Historical Issuer SP",
        b"Historical address 10",
        b"JIB / PIB: 4402222222222",
        b"Telefon: +387 51 111 222",
        b"Email: office@historical.example",
        b"Banka: Historical Bank",
        b"Racun: 555-111-222",
        b"IBAN: BA391290079401028494",
        b"SWIFT/BIC: HISTBA22",
    ):
        assert value in content
    for forbidden in (
        b"SP APP - DEMO LOGO",
        b"SP Primjer - demo korisnik",
        b"0000000000000",
        b"Demo Banka",
        b"DEMOBA22",
        b"Tenant:",
    ):
        assert forbidden not in content


def test_pdf_required_only_issuer_omits_optional_rows() -> None:
    invoice = _invoice(
        issuer_phone=" ",
        issuer_email=None,
        issuer_bank_name="",
        issuer_bank_account=None,
        issuer_iban="\t",
        issuer_swift_bic=None,
    )
    content = _pdf_text(render_invoice_pdf(invoice))
    assert b"Historical Issuer SP" in content
    assert b"JIB / PIB: 4402222222222" in content
    assert b"Telefon:" not in content
    assert b"Email:" not in content
    assert b"Instrukcije za uplatu" not in content


def test_legacy_invoice_has_exact_neutral_message_and_no_profile_fallback() -> None:
    invoice = _invoice(
        **{
            field: None
            for field in (
                "issuer_business_name",
                "issuer_address",
                "issuer_tax_id",
                "issuer_phone",
                "issuer_email",
                "issuer_bank_name",
                "issuer_bank_account",
                "issuer_iban",
                "issuer_swift_bic",
            )
        }
    )
    content = _pdf_text(render_invoice_pdf(invoice))
    rendered_text = b" ".join(re.findall(rb"\((.*?)\) Tj", content))
    assert (
        b"Istorijski podaci izdavaoca nisu sacuvani za ovu fakturu."
        in rendered_text
    )
    assert b"Test Issuer SP" not in content


def test_pdf_preserves_buyer_discount_vat_and_authoritative_totals() -> None:
    content = _pdf_text(render_invoice_pdf(_invoice()))
    for header in (b"#", b"Opis", b"Kol.", b"Cijena", b"Popust", b"PDV", b"Ukupno"):
        assert b"(" + header + b") Tj" in content
    assert b"(JM) Tj" not in content
    assert b"(kom) Tj" not in content
    assert b"Business Buyer" in content
    assert b"JIB/PIB: 4401111111111" in content
    assert b"Test service" in content
    assert b"2.00" in content
    assert b"10.00" in content
    assert b"5.00%" in content
    assert b"17.00%" in content
    assert b"22.23" in content
    assert b"Osnovica: 19.00 KM" in content
    assert b"Ukupan PDV: 3.23 KM" in content
    assert b"Ukupno: 22.23 KM" in content

    individual = render_invoice_pdf(
        _invoice(buyer_type="INDIVIDUAL", buyer_tax_id=None)
    )
    assert b"Business Buyer" in individual
    assert b"JIB/PIB: 4401111111111" not in individual


@pytest.mark.parametrize(
    ("image_format", "content_type", "filename"),
    [
        ("PNG", "image/png", "logo.png"),
        ("JPEG", "image/jpeg", "logo.jpg"),
        ("WEBP", "image/webp", "logo.webp"),
    ],
)
def test_pdf_embeds_supported_current_tenant_logo(
    isolated_logo_storage: Path,
    image_format: str,
    content_type: str,
    filename: str,
) -> None:
    headers = _headers(f"pdf-logo-{image_format.lower()}")
    created = _create_invoice(headers)
    upload = client.post(
        "/settings/profile/logo",
        headers=headers,
        files={"file": (filename, _image_bytes(image_format), content_type)},
    )
    assert upload.status_code == 201, upload.text
    pdf = client.get(f"/invoices/{created['id']}/pdf", headers=headers)
    assert pdf.status_code == 200
    assert b"/Subtype /Image" in pdf.content
    assert b"/Im1 Do" in pdf.content


def test_transparent_png_is_flattened_on_white() -> None:
    logo = _image_bytes("PNG", size=(10, 10), color=(255, 0, 0, 0))
    pdf = render_invoice_pdf(_invoice(), logo_bytes=logo)
    normalized = Image.open(BytesIO(_image_stream(pdf))).convert("RGB")
    pixel = normalized.getpixel((5, 5))
    assert all(channel >= 245 for channel in pixel)


def test_logo_absence_corruption_and_oversized_dimensions_are_non_fatal() -> None:
    plain = render_invoice_pdf(_invoice(), logo_bytes=None)
    corrupt = render_invoice_pdf(_invoice(), logo_bytes=b"not-an-image")
    oversized = render_invoice_pdf(
        _invoice(), logo_bytes=_image_bytes("PNG", size=(4097, 1))
    )
    for pdf in (plain, corrupt, oversized):
        assert pdf.startswith(b"%PDF-1.4")
        assert b"/Subtype /Image" not in pdf
        assert b"Faktura br:" in pdf


def test_logo_aspect_ratio_and_small_logo_are_not_stretched_or_upscaled() -> None:
    wide = render_invoice_pdf(
        _invoice(), logo_bytes=_image_bytes("PNG", size=(300, 30))
    )
    tall = render_invoice_pdf(
        _invoice(), logo_bytes=_image_bytes("PNG", size=(30, 300))
    )
    small = render_invoice_pdf(
        _invoice(), logo_bytes=_image_bytes("PNG", size=(20, 10))
    )
    assert re.search(rb"q 150\.00 0 0 15\.00 .* /Im1 Do Q", wide)
    assert re.search(rb"q 7\.00 0 0 70\.00 .* /Im1 Do Q", tall)
    assert re.search(rb"q 20\.00 0 0 10\.00 .* /Im1 Do Q", small)


def test_missing_and_corrupt_logo_files_do_not_break_endpoint(
    isolated_logo_storage: Path,
) -> None:
    headers = _headers("pdf-logo-file-errors")
    created = _create_invoice(headers)
    upload = client.post(
        "/settings/profile/logo",
        headers=headers,
        files={"file": ("logo.png", _image_bytes("PNG"), "image/png")},
    )
    assert upload.status_code == 201
    stored_files = list(isolated_logo_storage.rglob("*_logo.png"))
    assert len(stored_files) == 1

    stored_files[0].unlink()
    missing = client.get(f"/invoices/{created['id']}/pdf", headers=headers)
    assert missing.status_code == 200
    assert b"/Subtype /Image" not in missing.content

    stored_files[0].parent.mkdir(parents=True, exist_ok=True)
    stored_files[0].write_bytes(b"corrupt")
    corrupt = client.get(f"/invoices/{created['id']}/pdf", headers=headers)
    assert corrupt.status_code == 200
    assert b"/Subtype /Image" not in corrupt.content


def test_logo_asset_from_another_tenant_is_not_loaded(
    isolated_logo_storage: Path,
) -> None:
    owner_headers = _headers("pdf-logo-owner")
    target_headers = _headers("pdf-logo-target")
    _create_invoice(owner_headers)
    target_invoice = _create_invoice(target_headers)
    upload = client.post(
        "/settings/profile/logo",
        headers=owner_headers,
        files={"file": ("logo.png", _image_bytes("PNG"), "image/png")},
    )
    assert upload.status_code == 201

    with _db_session_for_test() as db:
        profile = db.query(TenantProfileSettings).filter_by(
            tenant_code=target_headers["X-Tenant-Code"]
        ).one()
        profile.logo_asset_id = upload.json()["logo_asset_id"]
        db.commit()

    pdf = client.get(
        f"/invoices/{target_invoice['id']}/pdf", headers=target_headers
    )
    assert pdf.status_code == 200
    assert b"/Subtype /Image" not in pdf.content


def test_changing_and_removing_logo_changes_old_invoice_pdf(
    isolated_logo_storage: Path,
) -> None:
    headers = _headers("pdf-logo-current")
    created = _create_invoice(headers)

    first_upload = client.post(
        "/settings/profile/logo",
        headers=headers,
        files={
            "file": (
                "logo.png",
                _image_bytes("PNG", color=(255, 0, 0, 255)),
                "image/png",
            )
        },
    )
    assert first_upload.status_code == 201
    first_pdf = client.get(f"/invoices/{created['id']}/pdf", headers=headers).content

    second_upload = client.post(
        "/settings/profile/logo",
        headers=headers,
        files={
            "file": (
                "logo.png",
                _image_bytes("PNG", color=(0, 0, 255, 255)),
                "image/png",
            )
        },
    )
    assert second_upload.status_code == 201
    second_pdf = client.get(f"/invoices/{created['id']}/pdf", headers=headers).content
    assert first_pdf != second_pdf
    assert b"/Subtype /Image" in second_pdf

    deleted = client.delete("/settings/profile/logo", headers=headers)
    assert deleted.status_code == 204
    without_logo = client.get(
        f"/invoices/{created['id']}/pdf", headers=headers
    )
    assert without_logo.status_code == 200
    assert b"/Subtype /Image" not in without_logo.content


def test_long_values_wrap_and_many_items_paginate_with_repeated_headers() -> None:
    long_token = "X" * 180
    items = [
        _item(f"Long service description {index} {long_token}")
        for index in range(45)
    ]
    pdf = render_invoice_pdf(
        _invoice(
            issuer_business_name=f"Historical issuer {long_token}",
            issuer_address=f"Long address {long_token}",
            issuer_email=f"{long_token}@example.test",
            issuer_bank_account=long_token,
            issuer_iban=long_token,
            items=items,
        )
    )
    count_match = re.search(rb"/Type /Pages /Kids \[.*?\] /Count (\d+)", pdf)
    assert count_match is not None
    page_count = int(count_match.group(1))
    assert page_count >= 2
    assert pdf.count(b"(Opis) Tj") >= 2
    assert b"Strana 1 / " + str(page_count).encode() in pdf
    assert (
        f"Strana {page_count} / {page_count}".encode("ascii")
        in pdf
    )
    assert b"Ukupno: 22.23 KM" in pdf


@pytest.mark.parametrize(
    ("invoice_number", "expected_component"),
    [
        ("PDF/INV\\01", "PDF_INV_01"),
        ('PDF"INV-02', "PDF_INV-02"),
        ("PDF\r\nINV-03", "PDF_INV-03"),
        ("Ž-račun-04", "ra_un-04"),
    ],
)
def test_invoice_pdf_sanitizes_content_disposition_filename(
    invoice_number: str,
    expected_component: str,
) -> None:
    headers = _headers("pdf-safe-filename")
    created = _create_invoice(
        headers,
        invoice_number=invoice_number,
    )

    response = client.get(
        f"/invoices/{created['id']}/pdf",
        headers=headers,
    )

    assert response.status_code == 200
    content_disposition = response.headers["content-disposition"]
    assert content_disposition == (
        f'inline; filename="invoice-{expected_component}.pdf"'
    )
    filename_match = re.fullmatch(
        r'inline; filename="([A-Za-z0-9._-]+)"',
        content_disposition,
    )
    assert filename_match is not None
    filename = filename_match.group(1)
    assert "\r" not in filename
    assert "\n" not in filename
    assert '"' not in filename
    assert "/" not in filename
    assert "\\" not in filename


def test_invoice_pdf_filename_component_is_limited_and_has_id_fallback() -> None:
    long_component = invoice_routes._safe_invoice_filename_component(
        "A" * 100,
        123,
    )
    assert long_component == "A" * 80
    assert len(long_component) == 80

    for unusable in (None, "", "._- ", "Žčć"):
        assert (
            invoice_routes._safe_invoice_filename_component(unusable, 123)
            == "123"
        )


def test_invoice_pdf_filename_sanitization_does_not_change_pdf_number() -> None:
    headers = _headers("pdf-original-number")
    invoice_number = f"ORIG/{uuid4().hex[:8]}"
    created = _create_invoice(
        headers,
        invoice_number=invoice_number,
    )

    response = client.get(
        f"/invoices/{created['id']}/pdf",
        headers=headers,
    )

    assert response.status_code == 200
    assert invoice_number.encode("ascii") in _pdf_text(response.content)
    assert (
        f'inline; filename="invoice-{invoice_number.replace("/", "_")}.pdf"'
        == response.headers["content-disposition"]
    )

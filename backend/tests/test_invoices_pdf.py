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
from pypdf import PdfReader

from app.main import app
from app.db import get_session as _get_session_dep
from app.models import Invoice, TenantAsset, TenantProfileSettings
from app.routes import invoices as invoice_routes
from app.routes import settings as settings_routes
from app.services.pdf_invoice import (
    LEGACY_ISSUER_MESSAGE,
    UnsupportedPdfGlyphError,
    render_invoice_pdf,
)
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
    assert pdf_resp.content.startswith(b"%PDF-1.4")
    content = _pdf_text(pdf_resp.content)
    # Provjerimo da se unutar PDF-a nalaze osnovni podaci iz fakture
    assert "Faktura br:" in content
    assert invoice_number in content
    assert f"Tenant: {tenant_code}" not in content
    assert "Osnovica:" in content
    assert "Ukupno:" in content


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
        "note": None,
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


def _pdf_reader(pdf: bytes) -> PdfReader:
    return PdfReader(BytesIO(pdf))


def _pdf_text(pdf: bytes) -> str:
    return "\n".join(page.extract_text() or "" for page in _pdf_reader(pdf).pages)


def _image_stream(pdf: bytes) -> bytes:
    images = [
        image.data
        for page in _pdf_reader(pdf).pages
        for image in page.images
    ]
    assert len(images) == 1
    return images[0]


def _page_commands(pdf: bytes) -> bytes:
    return b"\n".join(
        page.get_contents().get_data() for page in _pdf_reader(pdf).pages
    )


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
        "Historical Issuer SP",
        "Historical address 10",
        "JIB / PIB: 4402222222222",
        "Telefon: +387 51 111 222",
        "Email: office@historical.example",
        "Banka: Historical Bank",
        "Racun: 555-111-222",
        "IBAN: BA391290079401028494",
        "SWIFT/BIC: HISTBA22",
    ):
        assert value in content
    for forbidden in (
        "SP APP - DEMO LOGO",
        "SP Primjer - demo korisnik",
        "0000000000000",
        "Demo Banka",
        "DEMOBA22",
        "Tenant:",
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
    assert "Historical Issuer SP" in content
    assert "JIB / PIB: 4402222222222" in content
    assert "Telefon:" not in content
    assert "Email:" not in content
    assert "Instrukcije za uplatu" not in content


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
    normalized_content = " ".join(content.split())
    assert LEGACY_ISSUER_MESSAGE in normalized_content
    assert "Test Issuer SP" not in normalized_content


def test_pdf_preserves_buyer_discount_vat_and_authoritative_totals() -> None:
    content = _pdf_text(render_invoice_pdf(_invoice()))
    for header in ("#", "Opis", "Kol.", "Cijena", "Popust", "PDV", "Ukupno"):
        assert header in content
    assert "JM" not in content
    assert "kom" not in content
    assert "Business Buyer" in content
    assert "JIB/PIB: 4401111111111" in content
    assert "Test service" in content
    assert "2.00" in content
    assert "10.00" in content
    assert "5.00%" in content
    assert "17.00%" in content
    assert "22.23" in content
    assert "Osnovica: 19.00 KM" in content
    assert "Ukupan PDV: 3.23 KM" in content
    assert "Ukupno: 22.23 KM" in content

    individual = render_invoice_pdf(
        _invoice(buyer_type="INDIVIDUAL", buyer_tax_id=None)
    )
    individual_text = _pdf_text(individual)
    assert "Business Buyer" in individual_text
    assert "JIB/PIB: 4401111111111" not in individual_text


def test_pdf_preserves_unicode_and_embeds_searchable_noto_fonts() -> None:
    pdf = render_invoice_pdf(
        _invoice(
            buyer_name="Kupac / Купац / čćšđž ČĆŠĐŽ",
            buyer_address="Бања Лука",
            issuer_business_name="Историјски издавалац čćšđž",
            issuer_address="Адреса издаваоца",
            items=[_item("Услуга / Stavka čćšđž")],
        )
    )
    text = _pdf_text(pdf)
    for value in (
        "Kupac / Купац / čćšđž ČĆŠĐŽ",
        "Бања Лука",
        "Историјски издавалац čćšđž",
        "Адреса издаваоца",
        "Услуга / Stavka čćšđž",
    ):
        assert value in text
    assert "?" not in text

    fonts = _pdf_reader(pdf).pages[0]["/Resources"]["/Font"]
    noto_fonts = [
        reference.get_object()
        for reference in fonts.values()
        if "NotoSans" in str(reference.get_object().get("/BaseFont", ""))
    ]
    assert len(noto_fonts) == 2
    assert all("/ToUnicode" in font for font in noto_fonts)
    assert all(
        "/FontFile2" in font["/FontDescriptor"].get_object()
        for font in noto_fonts
    )


def test_pdf_renders_short_note() -> None:
    note = "Roba ostaje vlasništvo prodavca do potpune uplate."
    pdf = render_invoice_pdf(_invoice(note=note))
    text = _pdf_text(pdf)

    assert len(_pdf_reader(pdf).pages) == 1
    assert "Napomena" in text
    assert note in text


def test_pdf_renders_searchable_unicode_note() -> None:
    note = "Mišo čćšđž ČĆŠĐŽ - Напомена за купца"
    text = _pdf_text(render_invoice_pdf(_invoice(note=note)))

    assert "Napomena" in text
    assert note in text
    assert "?" not in text


@pytest.mark.parametrize("note", [None, "", "   \n\t  "])
def test_pdf_omits_empty_note_section(note: str | None) -> None:
    text = _pdf_text(render_invoice_pdf(_invoice(note=note)))

    assert "Napomena" not in text


def test_unsupported_note_emoji_is_controlled_for_service_and_endpoint() -> None:
    with pytest.raises(UnsupportedPdfGlyphError):
        render_invoice_pdf(_invoice(note="Napomena samo sa emoji znakom 😀"))

    headers = _headers("pdf-unsupported-glyph")
    created = _create_invoice(headers, note="Napomena samo sa emoji znakom 😀")
    response = client.get(f"/invoices/{created['id']}/pdf", headers=headers)
    assert response.status_code == 422
    assert response.json() == {
        "detail": (
            "Invoice PDF cannot be generated because the document contains "
            "characters unsupported by the PDF font"
        )
    }


def test_long_unicode_note_paginates_after_invoice_content_with_logo() -> None:
    paragraphs = [
        f"Pasus {index}: "
        + (
            "Дуга напомена за купца i računovodstvene "
            "informacije čćšđž koje moraju ostati kompletne i čitljive. "
        )
        * 5
        for index in range(1, 16)
    ]
    note = "\n\n".join(paragraphs)
    items = [
        _item(f"Unicode service {index}: Рачуноводствена услуга čćšđž")
        for index in range(45)
    ]
    pdf = render_invoice_pdf(
        _invoice(note=note, items=items),
        logo_bytes=_image_bytes("PNG", color=(20, 100, 180, 120)),
    )
    reader = _pdf_reader(pdf)
    text = _pdf_text(pdf)
    normalized = " ".join(text.split())
    semantic_text = re.sub(r"Strana \d+ / \d+", " ", normalized)
    semantic_text = semantic_text.replace(
        "Faktura br: UNIT-PDF-1 nastavak", " "
    )
    semantic_text = " ".join(semantic_text.split())
    expected_note = " ".join(note.split())

    assert len(reader.pages) >= 3
    assert expected_note in semantic_text
    marker_positions = []
    for index, paragraph in enumerate(paragraphs, start=1):
        normalized_paragraph = " ".join(paragraph.split())
        marker = f"Pasus {index}:"
        assert semantic_text.count(normalized_paragraph) == 1
        assert semantic_text.count(marker) == 1
        marker_positions.append(semantic_text.index(marker))
    assert marker_positions == sorted(marker_positions)
    assert expected_note.startswith("Pasus 1: Дуга напомена за купца")
    assert expected_note.endswith("moraju ostati kompletne i čitljive.")
    assert "računovodstvene" in expected_note
    assert "čćšđž" in expected_note
    assert "?" not in semantic_text
    assert text.count("Napomena") == 1
    assert text.count("Osnovica: 19.00 KM") == 1
    assert text.count("Ukupan PDV: 3.23 KM") == 1
    assert text.count("Ukupno: 22.23 KM") == 1
    assert "Instrukcije za uplatu" in text
    assert text.index("Ukupno: 22.23 KM") < text.index("Napomena")
    assert text.count("Opis") >= 2
    assert b"/Subtype /Image" in pdf
    assert f"Strana 1 / {len(reader.pages)}" in text
    assert f"Strana {len(reader.pages)} / {len(reader.pages)}" in text
    assert all((page.extract_text() or "").strip() for page in reader.pages)


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
        assert "Faktura br:" in _pdf_text(pdf)


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
    assert re.search(
        rb"150(?:\.0+)? 0 0 15(?:\.0+)? .*? cm\s*/\S+ Do",
        _page_commands(wide),
        re.DOTALL,
    )
    assert re.search(rb"7(?:\.0+)? 0 0 70(?:\.0+)? .*? cm\s*/\S+ Do", _page_commands(tall), re.DOTALL)
    assert re.search(rb"20(?:\.0+)? 0 0 10(?:\.0+)? .*? cm\s*/\S+ Do", _page_commands(small), re.DOTALL)


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
    reader = _pdf_reader(pdf)
    page_count = len(reader.pages)
    text = _pdf_text(pdf)
    assert page_count >= 2
    assert text.count("Opis") >= 2
    assert f"Strana 1 / {page_count}" in text
    assert f"Strana {page_count} / {page_count}" in text
    assert "Ukupno: 22.23 KM" in text


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
    assert invoice_number in _pdf_text(response.content)
    assert (
        f'inline; filename="invoice-{invoice_number.replace("/", "_")}.pdf"'
        == response.headers["content-disposition"]
    )

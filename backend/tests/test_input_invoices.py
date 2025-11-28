from __future__ import annotations

from typing import Dict, Any, List

import pytest
from fastapi.testclient import TestClient

from app.main import app


@pytest.fixture
def client() -> TestClient:
    """
    Jednostavan TestClient fixture za pozivanje API-ja u ovim testovima.
    """
    return TestClient(app)


def _make_payload(overrides: Dict[str, Any] | None = None) -> Dict[str, Any]:
    """
    Helper za kreiranje osnovnog payload-a za ulaznu fakturu.
    """
    data: Dict[str, Any] = {
        "supplier_name": "Elektrodistribucija Banja Luka",
        "supplier_tax_id": "1234567890000",
        "supplier_address": "Kralja Petra I Karađorđevića 15, Banja Luka",
        "invoice_number": "2025-INV-001",
        "issue_date": "2025-11-01",
        "due_date": "2025-11-15",
        "total_base": "100.00",
        "total_vat": "17.00",
        "total_amount": "117.00",
        "currency": "BAM",
        "note": "Račun za električnu energiju za oktobar.",
    }
    if overrides:
        data.update(overrides)
    return data


def _create_input_invoice(
    client: TestClient,
    tenant_code: str,
    overrides: Dict[str, Any] | None = None,
):
    """
    Helper koji preko API-ja kreira jednu ulaznu fakturu i vraća (status_code, json).
    """
    payload = _make_payload(overrides)
    resp = client.post(
        "/input-invoices",
        json=payload,
        headers={"X-Tenant-Code": tenant_code},
    )
    return resp.status_code, resp.json()


def _list_input_invoices(
    client: TestClient,
    tenant_code: str,
) -> List[Dict[str, Any]]:
    """
    Helper koji vraća sve ulazne fakture za datog tenanta.
    """
    resp = client.get(
        "/input-invoices",
        headers={"X-Tenant-Code": tenant_code},
    )
    assert resp.status_code == 200
    return resp.json()


def _find_invoice_id_in_list(
    rows: List[Dict[str, Any]],
    supplier_name: str,
    invoice_number: str,
) -> int | None:
    """
    Pokušava da pronađe id ulazne fakture u listi na osnovu
    supplier_name + invoice_number kombinacije.
    """
    for row in rows:
        if (
            row.get("supplier_name") == supplier_name
            and row.get("invoice_number") == invoice_number
        ):
            return row.get("id")
    return None


# ======================================================
#  CREATE
# ======================================================


def test_create_input_invoice_ok(client: TestClient) -> None:
    """
    Happy-path: kreiranje nove ulazne fakture za tenanta.

    Na svježoj bazi očekuje se 201.
    Ako ista kombinacija već postoji iz prethodnih test run-ova,
    dobićemo 409 – u tom slučaju samo provjeravamo da API radi i da
    poruka ima smisla (da ne pucamo zbog stare baze).
    """
    status_code, body = _create_input_invoice(client, tenant_code="t-input-1")

    assert status_code in (201, 409)

    if status_code == 201:
        # Svježa kreacija – provjeravamo kompletan odgovor
        assert body["tenant_code"] == "t-input-1"
        assert body["supplier_name"] == "Elektrodistribucija Banja Luka"
        assert body["invoice_number"] == "2025-INV-001"
        assert body["total_base"] == "100.00"
        assert body["total_vat"] == "17.00"
        assert body["total_amount"] == "117.00"
        assert body["currency"] == "BAM"
        assert isinstance(body["id"], int)
        assert isinstance(body["created_at"], str)
    else:
        # 409 – zapis već postoji, bitno je da poruka odgovara očekivanom conflict case-u
        assert body["detail"] == "Input invoice already exists for this supplier and tenant"


def test_create_input_invoice_missing_tenant_header(client: TestClient) -> None:
    """
    Ako nedostaje X-Tenant-Code header, očekujemo 400 i poruku iz shared helper-a.
    """
    resp = client.post("/input-invoices", json=_make_payload())

    assert resp.status_code == 400
    # poruka dolazi iz require_tenant_code helper-a
    assert resp.json()["detail"] == "Missing X-Tenant-Code header"


def test_create_input_invoice_duplicate_for_same_supplier_and_tenant(
    client: TestClient,
) -> None:
    """
    Duplikat kombinacije (tenant_code, supplier_name, invoice_number)
    treba da vrati 409 konflikt.

    Ako red već postoji u bazi od ranije, i prvi poziv može vratiti 409 –
    ono što je ključno jeste da je nemoguće napraviti DRUGI zapis sa
    istom kombinacijom.
    """
    tenant = "t-input-dup"

    # Prvi poziv – na svježoj bazi 201, na prljavoj može i 409
    status_code_1, _ = _create_input_invoice(client, tenant_code=tenant)
    assert status_code_1 in (201, 409)

    # Drugi poziv sa istim supplier_name + invoice_number → 409 je OBAVEZAN
    status_code_2, body_2 = _create_input_invoice(client, tenant_code=tenant)
    assert status_code_2 == 409
    assert body_2["detail"] == "Input invoice already exists for this supplier and tenant"


# ======================================================
#  LIST
# ======================================================


def test_list_input_invoices_with_filters(client: TestClient) -> None:
    """
    Kreiramo više ulaznih faktura za različite tenant-e i provjeravamo:
    - da list vraća samo fakture za traženi tenant,
    - da supplier_name prefiks filter radi kako treba.
    """
    # Za ovog tenanta kreiramo 2 fakture sa različitim dobavljačima
    tenant_a = "t-input-list-a"
    _create_input_invoice(
        client,
        tenant_code=tenant_a,
        overrides={"supplier_name": "Elektrodistribucija Banja Luka"},
    )
    _create_input_invoice(
        client,
        tenant_code=tenant_a,
        overrides={
            "supplier_name": "Elektro Servis DOO",
            "invoice_number": "2025-INV-002",
        },
    )

    # Za drugog tenanta kreiramo jednu fakturu koju ne smijemo vidjeti u listi za tenant_a
    tenant_b = "t-input-list-b"
    _create_input_invoice(
        client,
        tenant_code=tenant_b,
        overrides={
            "supplier_name": "Elektrodistribucija Banja Luka",
            "invoice_number": "2025-INV-003",
        },
    )

    # Lista za tenant_a bez filtera
    resp_all = client.get(
        "/input-invoices",
        headers={"X-Tenant-Code": tenant_a},
    )
    assert resp_all.status_code == 200
    data_all = resp_all.json()
    # Možda već ima starih podataka, pa provjeravamo "barem 2" za ovog tenanta
    assert len([row for row in data_all if row["tenant_code"] == tenant_a]) >= 2
    tenant_codes = {row["tenant_code"] for row in data_all}
    # U svakom slučaju svi vraćeni moraju biti za tenant_a
    assert tenant_codes == {tenant_a}

    # Lista za tenant_a sa supplier_name prefiks filterom "Elektrodistribucija"
    resp_filtered = client.get(
        "/input-invoices",
        headers={"X-Tenant-Code": tenant_a},
        params={"supplier_name": "Elektrodistribucija"},
    )
    assert resp_filtered.status_code == 200
    data_filtered = resp_filtered.json()
    # bar jedna faktura treba da se vrati i da ispunjava uslov
    assert len(data_filtered) >= 1
    for row in data_filtered:
        assert row["supplier_name"].startswith("Elektrodistribucija")
        assert row["tenant_code"] == tenant_a


# ======================================================
#  GET BY ID
# ======================================================


def test_get_input_invoice_by_id_ok(client: TestClient) -> None:
    """
    Happy-path za GET /input-invoices/{id}.

    Ako kreiranje vrati 201 – koristimo ID iz odgovora.
    Ako kreiranje vrati 409 (zapis već postoji), pronalazimo odgovarajući ID
    preko liste ulaznih faktura za tog tenanta.
    """
    tenant = "t-input-get-ok"
    supplier_name = "Elektrodistribucija Banja Luka"
    invoice_number = "2025-INV-001"

    status_code, body = _create_input_invoice(client, tenant_code=tenant)
    assert status_code in (201, 409)

    if status_code == 201:
        invoice_id = body["id"]
    else:
        # već postoji – pronađi ID u listi
        rows = _list_input_invoices(client, tenant_code=tenant)
        invoice_id = _find_invoice_id_in_list(rows, supplier_name, invoice_number)
        assert invoice_id is not None

    resp = client.get(
        f"/input-invoices/{invoice_id}",
        headers={"X-Tenant-Code": tenant},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["id"] == invoice_id
    assert data["tenant_code"] == tenant
    assert data["invoice_number"] == invoice_number
    assert data["supplier_name"] == supplier_name


def test_get_input_invoice_by_id_not_found_for_other_tenant(
    client: TestClient,
) -> None:
    """
    Ako pokušamo da dohvatimo ulaznu fakturu sa drugim tenant-om,
    očekujemo 404 (iz sigurnosnih i izolacionih razloga).

    Ako kreiranje vrati 409 (zapis već postoji), ID pronalazimo iz liste.
    """
    tenant_owner = "t-input-owner"
    other_tenant = "t-input-other"
    supplier_name = "Elektrodistribucija Banja Luka"
    invoice_number = "2025-INV-001"

    status_code, body = _create_input_invoice(client, tenant_code=tenant_owner)
    assert status_code in (201, 409)

    if status_code == 201:
        invoice_id = body["id"]
    else:
        rows = _list_input_invoices(client, tenant_code=tenant_owner)
        invoice_id = _find_invoice_id_in_list(rows, supplier_name, invoice_number)
        assert invoice_id is not None

    resp = client.get(
        f"/input-invoices/{invoice_id}",
        headers={"X-Tenant-Code": other_tenant},
    )
    assert resp.status_code == 404
    assert resp.json()["detail"] == "Input invoice not found"

from __future__ import annotations

from typing import Any

import httpx
from fastapi.testclient import TestClient


COMPLETE_PROFILE = {
    "business_name": "Test Issuer SP",
    "address": "Test address 1",
    "tax_id": "4400000000000",
    "phone": "+387 51 000 000",
    "email": "issuer@example.ba",
    "bank_name": "Test Bank",
    "bank_account": "555-000-111",
    "iban": "BA391290079401028494",
    "swift_bic": "TESTBA22",
}


def save_complete_profile(
    client: TestClient,
    headers: dict[str, str],
    **overrides: Any,
) -> dict:
    payload = {**COMPLETE_PROFILE, **overrides}
    response = client.put("/settings/profile", headers=headers, json=payload)
    assert response.status_code == 200, response.text
    return response.json()


def save_complete_profile_http(
    base_url: str,
    headers: dict[str, str],
) -> dict:
    response = httpx.put(
        f"{base_url}/settings/profile", headers=headers, json=COMPLETE_PROFILE, timeout=5
    )
    assert response.status_code == 200, response.text
    return response.json()

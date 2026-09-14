from fastapi.testclient import TestClient


def set_recognition_test_tax_rates(client: TestClient, headers: dict[str, str]) -> None:
    """Configure explicit rates for aggregation/snapshot tests, without fallback."""
    response = client.put(
        "/tax/settings",
        headers=headers,
        json={
            "income_tax_rate": "0.10",
            "pension_contribution_rate": "0.18",
            "health_contribution_rate": "0.12",
            "unemployment_contribution_rate": "0.015",
            "flat_costs_rate": "0.30",
            "currency": "BAM",
        },
    )
    assert response.status_code == 200, response.text

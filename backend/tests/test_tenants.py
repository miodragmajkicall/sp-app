import pytest

pytestmark = pytest.mark.skip(reason="Tenants API nije još implementiran; test će biti uključen kada dodamo /tenants CRUD.")

def test_tenants_crud_flow():
    assert True

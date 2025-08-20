import httpx
import time

BASE_URL = "http://localhost:8000"

def test_health_ok():
    # Probaj /db/health (budući endpoint), pa /health (trenutni)
    last_status = None
    for path in ("/db/health", "/health"):
        try:
            r = httpx.get(f"{BASE_URL}{path}", timeout=5)
        except Exception:
            time.sleep(0.5)
            r = httpx.get(f"{BASE_URL}{path}", timeout=5)
        last_status = r.status_code
        if r.status_code == 200:
            break
    assert last_status == 200, f"Neither /db/health nor /health returned 200, last was {last_status}"

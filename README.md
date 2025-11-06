# sp-app

Minimalni FastAPI + SQLAlchemy servis sa **multi-tenant** keš knjigom (cashbook).
Docker Compose podiže API i Postgres. Endpointi su stabilni i dokumentovani u nastavku.

- OpenAPI/Swagger: `http://localhost:8000/docs`
- Health: `GET /health` → `{"status":"ok"}`

> **Tenant obavezno**: svaki poziv ka `cash` endpoinitma mora imati header  
> `X-Tenant-Code: <tenant>` (npr. `t-demo`).

---

## Quick start (lokalno)

```bash
# iz root-a projekta
docker compose down
docker compose up -d

# provjere
curl -sS http://localhost:8000/health | jq .

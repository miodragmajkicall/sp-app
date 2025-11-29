<!-- /home/miso/dev/sp-app/sp-app/backend/docs/api-reference-v1.md -->

# SP-APP API – V1 Reference

Ovaj dokument je **developer-friendly** pregled SP-APP backenda (V1 jezgro), da frontend lako zna šta postoji i kako otprilike izgleda.

> 🔎 Za punu mašinsku šemu uvijek postoji:
> - Swagger UI: `/docs`
> - OpenAPI JSON: `/openapi.json`


---

## 1. Osnovne konvencije

### 1.1. Base URL

- U lokalnom docker okruženju:
  - `http://localhost:8000` (ili kako je već mapirano u `docker-compose.yml`)
- Svi endpointi iz ovog dokumenta počinju od tog base URL-a.

---

### 1.2. X-Tenant-Code header (obavezno)

Skoro svi “business” endpointi rade **po tenantu** i traže header:

- `X-Tenant-Code: t-demo`  
  ili npr. `X-Tenant-Code: frizer-mika`

Ako header nedostaje, backend vraća:

```json
HTTP 400
{"detail": "Missing X-Tenant-Code header"}

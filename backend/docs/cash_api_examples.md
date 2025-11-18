# sp-app – Cash API cURL primjeri

Ovaj dokument daje praktične cURL primjere za rad sa `/cash` modulom u sp-app API-ju.

> **NAPOMENA:**  
> Sve rute zahtijevaju header `X-Tenant-Code`, kojim se identifikuje tenant (npr. `t-demo`).
> Backend po defaultu radi na `http://localhost:8000`.

---

## 1. Health check (provjera da API radi)

```bash
curl -sS http://localhost:8000/health

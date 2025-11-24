from sqlalchemy import select
from app.db import SessionLocal
from app.models import Tenant

DATA = [
    {"code": "acme",  "name": "ACME d.o.o."},
    {"code": "beta",  "name": "Beta d.o.o."},
    {"code": "gamma", "name": "Gamma d.o.o."},
]

def run() -> None:
    created = 0
    with SessionLocal() as db:
        for row in DATA:
            exists = db.execute(
                select(Tenant).where(Tenant.code == row["code"])
            ).scalar_one_or_none()
            if exists:
                continue
            db.add(Tenant(**row))
            created += 1
        db.commit()
    print(f"seed done, created={created}")

if __name__ == "__main__":
    run()

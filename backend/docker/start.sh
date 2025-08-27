#!/usr/bin/env bash
set -euo pipefail

echo "[start] waiting for DB via app.db.ping() ..."
# čekaj DB max 60s
for i in $(seq 1 60); do
  if python - <<'PY'
from app import db as dbmod
import sys
try:
    ok = getattr(dbmod, "ping", None)
    sys.exit(0 if callable(ok) and ok() else 1)
except Exception:
    sys.exit(1)
PY
  then
    echo "[start] DB is up."
    break
  fi
  sleep 1
done

echo "[start] running alembic upgrade head (if available) ..."
if [ -f ./alembic.ini ] && [ -d ./alembic ]; then
  alembic upgrade head || echo "[warn] alembic upgrade head failed; continuing to ensure tables"
else
  echo "[start] alembic not found; skipping migrations."
fi

echo "[start] verifying tables exist; creating missing ones if needed ..."
python - <<'PY'
from app.db import engine
from app import models
from sqlalchemy import inspect

insp = inspect(engine)
missing = []

# provjeri bar cash_entries; dodaj druge ako treba
if not insp.has_table("cash_entries"):
    missing.append("cash_entries")

if missing:
    print(f"[ensure] creating missing tables: {missing}")
    models.Base.metadata.create_all(bind=engine)
else:
    print("[ensure] all required tables exist")
PY

echo "[start] launching uvicorn ..."
exec uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
 
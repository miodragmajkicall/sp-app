FROM python:3.11-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Kopiramo lokalni folder "app" u image pod /app/app
COPY app ./app

# Uključimo "unbuffered" output da logovi odmah idu van
ENV PYTHONUNBUFFERED=1

# Uvicorn s reload-om (kompatibilno s dosadašnjim setupom)
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--reload"]

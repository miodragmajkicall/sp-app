# backend/Dockerfile
FROM python:3.11-slim

ENV PYTHONUNBUFFERED=1
WORKDIR /app

# 1) Depovi
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# 2) Aplikacija + Alembic
COPY app ./app
COPY alembic.ini ./alembic.ini
COPY alembic ./alembic

# 3) Start skripta
COPY docker/start.sh ./start.sh
RUN chmod +x ./start.sh

EXPOSE 8000
CMD ["./start.sh"]

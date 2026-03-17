# Site Analyzer - Fly.io
# Официальный образ Playwright с Python и Chromium
FROM mcr.microsoft.com/playwright/python:v1.49.0-jammy

# traceroute для маршрутизации
RUN apt-get update && apt-get install -y --no-install-recommends traceroute \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

ENV PORT=8080
EXPOSE 8080

CMD ["sh", "-c", "uvicorn main:app --host 0.0.0.0 --port ${PORT:-8080}"]

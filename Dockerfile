FROM node:22-alpine AS frontend-builder

WORKDIR /frontend
COPY frontend/package.json frontend/package-lock.json ./
RUN npm ci
COPY frontend/ ./
RUN npm run build

FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    PORT=8000

WORKDIR /app

COPY pyproject.toml requirements.txt README.md LICENSE ./
COPY tradingagents ./tradingagents
RUN pip install --no-cache-dir . \
 && useradd --create-home --uid 10001 appuser

COPY --chown=appuser:appuser dashboard.py ./dashboard.py
COPY --chown=appuser:appuser reports ./reports
COPY --from=frontend-builder --chown=appuser:appuser /frontend/dist ./frontend/dist

USER appuser
EXPOSE 8000

CMD ["sh", "-c", "uvicorn tradingagents.web.api:app --host 0.0.0.0 --port ${PORT:-8000}"]

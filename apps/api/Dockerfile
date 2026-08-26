# ---- Etapa 1: build del frontend (apps/web) ----
FROM node:20-slim AS build-web

WORKDIR /web
COPY apps/web/package.json apps/web/package-lock.json ./
RUN npm ci
COPY apps/web ./
RUN npm run build

# ---- Etapa 2: runtime de la API ----
FROM python:3.12-slim

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy \
    UV_PROJECT_ENVIRONMENT=/opt/venv \
    LINDERO_WEB_DIST=/app/web_dist

COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /bin/

WORKDIR /app

# Este Dockerfile se construye con el contexto en la RAÍZ del monorepo (no en
# apps/api/), igual que apps/worker/Dockerfile, porque necesita el workspace de
# uv completo (pyproject.toml + uv.lock de la raíz) y el paquete compartido
# packages/lindero_core.
COPY pyproject.toml uv.lock ./
COPY packages/lindero_core packages/lindero_core
COPY apps/api apps/api

RUN uv sync --frozen --package api

COPY --from=build-web /web/dist ./web_dist

EXPOSE 8000

CMD ["uv", "run", "--frozen", "--package", "api", "uvicorn", "api.main:app", "--host", "0.0.0.0", "--port", "8000"]

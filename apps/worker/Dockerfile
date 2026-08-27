FROM python:3.12-slim

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    CHROME_BINARY_PATH=/usr/bin/chromium \
    CHROMEDRIVER_PATH=/usr/bin/chromedriver \
    UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy \
    UV_PROJECT_ENVIRONMENT=/opt/venv

# chromium + chromium-driver vienen pareados en los repos de Debian (misma versión
# mayor garantizada), evitando el mismatch de versiones y la descarga en runtime
# que hace webdriver-manager cuando no se fijan estas rutas.
RUN apt-get update && apt-get install -y --no-install-recommends \
        chromium \
        chromium-driver \
        tzdata \
    && rm -rf /var/lib/apt/lists/*

COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /bin/

WORKDIR /app

# Este Dockerfile se construye con el contexto en la RAÍZ del monorepo (no en
# apps/worker/), porque necesita copiar el workspace de uv completo:
# pyproject.toml + uv.lock de la raíz, y el paquete compartido packages/lindero_core.
COPY pyproject.toml uv.lock ./
COPY packages/lindero_core packages/lindero_core
COPY apps/worker apps/worker
# Utilidad de setup (obtener el Chat ID de Telegram); no es parte del paquete
# worker, pero reutiliza sus dependencias (requests, python-dotenv) para poder
# correrla con `docker compose run --rm worker python get_chat_id.py`.
COPY get_chat_id.py .

RUN uv sync --frozen --package worker

CMD ["uv", "run", "--frozen", "--package", "worker", "python", "-m", "worker.scheduler"]

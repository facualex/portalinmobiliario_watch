# -*- coding: utf-8 -*-
"""API de Lindero: administra propiedades vigiladas y a qué chats de Telegram
notifican. Sin autenticación: corre localmente, self-hosted, un solo operador."""

import os
from contextlib import asynccontextmanager
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()

from fastapi import FastAPI  # noqa: E402
from fastapi.responses import FileResponse  # noqa: E402
from lindero_core.db import crear_tablas  # noqa: E402

from api.routers import chats_telegram, propiedades  # noqa: E402


@asynccontextmanager
async def lifespan(app: FastAPI):
    crear_tablas()
    yield


app = FastAPI(title="Lindero API", lifespan=lifespan)

app.include_router(propiedades.router, prefix="/api")
app.include_router(chats_telegram.router, prefix="/api")


@app.get("/api/salud")
def salud():
    return {"estado": "ok"}


# Sirve el build de apps/web (React), si existe. En desarrollo local no existe
# (se usa `vite dev` en el puerto 5173 en su lugar), así que esta ruta comodín
# solo se registra dentro del contenedor Docker, donde sí se buildeó.
WEB_DIST = Path(os.getenv("LINDERO_WEB_DIST", "web_dist"))

if WEB_DIST.is_dir():

    @app.get("/{ruta_completa:path}")
    async def servir_frontend(ruta_completa: str):
        candidato = WEB_DIST / ruta_completa
        if candidato.is_file():
            return FileResponse(candidato)
        # Cualquier otra ruta (ej. /configuracion) es una ruta de React Router,
        # no un archivo: le devolvemos el index.html y el router del cliente
        # la resuelve en el navegador.
        return FileResponse(WEB_DIST / "index.html")

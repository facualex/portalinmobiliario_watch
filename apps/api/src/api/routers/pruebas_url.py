# -*- coding: utf-8 -*-
"""Prueba rápida de una URL (antes de conectarla como propiedad, o al editarla).

No scrapea en este proceso: la API no tiene Chromium instalado a propósito
(imagen liviana). En su lugar, encola la prueba y el worker la procesa en su
próximo tick, igual que a cualquier propiedad vencida; el cliente sondea el
resultado (ver GET /{prueba_id})."""

from fastapi import APIRouter, Depends, HTTPException
from lindero_core import repository
from lindero_core.models import PruebaUrl, PruebaUrlCrear
from sqlmodel import Session

from api.deps import obtener_sesion_db

router = APIRouter(prefix="/pruebas-url", tags=["pruebas-url"])


@router.post("", response_model=PruebaUrl, status_code=202)
def crear(payload: PruebaUrlCrear, sesion: Session = Depends(obtener_sesion_db)):
    return repository.crear_prueba_url(sesion, url=payload.url)


@router.get("/{prueba_id}", response_model=PruebaUrl)
def obtener(prueba_id: int, sesion: Session = Depends(obtener_sesion_db)):
    prueba = repository.obtener_prueba_url(sesion, prueba_id)
    if prueba is None:
        raise HTTPException(404, "Prueba no encontrada")
    return prueba

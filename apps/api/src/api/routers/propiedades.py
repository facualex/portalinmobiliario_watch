# -*- coding: utf-8 -*-
"""Endpoints de administración de propiedades vigiladas."""

import os
from typing import List

from fastapi import APIRouter, Depends, HTTPException
from lindero_core import repository
from lindero_core.models import (
    FrecuenciaTipo,
    Propiedad,
    PropiedadActualizar,
    PropiedadCrear,
)
from lindero_core.telegram import enviar_notificacion_telegram
from sqlmodel import Session

from api.deps import obtener_sesion_db

router = APIRouter(prefix="/propiedades", tags=["propiedades"])

BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")


@router.get("", response_model=List[Propiedad])
def listar(sesion: Session = Depends(obtener_sesion_db)):
    return repository.listar_propiedades(sesion)


@router.post("", response_model=Propiedad, status_code=201)
def crear(payload: PropiedadCrear, sesion: Session = Depends(obtener_sesion_db)):
    if repository.obtener_chat_telegram(sesion, payload.chat_telegram_id) is None:
        raise HTTPException(404, "El chat de Telegram indicado no existe")
    return repository.crear_propiedad(sesion, **payload.model_dump())


@router.get("/{propiedad_id}", response_model=Propiedad)
def obtener(propiedad_id: int, sesion: Session = Depends(obtener_sesion_db)):
    propiedad = repository.obtener_propiedad(sesion, propiedad_id)
    if propiedad is None:
        raise HTTPException(404, "Propiedad no encontrada")
    return propiedad


@router.patch("/{propiedad_id}", response_model=Propiedad)
def actualizar(
    propiedad_id: int,
    payload: PropiedadActualizar,
    sesion: Session = Depends(obtener_sesion_db),
):
    propiedad_existente = repository.obtener_propiedad(sesion, propiedad_id)
    if propiedad_existente is None:
        raise HTTPException(404, "Propiedad no encontrada")

    campos = payload.model_dump(exclude_unset=True)
    if "chat_telegram_id" in campos:
        if repository.obtener_chat_telegram(sesion, campos["chat_telegram_id"]) is None:
            raise HTTPException(404, "El chat de Telegram indicado no existe")

    # PropiedadActualizar no valida esto por ser una edición parcial (ver su
    # docstring): hay que mirar el resultado DESPUÉS del merge con lo existente.
    frecuencia_resultante = campos.get(
        "frecuencia_tipo", propiedad_existente.frecuencia_tipo
    )
    hora_resultante = campos.get("hora_ejecucion", propiedad_existente.hora_ejecucion)
    intervalo_resultante = campos.get(
        "intervalo_horas", propiedad_existente.intervalo_horas
    )
    if frecuencia_resultante == FrecuenciaTipo.hora_fija and not hora_resultante:
        raise HTTPException(
            422, "hora_ejecucion es obligatoria cuando frecuencia_tipo es 'hora_fija'"
        )
    if frecuencia_resultante == FrecuenciaTipo.intervalo and not intervalo_resultante:
        raise HTTPException(
            422, "intervalo_horas es obligatorio cuando frecuencia_tipo es 'intervalo'"
        )

    propiedad = repository.actualizar_propiedad(sesion, propiedad_id, **campos)
    return propiedad


@router.post("/{propiedad_id}/pausar", response_model=Propiedad)
def pausar(propiedad_id: int, sesion: Session = Depends(obtener_sesion_db)):
    propiedad = repository.pausar_propiedad(sesion, propiedad_id)
    if propiedad is None:
        raise HTTPException(404, "Propiedad no encontrada")

    # Aviso best-effort: si Telegram falla acá, no bloqueamos la pausa (que es
    # un simple cambio de estado en la base) por un problema de notificación.
    if BOT_TOKEN and propiedad.chat_telegram is not None:
        mensaje = (
            f"⏸️ <b>Monitoreo pausado</b> ⏸️\n\n"
            f"Se pausó el seguimiento de <b>{propiedad.nombre}</b>. "
            f"No recibirás más avisos hasta que lo reanudes."
        )
        enviar_notificacion_telegram(BOT_TOKEN, propiedad.chat_telegram.chat_id, mensaje)

    return propiedad


@router.post("/{propiedad_id}/reanudar", response_model=Propiedad)
def reanudar(propiedad_id: int, sesion: Session = Depends(obtener_sesion_db)):
    propiedad = repository.reanudar_propiedad(sesion, propiedad_id)
    if propiedad is None:
        raise HTTPException(404, "Propiedad no encontrada")

    # Mismo aviso best-effort que al pausar: no bloqueamos el cambio de estado
    # si Telegram falla.
    if BOT_TOKEN and propiedad.chat_telegram is not None:
        mensaje = (
            f"▶️ <b>Monitoreo reanudado</b> ▶️\n\n"
            f"Se reanudó el seguimiento de <b>{propiedad.nombre}</b>. "
            f"Volverás a recibir avisos de cambios."
        )
        enviar_notificacion_telegram(BOT_TOKEN, propiedad.chat_telegram.chat_id, mensaje)

    return propiedad


@router.post("/{propiedad_id}/ejecutar-ahora", response_model=Propiedad)
def ejecutar_ahora(propiedad_id: int, sesion: Session = Depends(obtener_sesion_db)):
    """
    Marca la propiedad para que el worker la procese en su próximo tick (hasta
    ~1 min), sin esperar a su hora fija/intervalo normal. No ejecuta el scraping
    acá mismo: la API no tiene Chromium instalado (a propósito, para mantener su
    imagen liviana), eso sigue siendo trabajo exclusivo del worker.
    """
    propiedad = repository.forzar_ejecucion_inmediata(sesion, propiedad_id)
    if propiedad is None:
        raise HTTPException(404, "Propiedad no encontrada")
    return propiedad


@router.delete("/{propiedad_id}", status_code=204)
def eliminar(propiedad_id: int, sesion: Session = Depends(obtener_sesion_db)):
    eliminado = repository.eliminar_propiedad(sesion, propiedad_id)
    if not eliminado:
        raise HTTPException(404, "Propiedad no encontrada")


@router.get("/{propiedad_id}/ultimo-aviso")
def ultimo_aviso(propiedad_id: int, sesion: Session = Depends(obtener_sesion_db)):
    """Para el 'Ver aviso' del mockup: el último estado conocido, derivado de las
    columnas existentes (no se guarda el texto exacto del mensaje enviado)."""
    propiedad = repository.obtener_propiedad(sesion, propiedad_id)
    if propiedad is None:
        raise HTTPException(404, "Propiedad no encontrada")
    return {
        "ultimo_recuento": propiedad.ultimo_recuento,
        "ultima_verificacion_en": propiedad.ultima_verificacion_en,
        "estado_operativo": propiedad.estado_operativo,
        "ultimo_error": propiedad.ultimo_error,
        "url_poligono": propiedad.url_poligono,
    }

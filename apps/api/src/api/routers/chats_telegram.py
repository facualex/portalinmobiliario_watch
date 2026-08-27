# -*- coding: utf-8 -*-
"""Endpoints para gestionar los chats de Telegram a los que se puede notificar."""

import os
from typing import List

from fastapi import APIRouter, Depends, HTTPException
from lindero_core import repository
from lindero_core.models import ChatTelegram, ChatTelegramActualizar, ChatTelegramCrear
from lindero_core.telegram import enviar_notificacion_telegram
from sqlalchemy.exc import IntegrityError
from sqlmodel import Session

from api.deps import obtener_sesion_db

router = APIRouter(prefix="/chats-telegram", tags=["chats-telegram"])

BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")


@router.get("", response_model=List[ChatTelegram])
def listar(sesion: Session = Depends(obtener_sesion_db)):
    return repository.listar_chats_telegram(sesion)


@router.post("", response_model=ChatTelegram, status_code=201)
def conectar(payload: ChatTelegramCrear, sesion: Session = Depends(obtener_sesion_db)):
    """
    Conecta un chat nuevo: antes de guardarlo, manda un mensaje de prueba para
    confirmar que el chat_id es válido y que el bot puede escribirle (el usuario
    debe haberle escrito primero al bot, igual que hoy con get_chat_id.py).
    """
    if not BOT_TOKEN:
        raise HTTPException(500, "TELEGRAM_BOT_TOKEN no está configurado en el servidor")

    if repository.obtener_chat_telegram_por_chat_id(sesion, payload.chat_id) is not None:
        raise HTTPException(409, "Ese chat_id ya está conectado")

    mensaje = (
        "✅ <b>Chat conectado a Lindero</b> ✅\n\n"
        "A partir de ahora puedes recibir avisos de propiedades en este chat."
    )
    enviado = enviar_notificacion_telegram(BOT_TOKEN, payload.chat_id, mensaje)
    if not enviado:
        raise HTTPException(
            400,
            "No se pudo enviar un mensaje de prueba a ese chat_id. Verifica que "
            "le hayas escrito primero al bot.",
        )

    try:
        return repository.crear_chat_telegram(
            sesion, chat_id=payload.chat_id, nombre=payload.nombre
        )
    except IntegrityError:
        # El chequeo de arriba no cubre la carrera entre dos requests
        # concurrentes con el mismo chat_id (ej. doble clic); esto es el
        # respaldo a nivel de base de datos para esos casos.
        sesion.rollback()
        raise HTTPException(409, "Ese chat_id ya está conectado")


@router.patch("/{chat_telegram_id}", response_model=ChatTelegram)
def actualizar(
    chat_telegram_id: int,
    payload: ChatTelegramActualizar,
    sesion: Session = Depends(obtener_sesion_db),
):
    chat = repository.actualizar_chat_telegram(
        sesion, chat_telegram_id, **payload.model_dump(exclude_unset=True)
    )
    if chat is None:
        raise HTTPException(404, "Chat no encontrado")
    return chat


@router.delete("/{chat_telegram_id}", status_code=204)
def eliminar(chat_telegram_id: int, sesion: Session = Depends(obtener_sesion_db)):
    en_uso = repository.contar_propiedades_por_chat(sesion, chat_telegram_id)
    if en_uso > 0:
        raise HTTPException(
            409,
            f"No se puede eliminar: hay {en_uso} propiedad(es) usando este chat. "
            "Reasígnalas a otro chat o elimínalas primero.",
        )
    eliminado = repository.eliminar_chat_telegram(sesion, chat_telegram_id)
    if not eliminado:
        raise HTTPException(404, "Chat no encontrado")

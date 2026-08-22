# -*- coding: utf-8 -*-
"""Envío de notificaciones a través de un bot de Telegram."""

import logging

import requests


def enviar_notificacion_telegram(bot_token, chat_id, mensaje):
    """Envía `mensaje` (HTML) al chat `chat_id` a través del bot `bot_token`."""
    url_telegram_api = f"https://api.telegram.org/bot{bot_token}/sendMessage"
    payload = {"chat_id": chat_id, "text": mensaje, "parse_mode": "HTML"}
    try:
        response = requests.post(url_telegram_api, data=payload)
        if response.status_code == 200:
            logging.info("Notificación enviada exitosamente.")
        else:
            logging.error(
                f"Error al enviar notificación: {response.status_code} - {response.text}"
            )
    except requests.exceptions.RequestException as e:
        logging.error(f"Error de conexión al enviar notificación: {e}")

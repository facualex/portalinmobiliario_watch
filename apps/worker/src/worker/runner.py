# -*- coding: utf-8 -*-
"""Ejecuta un ciclo de monitoreo para UNA propiedad: scrapea, compara, notifica y persiste."""

import logging
import os

from dotenv import load_dotenv
from lindero_core.repository import (
    registrar_ejecucion_exitosa,
    registrar_error_scraping,
    registrar_reprogramacion_sin_cambios,
)
from lindero_core.scraping import scrapear_unidades_disponibles
from lindero_core.telegram import enviar_notificacion_telegram

# Carga las variables de entorno desde el archivo .env
load_dotenv()

# El bot es único por instancia (self-hosted); el destino (chat_id) es por propiedad.
BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")

# Selector CSS para todos los marcadores de precio/unidades
SELECTOR_UNIDADES = "span.ui-search-map-marker--price__label"

# Si se definen, se usa un Chrome y un chromedriver ya instalados en el sistema
# (como en la imagen Docker) en vez de que webdriver-manager descargue uno.
CHROME_BINARY_PATH = os.getenv("CHROME_BINARY_PATH")
CHROMEDRIVER_PATH = os.getenv("CHROMEDRIVER_PATH")


def ejecutar_para_propiedad(sesion, propiedad, proxima_ejecucion_en):
    """
    Corre el ciclo completo de monitoreo para `propiedad`: scrapea, compara contra
    su último recuento conocido, notifica al chat de Telegram que corresponda si
    hay cambio (o es la primera vez), y persiste según el resultado.

    `proxima_ejecucion_en` ya viene calculado por el llamante (el scheduler, según
    la frecuencia propia de esta propiedad), para que esta función se quede solo
    con la lógica de negocio de una corrida.
    """
    logging.info(f"--- Procesando propiedad '{propiedad.nombre}' (id={propiedad.id}) ---")

    if not BOT_TOKEN:
        logging.error(
            "ERROR CRÍTICO: TELEGRAM_BOT_TOKEN no está definido. Revisa tu archivo .env."
        )
        return

    chat_id = propiedad.chat_telegram.chat_id
    recuento_anterior = propiedad.ultimo_recuento
    recuento_actual = scrapear_unidades_disponibles(
        propiedad.url_poligono,
        SELECTOR_UNIDADES,
        chrome_binary_path=CHROME_BINARY_PATH,
        chromedriver_path=CHROMEDRIVER_PATH,
    )

    if recuento_actual is None:
        mensaje_error = (
            f"🚨 <b>ERROR DE SCRAPING</b> 🚨\n"
            f"No se pudo obtener el número de unidades de <b>{propiedad.nombre}</b>. "
            f"Revisa la URL o la página web."
        )
        enviar_notificacion_telegram(BOT_TOKEN, chat_id, mensaje_error)
        registrar_error_scraping(
            sesion,
            propiedad.id,
            "Scraping falló tras agotar los reintentos",
            proxima_ejecucion_en,
        )
        logging.info(f"--- Propiedad '{propiedad.nombre}' procesada (error) ---")
        return

    recuento_actual_str = str(recuento_actual)

    if recuento_anterior is None:
        logging.info("Primera ejecución. Enviando notificación de bienvenida...")
        mensaje = (
            f"✅ <b>Servicio de Monitoreo Activado</b> ✅\n\n"
            f"Se ha iniciado el seguimiento para {propiedad.nombre}\n\n"
            f"Actualmente hay <b>{recuento_actual_str}</b> disponibles.\n"
            f"Se te notificará sobre cualquier cambio futuro."
        )
        notificacion_enviada = enviar_notificacion_telegram(BOT_TOKEN, chat_id, mensaje)
    elif recuento_anterior != recuento_actual_str:
        logging.info("¡Cambio detectado! Enviando notificación...")
        mensaje = (
            f"🔔 <b>¡Cambio en {propiedad.nombre}!</b> 🔔\n\n"
            f"Unidades disponibles cambiaron de <b>{recuento_anterior}</b> a <b>{recuento_actual_str}</b>.\n\n"
            f"Revisa ahora: {propiedad.url_poligono}"
        )
        notificacion_enviada = enviar_notificacion_telegram(BOT_TOKEN, chat_id, mensaje)
    else:
        logging.info("Sin cambios detectados. No se enviará notificación.")
        notificacion_enviada = True  # No había nada que notificar.

    if notificacion_enviada:
        registrar_ejecucion_exitosa(
            sesion, propiedad.id, recuento_actual_str, proxima_ejecucion_en
        )
    else:
        logging.warning(
            "No se guarda el nuevo recuento porque la notificación no pudo enviarse; "
            "se reintentará notificar en la próxima ejecución de esta propiedad."
        )
        registrar_reprogramacion_sin_cambios(sesion, propiedad.id, proxima_ejecucion_en)

    logging.info(f"--- Propiedad '{propiedad.nombre}' procesada ---")

# -*- coding: utf-8 -*-
"""Ejecuta un ciclo de monitoreo para UNA propiedad: scrapea, compara, notifica y persiste."""

import logging
import os

from dotenv import load_dotenv
from lindero_core.models import EstadoPrueba, EventoTipo
from lindero_core.repository import (
    registrar_ejecucion_exitosa,
    registrar_error_scraping,
    registrar_evento,
    registrar_reprogramacion_sin_cambios,
    registrar_resultado_prueba_url,
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

# Una prueba de URL es un chequeo manual y puntual (el usuario está esperando
# el resultado), no la vigilancia garantizada de una propiedad real: menos
# reintentos que MAX_INTENTOS_SCRAPING_POR_DEFECTO para no acaparar el tick del
# worker ni sumar carga extra sobre el sitio por cada click de "Probar".
INTENTOS_PRUEBA_URL = 2
ESPERA_INICIAL_PRUEBA_URL_SEGUNDOS = 5


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
        registrar_evento(
            sesion,
            propiedad.id,
            EventoTipo.error,
            "Scraping falló tras agotar los reintentos.",
        )
        logging.info(f"--- Propiedad '{propiedad.nombre}' procesada (error) ---")
        return

    recuento_actual_str = str(recuento_actual)
    tipo_evento = None
    mensaje_evento = None

    if recuento_anterior is None:
        logging.info("Primera ejecución. Enviando notificación de bienvenida...")
        mensaje = (
            f"✅ <b>Servicio de Monitoreo Activado</b> ✅\n\n"
            f"Se ha iniciado el seguimiento para {propiedad.nombre}\n\n"
            f"Actualmente hay <b>{recuento_actual_str}</b> disponibles.\n"
            f"Se te notificará sobre cualquier cambio futuro."
        )
        notificacion_enviada = enviar_notificacion_telegram(BOT_TOKEN, chat_id, mensaje)
        tipo_evento = EventoTipo.activacion
        mensaje_evento = f"Monitoreo activado: {recuento_actual_str} unidades disponibles."
    elif recuento_anterior != recuento_actual_str:
        logging.info("¡Cambio detectado! Enviando notificación...")
        mensaje = (
            f"🔔 <b>¡Cambio en {propiedad.nombre}!</b> 🔔\n\n"
            f"Unidades disponibles cambiaron de <b>{recuento_anterior}</b> a <b>{recuento_actual_str}</b>.\n\n"
            f"Revisa ahora: {propiedad.url_poligono}"
        )
        notificacion_enviada = enviar_notificacion_telegram(BOT_TOKEN, chat_id, mensaje)
        tipo_evento = EventoTipo.cambio
        mensaje_evento = (
            f"Unidades disponibles cambiaron de {recuento_anterior} a {recuento_actual_str}."
        )
    else:
        logging.info("Sin cambios detectados. No se enviará notificación.")
        notificacion_enviada = True  # No había nada que notificar.

    if notificacion_enviada:
        registrar_ejecucion_exitosa(
            sesion, propiedad.id, recuento_actual_str, proxima_ejecucion_en
        )
        # Solo activación/cambio quedan en el historial: una corrida "sin
        # cambios" no es algo que el usuario necesite revisar después.
        if tipo_evento is not None:
            registrar_evento(sesion, propiedad.id, tipo_evento, mensaje_evento)
    else:
        logging.warning(
            "No se guarda el nuevo recuento porque la notificación no pudo enviarse; "
            "se reintentará notificar en la próxima ejecución de esta propiedad."
        )
        registrar_reprogramacion_sin_cambios(sesion, propiedad.id, proxima_ejecucion_en)

    logging.info(f"--- Propiedad '{propiedad.nombre}' procesada ---")


def ejecutar_prueba_url(sesion, prueba):
    """
    Corre un chequeo rápido y puntual de `prueba.url` (sin crear ninguna
    propiedad ni notificar a Telegram): sirve para validar una URL antes de
    conectarla, o tras editarla. Usa menos reintentos que una propiedad real
    (ver INTENTOS_PRUEBA_URL) porque acá hay un usuario esperando el resultado
    en la UI, no la garantía de entrega de una vigilancia real.
    """
    logging.info(f"--- Probando URL (id={prueba.id}): {prueba.url} ---")
    recuento = scrapear_unidades_disponibles(
        prueba.url,
        SELECTOR_UNIDADES,
        chrome_binary_path=CHROME_BINARY_PATH,
        chromedriver_path=CHROMEDRIVER_PATH,
        max_intentos=INTENTOS_PRUEBA_URL,
        espera_inicial_segundos=ESPERA_INICIAL_PRUEBA_URL_SEGUNDOS,
    )
    if recuento is None:
        registrar_resultado_prueba_url(
            sesion,
            prueba.id,
            EstadoPrueba.error,
            mensaje_error=(
                "No se encontraron unidades en esa URL. Revisa que el enlace "
                "tenga el polígono dibujado y que la página cargue correctamente."
            ),
        )
    else:
        registrar_resultado_prueba_url(sesion, prueba.id, EstadoPrueba.ok, recuento=recuento)
    logging.info(f"--- Prueba de URL (id={prueba.id}) finalizada ---")

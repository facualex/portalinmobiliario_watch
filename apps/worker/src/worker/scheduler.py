# -*- coding: utf-8 -*-
"""
Programador interno: un solo bucle global que, en cada tick, revisa qué
propiedades (no pausadas) les toca correr según su PROPIA frecuencia
(hora fija + zona horaria, o intervalo), y las procesa secuencialmente.
Reemplaza cron/launchd/Task Scheduler cuando se usa Docker.

Un solo proceso, un solo bucle: no se lanzan N schedulers ni N procesos de
Selenium en paralelo (indeseable en una VM self-hosted chica). El tick es
mucho más corto que la frecuencia mínima configurable, así que ninguna
propiedad se atrasa de forma perceptible.
"""

import logging
import os
import time
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

from lindero_core.db import crear_tablas, obtener_sesion
from lindero_core.models import FrecuenciaTipo, Propiedad
from lindero_core.repository import (
    obtener_propiedades_que_les_toca_correr,
    obtener_pruebas_pendientes,
)

from worker.logger_config import configurar_logging
from worker.runner import ejecutar_para_propiedad, ejecutar_prueba_url

TICK_SEGUNDOS_POR_DEFECTO = 60
DIRECTORIO_LOGS = os.getenv("LINDERO_LOGS_DIR", "logs")
MAX_LOGS_A_CONSERVAR = 10


def _ahora_utc_naive() -> datetime:
    """Igual a la convención de lindero_core.repository: naive, pero siempre en UTC
    (SQLite no preserva tzinfo al guardar/leer datetimes)."""
    return datetime.now(ZoneInfo("UTC")).replace(tzinfo=None)


def obtener_tick_segundos() -> int:
    return int(os.getenv("LINDERO_TICK_SEGUNDOS", TICK_SEGUNDOS_POR_DEFECTO))


def calcular_proxima_ejecucion(
    propiedad: Propiedad, ahora_naive_utc: datetime = None
) -> datetime:
    """
    Calcula la próxima vez (naive, UTC) que debe correr `propiedad`:
    - frecuencia_tipo == intervalo: ahora + intervalo_horas.
    - frecuencia_tipo == hora_fija: la próxima ocurrencia de `hora_ejecucion`
      (hoy si no pasó, mañana si ya pasó) calculada en la zona horaria propia
      de la propiedad (`propiedad.tz`), sin acumular drift, convertida a UTC
      naive para guardarla.
    """
    ahora_naive_utc = ahora_naive_utc or _ahora_utc_naive()

    if propiedad.frecuencia_tipo == FrecuenciaTipo.intervalo:
        horas = propiedad.intervalo_horas or 24
        return ahora_naive_utc + timedelta(hours=horas)

    tz = ZoneInfo(propiedad.tz or "UTC")
    ahora_tz = datetime.now(tz)
    hora, minuto = map(int, propiedad.hora_ejecucion.split(":"))
    objetivo_tz = ahora_tz.replace(hour=hora, minute=minuto, second=0, microsecond=0)
    if objetivo_tz <= ahora_tz:
        objetivo_tz += timedelta(days=1)
    return objetivo_tz.astimezone(ZoneInfo("UTC")).replace(tzinfo=None)


def ejecutar_tick() -> None:
    """
    Procesa, secuencialmente, todas las propiedades a las que les toca correr
    ahora, y también cualquier prueba de URL pendiente. Las pruebas se resuelven
    en el mismo tick regular (no en un bucle aparte) para no introducir una
    frecuencia de scraping nueva: como mucho tardan hasta `tick_segundos` en
    empezar a procesarse, igual que cualquier propiedad recién conectada.
    """
    ahora = _ahora_utc_naive()
    with obtener_sesion() as sesion:
        propiedades = obtener_propiedades_que_les_toca_correr(sesion, ahora)
        pruebas = obtener_pruebas_pendientes(sesion)
        if not propiedades and not pruebas:
            return

        configurar_logging(DIRECTORIO_LOGS, MAX_LOGS_A_CONSERVAR)
        logging.info(
            f"--- Iniciando corrida: {len(propiedades)} propiedad(es) y "
            f"{len(pruebas)} prueba(s) de URL a procesar ---"
        )
        for propiedad in propiedades:
            proxima = calcular_proxima_ejecucion(propiedad, ahora)
            ejecutar_para_propiedad(sesion, propiedad, proxima)
        for prueba in pruebas:
            ejecutar_prueba_url(sesion, prueba)
        logging.info("--- Corrida finalizada ---")


def ejecutar_en_bucle() -> None:
    crear_tablas()
    tick_segundos = obtener_tick_segundos()
    # print() en vez de logging: todavía no corrió ningún tick, así que logging
    # aún no está configurado (ver worker/logger_config.py).
    print(f"[scheduler] Worker iniciado. Revisando propiedades cada {tick_segundos}s.")
    while True:
        try:
            ejecutar_tick()
        except Exception:
            logging.exception("Error inesperado durante el tick del scheduler.")
        time.sleep(tick_segundos)


if __name__ == "__main__":
    ejecutar_en_bucle()

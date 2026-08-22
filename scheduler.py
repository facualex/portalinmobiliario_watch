# -*- coding: utf-8 -*-
"""
Programador interno: ejecuta monitor.main() en un bucle infinito, sin depender
de cron/launchd/Task Scheduler del sistema operativo. Pensado para correr como
proceso de larga duración (ej. dentro de un contenedor Docker).

Dos modos, según la variable de entorno HORA_EJECUCION:
- Definida ("HH:MM"): corre una vez al día, anclado a esa hora exacta en la
  zona horaria TZ, sin acumular drift sin importar cuánto dure cada ejecución.
  Ignora INTERVALO_HORAS.
- No definida: corre apenas arranca y luego cada INTERVALO_HORAS (comportamiento
  original, simple).
"""

import logging
import os
import time
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

import monitor

INTERVALO_HORAS_POR_DEFECTO = 24
ZONA_HORARIA_POR_DEFECTO = "UTC"


def obtener_intervalo_segundos():
    """Lee INTERVALO_HORAS desde el entorno (default 24hs) y lo convierte a segundos."""
    horas = float(os.getenv("INTERVALO_HORAS", INTERVALO_HORAS_POR_DEFECTO))
    return int(horas * 3600)


def _proxima_hora_objetivo(hora_ejecucion, zona_horaria):
    """
    Devuelve el próximo datetime (con timezone) en que ocurre `hora_ejecucion`
    ("HH:MM"): hoy si todavía no pasó, mañana si ya pasó.
    """
    hora, minuto = map(int, hora_ejecucion.split(":"))
    tz = ZoneInfo(zona_horaria)
    ahora = datetime.now(tz)
    objetivo = ahora.replace(hour=hora, minute=minuto, second=0, microsecond=0)
    if objetivo <= ahora:
        objetivo += timedelta(days=1)
    return objetivo


def _ejecutar_en_bucle_con_hora_fija(hora_ejecucion, zona_horaria):
    """Corre monitor.main() una vez al día, siempre a la misma hora exacta."""
    # print() en vez de logging: todavía no corrió monitor.main() por primera
    # vez, así que logging aún no está configurado (ver logger_config.py).
    print(
        f"[scheduler] Modo de hora fija: se ejecutará todos los días a las "
        f"{hora_ejecucion} ({zona_horaria})."
    )
    while True:
        objetivo = _proxima_hora_objetivo(hora_ejecucion, zona_horaria)
        espera_segundos = (objetivo - datetime.now(ZoneInfo(zona_horaria))).total_seconds()
        print(
            f"[scheduler] Próxima ejecución: {objetivo.isoformat()} "
            f"(en {espera_segundos:.0f} segundos)."
        )
        time.sleep(max(espera_segundos, 0))
        monitor.main()


def _ejecutar_en_bucle_por_intervalo():
    """Corre monitor.main() y luego espera INTERVALO_HORAS, indefinidamente."""
    intervalo_segundos = obtener_intervalo_segundos()
    while True:
        monitor.main()
        logging.info(
            f"Próxima ejecución en {intervalo_segundos} segundos "
            f"({intervalo_segundos / 3600:.1f} horas)."
        )
        time.sleep(intervalo_segundos)


def ejecutar_en_bucle():
    """Elige el modo de programación según la variable de entorno HORA_EJECUCION."""
    hora_ejecucion = os.getenv("HORA_EJECUCION")
    if hora_ejecucion:
        zona_horaria = os.getenv("TZ", ZONA_HORARIA_POR_DEFECTO)
        _ejecutar_en_bucle_con_hora_fija(hora_ejecucion, zona_horaria)
    else:
        _ejecutar_en_bucle_por_intervalo()


if __name__ == "__main__":
    ejecutar_en_bucle()

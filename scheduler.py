# -*- coding: utf-8 -*-
"""
Programador interno: ejecuta monitor.main() en un bucle infinito, sin depender
de cron/launchd/Task Scheduler del sistema operativo. Pensado para correr como
proceso de larga duración (ej. dentro de un contenedor Docker).
"""

import logging
import os
import time

import monitor

INTERVALO_HORAS_POR_DEFECTO = 24


def obtener_intervalo_segundos():
    """Lee INTERVALO_HORAS desde el entorno (default 24hs) y lo convierte a segundos."""
    horas = float(os.getenv("INTERVALO_HORAS", INTERVALO_HORAS_POR_DEFECTO))
    return int(horas * 3600)


def ejecutar_en_bucle():
    """Corre monitor.main() y luego espera el intervalo configurado, indefinidamente."""
    intervalo_segundos = obtener_intervalo_segundos()
    while True:
        monitor.main()
        logging.info(
            f"Próxima ejecución en {intervalo_segundos} segundos "
            f"({intervalo_segundos / 3600:.1f} horas)."
        )
        time.sleep(intervalo_segundos)


if __name__ == "__main__":
    ejecutar_en_bucle()

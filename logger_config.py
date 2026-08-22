# -*- coding: utf-8 -*-
"""Configuración de logging reutilizable: consola + un archivo por ejecución,
con retención acotada de los N archivos más recientes."""

import glob
import logging
import os
from datetime import datetime


def configurar_logging(directorio_logs, max_logs=10):
    """
    Configura logging a consola y a un archivo propio de esta ejecución dentro de
    `directorio_logs`, con el timestamp de inicio en el nombre del archivo.
    Antes de crear el nuevo archivo, conserva solo los `max_logs` más recientes,
    eliminando los sobrantes más antiguos.
    Devuelve la ruta del archivo de log creado.
    """
    os.makedirs(directorio_logs, exist_ok=True)
    _limpiar_logs_antiguos(directorio_logs, max_logs)

    timestamp = datetime.now().strftime("%Y-%m-%d_%H%M%S")
    archivo_log = os.path.join(directorio_logs, f"{timestamp}.log")

    logging.basicConfig(
        level=logging.INFO,
        format="[%(asctime)s] %(message)s",
        datefmt="%d-%m-%Y %H:%M:%S",
        handlers=[
            logging.FileHandler(archivo_log, encoding="utf-8"),
            logging.StreamHandler(),
        ],
    )
    return archivo_log


def _limpiar_logs_antiguos(directorio_logs, max_logs):
    """
    Elimina los archivos de log más antiguos en `directorio_logs`, dejando espacio
    para que, tras crearse el log de la ejecución actual, queden como máximo `max_logs`.
    """
    archivos = sorted(
        glob.glob(os.path.join(directorio_logs, "*.log")), key=os.path.getmtime
    )
    exceso = len(archivos) - (max_logs - 1)
    for archivo in archivos[: max(exceso, 0)]:
        try:
            os.remove(archivo)
        except OSError:
            pass

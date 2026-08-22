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
    Luego de configurar el logging, conserva solo los `max_logs` más recientes
    (sin contar el archivo recién creado), eliminando los sobrantes más antiguos.
    Devuelve la ruta del archivo de log creado.
    """
    os.makedirs(directorio_logs, exist_ok=True)

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

    # Se limpia después de configurar el logging (excluyendo el archivo recién
    # creado) para que cualquier falla al eliminar quede registrada, en vez de
    # ignorarse en silencio.
    _limpiar_logs_antiguos(directorio_logs, max_logs, excluir=archivo_log)
    return archivo_log


def _limpiar_logs_antiguos(directorio_logs, max_logs, excluir=None):
    """
    Elimina los archivos de log más antiguos en `directorio_logs` (sin contar
    `excluir`), dejando como máximo `max_logs` en total.
    """
    archivos = sorted(
        (
            archivo
            for archivo in glob.glob(os.path.join(directorio_logs, "*.log"))
            if archivo != excluir
        ),
        key=os.path.getmtime,
    )
    exceso = len(archivos) - (max_logs - 1)
    for archivo in archivos[: max(exceso, 0)]:
        try:
            os.remove(archivo)
        except OSError as e:
            logging.warning(f"No se pudo eliminar el log antiguo '{archivo}': {e}")

# -*- coding: utf-8 -*-
"""Persistencia del último recuento conocido, para detectar cambios entre ejecuciones."""

import logging
import os


def obtener_recuento_anterior(nombre_archivo_estado):
    """Lee el último recuento guardado en `nombre_archivo_estado`. Devuelve None si no existe."""
    if not os.path.exists(nombre_archivo_estado):
        return None
    try:
        with open(nombre_archivo_estado, "r") as f:
            return f.read().strip() or None
    except IOError as e:
        logging.error(f"Error al leer el archivo de estado: {e}")
        return None


def guardar_recuento_actual(nombre_archivo_estado, recuento):
    """Guarda `recuento` en `nombre_archivo_estado`, creando su carpeta si falta."""
    try:
        os.makedirs(os.path.dirname(nombre_archivo_estado), exist_ok=True)
        with open(nombre_archivo_estado, "w") as f:
            f.write(str(recuento))
        logging.info(f"Recuento actualizado guardado: {recuento}")
    except IOError as e:
        logging.error(f"Error al guardar el nuevo recuento: {e}")

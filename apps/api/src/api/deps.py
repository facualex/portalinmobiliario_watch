# -*- coding: utf-8 -*-
"""Dependencias de FastAPI: una sesión de base de datos por request."""

from typing import Iterator

from lindero_core.db import obtener_sesion
from sqlmodel import Session


def obtener_sesion_db() -> Iterator[Session]:
    with obtener_sesion() as sesion:
        yield sesion

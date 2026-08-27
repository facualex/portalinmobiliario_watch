# -*- coding: utf-8 -*-
"""Engine SQLite compartido por el worker y la API. Una sola base de datos,
un solo archivo, sin infraestructura adicional (coherente con el self-hosted)."""

import os
from contextlib import contextmanager
from typing import Iterator

from sqlmodel import Session, SQLModel, create_engine


def _ruta_db() -> str:
    return os.getenv("DB_PATH", "data/lindero.db")


def crear_engine_lindero():
    ruta = _ruta_db()
    directorio = os.path.dirname(ruta)
    if directorio:
        os.makedirs(directorio, exist_ok=True)

    engine = create_engine(
        f"sqlite:///{ruta}", connect_args={"check_same_thread": False}
    )
    # WAL permite que el worker y la API lean/escriban concurrentemente sin
    # bloquearse entre sí (en vez del locking exclusivo por defecto de SQLite).
    with engine.connect() as conexion:
        conexion.exec_driver_sql("PRAGMA journal_mode=WAL")
    return engine


engine = crear_engine_lindero()


def crear_tablas() -> None:
    """Crea las tablas si no existen. Se llama al boot del worker y de la API."""
    from lindero_core import models  # noqa: F401 - registra las tablas en SQLModel.metadata

    SQLModel.metadata.create_all(engine)


@contextmanager
def obtener_sesion() -> Iterator[Session]:
    with Session(engine) as sesion:
        yield sesion

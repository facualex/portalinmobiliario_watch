# -*- coding: utf-8 -*-
"""Modelos de datos (SQLModel): esquema compartido entre el ORM (worker/repository)
y los schemas de la futura API (FastAPI los usa directamente para (de)serializar)."""

import enum
from datetime import datetime, timezone
from typing import List, Optional

from sqlmodel import Field, Relationship, SQLModel


def _ahora_utc() -> datetime:
    """
    'Ahora' en UTC, naive (sin tzinfo). SQLite no preserva tzinfo al guardar/leer
    datetimes, así que la convención en todo el proyecto es guardar siempre naive
    pero en UTC (ver también lindero_core.repository._ahora_utc).
    """
    return datetime.now(timezone.utc).replace(tzinfo=None)


class FrecuenciaTipo(str, enum.Enum):
    hora_fija = "hora_fija"
    intervalo = "intervalo"


class EstadoOperativo(str, enum.Enum):
    activo = "activo"
    error = "error"


class ChatTelegram(SQLModel, table=True):
    __tablename__ = "chat_telegram"

    id: Optional[int] = Field(default=None, primary_key=True)
    chat_id: str = Field(unique=True, index=True)
    nombre: str
    creado_en: datetime = Field(default_factory=_ahora_utc)

    propiedades: List["Propiedad"] = Relationship(back_populates="chat_telegram")


class Propiedad(SQLModel, table=True):
    __tablename__ = "propiedad"

    id: Optional[int] = Field(default=None, primary_key=True)
    nombre: str
    url_poligono: str
    comuna: Optional[str] = None
    # Dato informativo, no se scrapea en v1 — se completa a mano.
    precio_referencia: Optional[str] = None

    chat_telegram_id: int = Field(foreign_key="chat_telegram.id")
    chat_telegram: Optional[ChatTelegram] = Relationship(back_populates="propiedades")

    frecuencia_tipo: FrecuenciaTipo = FrecuenciaTipo.hora_fija
    hora_ejecucion: Optional[str] = None  # "HH:MM", usado si frecuencia_tipo=hora_fija
    intervalo_horas: Optional[float] = None  # usado si frecuencia_tipo=intervalo
    tz: str = "UTC"  # zona horaria IANA para hora_ejecucion

    pausado: bool = False
    # Separado de `pausado`: el operativo lo calcula el worker (éxito/fallo de
    # scraping), pausado lo controla el usuario. No se pisan entre sí.
    estado_operativo: EstadoOperativo = EstadoOperativo.activo

    ultimo_recuento: Optional[str] = None
    ultima_verificacion_en: Optional[datetime] = None
    ultimo_error: Optional[str] = None
    proxima_ejecucion_en: Optional[datetime] = None

    creado_en: datetime = Field(default_factory=_ahora_utc)
    actualizado_en: datetime = Field(default_factory=_ahora_utc)


# --- Schemas de entrada de la API (no son tablas) ---
# Separados de Propiedad/ChatTelegram a propósito: un cliente no debe poder
# setear campos como `id`, `estado_operativo` o `ultimo_recuento` al crear/editar.


class PropiedadCrear(SQLModel):
    nombre: str
    url_poligono: str
    comuna: Optional[str] = None
    precio_referencia: Optional[str] = None
    chat_telegram_id: int
    frecuencia_tipo: FrecuenciaTipo = FrecuenciaTipo.hora_fija
    hora_ejecucion: Optional[str] = None
    intervalo_horas: Optional[float] = None
    tz: str = "UTC"


class PropiedadActualizar(SQLModel):
    nombre: Optional[str] = None
    url_poligono: Optional[str] = None
    comuna: Optional[str] = None
    precio_referencia: Optional[str] = None
    chat_telegram_id: Optional[int] = None
    frecuencia_tipo: Optional[FrecuenciaTipo] = None
    hora_ejecucion: Optional[str] = None
    intervalo_horas: Optional[float] = None
    tz: Optional[str] = None


class ChatTelegramCrear(SQLModel):
    chat_id: str
    nombre: str

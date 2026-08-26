# -*- coding: utf-8 -*-
"""Modelos de datos (SQLModel): esquema compartido entre el ORM (worker/repository)
y los schemas de la futura API (FastAPI los usa directamente para (de)serializar)."""

import enum
import re
from datetime import datetime, timezone
from typing import List, Optional
from urllib.parse import urlparse
from zoneinfo import available_timezones

from pydantic import field_validator, model_validator
from sqlmodel import Field, Relationship, SQLModel

# --- Reglas de validación compartidas por PropiedadCrear y PropiedadActualizar ---

_PATRON_HORA = re.compile(r"^([01]\d|2[0-3]):([0-5]\d)$")
_INTERVALO_MINIMO_HORAS = 1.0
_DOMINIO_URL_PERMITIDO = "portalinmobiliario.com"


def _validar_hora_ejecucion(valor: Optional[str]) -> Optional[str]:
    if valor is not None and not _PATRON_HORA.match(valor):
        raise ValueError("hora_ejecucion debe tener formato HH:MM (24 horas), ej: 09:00")
    return valor


def _validar_tz(valor: Optional[str]) -> Optional[str]:
    if valor is not None and valor not in available_timezones():
        raise ValueError(f"'{valor}' no es una zona horaria IANA válida (ej: America/Santiago)")
    return valor


def _validar_intervalo_horas(valor: Optional[float]) -> Optional[float]:
    if valor is not None and valor < _INTERVALO_MINIMO_HORAS:
        raise ValueError(f"intervalo_horas debe ser al menos {_INTERVALO_MINIMO_HORAS}")
    return valor


def _validar_url_poligono(valor: Optional[str]) -> Optional[str]:
    if valor is not None:
        partes = urlparse(valor)
        host = (partes.hostname or "").lower()
        es_dominio_valido = host == _DOMINIO_URL_PERMITIDO or host.endswith(
            f".{_DOMINIO_URL_PERMITIDO}"
        )
        if partes.scheme not in ("http", "https") or not es_dominio_valido:
            raise ValueError(
                f"La URL debe ser de {_DOMINIO_URL_PERMITIDO} "
                f"(ej: https://www.portalinmobiliario.com/...)"
            )
    return valor


class _ValidacionesPropiedadMixin:
    """Validadores de campo compartidos entre PropiedadCrear y PropiedadActualizar.
    Aplican por igual en un alta completa o en una edición parcial."""

    @field_validator("hora_ejecucion")
    @classmethod
    def _check_hora_ejecucion(cls, v):
        return _validar_hora_ejecucion(v)

    @field_validator("tz")
    @classmethod
    def _check_tz(cls, v):
        return _validar_tz(v)

    @field_validator("intervalo_horas")
    @classmethod
    def _check_intervalo_horas(cls, v):
        return _validar_intervalo_horas(v)

    @field_validator("url_poligono")
    @classmethod
    def _check_url_poligono(cls, v):
        return _validar_url_poligono(v)


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


class PropiedadCrear(_ValidacionesPropiedadMixin, SQLModel):
    nombre: str
    url_poligono: str
    comuna: Optional[str] = None
    precio_referencia: Optional[str] = None
    chat_telegram_id: int
    frecuencia_tipo: FrecuenciaTipo = FrecuenciaTipo.hora_fija
    hora_ejecucion: Optional[str] = None
    intervalo_horas: Optional[float] = None
    tz: str = "UTC"

    @model_validator(mode="after")
    def _check_frecuencia_consistente(self):
        if self.frecuencia_tipo == FrecuenciaTipo.hora_fija and not self.hora_ejecucion:
            raise ValueError(
                "hora_ejecucion es obligatoria cuando frecuencia_tipo es 'hora_fija'"
            )
        if self.frecuencia_tipo == FrecuenciaTipo.intervalo and not self.intervalo_horas:
            raise ValueError(
                "intervalo_horas es obligatorio cuando frecuencia_tipo es 'intervalo'"
            )
        return self


class PropiedadActualizar(_ValidacionesPropiedadMixin, SQLModel):
    """
    Igual que PropiedadCrear pero con todo opcional (PATCH parcial). La
    consistencia cruzada entre frecuencia_tipo y hora_ejecucion/intervalo_horas
    no se valida acá: como es una edición parcial, hace falta el estado actual
    de la propiedad para saber qué valor rige tras el merge — eso se valida en
    el router (api/routers/propiedades.py), no en el schema.
    """

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

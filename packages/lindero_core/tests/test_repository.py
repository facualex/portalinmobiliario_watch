# -*- coding: utf-8 -*-
"""Tests de la capa repository contra un SQLite en memoria (sin tocar db.py real)."""

from datetime import datetime, timedelta, timezone

import pytest
from sqlmodel import Session, SQLModel, create_engine

from lindero_core import repository
from lindero_core.models import EstadoOperativo, FrecuenciaTipo


def _ahora_utc_naive() -> datetime:
    """Igual a repository._ahora_utc(): SQLite guarda datetimes naive."""
    return datetime.now(timezone.utc).replace(tzinfo=None)


@pytest.fixture()
def sesion():
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False})
    SQLModel.metadata.create_all(engine)
    with Session(engine) as s:
        yield s


def _crear_chat(sesion, chat_id="12345", nombre="Facu"):
    return repository.crear_chat_telegram(sesion, chat_id=chat_id, nombre=nombre)


def _crear_propiedad(sesion, chat_id_fk, **overrides):
    campos = dict(
        nombre="Manuel Montt 2440",
        url_poligono="https://example.com/poligono",
        chat_telegram_id=chat_id_fk,
    )
    campos.update(overrides)
    return repository.crear_propiedad(sesion, **campos)


def test_crear_y_listar_propiedad(sesion):
    chat = _crear_chat(sesion)
    propiedad = _crear_propiedad(
        sesion,
        chat.id,
        frecuencia_tipo=FrecuenciaTipo.hora_fija,
        hora_ejecucion="09:00",
        tz="America/Santiago",
    )

    assert propiedad.id is not None
    assert propiedad.estado_operativo == EstadoOperativo.activo
    assert propiedad.pausado is False

    propiedades = repository.listar_propiedades(sesion)
    assert len(propiedades) == 1
    assert propiedades[0].nombre == "Manuel Montt 2440"


def test_pausar_y_reanudar(sesion):
    chat = _crear_chat(sesion)
    propiedad = _crear_propiedad(sesion, chat.id)

    repository.pausar_propiedad(sesion, propiedad.id)
    assert repository.obtener_propiedad(sesion, propiedad.id).pausado is True

    repository.reanudar_propiedad(sesion, propiedad.id)
    assert repository.obtener_propiedad(sesion, propiedad.id).pausado is False


def test_eliminar_propiedad(sesion):
    chat = _crear_chat(sesion)
    propiedad = _crear_propiedad(sesion, chat.id)

    assert repository.eliminar_propiedad(sesion, propiedad.id) is True
    assert repository.obtener_propiedad(sesion, propiedad.id) is None
    assert repository.eliminar_propiedad(sesion, propiedad.id) is False


def test_propiedades_que_les_toca_correr(sesion):
    chat = _crear_chat(sesion)
    ahora = _ahora_utc_naive()

    nunca_corrio = _crear_propiedad(sesion, chat.id, nombre="Nunca corrió")
    le_toca = _crear_propiedad(
        sesion,
        chat.id,
        nombre="Le toca",
        proxima_ejecucion_en=ahora - timedelta(minutes=5),
    )
    todavia_no = _crear_propiedad(
        sesion,
        chat.id,
        nombre="Todavía no",
        proxima_ejecucion_en=ahora + timedelta(hours=1),
    )
    pausada = _crear_propiedad(
        sesion,
        chat.id,
        nombre="Pausada",
        proxima_ejecucion_en=ahora - timedelta(minutes=5),
        pausado=True,
    )

    resultado = repository.obtener_propiedades_que_les_toca_correr(sesion, ahora)
    ids_resultado = {p.id for p in resultado}

    assert nunca_corrio.id in ids_resultado
    assert le_toca.id in ids_resultado
    assert todavia_no.id not in ids_resultado
    assert pausada.id not in ids_resultado


def test_registrar_ejecucion_exitosa(sesion):
    chat = _crear_chat(sesion)
    propiedad = _crear_propiedad(
        sesion,
        chat.id,
        estado_operativo=EstadoOperativo.error,
        ultimo_error="fallo anterior",
    )
    proxima = _ahora_utc_naive() + timedelta(hours=1)

    actualizada = repository.registrar_ejecucion_exitosa(
        sesion, propiedad.id, recuento="7", proxima_ejecucion_en=proxima
    )

    assert actualizada.ultimo_recuento == "7"
    assert actualizada.estado_operativo == EstadoOperativo.activo
    assert actualizada.ultimo_error is None
    assert actualizada.ultima_verificacion_en is not None
    assert actualizada.proxima_ejecucion_en == proxima


def test_registrar_reprogramacion_sin_cambios_no_persiste_recuento(sesion):
    chat = _crear_chat(sesion)
    propiedad = _crear_propiedad(sesion, chat.id, ultimo_recuento="5")
    proxima = _ahora_utc_naive() + timedelta(hours=1)

    actualizada = repository.registrar_reprogramacion_sin_cambios(
        sesion, propiedad.id, proxima_ejecucion_en=proxima
    )

    # El recuento NO cambia: la notificación falló, se reintentará el mismo cambio.
    assert actualizada.ultimo_recuento == "5"
    assert actualizada.proxima_ejecucion_en == proxima


def test_registrar_error_scraping(sesion):
    chat = _crear_chat(sesion)
    propiedad = _crear_propiedad(sesion, chat.id)
    proxima = _ahora_utc_naive() + timedelta(hours=1)

    actualizada = repository.registrar_error_scraping(
        sesion, propiedad.id, mensaje_error="timeout", proxima_ejecucion_en=proxima
    )

    assert actualizada.estado_operativo == EstadoOperativo.error
    assert actualizada.ultimo_error == "timeout"
    assert actualizada.proxima_ejecucion_en == proxima


def test_forzar_ejecucion_inmediata(sesion):
    chat = _crear_chat(sesion)
    propiedad = _crear_propiedad(
        sesion,
        chat.id,
        proxima_ejecucion_en=_ahora_utc_naive() + timedelta(hours=5),
    )

    antes = _ahora_utc_naive()
    actualizada = repository.forzar_ejecucion_inmediata(sesion, propiedad.id)
    despues = _ahora_utc_naive()

    assert actualizada.proxima_ejecucion_en is not None
    assert antes <= actualizada.proxima_ejecucion_en <= despues

    # Debe quedar "pendiente ya" para obtener_propiedades_que_les_toca_correr.
    pendientes = repository.obtener_propiedades_que_les_toca_correr(sesion, despues)
    assert propiedad.id in {p.id for p in pendientes}


def test_chat_telegram_unico(sesion):
    repository.crear_chat_telegram(sesion, chat_id="111", nombre="Facu")
    chats = repository.listar_chats_telegram(sesion)

    assert len(chats) == 1
    assert chats[0].chat_id == "111"

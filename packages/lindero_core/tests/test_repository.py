# -*- coding: utf-8 -*-
"""Tests de la capa repository contra un SQLite en memoria (sin tocar db.py real)."""

from datetime import datetime, timedelta, timezone

import pytest
from sqlmodel import Session, SQLModel, create_engine, select

from lindero_core import repository
from lindero_core.models import (
    EstadoOperativo,
    EstadoPrueba,
    EventoTipo,
    FrecuenciaTipo,
    PruebaUrl,
)


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


def test_chat_telegram_unico(sesion):
    repository.crear_chat_telegram(sesion, chat_id="111", nombre="Facu")
    chats = repository.listar_chats_telegram(sesion)

    assert len(chats) == 1
    assert chats[0].chat_id == "111"


def test_contar_propiedades_por_chat(sesion):
    chat = _crear_chat(sesion)
    otro_chat = _crear_chat(sesion, chat_id="999", nombre="Otro")
    _crear_propiedad(sesion, chat.id, nombre="A")
    _crear_propiedad(sesion, chat.id, nombre="B")

    assert repository.contar_propiedades_por_chat(sesion, chat.id) == 2
    assert repository.contar_propiedades_por_chat(sesion, otro_chat.id) == 0


def test_registrar_evento_recorta_al_maximo(sesion):
    chat = _crear_chat(sesion)
    propiedad = _crear_propiedad(sesion, chat.id)

    for i in range(repository.MAX_EVENTOS_POR_PROPIEDAD + 3):
        repository.registrar_evento(
            sesion, propiedad.id, EventoTipo.cambio, f"Cambio número {i}"
        )

    eventos = repository.listar_eventos_propiedad(sesion, propiedad.id)
    assert len(eventos) == repository.MAX_EVENTOS_POR_PROPIEDAD
    # Se conservan los más recientes: el último insertado queda primero.
    assert eventos[0].mensaje == f"Cambio número {repository.MAX_EVENTOS_POR_PROPIEDAD + 2}"


def test_listar_eventos_propiedad_no_mezcla_otras_propiedades(sesion):
    chat = _crear_chat(sesion)
    propiedad_a = _crear_propiedad(sesion, chat.id, nombre="A")
    propiedad_b = _crear_propiedad(sesion, chat.id, nombre="B")

    repository.registrar_evento(sesion, propiedad_a.id, EventoTipo.activacion, "A activada")
    repository.registrar_evento(sesion, propiedad_b.id, EventoTipo.activacion, "B activada")

    eventos_a = repository.listar_eventos_propiedad(sesion, propiedad_a.id)
    assert len(eventos_a) == 1
    assert eventos_a[0].mensaje == "A activada"


def test_prueba_url_ciclo_completo(sesion):
    prueba = repository.crear_prueba_url(sesion, url="https://www.portalinmobiliario.com/x")
    assert prueba.estado == EstadoPrueba.pendiente

    pendientes = repository.obtener_pruebas_pendientes(sesion)
    assert prueba.id in {p.id for p in pendientes}

    actualizada = repository.registrar_resultado_prueba_url(
        sesion, prueba.id, EstadoPrueba.ok, recuento=3
    )
    assert actualizada.estado == EstadoPrueba.ok
    assert actualizada.recuento == 3
    assert actualizada.completado_en is not None

    # Ya no debe aparecer entre las pendientes.
    pendientes = repository.obtener_pruebas_pendientes(sesion)
    assert prueba.id not in {p.id for p in pendientes}


def test_prueba_url_antigua_se_descarta_al_crear_una_nueva(sesion):
    url_vieja = "https://www.portalinmobiliario.com/vieja"
    vieja = repository.crear_prueba_url(sesion, url=url_vieja)
    repository.registrar_resultado_prueba_url(sesion, vieja.id, EstadoPrueba.ok, recuento=1)
    vieja.creado_en = _ahora_utc_naive() - repository.ANTIGUEDAD_MAXIMA_PRUEBA_URL - timedelta(minutes=1)
    sesion.add(vieja)
    sesion.commit()

    repository.crear_prueba_url(sesion, url="https://www.portalinmobiliario.com/nueva")

    # Se identifica por URL en vez de por id: SQLite puede reasignar el mismo
    # rowid a la fila nueva una vez que la vieja se borró.
    restantes = sesion.exec(select(PruebaUrl).where(PruebaUrl.url == url_vieja)).all()
    assert restantes == []

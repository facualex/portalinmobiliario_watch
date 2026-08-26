# -*- coding: utf-8 -*-
"""Capa de acceso a datos: toda la lógica de lectura/escritura de propiedades y
chats de Telegram vive acá, para que ni el worker ni la futura API tengan SQL
disperso. No importa `db.py` a propósito, para que se pueda testear con
cualquier Session (ej. un engine SQLite en memoria) sin tocar el archivo real."""

from datetime import datetime, timedelta, timezone
from typing import List, Optional

from sqlmodel import Session, select

from lindero_core.models import (
    ChatTelegram,
    EstadoOperativo,
    EstadoPrueba,
    EventoPropiedad,
    EventoTipo,
    Propiedad,
    PruebaUrl,
)

MAX_EVENTOS_POR_PROPIEDAD = 5
ANTIGUEDAD_MAXIMA_PRUEBA_URL = timedelta(hours=1)


def _ahora_utc() -> datetime:
    """
    'Ahora' en UTC, sin tzinfo (naive). SQLite no preserva tzinfo al guardar/leer
    datetimes, así que la convención en todo el proyecto es: todas las fechas
    persistidas son naive, pero SIEMPRE en UTC. Quien llame a funciones de este
    módulo con un `proxima_ejecucion_en` debe pasar también un datetime naive en
    UTC (ej. `datetime.now(timezone.utc).replace(tzinfo=None)`).
    """
    return datetime.now(timezone.utc).replace(tzinfo=None)


# --- Propiedades ---


def listar_propiedades(sesion: Session) -> List[Propiedad]:
    return list(sesion.exec(select(Propiedad).order_by(Propiedad.nombre)).all())


def obtener_propiedad(sesion: Session, propiedad_id: int) -> Optional[Propiedad]:
    return sesion.get(Propiedad, propiedad_id)


def crear_propiedad(sesion: Session, **campos) -> Propiedad:
    propiedad = Propiedad(**campos)
    sesion.add(propiedad)
    sesion.commit()
    sesion.refresh(propiedad)
    return propiedad


def actualizar_propiedad(
    sesion: Session, propiedad_id: int, **campos
) -> Optional[Propiedad]:
    propiedad = sesion.get(Propiedad, propiedad_id)
    if propiedad is None:
        return None
    for campo, valor in campos.items():
        setattr(propiedad, campo, valor)
    propiedad.actualizado_en = _ahora_utc()
    sesion.add(propiedad)
    sesion.commit()
    sesion.refresh(propiedad)
    return propiedad


def eliminar_propiedad(sesion: Session, propiedad_id: int) -> bool:
    propiedad = sesion.get(Propiedad, propiedad_id)
    if propiedad is None:
        return False
    sesion.delete(propiedad)
    sesion.commit()
    return True


def pausar_propiedad(sesion: Session, propiedad_id: int) -> Optional[Propiedad]:
    return actualizar_propiedad(sesion, propiedad_id, pausado=True)


def reanudar_propiedad(sesion: Session, propiedad_id: int) -> Optional[Propiedad]:
    return actualizar_propiedad(sesion, propiedad_id, pausado=False)


def obtener_propiedades_que_les_toca_correr(
    sesion: Session, ahora: Optional[datetime] = None
) -> List[Propiedad]:
    """Propiedades no pausadas cuya proxima_ejecucion_en ya llegó, o que nunca corrieron."""
    ahora = ahora or _ahora_utc()
    consulta = select(Propiedad).where(
        Propiedad.pausado == False,  # noqa: E712
        (Propiedad.proxima_ejecucion_en == None)  # noqa: E711
        | (Propiedad.proxima_ejecucion_en <= ahora),
    )
    return list(sesion.exec(consulta).all())


def registrar_ejecucion_exitosa(
    sesion: Session,
    propiedad_id: int,
    recuento: str,
    proxima_ejecucion_en: datetime,
) -> Optional[Propiedad]:
    """La notificación se envió con éxito (o no había nada que notificar): se
    persiste el nuevo recuento y se limpia cualquier error previo."""
    return actualizar_propiedad(
        sesion,
        propiedad_id,
        ultimo_recuento=recuento,
        ultima_verificacion_en=_ahora_utc(),
        estado_operativo=EstadoOperativo.activo,
        ultimo_error=None,
        proxima_ejecucion_en=proxima_ejecucion_en,
    )


def registrar_reprogramacion_sin_cambios(
    sesion: Session,
    propiedad_id: int,
    proxima_ejecucion_en: datetime,
) -> Optional[Propiedad]:
    """La notificación de un cambio falló: NO se persiste el nuevo recuento (para
    reintentar notificar el mismo cambio la próxima vez), pero igual hay que
    reprogramar cuándo será esa próxima corrida."""
    return actualizar_propiedad(
        sesion, propiedad_id, proxima_ejecucion_en=proxima_ejecucion_en
    )


def registrar_error_scraping(
    sesion: Session,
    propiedad_id: int,
    mensaje_error: str,
    proxima_ejecucion_en: datetime,
) -> Optional[Propiedad]:
    return actualizar_propiedad(
        sesion,
        propiedad_id,
        estado_operativo=EstadoOperativo.error,
        ultimo_error=mensaje_error,
        proxima_ejecucion_en=proxima_ejecucion_en,
    )


# --- Chats de Telegram ---


def listar_chats_telegram(sesion: Session) -> List[ChatTelegram]:
    return list(sesion.exec(select(ChatTelegram).order_by(ChatTelegram.nombre)).all())


def obtener_chat_telegram(
    sesion: Session, chat_telegram_id: int
) -> Optional[ChatTelegram]:
    return sesion.get(ChatTelegram, chat_telegram_id)


def obtener_chat_telegram_por_chat_id(
    sesion: Session, chat_id: str
) -> Optional[ChatTelegram]:
    return sesion.exec(
        select(ChatTelegram).where(ChatTelegram.chat_id == chat_id)
    ).first()


def crear_chat_telegram(sesion: Session, chat_id: str, nombre: str) -> ChatTelegram:
    chat = ChatTelegram(chat_id=chat_id, nombre=nombre)
    sesion.add(chat)
    sesion.commit()
    sesion.refresh(chat)
    return chat


def actualizar_chat_telegram(
    sesion: Session, chat_telegram_id: int, **campos
) -> Optional[ChatTelegram]:
    chat = sesion.get(ChatTelegram, chat_telegram_id)
    if chat is None:
        return None
    for campo, valor in campos.items():
        setattr(chat, campo, valor)
    sesion.add(chat)
    sesion.commit()
    sesion.refresh(chat)
    return chat


def contar_propiedades_por_chat(sesion: Session, chat_telegram_id: int) -> int:
    """Cuántas propiedades notifican hoy a este chat (para bloquear su
    eliminación mientras siga en uso, en vez de dejar una FK huérfana:
    SQLite no la rechazaría por su cuenta, ya que no forzamos
    PRAGMA foreign_keys=ON)."""
    propiedades = sesion.exec(
        select(Propiedad).where(Propiedad.chat_telegram_id == chat_telegram_id)
    ).all()
    return len(propiedades)


def eliminar_chat_telegram(sesion: Session, chat_telegram_id: int) -> bool:
    chat = sesion.get(ChatTelegram, chat_telegram_id)
    if chat is None:
        return False
    sesion.delete(chat)
    sesion.commit()
    return True


# --- Historial de eventos por propiedad ---


def registrar_evento(
    sesion: Session,
    propiedad_id: int,
    tipo: EventoTipo,
    mensaje: str,
) -> EventoPropiedad:
    """Agrega un evento al historial de la propiedad y recorta lo viejo:
    conserva solo los últimos MAX_EVENTOS_POR_PROPIEDAD (mismo criterio de
    retención acotada que ya se usa para los archivos de log del worker)."""
    evento = EventoPropiedad(propiedad_id=propiedad_id, tipo=tipo, mensaje=mensaje)
    sesion.add(evento)
    sesion.commit()
    sesion.refresh(evento)

    eventos = sesion.exec(
        select(EventoPropiedad)
        .where(EventoPropiedad.propiedad_id == propiedad_id)
        .order_by(EventoPropiedad.ocurrido_en.desc())
    ).all()
    sobrantes = eventos[MAX_EVENTOS_POR_PROPIEDAD:]
    if sobrantes:
        for sobrante in sobrantes:
            sesion.delete(sobrante)
        sesion.commit()

    return evento


def listar_eventos_propiedad(
    sesion: Session, propiedad_id: int, limite: int = MAX_EVENTOS_POR_PROPIEDAD
) -> List[EventoPropiedad]:
    return list(
        sesion.exec(
            select(EventoPropiedad)
            .where(EventoPropiedad.propiedad_id == propiedad_id)
            .order_by(EventoPropiedad.ocurrido_en.desc())
            .limit(limite)
        ).all()
    )


# --- Pruebas efímeras de una URL (antes de conectarla, o al editarla) ---


def _limpiar_pruebas_url_antiguas(sesion: Session) -> None:
    """Las pruebas de URL son datos de scratch, no historial del producto: se
    descartan pasada ANTIGUEDAD_MAXIMA_PRUEBA_URL para que la tabla no crezca
    sin límite en una instancia de larga duración. Nunca se toca una prueba
    todavía 'pendiente' (podría estar por procesarse en el próximo tick)."""
    limite = _ahora_utc() - ANTIGUEDAD_MAXIMA_PRUEBA_URL
    viejas = sesion.exec(
        select(PruebaUrl).where(
            PruebaUrl.estado != EstadoPrueba.pendiente,
            PruebaUrl.creado_en < limite,
        )
    ).all()
    if viejas:
        for vieja in viejas:
            sesion.delete(vieja)
        sesion.commit()


def crear_prueba_url(sesion: Session, url: str) -> PruebaUrl:
    _limpiar_pruebas_url_antiguas(sesion)
    prueba = PruebaUrl(url=url)
    sesion.add(prueba)
    sesion.commit()
    sesion.refresh(prueba)
    return prueba


def obtener_prueba_url(sesion: Session, prueba_id: int) -> Optional[PruebaUrl]:
    return sesion.get(PruebaUrl, prueba_id)


def obtener_pruebas_pendientes(sesion: Session) -> List[PruebaUrl]:
    return list(
        sesion.exec(
            select(PruebaUrl).where(PruebaUrl.estado == EstadoPrueba.pendiente)
        ).all()
    )


def registrar_resultado_prueba_url(
    sesion: Session,
    prueba_id: int,
    estado: EstadoPrueba,
    recuento: Optional[int] = None,
    mensaje_error: Optional[str] = None,
) -> Optional[PruebaUrl]:
    prueba = sesion.get(PruebaUrl, prueba_id)
    if prueba is None:
        return None
    prueba.estado = estado
    prueba.recuento = recuento
    prueba.mensaje_error = mensaje_error
    prueba.completado_en = _ahora_utc()
    sesion.add(prueba)
    sesion.commit()
    sesion.refresh(prueba)
    return prueba

# -*- coding: utf-8 -*-
"""Capa de acceso a datos: toda la lógica de lectura/escritura de propiedades y
chats de Telegram vive acá, para que ni el worker ni la futura API tengan SQL
disperso. No importa `db.py` a propósito, para que se pueda testear con
cualquier Session (ej. un engine SQLite en memoria) sin tocar el archivo real."""

from datetime import datetime, timezone
from typing import List, Optional

from sqlmodel import Session, select

from lindero_core.models import ChatTelegram, EstadoOperativo, Propiedad


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


def forzar_ejecucion_inmediata(
    sesion: Session, propiedad_id: int
) -> Optional[Propiedad]:
    """Marca la propiedad como 'pendiente ya', para que el worker la recoja en
    su próximo tick (hasta ~1 min) en vez de esperar a su hora fija/intervalo."""
    return actualizar_propiedad(sesion, propiedad_id, proxima_ejecucion_en=_ahora_utc())


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

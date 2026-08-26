# -*- coding: utf-8 -*-
"""Tests de los validadores de PropiedadCrear/PropiedadActualizar (sin DB)."""

import pytest
from pydantic import ValidationError

from lindero_core.models import PropiedadActualizar, PropiedadCrear

URL_VALIDA = "https://www.portalinmobiliario.com/venta/departamento/algo"


def _payload_base(**overrides):
    campos = dict(
        nombre="Manuel Montt 2440",
        url_poligono=URL_VALIDA,
        chat_telegram_id=1,
        frecuencia_tipo="hora_fija",
        hora_ejecucion="09:00",
        tz="America/Santiago",
    )
    campos.update(overrides)
    return campos


def test_crear_valida_hora_fija_ok():
    propiedad = PropiedadCrear(**_payload_base())
    assert propiedad.hora_ejecucion == "09:00"


def test_crear_valida_intervalo_ok():
    propiedad = PropiedadCrear(
        **_payload_base(
            frecuencia_tipo="intervalo",
            hora_ejecucion=None,
            intervalo_horas=6,
        )
    )
    assert propiedad.intervalo_horas == 6


@pytest.mark.parametrize("hora_invalida", ["9:00", "09:60", "24:00", "abc", "09-00"])
def test_crear_hora_ejecucion_invalida(hora_invalida):
    with pytest.raises(ValidationError):
        PropiedadCrear(**_payload_base(hora_ejecucion=hora_invalida))


def test_crear_tz_invalida():
    with pytest.raises(ValidationError):
        PropiedadCrear(**_payload_base(tz="Marte/Cráter_Gale"))


def test_crear_intervalo_bajo_el_minimo():
    with pytest.raises(ValidationError):
        PropiedadCrear(
            **_payload_base(
                frecuencia_tipo="intervalo",
                hora_ejecucion=None,
                intervalo_horas=0.5,
            )
        )


@pytest.mark.parametrize(
    "url_invalida",
    [
        "https://www.yapo.cl/algo",
        "https://portalinmobiliario.com.malicioso.io/algo",
        "ftp://www.portalinmobiliario.com/algo",
        "no-es-una-url",
    ],
)
def test_crear_url_fuera_de_dominio(url_invalida):
    with pytest.raises(ValidationError):
        PropiedadCrear(**_payload_base(url_poligono=url_invalida))


def test_crear_url_subdominio_valido():
    propiedad = PropiedadCrear(
        **_payload_base(url_poligono="https://www2.portalinmobiliario.com/algo")
    )
    assert propiedad.url_poligono.startswith("https://www2.portalinmobiliario.com")


def test_crear_hora_fija_sin_hora_ejecucion_falla():
    with pytest.raises(ValidationError):
        PropiedadCrear(**_payload_base(hora_ejecucion=None))


def test_crear_intervalo_sin_intervalo_horas_falla():
    with pytest.raises(ValidationError):
        PropiedadCrear(
            **_payload_base(frecuencia_tipo="intervalo", hora_ejecucion=None)
        )


def test_actualizar_parcial_no_exige_consistencia_cruzada():
    # PropiedadActualizar es un PATCH parcial: no debe exigir hora_ejecucion
    # solo porque no se está tocando frecuencia_tipo en este payload.
    actualizacion = PropiedadActualizar(nombre="Nuevo nombre")
    assert actualizacion.nombre == "Nuevo nombre"
    assert actualizacion.hora_ejecucion is None


def test_actualizar_valida_formato_hora_si_se_envia():
    with pytest.raises(ValidationError):
        PropiedadActualizar(hora_ejecucion="99:99")


def test_actualizar_valida_dominio_url_si_se_envia():
    with pytest.raises(ValidationError):
        PropiedadActualizar(url_poligono="https://www.otrositio.cl/x")

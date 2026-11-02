"""
Piezas de interfaz reutilizables.

El tablero sigue los patrones de iOS: barra de navegacion fija arriba, titulo
grande, control segmentado para cambiar de seccion, menus emergentes para los
filtros y listas de tarjetas blancas sobre fondo gris agrupado. La idea es que
un directivo no tenga que aprender nada: ya usa estos gestos todos los dias.
"""

from __future__ import annotations

import altair as alt
import plotly.graph_objects as go
import streamlit as st

from config import (AZUL, CELESTE, GRIS, IOS_SEC, MORADO, NARANJA, ROSA,
                    VERDE, VIOLETA, plantilla_plotly, tema_altair)

_COLOR_ACENTO = {"azul": AZUL, "naranja": NARANJA, "verde": VERDE,
                 "rosa": ROSA, "morado": MORADO, "celeste": CELESTE,
                 "gris": GRIS}


# --------------------------------------------------------------------------
# Estructura de pagina
# --------------------------------------------------------------------------
def barra_navegacion(subtitulo: str) -> None:
    """Nav bar translucida fija: marca a la izquierda, contexto a la derecha."""
    st.markdown(
        '<div class="ots-nav">'
        '<span class="ots-marca">🧭</span>'
        '<span class="ots-marca-txt">Observatorio de Turismo Sostenible</span>'
        f'<span class="ots-marca-sub">· {subtitulo}</span>'
        '</div>',
        unsafe_allow_html=True)


def titulo_grande(titulo: str, bajada: str) -> None:
    st.markdown(f'<div class="ots-titulo">{titulo}</div>'
                f'<div class="ots-bajada">{bajada}</div>',
                unsafe_allow_html=True)


def grupo(texto: str) -> None:
    """Rotulo de grupo, como los encabezados de las listas de Ajustes."""
    st.markdown(f'<div class="ots-grupo">{texto}</div>', unsafe_allow_html=True)


def par_columnas(izquierda: bool, derecha: bool, pesos=(1, 1)):
    """Dos columnas si ambas graficas estan visibles; si no, una sola a lo ancho.

    Evita el hueco que queda cuando el usuario apaga una de las dos graficas
    de una fila desde el menu "Graficas".
    """
    if izquierda and derecha:
        return st.columns(list(pesos), gap="small")
    unica = st.container()
    return unica, unica


def chips(etiquetas: list[str]) -> None:
    if not etiquetas:
        return
    st.markdown("".join(f'<span class="ots-chip">{e}</span>' for e in etiquetas),
                unsafe_allow_html=True)


# --------------------------------------------------------------------------
# Contenido
# --------------------------------------------------------------------------
GLIFOS = {"azul": "👥", "naranja": "💵", "verde": "🌙", "morado": "⭐",
          "rosa": "⚠️", "celeste": "📈"}


def kpi(rotulo: str, valor: str, sub: str = "", acento: str = "azul",
        tendencia: float | None = None) -> None:
    color = _COLOR_ACENTO[acento]
    glifo = GLIFOS.get(acento, "•")
    if tendencia is None:
        pie = f'<div class="sub">{sub}</div>'
    else:
        clase = "sube" if tendencia >= 0 else "baja"
        flecha = "↑" if tendencia >= 0 else "↓"
        pie = (f'<div class="sub"><span class="{clase}">{flecha} '
               f'{abs(tendencia):,.1f}%</span> {sub}</div>')
    st.markdown(
        f'<div class="ots-kpi">'
        f'<div class="gl" style="background:{color}1F;color:{color}">{glifo}</div>'
        f'<div class="rot">{rotulo}</div>'
        f'<div class="val">{valor}</div>{pie}</div>',
        unsafe_allow_html=True)


def nota(texto: str) -> None:
    st.markdown(f'<div class="ots-nota">{texto}</div>', unsafe_allow_html=True)


def lectura(texto: str) -> None:
    """Como leer la grafica / para que le sirve a un directivo."""
    st.markdown(f'<div class="ots-lectura">{texto}</div>', unsafe_allow_html=True)


def aviso(texto: str) -> None:
    st.markdown(f'<div class="ots-aviso">{texto}</div>', unsafe_allow_html=True)


def sin_datos(mensaje: str) -> None:
    st.markdown(f'<div class="ots-vacio">{mensaje}</div>', unsafe_allow_html=True)


def titulo_grafica(numero: str, titulo: str, pregunta: str,
                   etiquetas: list[str] | None = None) -> None:
    """Cada grafica dice que numero es, que muestra y que pregunta responde."""
    chips_html = ""
    for e in (etiquetas or []):
        clase = ("enlazada" if "Enlazada" in e else
                 "estimacion" if "Estimacion" in e else "")
        chips_html += f'<span class="ots-etq {clase}">{e}</span>'
    st.markdown(
        f'<div class="ots-vt"><span class="ots-vn">{numero}</span> &nbsp;{titulo}</div>'
        f'<div class="ots-vp">{pregunta}</div>{chips_html}',
        unsafe_allow_html=True)


# --------------------------------------------------------------------------
# Graficas
# --------------------------------------------------------------------------
def aplicar_estilo(fig: go.Figure, alto: int = 380, **extra) -> go.Figure:
    """Aplica la plantilla comun y encima lo que pida cada grafica.

    Los diccionarios (margin, xaxis, yaxis...) se fusionan en vez de
    sustituirse, para que una grafica pueda cambiar solo el titulo de un eje
    sin perder la rejilla ni la tipografia de la plantilla.
    """
    base = plantilla_plotly()
    for clave, valor in extra.items():
        if isinstance(valor, dict) and isinstance(base.get(clave), dict):
            base[clave] = {**base[clave], **valor}
        else:
            base[clave] = valor
    fig.update_layout(**base, height=alto)
    return fig


def mostrar(fig: go.Figure, clave: str | None = None):
    st.plotly_chart(fig, width="stretch", key=clave,
                    config={"displayModeBar": False})


def mostrar_tactil(grafico: alt.Chart, clave: str, campo: str,
                   nombre_seleccion: str = "toque") -> str | None:
    """Dibuja una grafica de Altair que responde al toque.

    Devuelve el valor del campo tocado, o None si no hay seleccion.

    Dos decisiones que no son obvias y conviene no deshacer:
    - Se usa Altair y no Plotly para los graficos que originan un enlace,
      porque es la via que entrega el toque al servidor de forma fiable en
      esta version de Streamlit.
    - La grafica NO lleva `.configure(...)`: al fijar la configuracion del
      grafico, Streamlit deja de reportar la seleccion. El estilo se aplica
      entonces desde las propias codificaciones y desde el tema de
      `.streamlit/config.toml`.
    """
    evento = st.altair_chart(grafico, key=clave, on_select="rerun",
                             width="stretch")
    try:
        puntos = evento["selection"][nombre_seleccion]
    except (KeyError, TypeError):
        return None
    if not puntos:
        return None
    valor = puntos[0].get(campo)
    if isinstance(valor, list):
        valor = valor[0] if valor else None
    return valor


# --------------------------------------------------------------------------
# Formato
# --------------------------------------------------------------------------
def miles(x: float) -> str:
    return f"{x:,.0f}".replace(",", " ")


def dinero(x: float) -> str:
    """Formato corto y sin ambiguedad: M = millones, mil M = miles de millones."""
    if abs(x) >= 1_000_000_000:
        return f"US$ {x/1_000_000_000:,.2f} mil M".replace(",", " ")
    if abs(x) >= 1_000_000:
        return f"US$ {x/1_000_000:,.1f} M".replace(",", " ")
    return f"US$ {x:,.0f}".replace(",", " ")

"""
Observatorio de Turismo Sostenible — cuadro de mando interactivo.
Laboratorio 10 · Visualizacion Interactiva · CC3084, UVG.
Laboratorio 11 (MLOps): seccion "Estimaciones oficiales", que solo lee la
version aprobada publicada por el pipeline (results/approved/).

Navegacion con patrones de iOS: barra superior fija, control segmentado para
cambiar de seccion, menus emergentes para los filtros y tarjetas agrupadas.
No hay panel lateral: todo el control vive en la barra de arriba.

Ejecutar:
    streamlit run app/app.py
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import pandas as pd
import streamlit as st

import datos as dt
from componentes import barra_navegacion, chips, grupo, titulo_grande
from config import CSS
from vistas import (exploracion, guia, modelos_vista, panorama, sostenibilidad,
                    version_aprobada)

st.set_page_config(page_title="Observatorio de Turismo Sostenible",
                   page_icon="🧭", layout="wide",
                   initial_sidebar_state="collapsed")
st.markdown(CSS, unsafe_allow_html=True)

# --------------------------------------------------------------------------
# Catalogo de secciones y de graficas que el usuario puede encender o apagar
# --------------------------------------------------------------------------
SECCIONES = {
    "Panorama": ("Panorama",
                 "Que esta pasando ahora mismo en los destinos",
                 panorama.render),
    "Explorar": ("Explorar los datos",
                 "De donde viene la visita, cuando llega y en que gasta",
                 exploracion.render),
    "Sostenibilidad": ("Sostenibilidad",
                       "Presion sobre el destino, huella y beneficio local",
                       sostenibilidad.render),
    "Modelos": ("Modelos y pronosticos",
                "Que esperar los proximos meses y a quien atender",
                modelos_vista.render),
    "Oficial": ("Estimaciones oficiales",
                "Version aprobada del procedimiento: observado, estimacion y estado",
                version_aprobada.render),
    "Guia": ("Guia de lectura",
             "Alcance, colores, glosario y limitaciones",
             guia.render),
}

ICONOS = {"Panorama": ":material/dashboard:", "Explorar": ":material/explore:",
          "Sostenibilidad": ":material/eco:", "Modelos": ":material/insights:",
          "Oficial": ":material/verified:", "Guia": ":material/help:"}

GRAFICAS = {
    "Panorama": ["V1 Mapa de presion", "V2 Evolucion de la visita",
                 "V3 Ranking de destinos", "V4 Volumen frente a valor"],
    "Explorar": ["V5 Mercados emisores", "V6 Estacionalidad",
                 "V7 Composicion del gasto", "V8 Ocupacion y gasto",
                 "V9 Perfil del visitante", "V10 Alojamiento"],
    "Sostenibilidad": ["V11 Desacoplamiento", "V12 Presion por destino",
                       "V13 Perfil de sostenibilidad", "V14 Beneficio local"],
    "Modelos": ["V15 Pronostico", "V16 Validacion del pronostico",
                "V17 Matrices de confusion", "V18 Curvas ROC",
                "V19 Curva de aprendizaje", "V20 Que mueve la recomendacion"],
    "Oficial": version_aprobada.TODAS,
    "Guia": [],
}


# --------------------------------------------------------------------------
# Barra superior: navegacion + filtros en menus emergentes
# --------------------------------------------------------------------------
def navegacion() -> str:
    seccion = st.segmented_control(
        "Seccion", list(SECCIONES), default="Panorama", key="seccion",
        format_func=lambda s: SECCIONES[s][0], label_visibility="collapsed",
        width="stretch")
    return seccion or st.session_state.get("seccion_previa", "Panorama")


def herramientas(mensual: pd.DataFrame, seccion: str) -> dict:
    """Fila de controles tipo barra de herramientas de iOS."""
    anio_min, anio_max = int(mensual["anio"].min()), int(mensual["anio"].max())
    anios = st.session_state.get("anios", (2022, anio_max))
    regiones = st.session_state.get("regiones", [])
    destinos = st.session_state.get("destinos", [])
    catalogo = GRAFICAS[seccion]

    cols = st.columns([1.15, 1.15, 1.25, 1.25, 1.1], gap="small")

    with cols[0]:
        with st.popover(f"Periodo · {anios[0]}–{anios[1]}",
                        icon=":material/calendar_month:", width="stretch"):
            anios = st.slider("Anos incluidos", anio_min, anio_max,
                              anios, key="anios",
                              help="Acota todo el tablero al rango elegido.")

    with cols[1]:
        rotulo = ("Lugar · todos" if not (regiones or destinos)
                  else f"Lugar · {len(destinos) or len(regiones)} elegidos")
        with st.popover(rotulo, icon=":material/place:", width="stretch"):
            regiones = st.multiselect(
                "Region", sorted(mensual["region"].unique()),
                key="regiones", placeholder="Todas las regiones")
            posibles = sorted(
                mensual[mensual["region"].isin(regiones)]["destino"].unique()
                if regiones else mensual["destino"].unique())
            # Si al cambiar de region un destino deja de existir, se descarta
            # antes de dibujar el control para que no quede un filtro fantasma.
            vigentes = [d for d in st.session_state.get("destinos", [])
                        if d in posibles]
            if vigentes != st.session_state.get("destinos", []):
                st.session_state["destinos"] = vigentes
            destinos = st.multiselect(
                "Destino", posibles, key="destinos",
                placeholder="Todos los destinos")

    with cols[2]:
        nivel = st.session_state.get("nivel_tiempo", "Mes")
        with st.popover(f"Detalle · {nivel.lower()}",
                        icon=":material/tune:", width="stretch"):
            nivel = st.segmented_control(
                "Agregacion temporal", ["Ano", "Trimestre", "Mes"],
                default=nivel, key="nivel_tiempo", width="stretch",
                help="Izquierda: tendencia de fondo. Derecha: detalle mes a mes.")
            detalle = st.segmented_control(
                "Profundidad del contenido",
                ["Resumen ejecutivo", "Analisis completo"],
                default=st.session_state.get("detalle", "Analisis completo"),
                key="detalle", width="stretch",
                help="El resumen ejecutivo deja solo la lectura principal de "
                     "cada grafica y oculta las notas metodologicas.")
        nivel = nivel or "Mes"
        detalle = st.session_state.get("detalle") or "Analisis completo"

    with cols[3]:
        if catalogo:
            activas = st.session_state.get(f"activas_{seccion}", catalogo)
            with st.popover(f"Graficas · {len(activas)} de {len(catalogo)}",
                            icon=":material/bar_chart:", width="stretch"):
                activas = st.multiselect(
                    "Graficas visibles en esta seccion", catalogo,
                    default=catalogo, key=f"activas_{seccion}",
                    placeholder="Ninguna grafica seleccionada")
        else:
            activas = []
            st.empty()

    with cols[4]:
        if st.button("Restablecer", icon=":material/restart_alt:",
                     width="stretch", help="Vuelve a la vista inicial."):
            for clave in ["anios", "regiones", "destinos", "nivel_tiempo",
                          "detalle", "destino_foco", "mercado_foco",
                          f"activas_{seccion}"]:
                st.session_state.pop(clave, None)
            st.rerun()

    return {"anios": tuple(anios), "regiones": regiones, "destinos": destinos,
            "nivel_tiempo": nivel, "detalle": detalle,
            "graficas_activas": activas}


def estado_actual(opc: dict) -> None:
    """Pildoras que resumen, en una linea, que esta viendo el usuario."""
    etiquetas = [f"{opc['anios'][0]}–{opc['anios'][1]}"]
    if opc["destinos"]:
        etiquetas += opc["destinos"]
    elif opc["regiones"]:
        etiquetas += opc["regiones"]
    else:
        etiquetas.append("Todos los destinos")
    foco = st.session_state.get("destino_foco")
    if foco:
        etiquetas.append(f"Enfoque: {foco}")
    foco_m = st.session_state.get("mercado_foco")
    if foco_m:
        etiquetas.append(f"Mercado: {foco_m}")
    chips(etiquetas)

    if foco or foco_m:
        if st.button("Quitar enfoque", icon=":material/close:",
                     key="quitar_foco"):
            st.session_state.pop("destino_foco", None)
            st.session_state.pop("mercado_foco", None)
            st.rerun()


# --------------------------------------------------------------------------
def preparar(base: dict[str, pd.DataFrame], opc: dict) -> dict:
    anios = opc["anios"]
    largo = anios[1] - anios[0] + 1
    previos = (anios[0] - largo, anios[0] - 1)
    todos = (int(base["mensual"]["anio"].min()), int(base["mensual"]["anio"].max()))

    mensual = dt.filtrar(base["mensual"], anios, opc["destinos"], opc["regiones"])
    mensual_completo = dt.filtrar(base["mensual"], todos, opc["destinos"],
                                  opc["regiones"])
    mensual_previo = dt.filtrar(base["mensual"], previos, opc["destinos"],
                                opc["regiones"])
    mercados = dt.filtrar(base["mercados"], anios, opc["destinos"], opc["regiones"])
    visitantes = dt.filtrar(base["visitantes"], anios, opc["destinos"],
                            opc["regiones"])

    # El enfoque que nace del toque en V3 (o V1) se propaga a las secciones de
    # detalle. En Panorama no se filtra: ahi la gracia es comparar contra el total.
    foco = st.session_state.get("destino_foco")
    if foco and foco in set(mensual["destino"]):
        det_m, det_v, det_k = (mensual[mensual["destino"] == foco],
                               visitantes[visitantes["destino"] == foco],
                               mercados[mercados["destino"] == foco])
    else:
        det_m, det_v, det_k = mensual, visitantes, mercados

    ctx = dict(opc)
    ctx.update({"mensual": mensual, "mensual_previo": mensual_previo,
                "mensual_completo": mensual_completo, "mercados": mercados,
                "visitantes": visitantes, "detalle_mensual": det_m,
                "detalle_visitantes": det_v, "detalle_mercados": det_k})
    return ctx


def main() -> None:
    base = dt.cargar()

    seccion = st.session_state.get("seccion") or "Panorama"
    titulo, bajada, _ = SECCIONES[seccion]
    barra_navegacion(titulo)

    seccion = navegacion() or seccion
    titulo, bajada, render = SECCIONES[seccion]

    titulo_grande(titulo, bajada)
    opc = herramientas(base["mensual"], seccion)
    estado_actual(opc)

    ctx = preparar(base, opc)
    if seccion in ("Explorar", "Sostenibilidad"):
        ctx = {**ctx, "mensual": ctx["detalle_mensual"],
               "visitantes": ctx["detalle_visitantes"],
               "mercados": ctx["detalle_mercados"]}

    render(ctx)


if __name__ == "__main__":
    main()

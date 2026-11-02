"""
Seccion Modelos: pronostico de demanda (V15-V16) y clasificacion de
visitantes promotores (V17-V20).

Todo lo que se dibuja aqui es ESTIMACION de un modelo, salvo la serie
observada de llegadas: lo observado va en linea continua azul y lo estimado
en linea punteada con el color fijo de cada modelo.
"""

from __future__ import annotations

import numpy as np
import pandas as pd
import plotly.graph_objects as go
import streamlit as st
from plotly.subplots import make_subplots

import datos as dt
import modelos as md
from componentes import (aplicar_estilo, aviso, grupo, lectura, miles, mostrar,
                         nota, par_columnas, sin_datos, titulo_grafica)
from config import (AZUL, COLOR_MODELO, GRIS, MORADO, NARANJA, ROSA,
                    SECUENCIAL, VERDE)

V15 = "V15 Pronostico"
V16 = "V16 Validacion del pronostico"
V17 = "V17 Matrices de confusion"
V18 = "V18 Curvas ROC"
V19 = "V19 Curva de aprendizaje"
V20 = "V20 Que mueve la recomendacion"
TODAS = [V15, V16, V17, V18, V19, V20]

MESES_HISTORIA = 36          # meses observados que se muestran antes del pronostico
MIN_ENCUESTAS = 300          # por debajo, la curva de aprendizaje y k-vecinos no son fiables
MIN_POR_CLASE = 40

ETIQUETA_CLASE = ["No recomienda", "Recomienda"]

# Los nombres que entrega modelos._nombres_variables para las categoricas
# vienen como "tipo: alojamiento_Ecolodge"; aqui se pasan a lenguaje llano.
_PREFIJOS = {
    "destino: ": "Destino: ",
    "mercado: ": "Mercado: ",
    "grupo: viaje_": "Viaja en: ",
    "tipo: alojamiento_": "Alojamiento: ",
    "transporte: principal_": "Transporte: ",
}
_COLUMNAS = {
    "Destino": "Destino", "Mercado": "Mercado emisor",
    "Grupo_viaje": "Con quien viaja", "Tipo_alojamiento": "Tipo de alojamiento",
    "Transporte_principal": "Transporte principal",
}


# --------------------------------------------------------------------------
# Utilidades
# --------------------------------------------------------------------------
def _rgba(hex_color: str, alfa: float) -> str:
    h = hex_color.lstrip("#")
    r, g, b = int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16)
    return f"rgba({r},{g},{b},{alfa})"


def _nombre_variable(nombre: str) -> str:
    for prefijo, nuevo in _PREFIJOS.items():
        if nombre.startswith(prefijo):
            return nuevo + nombre[len(prefijo):]
    return _COLUMNAS.get(nombre, nombre)


def _mes_anio(fecha: pd.Timestamp) -> str:
    return f"{dt.NOMBRES_MES[fecha.month - 1]} {fecha.year}"


def _pct(x: float) -> str:
    return f"{x:.1f}%"


# --------------------------------------------------------------------------
# Entrada
# --------------------------------------------------------------------------
def render(ctx: dict) -> None:
    activas = ctx.get("graficas_activas")
    activas = TODAS if activas is None else activas
    if not activas:
        sin_datos("No hay graficas seleccionadas en esta seccion. Abra el menu "
                  "<b>Graficas</b> de la barra superior y elija al menos una.")
        return
    completo = ctx.get("detalle") != "Resumen ejecutivo"

    if V15 in activas or V16 in activas:
        _seccion_pronostico(ctx, activas, completo)
    if any(v in activas for v in (V17, V18, V19, V20)):
        _seccion_clasificacion(ctx, activas, completo)


# ==========================================================================
# PRONOSTICO DE DEMANDA
# ==========================================================================
def _seccion_pronostico(ctx: dict, activas: list[str], completo: bool) -> None:
    grupo("PRONOSTICO DE DEMANDA")

    lugar = (", ".join(ctx.get("destinos") or []) or
             ", ".join(ctx.get("regiones") or []) or "todos los destinos")
    aviso(f"Los modelos usan <b>toda la historia 2017-2025</b> de {lugar}: el "
          "filtro de lugar si se aplica, pero el de periodo no, porque un "
          "pronostico necesita varios anos completos para aprender la tendencia "
          "y el patron de cada mes.")

    serie = dt.serie_nacional(ctx["mensual_completo"])
    if len(serie) < 48 or (serie["llegadas"] <= 0).any():
        sin_datos("No hay suficiente historia mensual para entrenar los modelos "
                  "de pronostico con este filtro de lugar. Pruebe con otro "
                  "destino o pulse <b>Restablecer</b>.")
        return

    try:
        resultados = md.pronosticar(serie)
    except Exception as err:  # el tablero no debe caerse por un ajuste fallido
        sin_datos(f"No fue posible entrenar los modelos de pronostico con este "
                  f"filtro ({type(err).__name__}). Pruebe con otro lugar.")
        return

    tabla = md.tabla_serie(resultados)
    mejor = tabla.iloc[0]["Modelo"]

    elegidos = st.segmented_control(
        "Modelos a mostrar", md.MODELOS_SERIE, selection_mode="multi",
        default=md.MODELOS_SERIE, key="modelos_serie", width="stretch",
        help="Encienda o apague cada modelo en V15 y V16.")
    elegidos = [m for m in md.MODELOS_SERIE if m in (elegidos or [])]

    if V15 in activas:
        with st.container(border=True):
            titulo_grafica("V15", "Pronostico de visitantes a 12 meses",
                           "¿Cuanta visita se espera en los proximos 12 meses y "
                           "con que margen?",
                           ["Serie de tiempo", "Banda de confianza", "Estimacion"])
            if not elegidos:
                sin_datos("Elija al menos un modelo en <b>Modelos a mostrar</b>.")
            else:
                _v15(serie, resultados, elegidos, mejor, completo)

    if V16 in activas:
        with st.container(border=True):
            titulo_grafica("V16", "Prueba contra la realidad",
                           "¿Que tan confiable es cada modelo frente a meses que "
                           "no vio al entrenar?",
                           ["Serie de tiempo", "Observado vs. estimado", "Estimacion"])
            if not elegidos:
                sin_datos("Elija al menos un modelo en <b>Modelos a mostrar</b>.")
            else:
                _v16(resultados, elegidos, tabla, completo)


def _v15(serie, resultados, elegidos, mejor, completo) -> None:
    historia = serie.tail(MESES_HISTORIA)
    fig = go.Figure()
    fig.add_trace(go.Scatter(
        x=historia["fecha"], y=historia["llegadas"], name="Observado",
        mode="lines", line=dict(color=AZUL, width=2.6),
        hovertemplate="%{x|%b %Y}<br>Observado: %{y:,.0f}<extra></extra>"))

    ultimo = serie.iloc[-1]
    for nombre in elegidos:
        r = resultados[nombre]
        color = COLOR_MODELO[nombre]
        fut = r.futuro
        fig.add_trace(go.Scatter(
            x=list(fut["fecha"]) + list(fut["fecha"][::-1]),
            y=list(fut["superior"]) + list(fut["inferior"][::-1]),
            fill="toself", fillcolor=_rgba(color, 0.10),
            line=dict(width=0), hoverinfo="skip", showlegend=False,
            legendgroup=nombre, name=f"Banda {nombre}"))
        # se une al ultimo mes observado para que no quede un salto visual
        xs = [ultimo["fecha"], *fut["fecha"]]
        ys = [ultimo["llegadas"], *fut["estimado"]]
        fig.add_trace(go.Scatter(
            x=xs, y=ys, name=nombre, legendgroup=nombre, mode="lines",
            line=dict(color=color, width=2.3, dash="dash"),
            customdata=np.column_stack([
                [ultimo["llegadas"], *fut["inferior"]],
                [ultimo["llegadas"], *fut["superior"]]]),
            hovertemplate=(f"{nombre}<br>%{{x|%b %Y}}: %{{y:,.0f}}"
                           "<br>Rango: %{customdata[0]:,.0f} - %{customdata[1]:,.0f}"
                           "<extra></extra>")))

    fig.add_vline(x=ultimo["fecha"], line=dict(color=GRIS, width=1, dash="dot"))
    fig.add_annotation(x=ultimo["fecha"], y=1, yref="paper", text="Hoy  ",
                       showarrow=False, xanchor="right", yanchor="top",
                       font=dict(size=11, color=GRIS))

    # el eje Y se acota a la serie y a los pronosticos: las bandas muy anchas
    # (tendencia, arrastra la caida de la pandemia) no deben aplastar la linea
    techo = max(historia["llegadas"].max(),
                *[resultados[n].futuro["estimado"].max() for n in elegidos]) * 1.35
    aplicar_estilo(fig, alto=420, hovermode="x unified",
                   yaxis=dict(title="Visitantes por mes", rangemode="tozero",
                              range=[0, techo]),
                   xaxis=dict(title=None))
    mostrar(fig, clave="v15")

    ref = mejor if mejor in elegidos else elegidos[0]
    fut = resultados[ref].futuro
    total_fut = fut["estimado"].sum()
    total_prev = serie.tail(12)["llegadas"].sum()
    cambio = (total_fut / total_prev - 1) * 100
    pico = fut.loc[fut["estimado"].idxmax()]
    lectura(
        f"Segun <b>{ref}</b>{' (el que menos se equivoco en la prueba)' if ref == mejor else ''}, "
        f"se esperan <b>{miles(total_fut)} visitantes</b> en los proximos 12 meses, "
        f"{'un' if cambio >= 0 else 'una caida del'} {_pct(abs(cambio))} "
        f"{'mas que' if cambio >= 0 else 'frente a'} los ultimos 12 meses observados. "
        f"El mes mas cargado seria <b>{_mes_anio(pico['fecha'])}</b> "
        f"(~{miles(pico['estimado'])}, entre {miles(pico['inferior'])} y "
        f"{miles(pico['superior'])}). Planifique personal y aforos con el "
        "extremo alto de la banda, no con la linea central.")
    if completo:
        nota("Linea continua = dato observado; lineas punteadas = estimacion. La "
             "banda es el rango del 95%: en SARIMA es el intervalo calculado por "
             "el modelo; en Tendencia + estacionalidad y Holt-Winters es una "
             "aproximacion a partir de los residuos. La banda de Tendencia + "
             "estacionalidad es muy ancha porque la caida de 2020-2021 infla su "
             "error. Los modelos proyectan la continuidad del patron historico: no "
             "incorporan nuevas rutas, crisis ni campanas de promocion.")


def _v16(resultados, elegidos, tabla, completo) -> None:
    prueba = resultados[elegidos[0]].prueba
    fig = go.Figure()
    fig.add_trace(go.Scatter(
        x=prueba["fecha"], y=prueba["real"], name="Observado",
        mode="lines+markers", line=dict(color=AZUL, width=2.6),
        marker=dict(size=6),
        hovertemplate="%{x|%b %Y}<br>Observado: %{y:,.0f}<extra></extra>"))
    for nombre in elegidos:
        p = resultados[nombre].prueba
        err = (p["estimado"] / p["real"] - 1) * 100
        fig.add_trace(go.Scatter(
            x=p["fecha"], y=p["estimado"], name=nombre, mode="lines+markers",
            line=dict(color=COLOR_MODELO[nombre], width=2.1, dash="dash"),
            marker=dict(size=5, symbol="diamond"), customdata=err,
            hovertemplate=(f"{nombre}<br>%{{x|%b %Y}}: %{{y:,.0f}}"
                           "<br>Desvio: %{customdata:+.1f}%<extra></extra>")))
    aplicar_estilo(fig, alto=360, hovermode="x unified",
                   yaxis=dict(title="Visitantes por mes"), xaxis=dict(title=None))
    mostrar(fig, clave="v16")

    sub = tabla[tabla["Modelo"].isin(elegidos)].reset_index(drop=True)
    mejor = sub.iloc[0]
    texto = (f"En los 12 meses de prueba, <b>{mejor['Modelo']}</b> es el mas "
             f"confiable: se equivoca en promedio un "
             f"<b>{_pct(mejor['Error porcentual (MAPE)'])}</b> "
             f"(unos {miles(mejor['Error medio (visitantes)'])} visitantes por mes).")
    if len(sub) > 1:
        peor = sub.iloc[-1]
        texto += (f" El menos preciso, {peor['Modelo']}, se equivoca un "
                  f"{_pct(peor['Error porcentual (MAPE)'])}. Use el primero para "
                  "planificar y los demas como contraste.")
    lectura(texto)

    st.dataframe(
        tabla, hide_index=True, width="stretch",
        column_config={
            "Error medio (visitantes)": st.column_config.NumberColumn(
                help="MAE: diferencia media entre lo estimado y lo observado.",
                format="%d"),
            "RMSE": st.column_config.NumberColumn(
                help="Castiga mas los errores grandes.", format="%d"),
            "Error porcentual (MAPE)": st.column_config.NumberColumn(
                help="Error medio en % del valor real. Es la metrica que se "
                     "comunica.", format="%.2f%%"),
        })
    if completo:
        nota("Los ultimos 12 meses de la serie se reservaron: los modelos se "
             "entrenaron sin verlos y despues se compararon contra lo que paso. "
             "El pronostico de V15 se re-entrena con la serie completa. " +
             " ".join(f"<b>{n}</b>: {md.EXPLICACION_SERIE[n]}" for n in elegidos))


# ==========================================================================
# QUIEN RECOMIENDA EL DESTINO
# ==========================================================================
def _seccion_clasificacion(ctx: dict, activas: list[str], completo: bool) -> None:
    grupo("QUIEN RECOMIENDA EL DESTINO")

    vis = ctx["visitantes"]
    n = len(vis)
    conteo = vis["promotor"].value_counts() if n else pd.Series(dtype=int)
    if n < MIN_ENCUESTAS or len(conteo) < 2 or conteo.min() < MIN_POR_CLASE:
        sin_datos(
            f"Con los filtros actuales hay {miles(n)} encuestas"
            f"{'' if len(conteo) >= 2 or n == 0 else ' y todas con la misma respuesta'}"
            f"; se necesitan al menos {MIN_ENCUESTAS} con promotores y no "
            "promotores para entrenar los clasificadores. La encuesta cubre solo "
            "<b>2023-2025</b>: amplie el <b>Periodo</b> a esos anos o elija mas "
            "destinos en <b>Lugar</b>.")
        return

    try:
        resultados = md.clasificar(vis)
    except Exception as err:
        sin_datos(f"No fue posible entrenar los clasificadores con este filtro "
                  f"({type(err).__name__}). Amplie el periodo o el lugar.")
        return

    tabla = md.tabla_clase(resultados)
    st.dataframe(
        tabla, hide_index=True, width="stretch",
        column_config={
            "Exactitud": st.column_config.NumberColumn(
                help="Proporcion de visitantes bien clasificados.", format="%.3f"),
            "Precision": st.column_config.NumberColumn(
                help="De los que el modelo dice que recomiendan, cuantos si lo hacen.",
                format="%.3f"),
            "Exhaustividad": st.column_config.NumberColumn(
                help="De los que si recomiendan, cuantos detecta el modelo.",
                format="%.3f"),
            "F1": st.column_config.NumberColumn(
                help="Balance entre precision y exhaustividad.", format="%.3f"),
            "AUC": st.column_config.NumberColumn(
                help="Capacidad de ordenar promotores por encima de no promotores "
                     "(0.5 = azar, 1 = perfecto).", format="%.3f"),
        })
    if completo:
        nota(f"Entrenado con {miles(n)} encuestas (75% para aprender, 25% para "
             "evaluar, con la misma proporcion de promotores en ambas partes). "
             "<b>calificacion_general</b> se excluye a proposito: se conoce despues "
             "del hecho que se quiere anticipar.")

    if V17 in activas:
        with st.container(border=True):
            titulo_grafica("V17", "Aciertos y errores de cada modelo",
                           "De cada visitante que llega, ¿quien termina "
                           "recomendando el destino?",
                           ["Matriz de confusion", "Estimacion"])
            _v17(resultados, tabla, completo)

    v18, v19 = V18 in activas, V19 in activas
    izq, der = par_columnas(v18, v19)
    if v18:
        with izq:
            with st.container(border=True):
                titulo_grafica("V18", "Capacidad de distinguir promotores",
                               "¿Que modelo separa mejor a quien recomienda de "
                               "quien no, sin importar el umbral?",
                               ["Curvas ROC", "Estimacion"])
                _v18(resultados, tabla, completo)
    if v19:
        with der:
            with st.container(border=True):
                titulo_grafica("V19", "¿Sirve seguir encuestando?",
                               "¿Mejoraria el modelo si se hicieran mas encuestas "
                               "del mismo tipo?",
                               ["Curva de aprendizaje", "Estimacion"])
                _v19(resultados, tabla, completo)

    if V20 in activas:
        with st.container(border=True):
            titulo_grafica("V20", "Que mueve la recomendacion",
                           "¿Sobre que palancas puede actuar la gestion del "
                           "destino para ganar promotores?",
                           ["Barras divergentes", "Estimacion"])
            _v20(resultados, completo)


def _v17(resultados, tabla, completo) -> None:
    nombres = list(md.MODELOS_CLASE)
    fig = make_subplots(rows=1, cols=3, subplot_titles=nombres,
                        horizontal_spacing=0.06)
    zmax = max(int(resultados[n].matriz.max()) for n in nombres)
    for i, nombre in enumerate(nombres, start=1):
        m = resultados[nombre].matriz
        fila_tot = m.sum(axis=1, keepdims=True)
        pct = np.divide(m, fila_tot, out=np.zeros_like(m, dtype=float),
                        where=fila_tot > 0) * 100
        texto = [[f"{miles(m[r, c])}<br>({pct[r, c]:.0f}%)" for c in range(2)]
                 for r in range(2)]
        fig.add_trace(go.Heatmap(
            z=m, x=ETIQUETA_CLASE, y=ETIQUETA_CLASE, text=texto,
            texttemplate="%{text}", textfont=dict(size=13),
            colorscale=[[k / (len(SECUENCIAL) - 1), c] for k, c in enumerate(SECUENCIAL)],
            zmin=0, zmax=zmax, showscale=False, xgap=3, ygap=3,
            hovertemplate=("En realidad: %{y}<br>El modelo dijo: %{x}"
                           "<br>Visitantes: %{z:,}<extra>" + nombre + "</extra>")),
            row=1, col=i)
        fig.update_xaxes(title_text="Lo que dijo el modelo", row=1, col=i,
                         showgrid=False, side="bottom")
        fig.update_yaxes(title_text="Lo que paso en realidad" if i == 1 else None,
                         row=1, col=i, showgrid=False, autorange="reversed",
                         showticklabels=(i == 1))
    aplicar_estilo(fig, alto=340, margin=dict(t=40))
    fig.update_annotations(font=dict(size=13))
    mostrar(fig, clave="v17")

    ref = tabla.iloc[0]["Modelo"]
    m = resultados[ref].matriz
    no_prom, prom = int(m[0].sum()), int(m[1].sum())
    perdida, falsa = int(m[0, 1]), int(m[1, 0])
    lectura(
        f"Con <b>{ref}</b> (el de mejor AUC), de {miles(no_prom)} visitantes que "
        f"<b>no</b> recomendarian, el modelo da por satisfechos a {miles(perdida)} "
        f"({perdida / max(no_prom, 1) * 100:.0f}%): son <b>oportunidades perdidas</b>, "
        "visitantes descontentos a los que nadie atenderia. En cambio, solo "
        f"{miles(falsa)} de {miles(prom)} promotores ({falsa / max(prom, 1) * 100:.0f}%) "
        "serian una <b>falsa alarma</b> (esfuerzo de atencion sobre alguien que ya "
        "estaba contento). Los tres modelos aciertan mucho con los promotores y "
        "poco con los descontentos: uselos para priorizar, no para descartar.")
    if completo:
        nota("Cada fila suma el total real de esa clase; el porcentaje es sobre la "
             "fila. Se usa el umbral de 0.5 de probabilidad. Subir el umbral para "
             "'Recomienda' reduciria las oportunidades perdidas a cambio de mas "
             "falsas alarmas.")


def _v18(resultados, tabla, completo) -> None:
    fig = go.Figure()
    fig.add_trace(go.Scatter(
        x=[0, 1], y=[0, 1], mode="lines", name="Azar (AUC 0.50)",
        line=dict(color=GRIS, width=1.4, dash="dot"), hoverinfo="skip"))
    for nombre in tabla["Modelo"]:
        r = resultados[nombre]
        fpr, tpr = r.roc
        fig.add_trace(go.Scatter(
            x=fpr, y=tpr, mode="lines",
            name=f"{nombre} (AUC {r.metricas['AUC']:.2f})",
            line=dict(color=COLOR_MODELO[nombre], width=2.3),
            hovertemplate=(f"{nombre}<br>Falsas alarmas: %{{x:.0%}}"
                           "<br>Promotores detectados: %{y:.0%}<extra></extra>")))
    aplicar_estilo(fig, alto=380,
                   xaxis=dict(title="Descontentos marcados como promotores",
                              range=[0, 1], tickformat=".0%"),
                   yaxis=dict(title="Promotores detectados", range=[0, 1.02],
                              tickformat=".0%"),
                   legend=dict(orientation="v", y=0.02, yanchor="bottom",
                               x=0.98, xanchor="right",
                               bgcolor="rgba(255,255,255,0.8)"))
    mostrar(fig, clave="v18")

    mejor = tabla.iloc[0]
    auc = mejor["AUC"]
    nivel = ("buena" if auc >= 0.8 else "moderada" if auc >= 0.7 else "modesta")
    lectura(
        f"<b>{mejor['Modelo']}</b> discrimina mejor (AUC {auc:.2f}): si se toma al "
        "azar un promotor y un no promotor, el modelo le da mas probabilidad al "
        f"promotor el {auc * 100:.0f}% de las veces. Es una capacidad {nivel}: util "
        "para ordenar a quien atender primero, no para decidir caso por caso. "
        "Cuanto mas se aleja una curva de la diagonal gris, mejor.")
    if completo:
        nota("La curva recorre todos los umbrales posibles; el AUC es el area bajo "
             "ella. Calculado sobre el 25% de encuestas reservadas para evaluar.")


def _v19(resultados, tabla, completo) -> None:
    nombre = st.segmented_control(
        "Modelo", md.MODELOS_CLASE, default=tabla.iloc[0]["Modelo"],
        key="modelo_aprendizaje", width="stretch") or tabla.iloc[0]["Modelo"]
    c = resultados[nombre].curva_aprendizaje.dropna()
    if c.empty:
        sin_datos("La curva de aprendizaje no pudo calcularse con tan pocas "
                  "encuestas. Amplie el periodo o el lugar.")
        return
    color = COLOR_MODELO[nombre]
    fig = go.Figure()
    sup = c["validacion"] + c["validacion_sd"]
    inf = c["validacion"] - c["validacion_sd"]
    fig.add_trace(go.Scatter(
        x=list(c["tamano"]) + list(c["tamano"][::-1]),
        y=list(sup) + list(inf[::-1]), fill="toself",
        fillcolor=_rgba(color, 0.15), line=dict(width=0), hoverinfo="skip",
        showlegend=False))
    fig.add_trace(go.Scatter(
        x=c["tamano"], y=c["entrenamiento"], name="Con encuestas ya vistas",
        mode="lines+markers", line=dict(color=GRIS, width=2, dash="dash"),
        hovertemplate="%{x:,} encuestas<br>AUC entrenamiento: %{y:.3f}<extra></extra>"))
    fig.add_trace(go.Scatter(
        x=c["tamano"], y=c["validacion"], name="Con encuestas nuevas",
        mode="lines+markers", line=dict(color=color, width=2.5, dash="dash"),
        hovertemplate="%{x:,} encuestas<br>AUC validacion: %{y:.3f}<extra></extra>"))
    piso = float(min(inf.min(), c["entrenamiento"].min()))
    aplicar_estilo(fig, alto=340,
                   xaxis=dict(title="Encuestas usadas para entrenar"),
                   yaxis=dict(title="AUC", range=[max(0.45, piso - 0.03), 1.02]))
    mostrar(fig, clave="v19")

    ult = c.iloc[-1]
    brecha = ult["entrenamiento"] - ult["validacion"]
    if len(c) >= 2:
        pen = c.iloc[-1]["validacion"] - c.iloc[-2]["validacion"]
        extra = c.iloc[-1]["tamano"] - c.iloc[-2]["tamano"]
    else:
        pen, extra = 0.0, 0
    if pen < 0.005:
        msg = (f"La curva de validacion ya esta plana: las ultimas {miles(extra)} "
               f"encuestas solo movieron el AUC en {pen:+.3f}. <b>Mas encuestas del "
               "mismo tipo casi no mejorarian el modelo</b>; rinde mas preguntar "
               "cosas nuevas (otras variables) que encuestar a mas gente.")
    else:
        msg = (f"La curva todavia sube ({pen:+.3f} de AUC con las ultimas "
               f"{miles(extra)} encuestas): <b>ampliar la muestra aun ayuda</b>.")
    if brecha > 0.15:
        msg += (f" La distancia entre las dos lineas es grande ({brecha:.2f}): "
                f"{nombre} memoriza las encuestas que ya vio, lo que infla su "
                "acierto en entrenamiento.")
    elif brecha < 0.03:
        msg += " Ambas lineas casi se tocan: el modelo no esta sobreajustado."
    lectura(msg)
    if completo:
        nota("Validacion cruzada en 4 partes; la banda es +/- 1 desviacion estandar "
             "del AUC de validacion entre esas partes.")


def _v20(resultados, completo) -> None:
    nombre = st.segmented_control(
        "Modelo", md.MODELOS_CLASE, default=md.MODELOS_CLASE[0],
        key="modelo_importancia", width="stretch") or md.MODELOS_CLASE[0]
    r = resultados[nombre]
    imp = r.importancia.copy()
    imp["variable"] = imp["variable"].map(_nombre_variable)
    imp = imp.iloc[::-1]          # la mas importante arriba

    fig = go.Figure()
    if r.tipo_importancia == "coeficiente":
        colores = [VERDE if p >= 0 else ROSA for p in imp["peso"]]
        fig.add_trace(go.Bar(
            x=imp["peso"], y=imp["variable"], orientation="h",
            marker=dict(color=colores),
            text=[f"{p:+.2f}" for p in imp["peso"]], textposition="outside",
            cliponaxis=False,
            hovertemplate="%{y}<br>Coeficiente: %{x:+.3f}<extra></extra>"))
        fig.add_vline(x=0, line=dict(color=GRIS, width=1))
        eje = "Efecto sobre la probabilidad de recomendar (coeficiente)"
    else:
        colores = [NARANJA if p > 0 else GRIS for p in imp["peso"]]
        fig.add_trace(go.Bar(
            x=imp["magnitud"], y=imp["variable"], orientation="h",
            marker=dict(color=colores),
            text=[f"{p:.3f}" for p in imp["magnitud"]], textposition="outside",
            cliponaxis=False,
            hovertemplate="%{y}<br>Importancia: %{x:.3f}<extra></extra>"))
        eje = ("Importancia en el arbol" if r.tipo_importancia == "importancia"
               else "Perdida de AUC al desordenar la variable")
    aplicar_estilo(fig, alto=430, showlegend=False,
                   xaxis=dict(title=eje), yaxis=dict(title=None),
                   margin=dict(r=40))
    mostrar(fig, clave="v20")

    if r.tipo_importancia == "coeficiente":
        pos = imp[imp["peso"] > 0].sort_values("peso", ascending=False)["variable"].head(3)
        neg = imp[imp["peso"] < 0].sort_values("peso")["variable"].head(2)
        lectura(
            "En verde lo que se <b>asocia</b> con mas recomendacion y en rosa lo que "
            f"la resta. Suman: {', '.join(pos) or 'ningun factor claro'}. Restan: "
            f"{', '.join(neg) or 'ningun factor claro'}. Las palancas operables "
            "(guia local, actividades, reducir incidencias) son las candidatas a "
            "priorizar; es una asociacion en una encuesta, no un efecto causal "
            "comprobado.")
    else:
        aviso(f"<b>{nombre}</b> no tiene direccion: dice <i>cuanto</i> pesa cada "
              "factor, pero no si suma o resta. Para saber el sentido, mire la "
              "Regresion logistica.")
        top = imp.sort_values("magnitud", ascending=False)["variable"].head(3)
        lectura(f"Los factores que mas pesan para {nombre} son: "
                f"<b>{', '.join(top)}</b>. Si coinciden con los de la regresion "
                "logistica, la conclusion es robusta al modelo elegido.")
    if completo:
        textos = {
            "coeficiente": "Coeficientes sobre variables estandarizadas: comparan "
                           "el efecto de mover cada factor una desviacion tipica. "
                           "Para destino, mercado y demas categorias el efecto es "
                           "relativo a la primera categoria de cada lista.",
            "importancia": "Importancia de Gini: cuanto reduce cada variable la "
                           "impureza de las particiones del arbol.",
            "permutacion": "Importancia por permutacion: cuanto cae el AUC cuando "
                           "se desordena esa variable. Valores cercanos a cero o "
                           "negativos (gris) indican que la variable no aporta.",
        }
        nota(textos[r.tipo_importancia] + " Se muestran los 12 factores de mayor "
             "magnitud. " + md.EXPLICACION_CLASE[nombre])

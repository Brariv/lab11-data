"""
Seccion Panorama: que esta pasando ahora mismo en los destinos.

V1 Mapa de presion · V2 Evolucion de la visita · V3 Ranking de destinos
(origen del enlace: el toque fija st.session_state["destino_foco"]) ·
V4 Volumen frente a valor.
"""

from __future__ import annotations

import altair as alt
import pandas as pd
import plotly.graph_objects as go
import streamlit as st

import datos as dt
from componentes import (aplicar_estilo, dinero, grupo, kpi, lectura, miles,
                         mostrar, mostrar_tactil, nota, par_columnas,
                         sin_datos, titulo_grafica)
from config import (AZUL, COLOR_DESTINO, DIVERGENTE, GRIS, IOS_SEC, LINEA,
                    NARANJA, TINTA, TIPOGRAFIA)

V1, V2, V3, V4 = ("V1 Mapa de presion", "V2 Evolucion de la visita",
                  "V3 Ranking de destinos", "V4 Volumen frente a valor")
TODAS = [V1, V2, V3, V4]


# --------------------------------------------------------------------------
def _por_destino(df: pd.DataFrame) -> pd.DataFrame:
    """Una fila por destino con volumen, derrama y presion media del periodo."""
    out = (df.groupby("destino", as_index=False)
             .agg(llegadas=("llegadas", "sum"),
                  gasto_total_usd=("gasto_total_usd", "sum"),
                  presion=("presion_turistica", "mean"),
                  capacidad=("capacidad_carga", "mean"),
                  lat=("lat", "first"), lon=("lon", "first"),
                  region=("region", "first")))
    out["gasto_por_visitante"] = (out["gasto_total_usd"]
                                  / out["llegadas"].replace(0, pd.NA)).astype(float)
    return out.sort_values("llegadas", ascending=False).reset_index(drop=True)


def _foco(df: pd.DataFrame) -> str | None:
    foco = st.session_state.get("destino_foco")
    return foco if foco and foco in set(df["destino"]) else None


# --------------------------------------------------------------------------
def _kpis(ctx: dict) -> None:
    m, p = ctx["mensual"], ctx["mensual_previo"]
    grupo("RESUMEN DEL PERIODO")
    llegadas = float(m["llegadas"].sum())
    gasto = float(m["gasto_total_usd"].sum())
    hay_previo = not p.empty
    var_ll = dt.variacion(llegadas, float(p["llegadas"].sum())) if hay_previo else None
    var_g = dt.variacion(gasto, float(p["gasto_total_usd"].sum())) if hay_previo else None
    pres = float(m["presion_turistica"].mean())
    sat = float((m["satisfaccion_promedio"] * m["llegadas"]).sum()
                / max(m["llegadas"].sum(), 1))
    sub_prev = "vs periodo anterior" if hay_previo else "sin periodo previo comparable"

    cols = st.columns(4, gap="small")
    with cols[0], st.container(border=True):
        kpi("Llegadas totales", miles(llegadas), sub_prev, "azul", var_ll)
    with cols[1], st.container(border=True):
        kpi("Derrama economica", dinero(gasto), sub_prev, "naranja", var_g)
    with cols[2], st.container(border=True):
        estado = ("por encima de la capacidad" if pres > 1 else
                  "cerca del limite" if pres >= 0.85 else "con holgura")
        kpi("Presion turistica media", f"{pres:.2f}",
            f"1.0 = capacidad de carga · {estado}", "rosa")
    with cols[3], st.container(border=True):
        kpi("Satisfaccion media", f"{sat:.2f} / 5",
            "ponderada por llegadas", "morado")
    if ctx["detalle"] == "Analisis completo":
        nota("Las variaciones comparan con el periodo anterior de igual duracion "
             "(por ejemplo, 2022-2025 contra 2018-2021) y con el mismo filtro de lugar. "
             "La presion media es el promedio mensual de llegadas / capacidad de carga.")


# --------------------------------------------------------------------------
def _v1(ctx: dict, d: pd.DataFrame, foco: str | None) -> None:
    with st.container(border=True):
        titulo_grafica("V1", "Donde esta la presion turistica",
                       "Que destinos concentran la visita y cuales se acercan a su "
                       "capacidad de carga?", ["Mapa", "Enlazada: destino de V3"])
        tope = max(float(d["llegadas"].max()), 1.0)
        tamano = 14 + 46 * (d["llegadas"] / tope) ** 0.5
        hover = [f"<b>{r.destino}</b><br>{r.region}<br>Llegadas: {miles(r.llegadas)}"
                 f"<br>Presion media: {r.presion:.2f}"
                 f"<br>Capacidad de carga: {miles(r.capacidad)} / mes"
                 for r in d.itertuples()]
        escala = [[i / (len(DIVERGENTE) - 1), c] for i, c in enumerate(DIVERGENTE)]
        lim = max(abs(float(d["presion"].max()) - 1), abs(1 - float(d["presion"].min())), 0.2)

        fig = go.Figure()
        fig.add_trace(go.Scattergeo(
            lat=d["lat"], lon=d["lon"], mode="markers+text",
            text=d["destino"], textposition="top center",
            textfont=dict(size=11, color=TINTA, family=TIPOGRAFIA),
            hovertext=hover, hoverinfo="text",
            marker=dict(size=tamano, color=d["presion"], colorscale=escala,
                        cmid=1.0, cmin=1 - lim, cmax=1 + lim, opacity=0.85,
                        line=dict(width=1, color="white"),
                        colorbar=dict(title=dict(text="Presion", side="top"),
                                      thickness=10, len=0.75,
                                      tickvals=[1 - lim, 1.0, 1 + lim],
                                      ticktext=[f"{1 - lim:.1f} holgura", "1.0 limite",
                                                f"{1 + lim:.1f} saturacion"])),
            showlegend=False, name="Destinos"))
        if foco:
            f = d[d["destino"] == foco]
            fig.add_trace(go.Scattergeo(
                lat=f["lat"], lon=f["lon"], mode="markers", hoverinfo="skip",
                marker=dict(size=tamano[f.index] + 10, color="rgba(0,0,0,0)",
                            line=dict(width=3, color=TINTA)),
                showlegend=False, name="Enfoque"))
        fig.update_geos(fitbounds="locations", projection_type="mercator",
                        showcountries=True, countrycolor=LINEA,
                        showland=True, landcolor="#F5F6FD",
                        showocean=True, oceancolor="#EEF3FB",
                        showlakes=True, lakecolor="#EEF3FB",
                        showcoastlines=True, coastlinecolor=LINEA,
                        showframe=False, resolution=50)
        fig = aplicar_estilo(fig, alto=420, margin=dict(l=0, r=0, t=10, b=0))
        fig.update_layout(geo=dict(bgcolor="rgba(0,0,0,0)"))
        mostrar(fig, clave="v1")
        sobre = d[d["presion"] > 1]["destino"].tolist()
        lectura("El tamano de la burbuja es el volumen de visita; el color, la presion "
                "media (verde = holgura, naranja = cerca del limite, rosa = por encima de "
                "la capacidad de carga). "
                + (f"Por encima de 1.0 en el periodo: {', '.join(sobre)}." if sobre
                   else "Ningun destino supera en promedio su capacidad de carga.")
                + (f" El anillo oscuro marca el destino en enfoque: {foco}." if foco else ""))
        if ctx["detalle"] == "Analisis completo":
            nota("Presion = llegadas del mes / capacidad de carga estimada por estudios "
                 "de sitio; aqui se promedia en el periodo, de modo que los picos de "
                 "temporada alta quedan suavizados. El area es una lectura gruesa del "
                 "volumen: para comparar con precision use V3.")


def _v2(ctx: dict, foco: str | None) -> None:
    m = ctx["mensual"]
    nivel = ctx["nivel_tiempo"]
    with st.container(border=True):
        titulo_grafica("V2", "Evolucion de la visita",
                       "Como se mueve la demanda en el tiempo y como se compara un "
                       "destino con el conjunto?",
                       ["Serie de tiempo", f"Nivel: {nivel.lower()}",
                        "Enlazada: destino de V3"])
        total = dt.agregar_tiempo(m, nivel)
        fig = go.Figure()
        if foco:
            fig.add_trace(go.Scatter(
                x=total["periodo"], y=total["llegadas"], name="Total del filtro",
                mode="lines", line=dict(color=GRIS, width=1), fill="tozeroy",
                fillcolor="rgba(128,137,168,0.22)",
                customdata=total["etiqueta"],
                hovertemplate="%{customdata}<br>Total: %{y:,.0f}<extra></extra>"))
            serie = dt.agregar_tiempo(m[m["destino"] == foco], nivel)
            fig.add_trace(go.Scatter(
                x=serie["periodo"], y=serie["llegadas"], name=foco, mode="lines+markers",
                line=dict(color=COLOR_DESTINO.get(foco, AZUL), width=2.6),
                marker=dict(size=4), customdata=serie["etiqueta"],
                hovertemplate="%{customdata}<br>" + foco + ": %{y:,.0f}<extra></extra>"))
        else:
            fig.add_trace(go.Scatter(
                x=total["periodo"], y=total["llegadas"], name="Llegadas",
                mode="lines+markers", line=dict(color=AZUL, width=2.4),
                marker=dict(size=4), fill="tozeroy", fillcolor="rgba(67,97,238,0.10)",
                customdata=total["etiqueta"],
                hovertemplate="%{customdata}<br>Llegadas: %{y:,.0f}<extra></extra>"))
        fig = aplicar_estilo(
            fig, alto=420, hovermode="x unified",
            yaxis=dict(title="Llegadas", rangemode="tozero"),
            xaxis=dict(title="", rangeslider=dict(visible=nivel == "Mes",
                                                  thickness=0.08)))
        mostrar(fig, clave="v2")
        if foco:
            lectura(f"La linea de color es {foco}; el area gris es el total de los "
                    "destinos filtrados. Si la linea pierde peso frente al area, el "
                    "destino crece menos que el conjunto.")
        else:
            lectura("Toque una barra en V3 para ver la linea de ese destino sobre el "
                    "total. Use el control Detalle para pasar de tendencia anual a "
                    "detalle mensual.")
        if ctx["detalle"] == "Analisis completo":
            nota("Datos observados (linea continua). La barra inferior, visible a nivel "
                 "mes, permite acotar el rango de fechas. La caida de 2020-2021 "
                 "corresponde a la pandemia.")


def _v3(ctx: dict, d: pd.DataFrame, foco: str | None) -> None:
    with st.container(border=True):
        titulo_grafica("V3", "Ranking de destinos",
                       "Que destinos concentran la visita del periodo?",
                       ["Barras", "Enlazada: origen", "Toque una barra"])
        datos = d[["destino", "llegadas", "presion"]].copy()
        datos["llegadas"] = datos["llegadas"].astype(float)
        datos["rotulo"] = datos["llegadas"].map(miles)
        datos["en_foco"] = (datos["destino"] == foco) if foco else True
        dominio = [x for x in COLOR_DESTINO if x in set(datos["destino"])]
        rango = [COLOR_DESTINO[x] for x in dominio]
        orden = datos.sort_values("llegadas", ascending=False)["destino"].tolist()

        sel = alt.selection_point(name="toque_destino", fields=["destino"],
                                  on="click", clear="dblclick")
        base = alt.Chart(datos).encode(
            y=alt.Y("destino:N", sort=orden, title=None,
                    axis=alt.Axis(labelColor=TINTA, labelFontSize=12, labelLimit=180,
                                  domain=False, ticks=False, labelFont=TIPOGRAFIA)),
            x=alt.X("llegadas:Q", title="Llegadas del periodo",
                    axis=alt.Axis(labelColor=IOS_SEC, titleColor=IOS_SEC, grid=True,
                                  gridColor=LINEA, domain=False, format="~s",
                                  labelFont=TIPOGRAFIA, titleFont=TIPOGRAFIA)),
        )
        if foco:
            opacidad = alt.condition("datum.en_foco", alt.value(1.0), alt.value(0.3))
        else:
            opacidad = alt.condition(sel, alt.value(1.0), alt.value(0.3))
        barras = base.mark_bar(cornerRadiusEnd=6, height=22).encode(
            color=alt.Color("destino:N", scale=alt.Scale(domain=dominio, range=rango),
                            legend=None),
            opacity=opacidad,
            tooltip=[alt.Tooltip("destino:N", title="Destino"),
                     alt.Tooltip("llegadas:Q", title="Llegadas", format=",.0f"),
                     alt.Tooltip("presion:Q", title="Presion media", format=".2f")],
        ).add_params(sel)
        texto = base.mark_text(align="left", dx=5, fontSize=11, color=TINTA,
                               font=TIPOGRAFIA).encode(text="rotulo:N")
        grafico = (barras + texto).properties(height=max(44 * len(datos), 160))
        # La clave cambia con el enfoque: asi el widget nace sin seleccion tras
        # cada cambio y "Quitar enfoque" no queda anulado por un toque antiguo.
        clave = "v3_" + "".join(ch for ch in (foco or "todos") if ch.isalnum())
        valor = mostrar_tactil(grafico, clave=clave, campo="destino",
                               nombre_seleccion="toque_destino")
        if valor is not None and valor != st.session_state.get("destino_foco"):
            st.session_state["destino_foco"] = valor
            st.rerun()

        if foco:
            lectura(f"Enfoque activo: {foco}. El mapa (V1), la serie (V2) y las "
                    "secciones Explorar y Sostenibilidad muestran ese destino. Toque "
                    "otra barra para cambiarlo o use \"Quitar enfoque\" arriba.")
        else:
            lectura("Toque una barra para enfocar ese destino: el mapa lo resalta, la "
                    "serie dibuja su linea y las secciones de detalle se recalculan "
                    "solo para el.")
        if ctx["detalle"] == "Analisis completo":
            nota("Suma de llegadas en el periodo y lugar filtrados. Barras ordenadas "
                 "de mayor a menor; la cifra al final evita depender del color.")


def _v4(ctx: dict, d: pd.DataFrame, foco: str | None) -> None:
    with st.container(border=True):
        titulo_grafica("V4", "Volumen frente a valor",
                       "Que destinos reciben mucha gente y cuales reciben gente que "
                       "gasta mas?", ["Dispersion", "Cuadrantes"])
        datos = d.dropna(subset=["gasto_por_visitante"])
        if datos.empty:
            sin_datos("No hay llegadas en la seleccion. Amplie el periodo o el lugar.")
            return
        mx, my = float(datos["llegadas"].mean()), float(datos["gasto_por_visitante"].mean())
        colores = [COLOR_DESTINO.get(x, AZUL) for x in datos["destino"]]
        bordes = [3 if x == foco else 1 for x in datos["destino"]]
        fig = go.Figure(go.Scatter(
            x=datos["llegadas"], y=datos["gasto_por_visitante"],
            mode="markers+text", text=datos["destino"], textposition="top center",
            textfont=dict(size=11, color=TINTA),
            marker=dict(size=16, color=colores, opacity=0.9,
                        line=dict(width=bordes, color=[TINTA if x == foco else "white"
                                                       for x in datos["destino"]])),
            customdata=datos[["gasto_total_usd"]].to_numpy(),
            hovertemplate="<b>%{text}</b><br>Llegadas: %{x:,.0f}"
                          "<br>Gasto por visitante: US$ %{y:,.0f}"
                          "<br>Derrama: US$ %{customdata[0]:,.0f}<extra></extra>",
            showlegend=False))
        fig.add_vline(x=mx, line=dict(color=GRIS, width=1, dash="dot"))
        fig.add_hline(y=my, line=dict(color=GRIS, width=1, dash="dot"))
        cuadrantes = [("Mucha visita, alto gasto", "right", "top"),
                      ("Poca visita, alto gasto", "left", "top"),
                      ("Mucha visita, bajo gasto", "right", "bottom"),
                      ("Poca visita, bajo gasto", "left", "bottom")]
        for texto, xa, ya in cuadrantes:
            fig.add_annotation(
                xref="x domain", yref="y domain",
                x=0.99 if xa == "right" else 0.01, y=0.99 if ya == "top" else 0.01,
                xanchor=xa, yanchor=ya, text=texto, showarrow=False,
                font=dict(size=11, color=IOS_SEC))
        fig = aplicar_estilo(
            fig, alto=420,
            xaxis=dict(title="Llegadas del periodo"),
            yaxis=dict(title="Gasto por visitante (US$)", tickprefix="US$ "))
        mostrar(fig, clave="v4")
        top = datos.sort_values("gasto_por_visitante", ascending=False).iloc[0]
        lectura("Las lineas punteadas son los promedios: arriba a la derecha estan los "
                "destinos que combinan volumen y valor. "
                f"El mayor gasto por visitante es {top['destino']} "
                f"(US$ {top['gasto_por_visitante']:,.0f}).".replace(",", " "))
        if ctx["detalle"] == "Analisis completo":
            nota(f"Promedio de llegadas: {miles(mx)}; promedio de gasto por visitante: "
                 f"US$ {my:,.0f}".replace(",", " ")
                 + ". Gasto por visitante = derrama total / llegadas del periodo. "
                 "La posicion es relativa al grupo filtrado: cambia si se filtran destinos.")


# --------------------------------------------------------------------------
def render(ctx: dict) -> None:
    m = ctx["mensual"]
    if m.empty:
        sin_datos("No hay datos para el periodo y lugar elegidos. Amplie el rango de "
                  "anos o quite filtros de lugar, o pulse Restablecer.")
        return

    _kpis(ctx)

    activas = ctx.get("graficas_activas")
    activas = TODAS if activas is None else activas
    if not activas:
        sin_datos("No hay graficas seleccionadas. Elija cuales mostrar en el menu "
                  "\"Graficas\" de la barra superior.")
        return

    d = _por_destino(m)
    foco = _foco(m)

    if V1 in activas or V2 in activas:
        grupo("DONDE Y CUANDO")
        izq, der = par_columnas(V1 in activas, V2 in activas)
        if V1 in activas:
            with izq:
                _v1(ctx, d, foco)
        if V2 in activas:
            with der:
                _v2(ctx, foco)

    if V3 in activas or V4 in activas:
        grupo("PESO DE CADA DESTINO")
        izq, der = par_columnas(V3 in activas, V4 in activas)
        if V3 in activas:
            with izq:
                _v3(ctx, d, foco)
        if V4 in activas:
            with der:
                _v4(ctx, d, foco)

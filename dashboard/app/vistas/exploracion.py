"""
Seccion Explorar: de donde viene la visita, cuando llega y en que gasta.

V5  Mercados emisores        (Altair, origen del enlace con V6)
V6  Calendario de la demanda (mapa de calor mes x ano, enlazado con V5)
V7  Composicion del gasto    (treemap con profundidad jerarquica)
V8  Ocupacion frente a gasto (dispersion con tendencia, asociacion)
V9  Perfil segun con quien viaja (diagrama de caja, encuesta)
V10 Alojamiento por destino  (barras apiladas al 100%, encuesta)
"""

from __future__ import annotations

import altair as alt
import numpy as np
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st

import datos as dt
from componentes import (aplicar_estilo, aviso, dinero, grupo, lectura, miles,
                         mostrar, mostrar_tactil, nota, par_columnas,
                         sin_datos, titulo_grafica)
from config import (AZUL, CATEGORICA, COLOR_DESTINO, GRIS, IOS_SEC, NARANJA,
                    SECUENCIAL, TINTA)

GRAFICAS = ["V5 Mercados emisores", "V6 Estacionalidad",
            "V7 Composicion del gasto", "V8 Ocupacion y gasto",
            "V9 Perfil del visitante", "V10 Alojamiento"]

_ESCALA = [[i / (len(SECUENCIAL) - 1), c] for i, c in enumerate(SECUENCIAL)]
_SIN_ENCUESTA = ("La encuesta a visitantes solo cubre 2023-2025. Amplie el "
                 "periodo para incluir alguno de esos anos (menu Periodo).")


def _rgba(hexa: str, alfa: float) -> str:
    h = hexa.lstrip("#")
    r, g, b = (int(h[i:i + 2], 16) for i in (0, 2, 4))
    return f"rgba({r},{g},{b},{alfa})"


def _completo(ctx: dict) -> bool:
    return ctx.get("detalle", "Analisis completo") != "Resumen ejecutivo"


# --------------------------------------------------------------------------
# V5 Mercados emisores (origen del enlace)
# --------------------------------------------------------------------------
def _v5(ctx: dict) -> None:
    mercados = ctx["mercados"]
    titulo_grafica("V5", "Mercados emisores",
                   "De donde viene el visitante y cuanto pesa cada mercado",
                   ["Barras", "Enlazada: origen"])
    if mercados.empty:
        sin_datos("No hay llegadas por mercado con estos filtros. "
                  "Amplie el periodo o el lugar.")
        return

    tabla = (mercados.groupby("mercado", as_index=False)["llegadas"].sum()
             .sort_values("llegadas", ascending=False))
    total = tabla["llegadas"].sum()
    tabla["pct"] = tabla["llegadas"] / total * 100 if total else 0.0
    tabla["texto"] = tabla["pct"].map(lambda p: f"{p:.1f}%")
    tabla["llegadas_txt"] = tabla["llegadas"].map(miles)

    foco = st.session_state.get("mercado_foco")
    sel = alt.selection_point(name="mercado_sel", fields=["mercado"],
                              on="click", clear="dblclick")
    if foco and foco in set(tabla["mercado"]):
        opacidad = alt.condition(alt.datum.mercado == foco,
                                 alt.value(1.0), alt.value(0.3))
    else:
        opacidad = alt.condition(sel, alt.value(1.0), alt.value(0.3))

    orden = list(tabla["mercado"])
    eje_y = alt.Y("mercado:N", sort=orden, title=None,
                  axis=alt.Axis(labelLimit=180, labelColor=TINTA,
                                labelFontSize=12, ticks=False, domain=False))
    base = alt.Chart(tabla).encode(y=eje_y)
    barras = base.mark_bar(color=AZUL, cornerRadiusEnd=4, height=20).encode(
        x=alt.X("llegadas:Q", title="Llegadas en el periodo",
                axis=alt.Axis(format="~s", labelColor=IOS_SEC, grid=True)),
        opacity=opacidad,
        tooltip=[alt.Tooltip("mercado:N", title="Mercado"),
                 alt.Tooltip("llegadas_txt:N", title="Llegadas"),
                 alt.Tooltip("texto:N", title="Participacion")],
    ).add_params(sel)
    textos = base.mark_text(align="left", dx=5, fontSize=12, color=TINTA,
                            fontWeight=600).encode(
        x="llegadas:Q", text="texto:N", opacity=opacidad)
    grafico = (barras + textos).properties(height=max(260, 34 * len(tabla)))

    # La clave cambia con el enfoque (igual que V3): el widget nace sin
    # seleccion y "Quitar enfoque" no queda anulado por un toque antiguo.
    clave = "v5_" + "".join(ch for ch in (foco or "todos") if ch.isalnum())
    valor = mostrar_tactil(grafico, clave=clave, campo="mercado",
                           nombre_seleccion="mercado_sel")
    if valor is not None and valor != foco:
        st.session_state["mercado_foco"] = valor
        st.rerun()

    lider = tabla.iloc[0]
    top3 = tabla["pct"].head(3).sum()
    lectura(f"<b>{lider['mercado']}</b> aporta el {lider['pct']:.1f}% de las "
            f"llegadas y los tres primeros mercados suman el {top3:.1f}%. "
            "Toque una barra para ver la estacionalidad de ese mercado en V6; "
            "quite el enfoque desde el chip de arriba.")
    if _completo(ctx):
        nota("Las llegadas por mercado suman exactamente las llegadas del "
             "destino-mes. El porcentaje es sobre el total del periodo y lugar "
             "filtrados.")


# --------------------------------------------------------------------------
# V6 Calendario de la demanda (enlazado con V5)
# --------------------------------------------------------------------------
def _v6(ctx: dict) -> None:
    mercados = ctx["mercados"]
    foco = st.session_state.get("mercado_foco")
    if foco and foco in set(mercados["mercado"]):
        datos = mercados[mercados["mercado"] == foco]
        quien = foco
    else:
        datos = mercados
        quien = "todos los mercados"

    titulo_grafica("V6", f"Calendario de la demanda · {quien}",
                   "Que meses concentran la visita y si el patron cambia entre anos",
                   ["Mapa de calor", "Enlazada con V5"])
    if datos.empty:
        sin_datos("No hay llegadas con estos filtros. Amplie el periodo o el lugar.")
        return

    modo = st.segmented_control(
        "Escala", ["Llegadas", "Indice (100 = mes promedio del ano)"],
        default="Llegadas", key="v6_modo", label_visibility="collapsed")
    modo = modo or "Llegadas"

    tabla = (datos.groupby(["anio", "mes"])["llegadas"].sum()
             .unstack("mes").reindex(columns=range(1, 13)))
    if modo == "Llegadas":
        z = tabla
        texto = z.map(lambda v: "" if pd.isna(v) else miles(v))
        hover = "%{y} · %{x}<br>Llegadas: %{text}<extra></extra>"
        barra = "Llegadas"
    else:
        promedio = tabla.mean(axis=1).replace(0, np.nan)
        z = tabla.div(promedio, axis=0) * 100
        texto = z.map(lambda v: "" if pd.isna(v) else f"{v:.0f}")
        hover = "%{y} · %{x}<br>Indice: %{text}<extra></extra>"
        barra = "Indice"

    fig = go.Figure(go.Heatmap(
        z=z.values, x=dt.NOMBRES_MES, y=[str(a) for a in z.index],
        text=texto.values, texttemplate="%{text}" if len(z) <= 5 else None,
        hovertemplate=hover, colorscale=_ESCALA, xgap=2, ygap=2,
        colorbar=dict(title=dict(text=barra, side="right"), thickness=10,
                      outlinewidth=0)))
    aplicar_estilo(fig, alto=max(260, 46 * len(z) + 90),
                   xaxis=dict(showgrid=False, side="top"),
                   yaxis=dict(showgrid=False, autorange="reversed", type="category"))
    mostrar(fig, clave="v6")

    perfil = tabla.sum(axis=0)
    pico, valle = perfil.idxmax(), perfil.idxmin()
    lectura(f"Para {quien}, el mes mas fuerte es <b>{dt.NOMBRES_MES[pico - 1]}</b> "
            f"y el mas flojo <b>{dt.NOMBRES_MES[valle - 1]}</b>. Celdas oscuras = "
            "mas visita. Use el indice para comparar la forma del ano entre "
            "anos de tamano muy distinto (por ejemplo, la pandemia).")
    if _completo(ctx):
        nota("Indice: llegadas del mes divididas por el promedio mensual de ese "
             "mismo ano, por 100. Un 130 significa 30% por encima de un mes "
             "tipico de ese ano.")


# --------------------------------------------------------------------------
# V7 Composicion del gasto (treemap con profundidad)
# --------------------------------------------------------------------------
_NIVELES_V7 = {"Region": ["region"],
               "Region y destino": ["region", "destino"],
               "Region, destino y categoria": ["region", "destino", "categoria"]}


def _v7(ctx: dict) -> None:
    mensual = ctx["mensual"]
    titulo_grafica("V7", "En que se gasta",
                   "Como se reparte la derrama entre regiones, destinos y rubros",
                   ["Treemap", "Nivel de detalle"])
    if mensual.empty:
        sin_datos("No hay gasto registrado con estos filtros. "
                  "Amplie el periodo o el lugar.")
        return

    nivel = st.segmented_control(
        "Profundidad", list(_NIVELES_V7), default="Region, destino y categoria",
        key="v7_profundidad", label_visibility="collapsed")
    nivel = nivel or "Region, destino y categoria"
    ruta = _NIVELES_V7[nivel]

    largo = dt.gasto_largo(mensual, ["region", "destino"])
    tabla = largo.groupby(ruta, as_index=False)["gasto_usd"].sum()
    tabla = tabla[tabla["gasto_usd"] > 0]
    total = tabla["gasto_usd"].sum()
    if tabla.empty or total <= 0:
        sin_datos("No hay gasto registrado con estos filtros.")
        return

    fig = px.treemap(tabla, path=[px.Constant("Total"), *ruta],
                     values="gasto_usd", color="gasto_usd",
                     color_continuous_scale=_ESCALA, maxdepth=len(ruta) + 1)
    fig.update_traces(
        texttemplate="<b>%{label}</b><br>%{percentRoot:.1%}",
        hovertemplate="<b>%{label}</b><br>US$ %{value:,.0f}<br>"
                      "%{percentRoot:.1%} del total<extra></extra>",
        marker=dict(line=dict(width=1.5, color="white")),
        root=dict(color="#F5F6FD"), branchvalues="total")
    aplicar_estilo(fig, alto=440, margin=dict(t=10, l=4, r=4, b=4),
                   coloraxis_showscale=False)
    mostrar(fig, clave="v7")

    por_cat = largo.groupby("categoria")["gasto_usd"].sum()
    cat = por_cat.idxmax()
    lectura(f"Derrama total del periodo: <b>{dinero(total)}</b>. El rubro con mas "
            f"peso es <b>{cat}</b> ({por_cat.max() / por_cat.sum() * 100:.0f}%). "
            "Cambie la profundidad para subir o bajar de nivel; toque un bloque "
            "para hacer zoom.")
    if _completo(ctx):
        nota("Area = proporcion del gasto total. El color repite la magnitud en "
             "escala secuencial. Las cinco categorias suman la derrama de cada "
             "destino-mes.")


# --------------------------------------------------------------------------
# V8 Ocupacion frente a gasto diario
# --------------------------------------------------------------------------
def _v8(ctx: dict) -> None:
    mensual = ctx["mensual"]
    nivel = ctx.get("nivel_tiempo", "Mes")
    titulo_grafica("V8", "Ocupacion frente a gasto diario",
                   "Cuando los hoteles se llenan, el visitante gasta mas o menos por dia?",
                   ["Dispersion", "Asociacion, no causa"])
    if mensual.empty:
        sin_datos("No hay datos con estos filtros. Amplie el periodo o el lugar.")
        return

    agg = dt.agregar_tiempo(mensual, nivel, por=["destino"])
    agg = agg.dropna(subset=["ocupacion_hotelera", "gasto_diario_usd"])
    agg = agg.astype({"ocupacion_hotelera": float, "gasto_diario_usd": float})
    if agg.empty:
        sin_datos("No hay datos con estos filtros.")
        return

    fig = go.Figure()
    for destino, sub in agg.groupby("destino"):
        fig.add_trace(go.Scatter(
            x=sub["ocupacion_hotelera"], y=sub["gasto_diario_usd"],
            mode="markers", name=destino, text=sub["etiqueta"],
            marker=dict(color=COLOR_DESTINO.get(destino, GRIS), size=8,
                        opacity=0.75, line=dict(width=0.5, color="white")),
            hovertemplate=f"<b>{destino}</b> · %{{text}}<br>Ocupacion: "
                          "%{x:.1f}%<br>Gasto diario: US$ %{y:.0f}<extra></extra>"))

    x = agg["ocupacion_hotelera"].to_numpy()
    y = agg["gasto_diario_usd"].to_numpy()
    r = None
    if len(x) >= 3 and np.ptp(x) > 0 and np.ptp(y) > 0:
        pendiente, intercepto = np.polyfit(x, y, 1)
        r = float(np.corrcoef(x, y)[0, 1])
        xs = np.linspace(x.min(), x.max(), 50)
        fig.add_trace(go.Scatter(
            x=xs, y=pendiente * xs + intercepto, mode="lines",
            name="Tendencia lineal", line=dict(color=GRIS, width=2),
            hoverinfo="skip"))

    aplicar_estilo(fig, alto=400,
                   xaxis=dict(title="Ocupacion hotelera (%)"),
                   yaxis=dict(title="Gasto diario por visitante (US$)"))
    mostrar(fig, clave="v8")

    if r is None:
        lectura("Hay muy pocos puntos para resumir la relacion. Amplie el periodo "
                "o cambie a nivel Mes.")
    else:
        fuerza = ("fuerte" if abs(r) >= 0.6 else
                  "moderada" if abs(r) >= 0.3 else "debil")
        sentido = "positiva" if r >= 0 else "negativa"
        lectura(f"Correlacion r = <b>{r:.2f}</b>: asociacion {fuerza} y {sentido}. "
                "Es una <b>asociacion, no una causa</b>: temporada alta, perfil "
                "del destino y tipo de visitante mueven ambas variables a la vez. "
                "Cada punto es un destino en un periodo.")
    if _completo(ctx):
        nota(f"Agregacion: {nivel.lower()}. Ocupacion y gasto diario se ponderan "
             "por llegadas al agregar. La recta es un ajuste de minimos "
             "cuadrados sobre todos los puntos; la dispersion alrededor de ella "
             "es parte del mensaje.")


# --------------------------------------------------------------------------
# V9 Perfil segun con quien viaja (encuesta)
# --------------------------------------------------------------------------
_METRICAS_V9 = {"Gasto diario (US$)": ("gasto_diario_usd", NARANJA),
                "Noches de estancia": ("noches", AZUL),
                "Gasto total del viaje (US$)": ("gasto_total_usd", NARANJA)}
_ORDEN_GRUPOS = ["Solo", "Pareja", "Familia", "Amigos", "Negocios"]


def _v9(ctx: dict) -> None:
    vis = ctx["visitantes"]
    titulo_grafica("V9", "Perfil segun con quien viaja",
                   "Que segmento gasta mas o se queda mas tiempo",
                   ["Diagrama de caja", "Encuesta 2023-2025"])
    if vis.empty:
        sin_datos(_SIN_ENCUESTA)
        return

    metrica = st.segmented_control(
        "Metrica", list(_METRICAS_V9), default="Gasto diario (US$)",
        key="v9_metrica", label_visibility="collapsed")
    metrica = metrica or "Gasto diario (US$)"
    col, color = _METRICAS_V9[metrica]

    grupos = [g for g in _ORDEN_GRUPOS if g in set(vis["grupo_viaje"])]
    grupos += sorted(set(vis["grupo_viaje"]) - set(grupos))
    fig = go.Figure()
    for g in grupos:
        fig.add_trace(go.Box(
            y=vis.loc[vis["grupo_viaje"] == g, col], name=g,
            marker=dict(color=color, size=3, opacity=0.5),
            line=dict(color=color), fillcolor=_rgba(color, 0.25),
            boxpoints="outliers", showlegend=False))
    aplicar_estilo(fig, alto=380, yaxis=dict(title=metrica),
                   xaxis=dict(showgrid=False))
    mostrar(fig, clave="v9")

    med = vis.groupby("grupo_viaje")[col].median()
    fmt = (lambda v: f"{v:.0f} noches") if col == "noches" else \
          (lambda v: f"US$ {v:,.0f}".replace(",", " "))
    lectura(f"Mediana mas alta: <b>{med.idxmax()}</b> ({fmt(med.max())}); mas baja: "
            f"<b>{med.idxmin()}</b> ({fmt(med.min())}). La caja muestra la mitad "
            "central de los visitantes: util para dimensionar un segmento sin que "
            "los casos extremos lo distorsionen.")
    if _completo(ctx):
        nota(f"Basado en {miles(len(vis))} entrevistas de la encuesta a pie de "
             "destino (2023-2025). Linea = mediana, caja = rango intercuartilico, "
             "puntos = valores atipicos.")


# --------------------------------------------------------------------------
# V10 Donde se hospeda cada destino (encuesta)
# --------------------------------------------------------------------------
def _v10(ctx: dict) -> None:
    vis = ctx["visitantes"]
    titulo_grafica("V10", "Donde se hospeda cada destino",
                   "Que mezcla de alojamiento tiene cada destino",
                   ["Barras apiladas al 100%", "Encuesta 2023-2025"])
    if vis.empty:
        sin_datos(_SIN_ENCUESTA)
        return

    tabla = pd.crosstab(vis["destino"], vis["tipo_alojamiento"], normalize="index") * 100
    tipos = list(tabla.sum().sort_values(ascending=False).index)
    tabla = tabla[tipos]
    if tipos:
        tabla = tabla.sort_values(tipos[0])

    fig = go.Figure()
    for i, tipo in enumerate(tipos):
        valores = tabla[tipo]
        fig.add_trace(go.Bar(
            y=tabla.index, x=valores, name=tipo, orientation="h",
            marker=dict(color=CATEGORICA[i % len(CATEGORICA)],
                        line=dict(width=1, color="white")),
            text=[f"{v:.0f}%" if v >= 7 else "" for v in valores],
            textposition="inside", insidetextanchor="middle",
            textfont=dict(color="white", size=11),
            hovertemplate=f"%{{y}}<br>{tipo}: %{{x:.1f}}%<extra></extra>"))
    aplicar_estilo(fig, alto=max(260, 46 * len(tabla) + 80), barmode="stack",
                   xaxis=dict(title="Porcentaje de visitantes", range=[0, 100],
                              ticksuffix="%"),
                   yaxis=dict(showgrid=False),
                   legend=dict(traceorder="normal"))
    mostrar(fig, clave="v10")

    dominante = tipos[0] if tipos else ""
    extremo = tabla[dominante].idxmax() if dominante else ""
    lectura(f"<b>{dominante}</b> es el alojamiento mas comun en el conjunto; "
            f"donde mas pesa es en <b>{extremo}</b> ({tabla[dominante].max():.0f}%). "
            "Al normalizar a 100% se comparan destinos de tamano muy distinto.")
    if _completo(ctx):
        nota("Porcentaje de entrevistados por tipo de alojamiento declarado. "
             "Los destinos con pocas entrevistas en el periodo tienen mayor "
             "margen de error.")


# --------------------------------------------------------------------------
def render(ctx: dict) -> None:
    activas = ctx.get("graficas_activas")
    if activas is None:
        activas = GRAFICAS
    if not activas:
        sin_datos("No hay graficas seleccionadas. Elija cuales ver en el menu "
                  "\"Graficas\".")
        return

    foco = st.session_state.get("destino_foco")
    if foco:
        aviso(f"Esta seccion esta filtrada al destino <b>{foco}</b> (enfoque "
              "elegido en Panorama). Quitelo desde el chip de arriba.")

    v = {n.split(" ")[0]: n in activas for n in GRAFICAS}

    if v["V5"] or v["V6"]:
        grupo("De donde y cuando llega la visita")
        izq, der = par_columnas(v["V5"], v["V6"], pesos=(1, 1.25))
        if v["V5"]:
            with izq, st.container(border=True):
                _v5(ctx)
        if v["V6"]:
            with der, st.container(border=True):
                _v6(ctx)

    if v["V7"] or v["V8"]:
        grupo("En que se gasta")
        izq, der = par_columnas(v["V7"], v["V8"])
        if v["V7"]:
            with izq, st.container(border=True):
                _v7(ctx)
        if v["V8"]:
            with der, st.container(border=True):
                _v8(ctx)

    if v["V9"] or v["V10"]:
        grupo("Quien es el visitante (encuesta)")
        izq, der = par_columnas(v["V9"], v["V10"])
        if v["V9"]:
            with izq, st.container(border=True):
                _v9(ctx)
        if v["V10"]:
            with der, st.container(border=True):
                _v10(ctx)

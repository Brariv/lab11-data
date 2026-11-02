"""
Seccion Sostenibilidad: "¿A que costo?".

V11 Desacoplamiento        doble eje Y: llegadas frente a una huella ambiental
V12 Presion por destino    barras con umbral 1.0 (capacidad de carga) y semaforo
V13 Perfil de sostenibilidad  radar de 6 dimensiones normalizadas (hasta 3 destinos)
V14 Beneficio local        dispersion empleo local x certificacion, tamano = derrama

Si hay un destino en enfoque (toque en V3), ctx["mensual"] ya llega acotado a
el; V13 usa ademas el conjunto de destinos del periodo como referencia para
normalizar, porque un radar normalizado con un solo destino no dice nada.
"""

from __future__ import annotations

import numpy as np
import pandas as pd
import plotly.graph_objects as go
import streamlit as st
from plotly.subplots import make_subplots

import datos as dt
from componentes import (aplicar_estilo, aviso, dinero, grupo, kpi, lectura,
                         miles, mostrar, nota, par_columnas, sin_datos,
                         titulo_grafica)
from config import (AZUL, COLOR_DESTINO, GRIS, LINEA, ROSA, SEMAFORO, TINTA_2,
                    VERDE)

CATALOGO = ["V11 Desacoplamiento", "V12 Presion por destino",
            "V13 Perfil de sostenibilidad", "V14 Beneficio local"]

HUELLAS = {
    "co2_ton": ("Emisiones de CO2", "t CO2"),
    "residuos_ton": ("Residuos solidos", "t"),
    "agua_miles_m3": ("Consumo de agua", "miles de m3"),
}

DIMENSIONES = ["Holgura de capacidad", "Empleo local", "Empresas certificadas",
               "Satisfaccion", "Eficiencia hidrica", "Baja huella de carbono"]


# --------------------------------------------------------------------------
# Utilidades
# --------------------------------------------------------------------------
def _ponderado(df: pd.DataFrame, col: str) -> float:
    peso = df["llegadas"].sum()
    if peso == 0:
        return float(df[col].mean())
    return float((df[col] * df["llegadas"]).sum() / peso)


def _clase_presion(valor: float) -> tuple[str, str]:
    if valor > 1.0:
        return "alto", "Saturacion"
    if valor >= 0.85:
        return "medio", "Al limite"
    return "bajo", "Holgura"


def _pct(a: float, b: float) -> str:
    var = dt.variacion(b, a)
    return "s/d" if var is None else f"{var:+.1f}%"


def _lista(nombres: list[str]) -> str:
    if len(nombres) <= 1:
        return "".join(nombres)
    return ", ".join(nombres[:-1]) + " y " + nombres[-1]


def _resumen_destinos(df: pd.DataFrame) -> pd.DataFrame:
    filas = []
    for destino, g in df.groupby("destino"):
        llegadas = g["llegadas"].sum()
        filas.append({
            "destino": destino,
            "llegadas": llegadas,
            "gasto_total_usd": g["gasto_total_usd"].sum(),
            "presion": g["presion_turistica"].mean(),
            "presion_pico": g["presion_turistica"].max(),
            "empleo_local_pct": _ponderado(g, "empleo_local_pct"),
            "empresas_certificadas_pct": _ponderado(g, "empresas_certificadas_pct"),
            "satisfaccion": _ponderado(g, "satisfaccion_promedio"),
            "agua_por_visitante": (g["agua_miles_m3"].sum() * 1000 / llegadas
                                   if llegadas else np.nan),
            "co2_por_visitante": (g["co2_ton"].sum() * 1000 / llegadas
                                  if llegadas else np.nan),
        })
    return pd.DataFrame(filas)


# --------------------------------------------------------------------------
# Tarjetas
# --------------------------------------------------------------------------
def _tarjetas(m: pd.DataFrame, previo: pd.DataFrame) -> None:
    llegadas = m["llegadas"].sum()
    hay_previo = not previo.empty

    def comparado(col: str) -> str:
        if not hay_previo:
            return "sin periodo previo"
        return f"{_pct(previo[col].sum(), m[col].sum())} vs periodo previo"

    cols = st.columns(4, gap="small")
    with cols[0]:
        kpi("Emisiones de CO2", f"{miles(m['co2_ton'].sum())} t",
            comparado("co2_ton"), acento="rosa")
    with cols[1]:
        kpi("Residuos solidos", f"{miles(m['residuos_ton'].sum())} t",
            comparado("residuos_ton"), acento="rosa")
    with cols[2]:
        por_vis = (m["agua_miles_m3"].sum() * 1000 / llegadas) if llegadas else 0
        kpi("Consumo de agua", f"{miles(m['agua_miles_m3'].sum())} mil m3",
            f"{por_vis:,.2f} m3 por visitante", acento="celeste")
    with cols[3]:
        kpi("Empleo local", f"{_ponderado(m, 'empleo_local_pct'):.1f}%",
            "del empleo turistico (ponderado por llegadas)", acento="verde")


# --------------------------------------------------------------------------
# V11
# --------------------------------------------------------------------------
def _v11(ctx: dict, m: pd.DataFrame, completo: bool) -> None:
    with st.container(border=True):
        titulo_grafica("V11", "Crecimiento frente a huella",
                       "¿Crece la huella ambiental al mismo ritmo que la visita?",
                       ["Doble eje Y"])
        c1, c2 = st.columns([1.4, 1], gap="small")
        with c1:
            huella = st.segmented_control(
                "Huella", list(HUELLAS), default="co2_ton", key="v11_huella",
                format_func=lambda k: HUELLAS[k][0],
                label_visibility="collapsed") or "co2_ton"
        with c2:
            indice = st.toggle("Indice base 100", key="v11_indice",
                               help="Pone ambas series en el mismo eje: primer "
                                    "periodo = 100. Sirve para comparar ritmos.")
        nombre, unidad = HUELLAS[huella]
        nivel = ctx["nivel_tiempo"]
        serie = dt.agregar_tiempo(m, nivel)[["periodo", "etiqueta", "llegadas", huella]]
        if serie.empty:
            sin_datos("No hay meses en el periodo elegido. Amplia el rango de anos.")
            return

        if indice:
            base_l, base_h = serie["llegadas"].iloc[0], serie[huella].iloc[0]
            y_l = serie["llegadas"] / base_l * 100 if base_l else serie["llegadas"] * np.nan
            y_h = serie[huella] / base_h * 100 if base_h else serie[huella] * np.nan
            fig = go.Figure()
            fig.add_scatter(x=serie["periodo"], y=y_l, name="Llegadas (indice)",
                            mode="lines+markers" if len(serie) < 30 else "lines",
                            line=dict(color=AZUL, width=2.6),
                            customdata=serie["etiqueta"],
                            hovertemplate="%{customdata}<br>Llegadas: %{y:.1f}<extra></extra>")
            fig.add_scatter(x=serie["periodo"], y=y_h, name=f"{nombre} (indice)",
                            mode="lines+markers" if len(serie) < 30 else "lines",
                            line=dict(color=ROSA, width=2.6),
                            customdata=serie["etiqueta"],
                            hovertemplate="%{customdata}<br>" + nombre
                                          + ": %{y:.1f}<extra></extra>")
            fig.add_hline(y=100, line=dict(color=GRIS, width=1, dash="dot"))
            aplicar_estilo(fig, alto=380,
                           yaxis=dict(title="Indice (primer periodo = 100)"),
                           hovermode="x unified")
        else:
            fig = make_subplots(specs=[[{"secondary_y": True}]])
            modo = "lines+markers" if len(serie) < 30 else "lines"
            fig.add_trace(go.Scatter(
                x=serie["periodo"], y=serie["llegadas"], name="Llegadas",
                mode=modo, line=dict(color=AZUL, width=2.6),
                customdata=serie["etiqueta"],
                hovertemplate="%{customdata}<br>Llegadas: %{y:,.0f}<extra></extra>"),
                secondary_y=False)
            fig.add_trace(go.Scatter(
                x=serie["periodo"], y=serie[huella], name=f"{nombre} ({unidad})",
                mode=modo, line=dict(color=ROSA, width=2.6),
                customdata=serie["etiqueta"],
                hovertemplate="%{customdata}<br>" + nombre + ": %{y:,.0f} "
                              + unidad + "<extra></extra>"),
                secondary_y=True)
            aplicar_estilo(
                fig, alto=380, hovermode="x unified",
                yaxis=dict(title=dict(text="Llegadas", font=dict(color=AZUL)),
                           tickfont=dict(color=AZUL)),
                yaxis2=dict(title=dict(text=f"{nombre} ({unidad})",
                                       font=dict(color=ROSA)),
                            tickfont=dict(size=11, color=ROSA),
                            showgrid=False, zeroline=False, linecolor=LINEA))
        mostrar(fig, clave="v11")

        # Crecimiento entre el primer y el ultimo ano completo del rango
        meses = m.groupby("anio")["fecha"].nunique()
        completos = sorted(meses[meses == 12].index)
        if len(completos) >= 2:
            a0, a1 = completos[0], completos[-1]
            por_anio = m.groupby("anio")[["llegadas", huella]].sum()
            g_l = dt.variacion(por_anio.loc[a1, "llegadas"], por_anio.loc[a0, "llegadas"])
            g_h = dt.variacion(por_anio.loc[a1, huella], por_anio.loc[a0, huella])
            if g_l is not None and g_h is not None:
                if g_h < g_l:
                    juicio = ("la huella crece <b>mas despacio</b> que la visita: hay "
                              "desacople relativo (cada visitante deja menos huella), "
                              "aunque el total puede seguir subiendo")
                elif g_h > g_l:
                    juicio = ("la huella crece <b>mas rapido</b> que la visita: cada "
                              "visitante deja mas huella que antes, senal de alerta")
                else:
                    juicio = "ambas crecen al mismo ritmo: no hay desacople"
                lectura(f"Entre {a0} y {a1} las llegadas variaron {g_l:+.1f}% y "
                        f"{nombre[0].lower() + nombre[1:]} {g_h:+.1f}%; {juicio}.")
            else:
                lectura("No se puede calcular el crecimiento: el primer ano completo "
                        "no tiene registros de esta variable.")
        else:
            lectura("Para medir el desacople se necesitan al menos dos anos completos "
                    "en el rango. Amplia el periodo para ver el crecimiento comparado.")
        if completo:
            nota("Las dos series tienen unidades distintas: en doble eje solo deben "
                 "compararse las <b>pendientes</b>, no la altura de las lineas (la "
                 "escala de cada eje es arbitraria). El indice base 100 evita esa "
                 "trampa. Desacople relativo no es reduccion absoluta. La huella es "
                 "una estimacion asociada a la visita, no una medicion directa.")


# --------------------------------------------------------------------------
# V12
# --------------------------------------------------------------------------
def _v12(res: pd.DataFrame, completo: bool) -> None:
    with st.container(border=True):
        titulo_grafica("V12", "Semaforo de presion turistica",
                       "¿Que destinos estan por encima de su capacidad de carga?",
                       ["Barras con umbral"])
        medida = st.segmented_control(
            "Medida", ["Promedio del periodo", "Mes pico"],
            default="Promedio del periodo", key="v12_medida",
            label_visibility="collapsed") or "Promedio del periodo"
        col = "presion" if medida == "Promedio del periodo" else "presion_pico"
        d = res[["destino", col]].rename(columns={col: "valor"})
        d = d.sort_values("valor").reset_index(drop=True)
        clases = d["valor"].map(_clase_presion)
        d["nivel"] = [c[0] for c in clases]
        d["palabra"] = [c[1] for c in clases]

        fig = go.Figure(go.Bar(
            x=d["valor"], y=d["destino"], orientation="h",
            marker=dict(color=[SEMAFORO[n] for n in d["nivel"]]),
            text=[f"{v:.2f} · {p}" for v, p in zip(d["valor"], d["palabra"])],
            textposition="outside", cliponaxis=False,
            hovertemplate="%{y}<br>Presion: %{x:.2f}<extra></extra>"))
        fig.add_vline(x=1.0, line=dict(color=TINTA_2, width=1.5, dash="dash"))
        fig.add_annotation(x=1.0, y=1.0, yref="paper", text="Capacidad de carga",
                           showarrow=False, xanchor="left", yanchor="bottom",
                           xshift=4, font=dict(size=11, color=TINTA_2))
        tope = max(1.15, float(d["valor"].max()) * 1.3)
        aplicar_estilo(fig, alto=max(260, 60 + 48 * len(d)), showlegend=False,
                       xaxis=dict(title="Llegadas / capacidad de carga",
                                  range=[0, tope]),
                       yaxis=dict(title=""), margin=dict(t=40, r=16))
        mostrar(fig, clave="v12")

        sat = d[d["valor"] > 1.0]["destino"].tolist()
        donde = "en promedio" if col == "presion" else "en su mes de mayor visita"
        if sat:
            lectura(f"{_lista(sat)} {'supera' if len(sat) == 1 else 'superan'} "
                    f"su capacidad de carga {donde}. Conviene revisar aforos y "
                    "escalonar horarios de acceso antes que ampliar la promocion.")
        else:
            lectura(f"Ningun destino supera su capacidad de carga {donde}. "
                    "Los que estan 'Al limite' son los primeros a vigilar.")
        if completo:
            nota("Presion = llegadas del mes / capacidad de carga. Umbrales: menos de "
                 "0.85 Holgura, 0.85 a 1.0 Al limite, mas de 1.0 Saturacion. El "
                 "promedio es simple entre meses; el mes pico muestra el peor mes del "
                 "periodo. La capacidad de carga viene de estudios de sitio: es una "
                 "estimacion, por eso la recomendacion es revisar, no cerrar.")


# --------------------------------------------------------------------------
# V13
# --------------------------------------------------------------------------
def _v13(ctx: dict, foco: str | None, completo: bool) -> None:
    with st.container(border=True):
        titulo_grafica("V13", "Perfil de sostenibilidad",
                       "¿En que dimensiones de sostenibilidad gana y pierde cada destino?",
                       ["Radar", "Hasta 3 destinos"])
        anios = ctx["anios"]
        ref = ctx["mensual_completo"]
        ref = ref[(ref["anio"] >= anios[0]) & (ref["anio"] <= anios[1])]
        if ref.empty:
            sin_datos("No hay datos en el periodo elegido. Amplia el rango de anos.")
            return
        res = _resumen_destinos(ref).set_index("destino")
        opciones = res.sort_values("llegadas", ascending=False).index.tolist()
        if foco and foco in opciones:
            defecto = [foco]
        else:
            defecto = opciones[:3]
        elegidos = st.multiselect("Destinos a comparar", opciones, default=defecto,
                                  max_selections=3, key="v13_destinos",
                                  placeholder="Elige hasta 3 destinos")
        if not elegidos:
            sin_datos("Elige al menos un destino en el selector de arriba para "
                      "dibujar su perfil.")
            return

        crudo = pd.DataFrame({
            DIMENSIONES[0]: -res["presion"],
            DIMENSIONES[1]: res["empleo_local_pct"],
            DIMENSIONES[2]: res["empresas_certificadas_pct"],
            DIMENSIONES[3]: res["satisfaccion"],
            DIMENSIONES[4]: -res["agua_por_visitante"],
            DIMENSIONES[5]: -res["co2_por_visitante"],
        })
        rango = crudo.max() - crudo.min()
        norm = (crudo - crudo.min()) / rango.replace(0, np.nan) * 100
        norm = norm.fillna(50.0)

        fig = go.Figure()
        theta = DIMENSIONES + [DIMENSIONES[0]]
        for destino in elegidos:
            valores = norm.loc[destino].tolist()
            color = COLOR_DESTINO.get(destino, GRIS)
            fig.add_trace(go.Scatterpolar(
                r=valores + [valores[0]], theta=theta, name=destino,
                fill="toself", opacity=0.55,
                line=dict(color=color, width=2.4),
                hovertemplate="%{theta}: %{r:.0f} / 100<extra>" + destino + "</extra>"))
        aplicar_estilo(
            fig, alto=420,
            polar=dict(bgcolor="rgba(0,0,0,0)",
                       radialaxis=dict(range=[0, 100], tickvals=[25, 50, 75, 100],
                                       gridcolor=LINEA, linecolor=LINEA,
                                       tickfont=dict(size=10, color=TINTA_2)),
                       angularaxis=dict(gridcolor=LINEA, linecolor=LINEA,
                                        tickfont=dict(size=11))),
            margin=dict(l=40, r=40, t=50, b=30))
        mostrar(fig, clave="v13")

        mejor = norm.loc[elegidos[0]].idxmax()
        peor = norm.loc[elegidos[0]].idxmin()
        lectura(f"Cuanto mas grande el poligono, mejor. {elegidos[0]} destaca en "
                f"<b>{mejor.lower()}</b> y queda mas rezagado en <b>{peor.lower()}</b> "
                "frente al resto de destinos: ahi esta su margen de mejora.")
        if len(res) < 2:
            aviso("Solo hay un destino en el filtro de lugar: sin otros con que "
                  "comparar, todas las dimensiones quedan en 50.")
        if completo:
            nota(f"Cada eje va de 0 (peor destino) a 100 (mejor destino) entre los "
                 f"{len(res)} destinos del filtro de lugar en {anios[0]}–{anios[1]} "
                 "(normalizacion min-max). Todos se orientan para que mas sea mejor: "
                 "holgura = inverso de la presion, eficiencia hidrica = inverso del agua "
                 "por visitante, baja huella = inverso del CO2 por visitante. Es una "
                 "posicion relativa, no un cumplimiento de metas absolutas.")


# --------------------------------------------------------------------------
# V14
# --------------------------------------------------------------------------
def _v14(res: pd.DataFrame, completo: bool) -> None:
    with st.container(border=True):
        titulo_grafica("V14", "Beneficio local y certificacion",
                       "¿El turismo esta dejando empleo local y empujando la certificacion?",
                       ["Dispersion con cuadrantes"])
        x, y = res["empleo_local_pct"], res["empresas_certificadas_pct"]
        mx, my = float(x.median()), float(y.median())
        tam = res["gasto_total_usd"]
        tam_ref = float(tam.max()) if float(tam.max()) > 0 else 1.0
        tamanos = 18 + 42 * np.sqrt(tam / tam_ref)

        fig = go.Figure(go.Scatter(
            x=x, y=y, mode="markers+text", text=res["destino"],
            textposition="top center", textfont=dict(size=11),
            marker=dict(size=tamanos, color=[COLOR_DESTINO.get(d, GRIS)
                                             for d in res["destino"]],
                        opacity=0.8, line=dict(color="white", width=1.5)),
            customdata=np.stack([res["gasto_total_usd"].map(dinero)], axis=-1),
            hovertemplate="%{text}<br>Empleo local: %{x:.1f}%<br>Certificadas: "
                          "%{y:.1f}%<br>Derrama: %{customdata[0]}<extra></extra>"))
        px_ = max((x.max() - x.min()) * 0.25, 2.0)
        py_ = max((y.max() - y.min()) * 0.25, 2.0)
        x0, x1 = float(x.min() - px_), float(x.max() + px_)
        y0, y1 = float(y.min() - py_), float(y.max() + py_ * 1.4)
        fig.add_vline(x=mx, line=dict(color=GRIS, width=1, dash="dot"))
        fig.add_hline(y=my, line=dict(color=GRIS, width=1, dash="dot"))
        cuadrantes = [
            (x1, y1, "right", "top", "Objetivo: beneficio local y certificacion", VERDE),
            (x0, y1, "left", "top", "Certifica, poco empleo local", TINTA_2),
            (x0, y0, "left", "bottom", "Rezagado en ambos", ROSA),
            (x1, y0, "right", "bottom", "Empleo local, poca certificacion", TINTA_2),
        ]
        for cx, cy, xa, ya, txt, color in cuadrantes:
            fig.add_annotation(x=cx, y=cy, text=txt, showarrow=False, xanchor=xa,
                               yanchor=ya, font=dict(size=11, color=color))
        aplicar_estilo(fig, alto=420, showlegend=False,
                       xaxis=dict(title="Empleo turistico de origen local (%)",
                                  range=[x0, x1]),
                       yaxis=dict(title="Empresas con certificacion sostenible (%)",
                                  range=[y0, y1]))
        mostrar(fig, clave="v14")

        objetivo = res[(x >= mx) & (y >= my)]["destino"].tolist()
        rico = res.sort_values("gasto_total_usd", ascending=False).iloc[0]
        incomodo = (rico["empleo_local_pct"] < mx
                    or rico["empresas_certificadas_pct"] < my)
        texto = ("Arriba a la derecha estan los destinos donde la derrama se "
                 "acompana de beneficio local y certificacion"
                 + (f": {_lista(objetivo)}." if objetivo and len(res) > 1 else "."))
        if incomodo and len(res) > 1:
            texto += (f" Ojo con {rico['destino']}: es el de mayor derrama "
                      f"({dinero(rico['gasto_total_usd'])}) pero queda por debajo de la "
                      "mediana en al menos un eje.")
        lectura(texto)
        if completo:
            nota("Porcentajes ponderados por llegadas en el periodo; el tamano de la "
                 "burbuja es la derrama total. Las lineas punteadas son las medianas "
                 "entre los destinos mostrados, asi que los cuadrantes son relativos. "
                 "La posicion muestra asociacion, no el efecto de una politica.")


# --------------------------------------------------------------------------
def render(ctx: dict) -> None:
    activas = ctx.get("graficas_activas")
    if activas is None:
        activas = CATALOGO
    completo = ctx.get("detalle", "Analisis completo") == "Analisis completo"
    m = ctx["mensual"]
    foco = st.session_state.get("destino_foco")
    foco_activo = bool(foco) and not m.empty and set(m["destino"]) == {foco}

    if foco_activo:
        aviso(f"Esta seccion esta filtrada a <b>{foco}</b> (enfoque elegido en "
              "Panorama). Usa \"Quitar enfoque\" arriba para ver todos los destinos.")

    if m.empty:
        sin_datos("No hay datos para esta combinacion de periodo y lugar. Amplia el "
                  "rango de anos o quita algun filtro de lugar.")
        return

    previo = ctx.get("mensual_previo", pd.DataFrame())
    if foco_activo and not previo.empty:
        previo = previo[previo["destino"] == foco]
    grupo("Huella del periodo")
    _tarjetas(m, previo)

    if not activas:
        sin_datos("No hay graficas seleccionadas. Elige cuales ver en el menu "
                  "\"Graficas\" de la barra superior.")
        return

    res = _resumen_destinos(m)

    if "V11 Desacoplamiento" in activas:
        grupo("Crecimiento y huella")
        _v11(ctx, m, completo)

    v12 = "V12 Presion por destino" in activas
    v13 = "V13 Perfil de sostenibilidad" in activas
    if v12 or v13:
        grupo("Presion y perfil de cada destino")
        izq, der = par_columnas(v12, v13)
        if v12:
            with izq:
                _v12(res, completo)
        if v13:
            with der:
                _v13(ctx, foco if foco_activo else None, completo)

    if "V14 Beneficio local" in activas:
        grupo("Beneficio local")
        _v14(res, completo)

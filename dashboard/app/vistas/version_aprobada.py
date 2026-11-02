"""
Seccion Estimaciones oficiales (Laboratorio 11, MLOps): V21-V23.

Muestra la VERSION APROBADA que publica el pipeline del Lab 11
(results/approved/). Esta seccion no ajusta ningun modelo: solo lee archivos.
Cambiar un filtro aqui nunca vuelve a correr el procedimiento; para cambiar
las cifras hay que ejecutar el pipeline y que la regla de aceptacion lo apruebe.

Si no hay version aprobada, lo dice ("estimaciones no disponibles") en lugar
de mostrar ceros o cifras viejas sin aviso.
"""

from __future__ import annotations

import json
import os
from pathlib import Path

import pandas as pd
import plotly.graph_objects as go
import streamlit as st

import datos as dt
from componentes import (aplicar_estilo, aviso, grupo, kpi, lectura, miles,
                         mostrar, nota, sin_datos, titulo_grafica)
from config import AZUL, GRIS, MORADO, NARANJA, ROSA, VERDE

V21 = "V21 Observado y estimacion oficial"
V22 = "V22 Prueba historica (backtesting)"
V23 = "V23 Estado del flujo"
TODAS = [V21, V22, V23]

# En Docker Compose la carpeta results/ del pipeline se monta en /resultados
CARPETA = Path(os.environ.get(
    "OTS_RESULTADOS", Path(__file__).resolve().parents[3] / "results"))
APROBADA = CARPETA / "approved"

NOMBRE_PROC = {"procedimiento": "Procedimiento oficial",
               "ref_ultimo_valor": "Referencia: ultimo valor",
               "ref_promedio_hist": "Referencia: promedio historico"}
COLOR_PROC = {"procedimiento": MORADO, "ref_ultimo_valor": NARANJA,
              "ref_promedio_hist": GRIS}


# --------------------------------------------------------------------------
# Lectura (la cache se invalida cuando cambia el archivo publicado)
# --------------------------------------------------------------------------
def _marca(ruta: Path) -> float:
    return ruta.stat().st_mtime if ruta.exists() else 0.0


@st.cache_data(show_spinner=False)
def _leer_csv(ruta: str, _marca_tiempo: float) -> pd.DataFrame | None:
    if not os.path.exists(ruta):
        return None
    return pd.read_csv(ruta)


@st.cache_data(show_spinner=False)
def _leer_json(ruta: str, _marca_tiempo: float) -> dict | None:
    if not os.path.exists(ruta):
        return None
    with open(ruta, encoding="utf-8") as f:
        return json.load(f)


def cargar_version() -> dict:
    rutas = {"estimaciones": APROBADA / "estimaciones.csv",
             "metadatos": APROBADA / "run_metadata.json",
             "backtest": APROBADA / "backtest.csv",
             "calidad": APROBADA / "reporte_calidad.json",
             "restauracion": APROBADA / "restauracion.json",
             "monitoreo": CARPETA / "monitoreo.json"}
    out = {}
    for k, r in rutas.items():
        lector = _leer_csv if r.suffix == ".csv" else _leer_json
        out[k] = lector(str(r), _marca(r))
    est = out["estimaciones"]
    if est is not None:
        est = est.copy()
        est["periodo_estimado"] = pd.to_datetime(est["periodo_estimado"])
        out["estimaciones"] = est
    if out["backtest"] is not None:
        out["backtest"] = out["backtest"].assign(
            periodo=pd.to_datetime(out["backtest"]["periodo"]))
    return out


def _mes_anio(fecha: pd.Timestamp) -> str:
    return f"{dt.NOMBRES_MES[fecha.month - 1]} {fecha.year}"


# --------------------------------------------------------------------------
# Entrada
# --------------------------------------------------------------------------
def render(ctx: dict) -> None:
    v = cargar_version()
    est, meta = v["estimaciones"], v["metadatos"]

    if est is None or meta is None:
        sin_datos("<b>Estimaciones no disponibles.</b> Todavia no hay una version "
                  "aprobada del procedimiento oficial. Las cifras apareceran aqui "
                  "cuando el pipeline del Laboratorio 11 publique una version que "
                  "pase los controles de calidad y la regla de aceptacion.")
        return

    activas = ctx.get("graficas_activas")
    activas = TODAS if activas is None else activas
    completo = ctx.get("detalle") != "Resumen ejecutivo"

    _encabezado(est, meta, v)
    if not activas:
        sin_datos("No hay graficas seleccionadas en esta seccion. Abra el menu "
                  "<b>Graficas</b> de la barra superior y elija al menos una.")
        return
    if V21 in activas:
        _v21(est, meta, ctx, completo)
    if V22 in activas:
        _v22(v["backtest"], meta, completo)
    if V23 in activas:
        _v23(meta, v["calidad"], v["monitoreo"], v["restauracion"], completo)


def _encabezado(est, meta, v) -> None:
    grupo("VERSION VIGENTE")
    proc = (meta.get("metricas") or {}).get("procedimiento", {})
    futuros = est[(est["tipo"] == "estimacion") & est["valor_observado"].isna()] \
        if "valor_observado" in est.columns else est[est["tipo"] == "estimacion"]
    c = st.columns(4, gap="small")
    with c[0]:
        kpi("Actualizado", str(est["fecha_generacion"].iloc[0]),
            f"version {meta.get('version_procedimiento', est['version_procedimiento'].iloc[0])}",
            "celeste")
    with c[1]:
        kpi("Error tipico (MAE)", miles(proc.get("MAE", est["metrica_validacion_MAE"].iloc[0])),
            f"personas/mes en {proc.get('n_meses', '?')} meses de prueba", "morado")
    with c[2]:
        if len(futuros):
            prox = futuros.iloc[0]
            kpi(f"Estimacion {_mes_anio(prox['periodo_estimado'])}",
                miles(prox["valor"]), "personas (estimacion)", "azul")
        else:
            kpi("Estimaciones futuras", "—", "sin horizonte publicado", "azul")
    with c[3]:
        aprob = meta.get("aprobado", False)
        kpi("Estado", "Aprobada" if aprob else "Sin aprobar",
            f"run {meta.get('run_id', '')[4:19]}", "verde" if aprob else "rosa")

    if (meta.get("fuente") or {}).get("es_muestra_sintetica"):
        aviso("Esta version se genero con la <b>muestra sintetica</b> del laboratorio, "
              "no con la base institucional. Las cifras ilustran el flujo; no deben "
              "citarse como dato oficial.")
    if v.get("restauracion") and v["restauracion"].get("run_id") == meta.get("run_id"):
        r = v["restauracion"]
        aviso(f"Version <b>restaurada</b> el {r['ts'][:10]} (motivo: {r.get('motivo')}). "
              f"Reemplazo a {r.get('reemplaza_a')}.")


# --------------------------------------------------------------------------
# V21: serie publicada
# --------------------------------------------------------------------------
def _v21(est, meta, ctx, completo) -> None:
    with st.container(border=True):
        titulo_grafica("V21", "Movimientos mensuales de viajeros: observado y estimacion",
                       "¿Que cifras oficiales puede usar hoy y cuales son estimaciones?",
                       ["Serie de tiempo", "Observado vs. estimado", "Estimacion"])
        anios = ctx.get("anios") or (2009, 2100)
        vista = est[est["periodo_estimado"].dt.year.between(anios[0] - 1, anios[1] + 1)
                    | (est["tipo"] == "estimacion")]
        obs = vista[vista["tipo"] == "observado"]
        estm = vista[vista["tipo"] == "estimacion"]

        fig = go.Figure()
        fig.add_trace(go.Scatter(
            x=obs["periodo_estimado"], y=obs["valor"], name="Observado",
            mode="lines", line=dict(color=AZUL, width=2.4),
            hovertemplate="%{x|%b %Y}<br>Observado: %{y:,.0f}<extra></extra>"))
        if "valor_observado" in estm.columns:
            contraste = estm[estm["valor_observado"].notna()]
            if len(contraste):
                fig.add_trace(go.Scatter(
                    x=contraste["periodo_estimado"], y=contraste["valor_observado"],
                    name="Observado (mes oculto)", mode="markers",
                    marker=dict(color=AZUL, size=9, symbol="circle-open", line=dict(width=2)),
                    hovertemplate="%{x|%b %Y}<br>Observado real: %{y:,.0f}<extra></extra>"))
        if len(estm):
            # se une al ultimo observado anterior para que no quede un salto visual
            antes = obs[obs["periodo_estimado"] < estm["periodo_estimado"].min()].tail(1)
            xs = [*antes["periodo_estimado"], *estm["periodo_estimado"]]
            ys = [*antes["valor"], *estm["valor"]]
            fig.add_trace(go.Scatter(
                x=xs, y=ys, name="Estimacion oficial", mode="lines+markers",
                line=dict(color=MORADO, width=2.4, dash="dash"),
                marker=dict(size=7, color=MORADO),
                hovertemplate="%{x|%b %Y}<br>Estimacion: %{y:,.0f}<extra></extra>"))
        aplicar_estilo(fig, alto=420, hovermode="x unified",
                       yaxis=dict(title="Personas por mes", rangemode="tozero"),
                       xaxis=dict(title=None))
        mostrar(fig, clave="v21")

        mae = (meta.get("metricas") or {}).get("procedimiento", {}).get("MAE")
        futuros = estm[estm["valor_observado"].isna()] if "valor_observado" in estm else estm
        if len(futuros) and mae:
            f0 = futuros.iloc[0]
            lectura(f"Para <b>{_mes_anio(f0['periodo_estimado'])}</b> la estimacion oficial es "
                    f"de <b>{miles(f0['valor'])} personas</b>. En la prueba historica el "
                    f"procedimiento se equivoco, en promedio, en ±{miles(mae)} personas por "
                    "mes: use la cifra como orden de magnitud, no como conteo exacto.")
        if completo:
            nota("Linea continua azul = dato observado; linea punteada morada = estimacion. "
                 "Los circulos huecos son el observado real de los meses que se ocultaron "
                 "al procedimiento para comprobarlo. Enero y febrero de 2026 no tienen "
                 "observado comparable (la clasificacion de la base cambio en 2023), por "
                 "eso no se calcula su error. Esta grafica lee el archivo aprobado; "
                 "cambiar los filtros no vuelve a ajustar el modelo.")


# --------------------------------------------------------------------------
# V22: backtesting
# --------------------------------------------------------------------------
def _v22(bt, meta, completo) -> None:
    with st.container(border=True):
        titulo_grafica("V22", "Prueba historica del procedimiento oficial",
                       "¿Se equivoca menos que un metodo ingenuo en meses que no vio?",
                       ["Serie de tiempo", "Observado vs. estimado", "Estimacion"])
        if bt is None or bt.empty:
            sin_datos("La version vigente no incluye el detalle del backtesting.")
            return
        fig = go.Figure()
        fig.add_trace(go.Scatter(
            x=bt["periodo"], y=bt["observado"], name="Observado", mode="lines",
            line=dict(color=AZUL, width=2.6),
            hovertemplate="%{x|%b %Y}<br>Observado: %{y:,.0f}<extra></extra>"))
        for col in ("procedimiento", "ref_ultimo_valor", "ref_promedio_hist"):
            fig.add_trace(go.Scatter(
                x=bt["periodo"], y=bt[col], name=NOMBRE_PROC[col], mode="lines",
                line=dict(color=COLOR_PROC[col], width=2.0 if col == "procedimiento" else 1.4,
                          dash="dash" if col == "procedimiento" else "dot"),
                hovertemplate=f"{NOMBRE_PROC[col]}: %{{y:,.0f}}<extra></extra>"))
        aplicar_estilo(fig, alto=380, hovermode="x unified",
                       yaxis=dict(title="Personas por mes", rangemode="tozero"),
                       xaxis=dict(title=None))
        mostrar(fig, clave="v22")

        m = meta.get("metricas") or {}
        filas = [{"Procedimiento": NOMBRE_PROC[k], "MAE": round(v["MAE"]),
                  "RMSE": round(v["RMSE"]), "MAPE (%)": round(v.get("MAPE", float("nan")), 1),
                  "Meses": v.get("n_meses")} for k, v in m.items() if k in NOMBRE_PROC]
        if filas:
            st.dataframe(pd.DataFrame(filas), hide_index=True, width="stretch")
            p = m.get("procedimiento", {})
            refs = [m[k]["MAE"] for k in ("ref_ultimo_valor", "ref_promedio_hist") if k in m]
            if p and refs:
                mejora = (1 - p["MAE"] / min(refs)) * 100
                lectura(f"En {p.get('n_meses')} meses de prueba el procedimiento oficial "
                        f"se equivoco <b>{mejora:.0f}% menos</b> que la mejor referencia "
                        "simple. Esa comparacion es parte de la regla que autoriza publicar.")
        if completo:
            per = meta.get("periodos") or {}
            u = meta.get("umbrales") or {}
            nota(f"Origen movil sobre {per.get('evaluacion_inicio', '?')[:7]} a "
                 f"{per.get('evaluacion_fin', '?')[:7]}: cada mes se estima solo con los "
                 f"meses anteriores. Regla de aceptacion: MAE ≤ {miles(u.get('mae_maximo', 0))}, "
                 f"RMSE ≤ {miles(u.get('rmse_maximo', 0))}, al menos "
                 f"{u.get('meses_minimos_backtest', '?')} meses evaluados, ningun control "
                 "critico fallido y MAE no peor que la mejor referencia.")


# --------------------------------------------------------------------------
# V23: estado del flujo (controles y monitoreo)
# --------------------------------------------------------------------------
_ESTADO = {"ok": ("Correcto", VERDE), "advertencia": ("Advertencia", NARANJA),
           "error": ("Detiene", ROSA)}
_NOMBRE_CONTROL = {"columnas_y_tipos": "1. Columnas y tipos",
                   "fechas_y_cobertura": "2. Fechas y cobertura",
                   "unicidad": "3. Unicidad",
                   "valores_faltantes": "4. Valores faltantes",
                   "valores_y_denominadores": "5. Valores y denominadores",
                   "regla_metodologica": "6. Regla metodologica"}


def _v23(meta, calidad, monitoreo, restauracion, completo) -> None:
    with st.container(border=True):
        titulo_grafica("V23", "Estado del flujo de actualizacion",
                       "¿Esta cifra paso los controles y esta al dia?",
                       ["Controles de calidad", "Monitoreo"])
        izq, der = st.columns(2, gap="small")
        with izq:
            st.markdown("**Controles de calidad de la version vigente**")
            controles = (calidad or {}).get("controles", [])
            if not controles:
                sin_datos("Sin reporte de calidad en la version vigente.")
            for c in controles:
                texto, color = _ESTADO.get(c["estado"], (c["estado"], GRIS))
                st.markdown(
                    f'<div style="display:flex;justify-content:space-between;'
                    f'padding:4px 0;border-bottom:1px solid #DFE3F2">'
                    f'<span>{_NOMBRE_CONTROL.get(c["control"], c["control"])}</span>'
                    f'<span style="color:{color};font-weight:600">{texto}</span></div>',
                    unsafe_allow_html=True)
        with der:
            st.markdown("**Monitoreo**")
            if not monitoreo:
                sin_datos("Aun no se ha ejecutado el monitoreo "
                          "(<code>python scripts/monitor.py</code>).")
            else:
                ok = monitoreo.get("estado") == "ok"
                det = monitoreo.get("detalle", {})
                st.markdown(
                    f'<span style="color:{VERDE if ok else ROSA};font-weight:700">'
                    f'{"Sin alertas" if ok else "Con alertas"}</span> · revisado '
                    f'{monitoreo.get("generado", "")[:16].replace("T", " ")} UTC',
                    unsafe_allow_html=True)
                if "dias_desde_actualizacion" in det:
                    st.markdown(f"- Dias desde la ultima actualizacion: "
                                f"**{det['dias_desde_actualizacion']:.0f}**")
                st.markdown(f"- Corridas registradas: **{det.get('corridas_registradas', 0)}**"
                            f" · sin aprobar seguidas: **{det.get('corridas_sin_aprobar_seguidas', 0)}**")
                for a in monitoreo.get("alertas", []):
                    st.markdown(f"- :red[{a}]")
                for a in monitoreo.get("advertencias", []):
                    st.markdown(f"- :orange[{a}]")
        if completo:
            fuente = meta.get("fuente") or {}
            nota(f"Trazabilidad: run <code>{meta.get('run_id')}</code> · commit "
                 f"<code>{meta.get('commit')}</code> · huella de la fuente "
                 f"<code>{fuente.get('huella')}</code> · huella de la configuracion "
                 f"<code>{meta.get('huella_config')}</code>"
                 + (f" · MLflow <code>{meta['mlflow_run_id']}</code>"
                    if meta.get("mlflow_run_id") else "")
                 + ". Si una corrida falla un control critico o la regla de aceptacion, "
                 "esta seccion sigue mostrando la ultima version aprobada.")

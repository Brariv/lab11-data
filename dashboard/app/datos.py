"""
Capa de datos del Observatorio: carga, cache y agregaciones.

Todo el tablero lee de aqui. Si manana se sustituyen los CSV por datos
oficiales de INGUAT o del INE, este es el unico modulo que hay que tocar.
"""

from __future__ import annotations

import runpy
from pathlib import Path

import pandas as pd
import streamlit as st

RAIZ = Path(__file__).resolve().parent.parent
CARPETA_DATOS = RAIZ / "data"

ARCHIVOS = {
    "mensual": CARPETA_DATOS / "turismo_mensual.csv",
    "mercados": CARPETA_DATOS / "mercados.csv",
    "visitantes": CARPETA_DATOS / "visitantes.csv",
}

CATEGORIAS_GASTO = {
    "gasto_alojamiento_usd": "Alojamiento",
    "gasto_alimentacion_usd": "Alimentacion",
    "gasto_transporte_usd": "Transporte",
    "gasto_actividades_usd": "Actividades y tours",
    "gasto_artesanias_usd": "Artesanias y compras",
}

NOMBRES_MES = ["Ene", "Feb", "Mar", "Abr", "May", "Jun",
               "Jul", "Ago", "Sep", "Oct", "Nov", "Dic"]


def _asegurar_datos() -> None:
    if all(p.exists() for p in ARCHIVOS.values()):
        return
    # Primera ejecucion: construye los CSV con la semilla fija del generador.
    runpy.run_path(str(CARPETA_DATOS / "generar_datos.py"), run_name="__main__")


@st.cache_data(show_spinner="Cargando datos del observatorio...")
def cargar() -> dict[str, pd.DataFrame]:
    _asegurar_datos()
    mensual = pd.read_csv(ARCHIVOS["mensual"], parse_dates=["fecha"])
    mercados = pd.read_csv(ARCHIVOS["mercados"], parse_dates=["fecha"])
    visitantes = pd.read_csv(ARCHIVOS["visitantes"], parse_dates=["fecha"])

    for df in (mensual, mercados):
        df["nombre_mes"] = df["mes"].map(lambda m: NOMBRES_MES[m - 1])
    mensual["trimestre_num"] = (mensual["mes"] - 1) // 3 + 1
    return {"mensual": mensual, "mercados": mercados, "visitantes": visitantes}


# --------------------------------------------------------------------------
# Filtros
# --------------------------------------------------------------------------
def filtrar(df: pd.DataFrame, anios: tuple[int, int],
            destinos: list[str] | None = None,
            regiones: list[str] | None = None) -> pd.DataFrame:
    out = df[(df["anio"] >= anios[0]) & (df["anio"] <= anios[1])]
    if regiones:
        out = out[out["region"].isin(regiones)]
    if destinos:
        out = out[out["destino"].isin(destinos)]
    return out


# --------------------------------------------------------------------------
# Agregaciones: el "nivel de detalle" temporal del tablero
# --------------------------------------------------------------------------
SUMABLES = ["llegadas", "noches_totales", "gasto_total_usd", "residuos_ton",
            "agua_miles_m3", "co2_ton", "empleos_turisticos",
            *CATEGORIAS_GASTO.keys()]
PROMEDIABLES = ["ocupacion_hotelera", "gasto_diario_usd", "estancia_promedio",
                "empleo_local_pct", "empresas_certificadas_pct",
                "presion_turistica", "satisfaccion_promedio"]


def agregar_tiempo(df: pd.DataFrame, nivel: str,
                   por: list[str] | None = None) -> pd.DataFrame:
    """Colapsa la serie al nivel pedido: 'Mes', 'Trimestre' o 'Ano'.

    Las magnitudes de volumen se suman; las tasas y promedios se ponderan por
    llegadas, para no dar el mismo peso a un mes de 9 000 visitantes que a uno
    de 90 000.
    """
    por = por or []
    if nivel == "Mes":
        clave = df["fecha"]
    elif nivel == "Trimestre":
        clave = df["fecha"].dt.to_period("Q").dt.start_time
    else:
        clave = df["fecha"].dt.to_period("Y").dt.start_time

    tmp = df.copy()
    tmp["periodo"] = clave
    tmp["_peso"] = tmp["llegadas"]
    for col in PROMEDIABLES:
        if col in tmp.columns:
            tmp[f"_w_{col}"] = tmp[col] * tmp["_peso"]

    llaves = ["periodo", *por]
    cols_suma = {c: "sum" for c in SUMABLES if c in tmp.columns}
    cols_suma["_peso"] = "sum"
    cols_suma.update({f"_w_{c}": "sum" for c in PROMEDIABLES if c in tmp.columns})

    out = tmp.groupby(llaves, as_index=False).agg(cols_suma)
    for col in PROMEDIABLES:
        if f"_w_{col}" in out.columns:
            out[col] = out[f"_w_{col}"] / out["_peso"].replace(0, pd.NA)
    out = out.drop(columns=[c for c in out.columns if c.startswith("_w_")] + ["_peso"])

    if nivel == "Mes":
        out["etiqueta"] = out["periodo"].dt.strftime("%b %Y")
    elif nivel == "Trimestre":
        out["etiqueta"] = (out["periodo"].dt.year.astype(str) + "-T"
                           + out["periodo"].dt.quarter.astype(str))
    else:
        out["etiqueta"] = out["periodo"].dt.year.astype(str)
    return out.sort_values(["periodo", *por]).reset_index(drop=True)


def gasto_largo(df: pd.DataFrame, por: list[str]) -> pd.DataFrame:
    """Pasa las columnas de gasto a formato largo (una fila por categoria)."""
    cols = list(CATEGORIAS_GASTO.keys())
    out = df.groupby(por, as_index=False)[cols].sum()
    out = out.melt(id_vars=por, value_vars=cols,
                   var_name="categoria", value_name="gasto_usd")
    out["categoria"] = out["categoria"].map(CATEGORIAS_GASTO)
    return out


def serie_nacional(df: pd.DataFrame) -> pd.DataFrame:
    """Serie mensual del pais (suma de destinos) lista para los modelos."""
    out = (df.groupby("fecha", as_index=False)["llegadas"].sum()
             .sort_values("fecha").reset_index(drop=True))
    return out


def variacion(actual: float, previo: float) -> float | None:
    if previo in (0, None) or pd.isna(previo) or pd.isna(actual):
        return None
    return (actual / previo - 1) * 100

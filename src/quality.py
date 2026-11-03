"""
Controles automaticos de calidad (Laboratorio 11, MLOps).

Seis controles minimos. Cada control declara:
  - que verifica
  - cuando genera ADVERTENCIA (el flujo continua)
  - cuando DETIENE la ejecucion (control critico fallido)

Regla general del laboratorio:
  - Los periodos sin cobertura NO se convierten automaticamente en cero.
  - Si falla un control critico, el pipeline se detiene ANTES de reemplazar
    los resultados vigentes del tablero.

El modulo no imprime resultados finales ni publica: solo evalua y devuelve un
reporte estructurado. La decision de detener la toma el orquestador.
"""
from __future__ import annotations
import math
import numpy as np
import pandas as pd

OK = "ok"
ADVERTENCIA = "advertencia"
ERROR = "error"


def _res(control, estado, critico, detalle, items=None):
    return {
        "control": control,
        "estado": estado,
        "critico": bool(critico),
        "detalle": detalle,
        "items": items or [],
    }


# ----------------------------------------------------------------------
# Control 1: Columnas y tipos
# ----------------------------------------------------------------------
def control_columnas_y_tipos(df, cfg):
    """Verifica que existan las columnas indispensables y que el tipo sea
    compatible. DETIENE si falta una variable o el tipo es incompatible."""
    requeridas = cfg["fuentes"]["migracion_mensual"]["columnas_requeridas"]
    faltantes = [c for c in requeridas if c not in df.columns]
    if faltantes:
        return _res("columnas_y_tipos", ERROR, True,
                    f"Faltan columnas indispensables: {faltantes}", faltantes)

    problemas = []
    for col, tipo in requeridas.items():
        serie = df[col]
        try:
            if tipo == "date":
                pd.to_datetime(serie, errors="raise")
            elif tipo == "int":
                # Los NA no son un problema de tipo: los clasifica el control 4
                # (ausencia permitida o faltante que impide estimar).
                conv = pd.to_numeric(serie, errors="coerce")
                no_convertibles = conv.isna() & serie.notna()
                if no_convertibles.any() or (conv.dropna() % 1 != 0).any():
                    problemas.append(f"{col}: no es entero compatible")
            elif tipo == "string":
                if serie.dropna().map(lambda x: isinstance(x, (int, float))).all() and len(serie.dropna()):
                    problemas.append(f"{col}: se esperaba texto")
        except Exception as e:  # tipo incompatible
            problemas.append(f"{col}: {e}")

    if problemas:
        return _res("columnas_y_tipos", ERROR, True,
                    "Tipos incompatibles detectados", problemas)
    return _res("columnas_y_tipos", OK, True, "Columnas y tipos correctos")


# ----------------------------------------------------------------------
# Control 2: Fechas y cobertura
# ----------------------------------------------------------------------
def control_fechas_y_cobertura(df, cfg):
    """Detecta fechas invalidas (DETIENE) y periodos requeridos sin informacion
    o con cobertura parcial (ADVERTENCIA; no se rellenan con cero)."""
    per = pd.to_datetime(df["periodo"], errors="coerce")
    invalidas = int(per.isna().sum())
    if invalidas:
        return _res("fechas_y_cobertura", ERROR, True,
                    f"{invalidas} fechas invalidas en 'periodo'")

    p = cfg["periodos"]
    esperados = pd.period_range(p["inicio_serie"], p["fin_serie"], freq="M")
    presentes = per.dt.to_period("M").unique()
    faltan_periodos = [str(x) for x in esperados if x not in presentes]

    dmin = cfg["controles"]["cobertura"]["dias_minimos_mes"]
    cobertura_parcial = []
    if "dias_fuente" in df.columns:
        d = pd.to_numeric(df["dias_fuente"], errors="coerce")
        cobertura_parcial = [
            str(pr.date()) for pr, dd in zip(per, d)
            if pd.notna(dd) and dd < dmin
        ]

    if faltan_periodos or cobertura_parcial:
        return _res("fechas_y_cobertura", ADVERTENCIA, False,
                    "Periodos sin informacion o con cobertura parcial "
                    "(NO se rellenan con cero; quedan como faltantes).",
                    {"periodos_faltantes": faltan_periodos,
                     "cobertura_parcial": cobertura_parcial})
    return _res("fechas_y_cobertura", OK, False, "Fechas validas y cobertura completa")


# ----------------------------------------------------------------------
# Control 3: Unicidad
# ----------------------------------------------------------------------
def control_unicidad(df, cfg):
    """Detecta duplicados segun la clave y granularidad definidas. DETIENE."""
    clave = cfg["fuentes"]["migracion_mensual"]["clave_unicidad"]
    dup = df.duplicated(subset=clave, keep=False)
    n = int(dup.sum())
    if n:
        ejemplos = (df.loc[dup, clave].astype(str)
                    .agg(" | ".join, axis=1).unique().tolist()[:10])
        return _res("unicidad", ERROR, True,
                    f"{n} filas duplicadas por clave {clave}", ejemplos)
    return _res("unicidad", OK, True, f"Sin duplicados por clave {clave}")


# ----------------------------------------------------------------------
# Control 4: Valores faltantes
# ----------------------------------------------------------------------
def control_valores_faltantes(df, cfg):
    """Distingue ausencias permitidas de faltantes que impiden estimar.
    NA en columnas que bloquean => DETIENE. NA en columnas permitidas => ADVERTENCIA."""
    conf = cfg["controles"]["faltantes"]
    bloquean = [c for c in conf["columnas_bloquean_na"] if c in df.columns]
    permiten = [c for c in conf["columnas_permiten_na"] if c in df.columns]

    criticos = {c: int(df[c].isna().sum()) for c in bloquean if df[c].isna().any()}
    if criticos:
        return _res("valores_faltantes", ERROR, True,
                    "Faltantes en columnas indispensables para estimar", criticos)

    permitidos = {c: int(df[c].isna().sum()) for c in permiten if df[c].isna().any()}
    if permitidos:
        return _res("valores_faltantes", ADVERTENCIA, False,
                    "Faltantes en columnas con ausencia permitida", permitidos)
    return _res("valores_faltantes", OK, True, "Sin faltantes bloqueantes")


# ----------------------------------------------------------------------
# Control 5: Valores y denominadores
# ----------------------------------------------------------------------
def control_valores_y_denominadores(df, cfg):
    """Detecta conteos negativos, valores no finitos y denominadores = 0.
    DETIENE en cualquiera de esos casos."""
    problemas = []
    if "viajeros" not in df.columns:
        problemas.append("no se puede verificar: falta la columna 'viajeros'")
    else:
        v = pd.to_numeric(df["viajeros"], errors="coerce").astype("float64")
        if (v < 0).any():
            problemas.append(f"viajeros negativos: {int((v < 0).sum())}")
        if (~np.isfinite(v.to_numpy())).any():
            problemas.append("viajeros con valores no finitos (inf/NaN)")
    if "dias_fuente" in df.columns:
        d = pd.to_numeric(df["dias_fuente"], errors="coerce")
        if (d == 0).any():
            problemas.append(f"denominador dias_fuente = 0: {int((d == 0).sum())}")

    if problemas:
        return _res("valores_y_denominadores", ERROR, True,
                    "Valores o denominadores invalidos", problemas)
    return _res("valores_y_denominadores", OK, True,
                "Conteos no negativos, finitos y denominadores validos")


# ----------------------------------------------------------------------
# Control 6: Regla metodologica del proyecto
# ----------------------------------------------------------------------
def control_regla_metodologica(df, cfg):
    """Regla del proyecto: la serie MENSUAL debe provenir de la fuente mensual
    correspondiente y NO de sumar presencias diarias. DETIENE si algun registro
    proviene de 'diaria_agregada'."""
    if "origen_fuente" not in df.columns:
        return _res("regla_metodologica", ERROR, True,
                    "No se puede verificar el origen de la serie (falta 'origen_fuente')")
    malos = df[df["origen_fuente"].astype(str).str.lower() != "mensual"]
    if len(malos):
        per = malos["periodo"].astype(str).tolist()[:10]
        return _res("regla_metodologica", ERROR, True,
                    "Hay meses que NO provienen de la fuente mensual "
                    "(posible suma de presencias diarias)", per)
    return _res("regla_metodologica", OK, True,
                "Toda la serie proviene de la fuente mensual")


CONTROLES = [
    control_columnas_y_tipos,
    control_fechas_y_cobertura,
    control_unicidad,
    control_valores_faltantes,
    control_valores_y_denominadores,
    control_regla_metodologica,
]


def perfil_calidad(df, cfg):
    """Conteos simples de faltantes, duplicados y cobertura de una fuente.

    No decide nada: se guarda en cada corrida para que el monitoreo compare
    una corrida con la anterior y detecte cambios relevantes. Tolera columnas
    ausentes (en ese caso el conteo correspondiente queda en None)."""
    fuente = cfg["fuentes"]["migracion_mensual"]
    requeridas = [c for c in fuente["columnas_requeridas"] if c in df.columns]
    clave = [c for c in fuente["clave_unicidad"] if c in df.columns]
    p = cfg["periodos"]
    out = {
        "filas": int(len(df)),
        "faltantes": int(df[requeridas].isna().sum().sum()) if requeridas else None,
        "duplicados": (int(df.duplicated(subset=clave, keep=False).sum())
                       if len(clave) == len(fuente["clave_unicidad"]) else None),
        "periodos_sin_informacion": None,
        "meses_cobertura_parcial": None,
        "ultimo_periodo": None,
    }
    if "periodo" in df.columns:
        per = pd.to_datetime(df["periodo"], errors="coerce")
        esperados = pd.period_range(p["inicio_serie"], p["fin_serie"], freq="M")
        presentes = set(per.dropna().dt.to_period("M"))
        out["periodos_sin_informacion"] = int(sum(x not in presentes for x in esperados))
        if per.notna().any():
            out["ultimo_periodo"] = per.max().date().isoformat()
    if "dias_fuente" in df.columns:
        d = pd.to_numeric(df["dias_fuente"], errors="coerce")
        out["meses_cobertura_parcial"] = int(
            (d < cfg["controles"]["cobertura"]["dias_minimos_mes"]).sum())
    return out


def ejecutar_controles(df, cfg):
    """Ejecuta los seis controles y devuelve (reporte, hay_error_critico)."""
    resultados = []
    for fn in CONTROLES:
        try:
            resultados.append(fn(df, cfg))
        except Exception as e:  # un control nunca debe tumbar el proceso en silencio
            resultados.append(_res(fn.__name__, ERROR, True,
                                   f"Excepcion en el control: {e}"))
    hay_critico = any(r["estado"] == ERROR and r["critico"] for r in resultados)
    reporte = {
        "controles": resultados,
        "resumen": {
            "ok": sum(r["estado"] == OK for r in resultados),
            "advertencias": sum(r["estado"] == ADVERTENCIA for r in resultados),
            "errores": sum(r["estado"] == ERROR for r in resultados),
        },
        "detener_pipeline": hay_critico,
        "perfil": perfil_calidad(df, cfg),
    }
    return reporte, hay_critico

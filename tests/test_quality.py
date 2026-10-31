"""Pruebas minimas de los controles de calidad."""
import pandas as pd
import yaml
import os
from src import quality

CFG = yaml.safe_load(open(os.path.join("config", "config.yaml")))


def _df_valido():
    return pd.DataFrame({
        "periodo": ["2024-01-01", "2024-02-01"],
        "destino": ["flujo_mensual_nacional"] * 2,
        "viajeros": [100000, 90000],
        "dias_fuente": [31, 29],
        "origen_fuente": ["mensual", "mensual"],
    })


def test_datos_validos_pasan():
    rep, critico = quality.ejecutar_controles(_df_valido(), CFG)
    assert not critico
    assert rep["resumen"]["errores"] == 0


def test_columna_ausente_detiene():
    df = _df_valido().drop(columns=["viajeros"])
    _, critico = quality.ejecutar_controles(df, CFG)
    assert critico


def test_duplicado_detiene():
    df = pd.concat([_df_valido(), _df_valido().iloc[[0]]], ignore_index=True)
    r = quality.control_unicidad(df, CFG)
    assert r["estado"] == quality.ERROR and r["critico"]


def test_denominador_cero_detiene():
    df = _df_valido()
    df.loc[0, "dias_fuente"] = 0
    r = quality.control_valores_y_denominadores(df, CFG)
    assert r["estado"] == quality.ERROR


def test_regla_metodologica_detiene():
    df = _df_valido()
    df.loc[0, "origen_fuente"] = "diaria_agregada"
    r = quality.control_regla_metodologica(df, CFG)
    assert r["estado"] == quality.ERROR

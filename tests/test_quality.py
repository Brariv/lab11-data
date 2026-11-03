"""Pruebas minimas de los controles de calidad."""
import pandas as pd
import yaml
import os
from src import quality

CFG = yaml.safe_load(open(os.path.join("config", "config.yaml"), encoding="utf-8"))


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


def test_columna_ausente_no_rompe_control_de_valores():
    df = _df_valido().drop(columns=["viajeros"])
    r = quality.control_valores_y_denominadores(df, CFG)
    assert r["estado"] == quality.ERROR
    assert "Excepcion" not in r["detalle"]


def test_negativos_detienen():
    df = _df_valido()
    df.loc[0, "viajeros"] = -5
    assert quality.control_valores_y_denominadores(df, CFG)["estado"] == quality.ERROR


def test_fecha_invalida_detiene():
    df = _df_valido()
    df.loc[0, "periodo"] = "2024-13-45"
    r = quality.control_fechas_y_cobertura(df, CFG)
    assert r["estado"] == quality.ERROR and r["critico"]


def test_cobertura_parcial_es_advertencia():
    df = _df_valido()
    df.loc[0, "dias_fuente"] = 10
    r = quality.control_fechas_y_cobertura(df, CFG)
    assert r["estado"] == quality.ADVERTENCIA and not r["critico"]
    assert "2024-01-01" in r["items"]["cobertura_parcial"]


def test_faltante_bloqueante_detiene_y_permitido_advierte():
    df = _df_valido()
    df.loc[0, "viajeros"] = None
    assert quality.control_valores_faltantes(df, CFG)["estado"] == quality.ERROR
    df = _df_valido()
    df.loc[0, "dias_fuente"] = None
    assert quality.control_valores_faltantes(df, CFG)["estado"] == quality.ADVERTENCIA


def test_regla_metodologica_detiene():
    df = _df_valido()
    df.loc[0, "origen_fuente"] = "diaria_agregada"
    r = quality.control_regla_metodologica(df, CFG)
    assert r["estado"] == quality.ERROR


def test_na_en_columna_entera_no_es_error_de_tipo():
    # dias_fuente admite NA: lo trata el control 4 como advertencia, no el 1
    df = _df_valido().astype({"dias_fuente": "float"})
    df.loc[1, "dias_fuente"] = None
    rep, critico = quality.ejecutar_controles(df, CFG)
    estados = {r["control"]: r["estado"] for r in rep["controles"]}
    assert estados["columnas_y_tipos"] == quality.OK
    assert estados["valores_faltantes"] == quality.ADVERTENCIA
    assert not critico


def test_texto_en_columna_entera_si_es_error_de_tipo():
    df = _df_valido().astype({"viajeros": "object"})
    df.loc[1, "viajeros"] = "mucho"
    assert quality.control_columnas_y_tipos(df, CFG)["estado"] == quality.ERROR

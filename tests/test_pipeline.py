"""Pruebas de punta a punta: publicacion, deteccion, recuperacion y monitoreo.

Cada prueba usa una copia de la configuracion que escribe todas las salidas en
un directorio temporal, de modo que nunca toca results/approved del repo.
"""
import json
import os
import sys

import pandas as pd
import pytest
import yaml

from src import run_pipeline

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "scripts"))
import monitor  # noqa: E402
import restore_version  # noqa: E402

MUESTRA = os.path.join("data", "sample", "migracion_mensual_sample.csv")


@pytest.fixture
def cfg_tmp(tmp_path):
    cfg = yaml.safe_load(open(os.path.join("config", "config.yaml"), encoding="utf-8"))
    cfg["fuentes"]["migracion_mensual"]["ruta"] = str(tmp_path / "no_existe.csv")
    for k in ("carpeta_aprobada", "carpeta_candidata", "carpeta_versiones", "carpeta_logs"):
        cfg["salida"][k] = str(tmp_path / k)
    cfg["salida"]["registro_corridas"] = str(tmp_path / "registro.jsonl")
    cfg["monitoreo"]["reporte"] = str(tmp_path / "monitoreo.json")
    cfg["mlflow"]["activo"] = False
    ruta = tmp_path / "config.yaml"
    ruta.write_text(yaml.safe_dump(cfg, allow_unicode=True), encoding="utf-8")
    return str(ruta), cfg, tmp_path


def _aprobada(cfg):
    ruta = os.path.join(cfg["salida"]["carpeta_aprobada"], cfg["salida"]["archivo_metadatos"])
    return json.load(open(ruta, encoding="utf-8"))


def _danar(tmp_path, fn):
    df = pd.read_csv(MUESTRA)
    df = fn(df)
    ruta = tmp_path / "danada.csv"
    df.to_csv(ruta, index=False)
    return str(ruta)


def test_corrida_valida_publica_con_esquema_del_tablero(cfg_tmp):
    ruta, cfg, _ = cfg_tmp
    codigo, meta = run_pipeline.ejecutar(ruta, usar_muestra=True)
    assert codigo == run_pipeline.SALIDA_OK and meta["aprobado"]
    est = pd.read_csv(os.path.join(cfg["salida"]["carpeta_aprobada"], "estimaciones.csv"))
    for col in ("destino", "periodo_estimado", "valor", "unidad", "tipo", "run_id",
                "fecha_generacion", "version_procedimiento", "metrica_validacion_MAE"):
        assert col in est.columns
    assert set(est["tipo"]) == {"observado", "estimacion"}
    assert (est["valor"] >= 0).all() and est["valor"].notna().all()
    # meses ocultos + horizonte futuro
    assert (est["tipo"] == "estimacion").sum() == (len(cfg["periodos"]["meses_ocultos"])
                                                  + cfg["periodos"]["horizonte_meses"])
    assert meta["metricas"]["procedimiento"]["n_meses"] >= cfg["aceptacion"]["meses_minimos_backtest"]
    assert _aprobada(cfg)["estado"] == "aprobado" and "fin" in _aprobada(cfg)


def test_dos_corridas_equivalentes_dan_el_mismo_resultado(cfg_tmp):
    ruta, cfg, _ = cfg_tmp
    _, m1 = run_pipeline.ejecutar(ruta, usar_muestra=True)
    _, m2 = run_pipeline.ejecutar(ruta, usar_muestra=True)
    assert m1["run_id"] != m2["run_id"]
    assert m1["fuente"]["huella"] == m2["fuente"]["huella"]
    assert m1["huella_config"] == m2["huella_config"]
    assert m1["metricas"] == m2["metricas"]


@pytest.mark.parametrize("dano", [
    lambda df: df.drop(columns=["viajeros"]),
    lambda df: pd.concat([df, df.iloc[[10]]], ignore_index=True),
    lambda df: df.assign(dias_fuente=df["dias_fuente"].where(df.index != 5, 0)),
    lambda df: df.assign(origen_fuente=df["origen_fuente"].where(df.index != 20, "diaria_agregada")),
])
def test_control_critico_detiene_y_conserva_la_aprobada(cfg_tmp, dano):
    ruta, cfg, tmp_path = cfg_tmp
    run_pipeline.ejecutar(ruta, usar_muestra=True)
    vigente = _aprobada(cfg)["run_id"]

    codigo, meta = run_pipeline.ejecutar(ruta, fuente=_danar(tmp_path, dano))
    assert codigo == run_pipeline.SALIDA_CONTROL_CRITICO
    assert meta["estado"] == "detenido_por_control_critico"
    assert _aprobada(cfg)["run_id"] == vigente


def test_regla_rechaza_metrica_degradada_sin_publicar(cfg_tmp):
    ruta, cfg, tmp_path = cfg_tmp
    run_pipeline.ejecutar(ruta, usar_muestra=True)
    vigente = _aprobada(cfg)["run_id"]

    def erratico(df):
        ev = pd.to_datetime(df["periodo"]) >= "2021-04-01"
        factores = [3.0 if i % 2 else 0.3 for i in range(ev.sum())]
        df.loc[ev, "viajeros"] = (df.loc[ev, "viajeros"] * factores).round().astype(int)
        return df

    codigo, meta = run_pipeline.ejecutar(ruta, fuente=_danar(tmp_path, erratico))
    assert codigo == run_pipeline.SALIDA_RECHAZADA
    assert meta["razones_rechazo"]
    assert _aprobada(cfg)["run_id"] == vigente


def test_restaurar_version_anterior(cfg_tmp):
    ruta, cfg, _ = cfg_tmp
    _, m1 = run_pipeline.ejecutar(ruta, usar_muestra=True)
    _, m2 = run_pipeline.ejecutar(ruta, usar_muestra=True)
    assert _aprobada(cfg)["run_id"] == m2["run_id"]
    assert restore_version.versiones(cfg) == sorted([m1["run_id"], m2["run_id"]])

    ev = restore_version.restaurar(cfg, m1["run_id"], "prueba")
    assert ev["reemplaza_a"] == m2["run_id"]
    assert _aprobada(cfg)["run_id"] == m1["run_id"]
    est = pd.read_csv(os.path.join(cfg["salida"]["carpeta_aprobada"], "estimaciones.csv"))
    assert set(est["run_id"]) == {m1["run_id"]}


def test_monitoreo_alerta_sin_version_y_ok_tras_publicar(cfg_tmp):
    ruta, cfg, tmp_path = cfg_tmp
    assert monitor.evaluar(cfg)["estado"] == "alerta"
    run_pipeline.ejecutar(ruta, usar_muestra=True)
    rep = monitor.evaluar(cfg)
    assert rep["estado"] == "ok", rep["alertas"]
    assert rep["advertencias"]  # se uso la muestra sintetica

    for _ in range(cfg["monitoreo"]["max_corridas_fallidas_seguidas"]):
        run_pipeline.ejecutar(ruta, fuente=_danar(tmp_path, lambda d: d.drop(columns=["viajeros"])))
    assert monitor.evaluar(cfg)["estado"] == "alerta"


def test_log_por_corrida_resume_etapas_y_publicacion(cfg_tmp):
    ruta, cfg, tmp_path = cfg_tmp
    _, meta = run_pipeline.ejecutar(ruta, usar_muestra=True)
    log = [json.loads(x) for x in open(os.path.join(cfg["salida"]["carpeta_logs"],
                                                    f"{meta['run_id']}.jsonl"), encoding="utf-8")]
    res = log[-1]
    assert res["etapa"] == "resumen"
    assert res["inicio"] and res["fin"] and res["publicacion"] == "publicada"
    assert res["etapas_completadas"][-1] == "publicacion"
    assert "advertencias" in res and res["errores"] == []

    _, meta2 = run_pipeline.ejecutar(ruta, fuente=_danar(tmp_path, lambda d: d.drop(columns=["viajeros"])))
    log2 = [json.loads(x) for x in open(os.path.join(cfg["salida"]["carpeta_logs"],
                                                     f"{meta2['run_id']}.jsonl"), encoding="utf-8")]
    assert log2[-1]["etapas_completadas"] == ["lectura", "validacion"]
    assert log2[-1]["errores"] and log2[-1]["publicacion"].startswith("no publicada")


def test_parametros_ajustados_reproducen_la_estimacion(cfg_tmp):
    ruta, cfg, _ = cfg_tmp
    run_pipeline.ejecutar(ruta, usar_muestra=True)
    apr = cfg["salida"]["carpeta_aprobada"]
    par = json.load(open(os.path.join(apr, cfg["salida"]["archivo_parametros"]), encoding="utf-8"))
    assert par["formula"]
    ph = par["parametros_horizonte"]
    assert len(ph["indice_estacional"]) == 12
    est = pd.read_csv(os.path.join(apr, "estimaciones.csv"))
    fut = est[est["valor_observado"].isna()].iloc[0]
    mes = pd.Timestamp(fut["periodo_estimado"]).month
    assert round(ph["nivel"] * ph["indice_estacional"][str(mes)]) == fut["valor"]


def test_mape_excluye_meses_con_observado_cero():
    ev = pd.DataFrame({"observado": [0.0, 100.0], "procedimiento": [10.0, 110.0],
                       "ref_ultimo_valor": [0.0, 90.0], "ref_promedio_hist": [5.0, 100.0]})
    m = run_pipeline._metricas(ev)["procedimiento"]
    assert m["MAE"] == 10.0 and m["n_meses"] == 2
    assert m["MAPE"] == 10.0 and m["n_meses_mape"] == 1
    solo_ceros = run_pipeline._metricas(ev.iloc[[0]])["procedimiento"]
    assert solo_ceros["MAPE"] is None


def test_monitoreo_actualizacion_detecta_fuente_desactualizada(cfg_tmp):
    ruta, cfg, tmp_path = cfg_tmp
    vieja = _danar(tmp_path, lambda d: d[pd.to_datetime(d["periodo"]) < "2025-09-01"])
    run_pipeline.ejecutar(ruta, fuente=vieja)
    rep = monitor.evaluar(cfg)
    act = rep["verificaciones"]["actualizacion"]
    assert act["estado"] == "alerta"
    assert act["detalle"]["ultimo_periodo_fuente"] == "2025-08"


def test_monitoreo_calidad_detecta_aumento_de_faltantes(cfg_tmp):
    ruta, cfg, tmp_path = cfg_tmp
    run_pipeline.ejecutar(ruta, usar_muestra=True)
    assert monitor.evaluar(cfg)["verificaciones"]["calidad"]["estado"] == "ok"
    # NA en dias_fuente es una ausencia permitida: la corrida sigue y se aprueba,
    # pero el monitoreo debe avisar que aumentaron los faltantes.
    con_na = _danar(tmp_path, lambda d: d.assign(
        dias_fuente=d["dias_fuente"].astype("float").where(d.index > 3)))
    codigo, _ = run_pipeline.ejecutar(ruta, fuente=con_na)
    assert codigo == run_pipeline.SALIDA_OK
    cal = monitor.evaluar(cfg)["verificaciones"]["calidad"]
    assert cal["estado"] == "alerta"
    assert cal["detalle"]["cambios_vs_anterior"]["faltantes"] == 4


def test_monitoreo_resultados_detecta_negativos_y_variacion(cfg_tmp):
    ruta, cfg, _ = cfg_tmp
    run_pipeline.ejecutar(ruta, usar_muestra=True)
    assert monitor.evaluar(cfg)["verificaciones"]["resultados"]["estado"] == "ok"
    ruta_est = os.path.join(cfg["salida"]["carpeta_aprobada"], "estimaciones.csv")
    est = pd.read_csv(ruta_est)
    fut = est.index[est["valor_observado"].isna()]
    est.loc[fut[0], "valor"] = est.loc[fut[0] - 1, "valor"] * 3   # salto de +200 %
    est.loc[fut[1], "valor"] = -5
    est.to_csv(ruta_est, index=False)
    res = monitor.evaluar(cfg)["verificaciones"]["resultados"]
    assert res["estado"] == "alerta"
    assert any("negativas" in a for a in res["alertas"])
    assert any("varia" in a for a in res["alertas"])

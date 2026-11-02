"""
Pipeline reproducible del Observatorio de Inteligencia Turistica (Lab 11 - MLOps).

Ejecuta, con un solo comando, las etapas:
  1. lectura de fuentes (+ huella digital de fuente y configuracion)
  2. validacion (6 controles de calidad)   <-- punto de validacion de datos
  3. preparacion (serie mensual, factor de reparto)
  4. ajuste / estimacion (procedimiento reproducible)
  5. evaluacion temporal (backtesting + regla de aceptacion)  <-- punto de evaluacion
  6. generacion de estimaciones
  7. almacenamiento (version candidata)
  8. publicacion de la version aprobada     <-- punto de autorizacion

Cada corrida (aprobada, rechazada, detenida o con error) queda registrada en
MLflow Tracking, en results/registro_corridas.jsonl y en logs/<run_id>.jsonl.

No modifica archivos intermedios a mano ni depende de la memoria de una sesion.
Si un control critico falla, se detiene ANTES de reemplazar los resultados
vigentes del tablero (la ultima version aprobada se conserva intacta).

Uso:
    python -m src.run_pipeline --config config/config.yaml
    python -m src.run_pipeline --config config/config.yaml --usar-muestra
    python -m src.run_pipeline --fuente data/sample/migracion_con_falla.csv

Codigos de salida: 0 aprobada y publicada | 1 rechazada por la regla |
2 detenida por control critico | 3 error no controlado.
"""
from __future__ import annotations
import argparse
import hashlib
import json
import os
import random
import shutil
import subprocess
import sys
from datetime import datetime, timezone

import numpy as np
import pandas as pd
import yaml

from src import quality, tracking

# Codigos de salida documentados
SALIDA_OK = 0
SALIDA_RECHAZADA = 1          # corrio completo pero la regla no autorizo publicar
SALIDA_CONTROL_CRITICO = 2    # se detuvo en la validacion de datos
SALIDA_ERROR = 3              # fallo no controlado


# ----------------------------- utilidades -----------------------------
def log(reg, etapa, msg, nivel="INFO"):
    linea = {"ts": datetime.now(timezone.utc).isoformat(), "etapa": etapa,
             "nivel": nivel, "msg": msg}
    reg.append(linea)
    print(f"[{nivel}] {etapa}: {msg}")


def git_commit():
    try:
        sha = subprocess.check_output(
            ["git", "rev-parse", "--short", "HEAD"],
            stderr=subprocess.DEVNULL).decode().strip()
        sucio = subprocess.check_output(
            ["git", "status", "--porcelain", "--untracked-files=no"],
            stderr=subprocess.DEVNULL).decode().strip()
        return sha + ("-modificado" if sucio else "")
    except Exception:
        # Dentro de Docker no hay .git: el commit llega por variable de entorno
        return os.environ.get("GIT_COMMIT", "sin-git")


def fingerprint(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(8192), b""):
            h.update(chunk)
    return h.hexdigest()[:16]


def cargar_config(path):
    with open(path, "r", encoding="utf-8") as f:
        return yaml.safe_load(f)


def _escribir_json(path, obj):
    """Escritura atomica: el tablero nunca lee un archivo a medio escribir."""
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(obj, f, indent=2, ensure_ascii=False, default=str)
    os.replace(tmp, path)


def _escribir_csv(df, path):
    tmp = path + ".tmp"
    df.to_csv(tmp, index=False)
    os.replace(tmp, path)


# ----------------------------- etapas ---------------------------------
def etapa_lectura(cfg, usar_muestra, reg, fuente=None):
    src = cfg["fuentes"]["migracion_mensual"]
    ruta = fuente or src["ruta"]
    if fuente:
        log(reg, "lectura", f"Fuente indicada por linea de comandos: {fuente}", "ADVERTENCIA")
    elif usar_muestra or not os.path.exists(ruta):
        ruta = src["ruta_respaldo_muestra"]
        log(reg, "lectura",
            f"Usando muestra sintetica (no hay datos institucionales en {src['ruta']})",
            "ADVERTENCIA")
    if not os.path.exists(ruta):
        raise FileNotFoundError(f"No existe la fuente: {ruta}. "
                                f"Ejecute scripts/make_sample_data.py")
    df = pd.read_csv(ruta)
    fp = fingerprint(ruta)
    log(reg, "lectura", f"Leidas {len(df)} filas de {ruta} (huella {fp})")
    return df, ruta, fp


def etapa_preparacion(df, cfg, reg):
    df = df.copy()
    df["periodo"] = pd.to_datetime(df["periodo"])
    df = df[df["destino"] == cfg["proyecto"]["destino"]]
    df = df.sort_values("periodo").reset_index(drop=True)
    # Factor de reparto: hook documentado. En la muestra todos los registros ya
    # tienen mes, por lo que no hay nada que repartir. Se deja la funcion lista.
    fr = cfg["procedimiento"]["factor_reparto"]
    if fr.get("activo"):
        log(reg, "preparacion",
            f"Factor de reparto activo ({fr['metodo']}); no hay registros sin mes que repartir")
    serie = df[["periodo", "viajeros"]].dropna().reset_index(drop=True)
    log(reg, "preparacion", f"Serie mensual preparada: {len(serie)} meses")
    return serie


def _indice_estacional(serie_train):
    s = serie_train.copy()
    s["mes"] = s["periodo"].dt.month
    media_global = s["viajeros"].mean()
    idx = s.groupby("mes")["viajeros"].mean() / media_global
    return idx.to_dict()


def estimar_mes(serie_disp, periodo_obj, cfg):
    """Procedimiento reproducible 'baseline_estacional'.
    Usa SOLO informacion anterior al periodo objetivo (orden temporal)."""
    v = cfg["procedimiento"]["ventana_nivel_meses"]
    train = serie_disp[serie_disp["periodo"] < periodo_obj]
    if len(train) < 12:
        return np.nan
    idx = _indice_estacional(train)
    ultimos = train.tail(v).copy()
    ultimos["mes"] = ultimos["periodo"].dt.month
    niveles = [row.viajeros / idx.get(row.mes, 1.0) for row in ultimos.itertuples()]
    nivel = float(np.mean(niveles))
    return max(0.0, nivel * idx.get(periodo_obj.month, 1.0))


def baseline_ultimo_valor(serie_disp, periodo_obj):
    train = serie_disp[serie_disp["periodo"] < periodo_obj]
    return float(train["viajeros"].iloc[-1]) if len(train) else np.nan


def baseline_promedio_hist(serie_disp, periodo_obj):
    train = serie_disp[serie_disp["periodo"] < periodo_obj]
    return float(train["viajeros"].mean()) if len(train) else np.nan


PROCEDIMIENTOS = ["procedimiento", "ref_ultimo_valor", "ref_promedio_hist"]


def _metricas(ev):
    metr = {}
    for col in PROCEDIMIENTOS:
        err = (ev[col] - ev["observado"]).dropna()
        if not len(err):
            continue
        metr[col] = {"MAE": float(err.abs().mean()),
                     "RMSE": float(np.sqrt((err ** 2).mean())),
                     "MAPE": float((err.abs() / ev.loc[err.index, "observado"]).mean() * 100),
                     "n_meses": int(len(err))}
    return metr


def backtest(serie, meses, cfg, reg=None):
    """Origen movil: cada mes se estima solo con los meses anteriores
    (ventana expansiva), igual que se haria en produccion. Los meses sin
    observado comparable se omiten (no se rellenan con cero)."""
    filas = []
    for po in meses:
        obs = serie.loc[serie["periodo"] == po, "viajeros"]
        if obs.empty:
            if reg is not None:
                log(reg, "evaluacion", f"{po.date()} sin observado comparable; se omite",
                    "ADVERTENCIA")
            continue
        disp = serie[serie["periodo"] < po]
        filas.append({
            "periodo": po,
            "observado": float(obs.iloc[0]),
            "procedimiento": estimar_mes(disp, po, cfg),
            "ref_ultimo_valor": baseline_ultimo_valor(disp, po),
            "ref_promedio_hist": baseline_promedio_hist(disp, po),
        })
    return pd.DataFrame(filas, columns=["periodo", "observado", *PROCEDIMIENTOS])


def etapa_evaluacion(serie, cfg, reg):
    """Validacion temporal sobre todo el periodo de evaluacion configurado
    (backtesting) y, por separado, sobre los meses ocultos que ve el tablero.
    Compara el procedimiento contra dos referencias sobre los mismos meses."""
    p = cfg["periodos"]
    meses_ev = pd.date_range(p["evaluacion_inicio"], p["evaluacion_fin"], freq="MS")
    ev = backtest(serie, meses_ev, cfg, reg)
    metr = _metricas(ev)

    ocultos = [pd.Timestamp(x) for x in p["meses_ocultos"]]
    metr_ocultos = _metricas(backtest(serie, ocultos, cfg))

    if "procedimiento" in metr:
        log(reg, "evaluacion",
            f"Backtesting {len(ev)} meses | MAE procedimiento={metr['procedimiento']['MAE']:.0f} | "
            f"MAE ultimo_valor={metr['ref_ultimo_valor']['MAE']:.0f} | "
            f"MAE promedio_hist={metr['ref_promedio_hist']['MAE']:.0f}")
    else:
        log(reg, "evaluacion", "Sin meses evaluables con observado comparable", "ADVERTENCIA")
    return ev, metr, metr_ocultos


def etapa_estimaciones(serie, cfg, metr, run_id, reg):
    """Genera la tabla de estimaciones para el tablero. Marca cada fila como
    observado o estimacion. Incluye los meses ocultos (con su observado para
    contrastar) y los meses futuros del horizonte, que no tienen observado."""
    unidad = cfg["variable"]["unidad"]
    version = cfg["proyecto"]["version_procedimiento"]
    destino = cfg["proyecto"]["destino"]
    gen = datetime.now(timezone.utc).date().isoformat()
    mae = metr.get("procedimiento", {}).get("MAE")
    ocultos = set(pd.Timestamp(x) for x in cfg["periodos"]["meses_ocultos"])

    def fila(periodo, valor, tipo, observado):
        return {"destino": destino,
                "periodo_estimado": periodo.date().isoformat(),
                "valor": valor,
                "valor_observado": observado,
                "unidad": unidad,
                "tipo": tipo,
                "run_id": run_id,
                "fecha_generacion": gen,
                "version_procedimiento": version,
                "metodo": cfg["procedimiento"]["metodo"],
                "metrica_validacion_MAE": mae}

    filas = []
    for row in serie.itertuples():
        if row.periodo in ocultos:
            est = estimar_mes(serie[serie["periodo"] < row.periodo], row.periodo, cfg)
            filas.append(fila(row.periodo, est, "estimacion", float(row.viajeros)))
        else:
            filas.append(fila(row.periodo, float(row.viajeros), "observado",
                              float(row.viajeros)))

    h = int(cfg["periodos"].get("horizonte_meses", 0))
    if h and len(serie):
        futuros = pd.date_range(serie["periodo"].max() + pd.offsets.MonthBegin(1),
                                periods=h, freq="MS")
        for po in futuros:
            filas.append(fila(po, estimar_mes(serie, po, cfg), "estimacion", np.nan))
        log(reg, "estimaciones",
            f"Horizonte: {h} meses futuros ({futuros[0].date()} a {futuros[-1].date()})")

    out = pd.DataFrame(filas)
    out["valor"] = out["valor"].round(0)
    log(reg, "estimaciones",
        f"{(out['tipo'] == 'observado').sum()} observados, "
        f"{(out['tipo'] == 'estimacion').sum()} estimaciones")
    return out


def regla_aceptacion(metr, hay_critico, estimaciones, cfg, reg):
    """Regla verificable y previa a publicar. Considera controles criticos,
    integridad de salidas, suficiencia del backtesting y desempeno predictivo."""
    acc = cfg["aceptacion"]
    razones = []
    if acc["requiere_controles_criticos_ok"] and hay_critico:
        razones.append("fallo un control critico de calidad")
    if acc["requiere_salidas_completas"] and estimaciones["valor"].isna().any():
        razones.append("hay estimaciones faltantes en la salida")
    proc = metr.get("procedimiento", {})
    n = proc.get("n_meses", 0)
    if n < acc.get("meses_minimos_backtest", 1):
        razones.append(f"backtesting con {n} meses < minimo {acc.get('meses_minimos_backtest', 1)}")
    mae, rmse = proc.get("MAE"), proc.get("RMSE")
    if mae is not None and mae > acc["mae_maximo"]:
        razones.append(f"MAE {mae:.0f} > umbral {acc['mae_maximo']}")
    if rmse is not None and rmse > acc["rmse_maximo"]:
        razones.append(f"RMSE {rmse:.0f} > umbral {acc['rmse_maximo']}")
    if acc["debe_igualar_o_superar_referencia"] and mae is not None:
        ref = min(metr.get("ref_ultimo_valor", {}).get("MAE", np.inf),
                  metr.get("ref_promedio_hist", {}).get("MAE", np.inf))
        if mae > ref:
            razones.append(f"MAE {mae:.0f} no supera a la mejor referencia {ref:.0f}")
    ok = not razones
    log(reg, "aceptacion", "APROBADA" if ok else f"RECHAZADA: {razones}",
        "INFO" if ok else "ADVERTENCIA")
    return ok, razones


def etapa_almacenamiento(estimaciones, ev, metadatos, cfg, reg):
    """Guarda la version candidata (siempre) para inspeccion."""
    sal = cfg["salida"]
    cand = sal["carpeta_candidata"]
    os.makedirs(cand, exist_ok=True)
    _escribir_csv(estimaciones, os.path.join(cand, sal["archivo_estimaciones"]))
    _escribir_csv(ev, os.path.join(cand, sal["archivo_backtest"]))
    _escribir_json(os.path.join(cand, sal["archivo_metadatos"]), metadatos)
    log(reg, "almacenamiento", f"Version candidata guardada en {cand}")


def etapa_publicacion(cfg, aprobado, run_id, reg):
    """Reemplaza la version vigente SOLO si fue aprobada. Antes guarda una
    copia inmutable en results/versions/<run_id>/ para poder restaurarla.
    Si no se aprueba, conserva la ultima aprobada."""
    sal = cfg["salida"]
    cand, apr = sal["carpeta_candidata"], sal["carpeta_aprobada"]
    archivos = [sal["archivo_estimaciones"], sal["archivo_metadatos"],
                sal["archivo_backtest"], sal["reporte_calidad"]]

    if not aprobado:
        existe = os.path.exists(os.path.join(apr, sal["archivo_estimaciones"]))
        log(reg, "publicacion",
            "No se publica. " + ("Se conserva la ultima version aprobada."
                                 if existe else "Aun no hay version aprobada: "
                                 "el tablero debe indicar 'estimaciones no disponibles'."),
            "ADVERTENCIA")
        return None

    destino_version = os.path.join(sal["carpeta_versiones"], run_id)
    os.makedirs(destino_version, exist_ok=True)
    os.makedirs(apr, exist_ok=True)
    for a in archivos:
        src = os.path.join(cand, a)
        if os.path.exists(src):
            shutil.copy2(src, os.path.join(destino_version, a))
    # Reemplazo atomico, archivo por archivo; la tabla de estimaciones va al
    # final para que el tablero vea metadatos coherentes con la tabla.
    for a in reversed(archivos):
        src = os.path.join(destino_version, a)
        if os.path.exists(src):
            shutil.copy2(src, os.path.join(apr, a + ".tmp"))
            os.replace(os.path.join(apr, a + ".tmp"), os.path.join(apr, a))
    # Una publicacion nueva deja sin efecto el aviso de una restauracion previa
    restauracion = os.path.join(apr, "restauracion.json")
    if os.path.exists(restauracion):
        os.remove(restauracion)
    log(reg, "publicacion", f"Version aprobada publicada en {apr} (copia en {destino_version})")
    return destino_version


# ----------------------------- orquestador ----------------------------
def ejecutar(config_path, usar_muestra=False, fuente=None):
    """Corre el pipeline completo y devuelve (codigo_salida, metadatos)."""
    cfg = cargar_config(config_path)
    random.seed(cfg["proyecto"]["semilla"])
    np.random.seed(cfg["proyecto"]["semilla"])

    run_id = datetime.now(timezone.utc).strftime("run-%Y%m%dT%H%M%S%fZ")
    reg = []
    commit = git_commit()
    log(reg, "inicio", f"run_id={run_id} commit={commit}")

    sal = cfg["salida"]
    # La candidata anterior se descarta para no confundirla con la de esta corrida
    shutil.rmtree(sal["carpeta_candidata"], ignore_errors=True)
    os.makedirs(sal["carpeta_candidata"], exist_ok=True)

    metadatos = {"run_id": run_id,
                 "inicio": datetime.now(timezone.utc).isoformat(),
                 "commit": commit,
                 "config": config_path,
                 "huella_config": fingerprint(config_path),
                 "version_procedimiento": cfg["proyecto"]["version_procedimiento"],
                 "aprobado": False}
    reporte = None
    codigo = SALIDA_ERROR
    try:
        df, ruta, fp = etapa_lectura(cfg, usar_muestra, reg, fuente)
        metadatos["fuente"] = {"ruta": ruta, "huella": fp, "filas": int(len(df)),
                               "es_muestra_sintetica": ruta == cfg["fuentes"][
                                   "migracion_mensual"]["ruta_respaldo_muestra"]}

        reporte, hay_critico = quality.ejecutar_controles(df, cfg)
        _escribir_json(os.path.join(sal["carpeta_candidata"], sal["reporte_calidad"]), reporte)
        log(reg, "validacion",
            f"ok={reporte['resumen']['ok']} adv={reporte['resumen']['advertencias']} "
            f"err={reporte['resumen']['errores']}")
        metadatos["controles"] = reporte["resumen"]
        metadatos["controles_detalle"] = {r["control"]: r["estado"]
                                          for r in reporte["controles"]}

        if hay_critico:
            log(reg, "validacion",
                "Control critico fallido: se DETIENE el pipeline sin tocar la "
                "version aprobada del tablero.", "ERROR")
            metadatos["estado"] = "detenido_por_control_critico"
            metadatos["razones_rechazo"] = [r["detalle"] for r in reporte["controles"]
                                            if r["estado"] == quality.ERROR]
            codigo = SALIDA_CONTROL_CRITICO
        else:
            serie = etapa_preparacion(df, cfg, reg)
            ev, metr, metr_ocultos = etapa_evaluacion(serie, cfg, reg)
            metadatos["metricas"] = metr
            metadatos["metricas_meses_ocultos"] = metr_ocultos
            metadatos["periodos"] = {k: cfg["periodos"][k] for k in
                                     ("ajuste_inicio", "ajuste_fin", "evaluacion_inicio",
                                      "evaluacion_fin", "meses_ocultos", "horizonte_meses")}
            metadatos["parametros"] = cfg["procedimiento"]
            metadatos["umbrales"] = cfg["aceptacion"]

            estimaciones = etapa_estimaciones(serie, cfg, metr, run_id, reg)
            aprobado, razones = regla_aceptacion(metr, hay_critico, estimaciones, cfg, reg)
            metadatos["aprobado"] = aprobado
            metadatos["razones_rechazo"] = razones
            metadatos["estado"] = "aprobado" if aprobado else "rechazado_por_regla"
            metadatos["fin"] = datetime.now(timezone.utc).isoformat()

            etapa_almacenamiento(estimaciones, ev, metadatos, cfg, reg)
            metadatos["version_guardada"] = etapa_publicacion(cfg, aprobado, run_id, reg)
            codigo = SALIDA_OK if aprobado else SALIDA_RECHAZADA
    except Exception as e:
        log(reg, "error", f"Fallo no controlado: {e}", "ERROR")
        metadatos["estado"] = "error"
        metadatos["error"] = str(e)
        codigo = SALIDA_ERROR

    metadatos.setdefault("fin", datetime.now(timezone.utc).isoformat())
    metadatos["codigo_salida"] = codigo
    if metadatos["estado"] != "aprobado":
        # La candidata queda con el registro de por que no se publico
        _escribir_json(os.path.join(sal["carpeta_candidata"], sal["archivo_metadatos"]),
                       metadatos)

    metadatos["mlflow_run_id"] = tracking.registrar_corrida(cfg, config_path, metadatos, reg)
    if metadatos.get("version_guardada") and metadatos["mlflow_run_id"]:
        # El id de MLflow se conoce despues de registrar: se anota en la version
        # publicada para que el tablero enlace la cifra con su corrida.
        for carpeta in (metadatos["version_guardada"], sal["carpeta_aprobada"]):
            _escribir_json(os.path.join(carpeta, sal["archivo_metadatos"]), metadatos)
    _registrar(metadatos, reg, cfg)
    log(reg, "fin", f"run_id={run_id} estado={metadatos['estado']} codigo={codigo}")
    _guardar_log(reg, run_id, cfg)
    return codigo, metadatos


def _registrar(metadatos, reg, cfg):
    """Una linea por corrida: insumo del monitoreo."""
    ruta = cfg["salida"]["registro_corridas"]
    os.makedirs(os.path.dirname(ruta) or ".", exist_ok=True)
    proc = (metadatos.get("metricas") or {}).get("procedimiento", {})
    linea = {k: metadatos.get(k) for k in
             ("run_id", "inicio", "fin", "commit", "estado", "aprobado",
              "codigo_salida", "version_procedimiento", "huella_config",
              "mlflow_run_id", "razones_rechazo")}
    linea["huella_fuente"] = (metadatos.get("fuente") or {}).get("huella")
    linea["controles"] = metadatos.get("controles")
    linea["MAE"], linea["RMSE"] = proc.get("MAE"), proc.get("RMSE")
    with open(ruta, "a", encoding="utf-8") as f:
        f.write(json.dumps(linea, ensure_ascii=False, default=str) + "\n")


def _guardar_log(reg, run_id, cfg):
    carpeta = cfg["salida"].get("carpeta_logs", "logs")
    os.makedirs(carpeta, exist_ok=True)
    with open(os.path.join(carpeta, f"{run_id}.jsonl"), "w", encoding="utf-8") as f:
        for linea in reg:
            f.write(json.dumps(linea, ensure_ascii=False) + "\n")


def main():
    ap = argparse.ArgumentParser(description="Pipeline MLOps - Observatorio Turistico")
    ap.add_argument("--config", default="config/config.yaml")
    ap.add_argument("--usar-muestra", action="store_true",
                    help="Fuerza el uso de la muestra sintetica")
    ap.add_argument("--fuente", help="Lee esta ruta en lugar de la configurada "
                    "(prueba controlada con una copia danada de los datos)")
    args = ap.parse_args()
    codigo, _ = ejecutar(args.config, args.usar_muestra, args.fuente)
    sys.exit(codigo)


if __name__ == "__main__":
    main()

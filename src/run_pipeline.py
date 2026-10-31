"""
Pipeline reproducible del Observatorio de Inteligencia Turistica (Lab 11 - MLOps).

Ejecuta, con un solo comando, las etapas:
  1. lectura de fuentes (+ huella digital)
  2. validacion (6 controles de calidad)   <-- punto de validacion de datos
  3. preparacion (serie mensual, factor de reparto)
  4. ajuste / estimacion (procedimiento reproducible)
  5. evaluacion temporal (regla de aceptacion)  <-- punto de evaluacion
  6. generacion de estimaciones
  7. almacenamiento (version candidata)
  8. publicacion de la version aprobada     <-- punto de autorizacion

No modifica archivos intermedios a mano ni depende de la memoria de una sesion.
Si un control critico falla, se detiene ANTES de reemplazar los resultados
vigentes del tablero (la ultima version aprobada se conserva intacta).

Uso:
    python -m src.run_pipeline --config config/config.yaml
    python -m src.run_pipeline --config config/config.yaml --usar-muestra
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

from src import quality


# ----------------------------- utilidades -----------------------------
def log(reg, etapa, msg, nivel="INFO"):
    linea = {"ts": datetime.now(timezone.utc).isoformat(), "etapa": etapa,
             "nivel": nivel, "msg": msg}
    reg.append(linea)
    print(f"[{nivel}] {etapa}: {msg}")


def git_commit():
    try:
        return subprocess.check_output(
            ["git", "rev-parse", "--short", "HEAD"],
            stderr=subprocess.DEVNULL).decode().strip()
    except Exception:
        return "sin-git"


def fingerprint(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(8192), b""):
            h.update(chunk)
    return h.hexdigest()[:16]


def cargar_config(path):
    with open(path, "r") as f:
        return yaml.safe_load(f)


# ----------------------------- etapas ---------------------------------
def etapa_lectura(cfg, usar_muestra, reg):
    src = cfg["fuentes"]["migracion_mensual"]
    ruta = src["ruta"]
    if usar_muestra or not os.path.exists(ruta):
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


def etapa_evaluacion(serie, cfg, reg):
    """Validacion temporal: oculta los meses configurados y los estima como si
    no estuvieran disponibles, respetando el orden temporal. Compara el
    procedimiento contra dos referencias sobre los mismos meses."""
    ocultos = [pd.Timestamp(x) for x in cfg["periodos"]["meses_ocultos"]]
    filas = []
    for po in ocultos:
        obs = serie.loc[serie["periodo"] == po, "viajeros"]
        if obs.empty:
            log(reg, "evaluacion", f"{po.date()} sin observado comparable; se omite", "ADVERTENCIA")
            continue
        disp = serie[serie["periodo"] < po]  # expanding window
        filas.append({
            "periodo": po,
            "observado": float(obs.iloc[0]),
            "procedimiento": estimar_mes(disp, po, cfg),
            "ref_ultimo_valor": baseline_ultimo_valor(serie, po),
            "ref_promedio_hist": baseline_promedio_hist(serie, po),
        })
    ev = pd.DataFrame(filas)
    metr = {}
    if len(ev):
        for col in ["procedimiento", "ref_ultimo_valor", "ref_promedio_hist"]:
            err = (ev[col] - ev["observado"]).abs()
            metr[col] = {"MAE": float(err.mean()),
                         "RMSE": float(np.sqrt(((ev[col] - ev["observado"]) ** 2).mean()))}
        log(reg, "evaluacion",
            f"MAE procedimiento={metr['procedimiento']['MAE']:.0f} | "
            f"MAE ultimo_valor={metr['ref_ultimo_valor']['MAE']:.0f} | "
            f"MAE promedio_hist={metr['ref_promedio_hist']['MAE']:.0f}")
    else:
        log(reg, "evaluacion", "Sin meses evaluables con observado comparable", "ADVERTENCIA")
    return ev, metr


def etapa_estimaciones(serie, cfg, metr, run_id, reg):
    """Genera la tabla de estimaciones para el tablero. Marca cada fila como
    observado o estimacion. Estima los meses ocultos (validacion) para mostrar
    el contraste; en produccion aqui irian los meses futuros sin observacion."""
    unidad = cfg["variable"]["unidad"]
    version = cfg["proyecto"]["version_procedimiento"]
    destino = cfg["proyecto"]["destino"]
    gen = datetime.now(timezone.utc).date().isoformat()
    mae = metr.get("procedimiento", {}).get("MAE")
    ocultos = set(pd.Timestamp(x) for x in cfg["periodos"]["meses_ocultos"])

    filas = []
    for row in serie.itertuples():
        es_oculto = row.periodo in ocultos
        filas.append({
            "destino": destino,
            "periodo_estimado": row.periodo.date().isoformat(),
            "valor": (estimar_mes(serie[serie["periodo"] < row.periodo], row.periodo, cfg)
                      if es_oculto else float(row.viajeros)),
            "unidad": unidad,
            "tipo": "estimacion" if es_oculto else "observado",
            "run_id": run_id,
            "fecha_generacion": gen,
            "version_procedimiento": version,
            "metodo": cfg["procedimiento"]["metodo"],
            "metrica_validacion_MAE": mae,
        })
    out = pd.DataFrame(filas)
    out["valor"] = out["valor"].round(0)
    return out


def regla_aceptacion(metr, hay_critico, estimaciones, cfg, reg):
    """Regla verificable y previa a publicar. Considera controles criticos,
    integridad de salidas y desempeno predictivo."""
    acc = cfg["aceptacion"]
    razones = []
    ok = True
    if acc["requiere_controles_criticos_ok"] and hay_critico:
        ok = False; razones.append("fallo un control critico de calidad")
    if acc["requiere_salidas_completas"] and estimaciones["valor"].isna().any():
        ok = False; razones.append("hay estimaciones faltantes en la salida")
    mae = metr.get("procedimiento", {}).get("MAE")
    rmse = metr.get("procedimiento", {}).get("RMSE")
    if mae is not None and mae > acc["mae_maximo"]:
        ok = False; razones.append(f"MAE {mae:.0f} > umbral {acc['mae_maximo']}")
    if rmse is not None and rmse > acc["rmse_maximo"]:
        ok = False; razones.append(f"RMSE {rmse:.0f} > umbral {acc['rmse_maximo']}")
    if acc["debe_igualar_o_superar_referencia"] and mae is not None:
        ref = min(metr.get("ref_ultimo_valor", {}).get("MAE", np.inf),
                  metr.get("ref_promedio_hist", {}).get("MAE", np.inf))
        if mae > ref:
            ok = False; razones.append(f"MAE {mae:.0f} no supera a la referencia {ref:.0f}")
    log(reg, "aceptacion", "APROBADA" if ok else f"RECHAZADA: {razones}")
    return ok, razones


def etapa_publicacion(estimaciones, metadatos, cfg, aprobado, reg):
    """Reemplaza la version vigente SOLO si fue aprobada. Si no, conserva la
    ultima aprobada y deja la candidata para inspeccion."""
    cand = cfg["salida"]["carpeta_candidata"]
    apr = cfg["salida"]["carpeta_aprobada"]
    os.makedirs(cand, exist_ok=True)
    os.makedirs(apr, exist_ok=True)
    arch = cfg["salida"]["archivo_estimaciones"]
    meta = cfg["salida"]["archivo_metadatos"]

    estimaciones.to_csv(os.path.join(cand, arch), index=False)
    with open(os.path.join(cand, meta), "w") as f:
        json.dump(metadatos, f, indent=2, ensure_ascii=False)

    if aprobado:
        shutil.copy(os.path.join(cand, arch), os.path.join(apr, arch))
        with open(os.path.join(apr, meta), "w") as f:
            json.dump(metadatos, f, indent=2, ensure_ascii=False)
        log(reg, "publicacion", f"Version aprobada publicada en {apr}")
    else:
        existe = os.path.exists(os.path.join(apr, arch))
        log(reg, "publicacion",
            "No se publica. " + ("Se conserva la ultima version aprobada."
                                 if existe else "Aun no hay version aprobada: "
                                 "el tablero debe indicar 'estimaciones no disponibles'."),
            "ADVERTENCIA")


# ----------------------------- orquestador ----------------------------
def main():
    ap = argparse.ArgumentParser(description="Pipeline MLOps - Observatorio Turistico")
    ap.add_argument("--config", default="config/config.yaml")
    ap.add_argument("--usar-muestra", action="store_true",
                    help="Fuerza el uso de la muestra sintetica")
    args = ap.parse_args()

    cfg = cargar_config(args.config)
    random.seed(cfg["proyecto"]["semilla"])
    np.random.seed(cfg["proyecto"]["semilla"])

    run_id = datetime.now(timezone.utc).strftime("run-%Y%m%dT%H%M%SZ")
    reg = []
    inicio = datetime.now(timezone.utc)
    log(reg, "inicio", f"run_id={run_id} commit={git_commit()}")

    aprobado = False
    metadatos = {"run_id": run_id, "inicio": inicio.isoformat(),
                 "commit": git_commit(), "config": args.config}
    try:
        df, ruta, fp = etapa_lectura(cfg, args.usar_muestra, reg)
        metadatos["fuente"] = {"ruta": ruta, "huella": fp}

        reporte, hay_critico = quality.ejecutar_controles(df, cfg)
        os.makedirs(cfg["salida"]["carpeta_candidata"], exist_ok=True)
        with open(os.path.join(cfg["salida"]["carpeta_candidata"],
                               cfg["salida"]["reporte_calidad"]), "w") as f:
            json.dump(reporte, f, indent=2, ensure_ascii=False)
        log(reg, "validacion",
            f"ok={reporte['resumen']['ok']} adv={reporte['resumen']['advertencias']} "
            f"err={reporte['resumen']['errores']}")
        metadatos["controles"] = reporte["resumen"]

        if hay_critico:
            log(reg, "validacion",
                "Control critico fallido: se DETIENE el pipeline sin tocar la "
                "version aprobada del tablero.", "ERROR")
            metadatos["estado"] = "detenido_por_control_critico"
            _guardar_log(reg, run_id, cfg)
            sys.exit(2)

        serie = etapa_preparacion(df, cfg, reg)
        ev, metr = etapa_evaluacion(serie, cfg, reg)
        metadatos["metricas"] = metr
        metadatos["periodos"] = {k: cfg["periodos"][k] for k in
                                 ("ajuste_inicio", "ajuste_fin",
                                  "evaluacion_inicio", "evaluacion_fin", "meses_ocultos")}
        metadatos["parametros"] = cfg["procedimiento"]

        estimaciones = etapa_estimaciones(serie, cfg, metr, run_id, reg)
        aprobado, razones = regla_aceptacion(metr, hay_critico, estimaciones, cfg, reg)
        metadatos["aprobado"] = aprobado
        metadatos["razones_rechazo"] = razones

        etapa_publicacion(estimaciones, metadatos, cfg, aprobado, reg)
        metadatos["estado"] = "completado"
    except Exception as e:
        log(reg, "error", f"Fallo no controlado: {e}", "ERROR")
        metadatos["estado"] = "error"
        metadatos["error"] = str(e)
        _guardar_log(reg, run_id, cfg)
        raise
    finally:
        metadatos["fin"] = datetime.now(timezone.utc).isoformat()

    _guardar_log(reg, run_id, cfg)
    log(reg, "fin", f"run_id={run_id} aprobado={aprobado}")


def _guardar_log(reg, run_id, cfg):
    os.makedirs("logs", exist_ok=True)
    with open(os.path.join("logs", f"{run_id}.jsonl"), "w") as f:
        for linea in reg:
            f.write(json.dumps(linea, ensure_ascii=False) + "\n")


if __name__ == "__main__":
    main()

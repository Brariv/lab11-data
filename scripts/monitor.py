"""
Monitoreo del flujo: actualizacion, calidad y resultados.

Lee la version aprobada vigente y el registro de corridas, y ejecuta las tres
verificaciones del laboratorio:

  1. Actualizacion: la fuente de la ultima corrida y la version aprobada
     llegan al ultimo periodo esperado segun la cobertura configurada
     (periodos.fin_serie) y la version cubre el horizonte de meses futuros.
     Tambien alerta si la version aprobada lleva demasiados dias sin renovarse.
  2. Calidad: compara faltantes, duplicados y cobertura de la ultima corrida
     con los de la corrida anterior y alerta si aumentaron; tambien alerta si
     varias corridas seguidas no se aprueban.
  3. Resultados: alerta si la version aprobada tiene estimaciones negativas o
     no finitas, o si una estimacion varia respecto del mes anterior mas que el
     umbral configurado. El error predictivo (MAE) solo se compara entre
     versiones aprobadas que se evaluaron con observados comparables.

Una alerta pide REVISION: no cambia la version publicada y una variacion alta
no demuestra por si sola perdida de precision.

Escribe results/monitoreo.json (el tablero lo muestra) y sale con codigo 1 si
hay alguna alerta, para poder usarlo en un cron o en CI. Las advertencias
(p. ej. que se uso la muestra sintetica) se informan pero no cambian el codigo.

Uso:
    python scripts/monitor.py --config config/config.yaml
"""
from __future__ import annotations
import argparse
import json
import math
import os
import sys
from datetime import datetime, timezone

import pandas as pd
import yaml


def _leer_registro(ruta):
    if not os.path.exists(ruta):
        return []
    with open(ruta, encoding="utf-8") as f:
        return [json.loads(x) for x in f if x.strip()]


def _mes(fecha):
    return pd.Timestamp(fecha).to_period("M")


class _Verificacion:
    def __init__(self):
        self.alertas, self.detalle = [], {}

    def alerta(self, msg):
        self.alertas.append(msg)

    def resultado(self):
        return {"estado": "alerta" if self.alertas else "ok",
                "alertas": self.alertas, "detalle": self.detalle}


# ----------------------------------------------------------------------
# 1. Actualizacion
# ----------------------------------------------------------------------
def verificar_actualizacion(cfg, meta, est, corridas, ahora):
    v = _Verificacion()
    mon, per = cfg["monitoreo"], cfg["periodos"]
    esperado = _mes(per["fin_serie"])
    horizonte = int(per.get("horizonte_meses", 0))
    v.detalle["ultimo_periodo_esperado"] = str(esperado)

    # Fuente: ultimo periodo que trajo la ultima corrida que pudo leerla
    perfiles = [c["perfil_calidad"] for c in corridas if c.get("perfil_calidad")]
    if perfiles and perfiles[-1].get("ultimo_periodo"):
        ult_fuente = _mes(perfiles[-1]["ultimo_periodo"])
        v.detalle["ultimo_periodo_fuente"] = str(ult_fuente)
        if ult_fuente < esperado:
            v.alerta(f"La fuente de la ultima corrida llega a {ult_fuente}; "
                     f"se esperaba {esperado}")

    if meta is None:
        v.alerta("No hay version aprobada: el tablero muestra 'estimaciones no disponibles'")
        return v.resultado()

    # Resultados publicados: ultimo mes con observado y ultimo mes estimado
    if est is not None and len(est):
        periodos = pd.to_datetime(est["periodo_estimado"])
        con_obs = periodos[est["valor_observado"].notna()]
        if len(con_obs):
            ult_obs = con_obs.max().to_period("M")
            v.detalle["ultimo_periodo_observado_publicado"] = str(ult_obs)
            if ult_obs < esperado:
                v.alerta(f"La version aprobada solo tiene observados hasta {ult_obs}; "
                         f"se esperaba {esperado}")
        ult_est = periodos.max().to_period("M")
        v.detalle["ultimo_periodo_estimado"] = str(ult_est)
        if ult_est < esperado + horizonte:
            v.alerta(f"La version aprobada estima hasta {ult_est}; con un horizonte de "
                     f"{horizonte} meses se esperaba {esperado + horizonte}")

    fin = datetime.fromisoformat(meta.get("fin") or meta["inicio"])
    dias = (ahora - fin).total_seconds() / 86400
    v.detalle["dias_desde_actualizacion"] = round(dias, 1)
    if dias > mon["dias_max_sin_actualizar"]:
        v.alerta(f"Version aprobada con {dias:.0f} dias sin actualizar "
                 f"(> {mon['dias_max_sin_actualizar']})")
    return v.resultado()


# ----------------------------------------------------------------------
# 2. Calidad
# ----------------------------------------------------------------------
_NOMBRES = {"faltantes": "valores faltantes", "duplicados": "filas duplicadas",
            "periodos_sin_informacion": "periodos sin informacion",
            "meses_cobertura_parcial": "meses con cobertura parcial"}


def verificar_calidad(cfg, corridas):
    v = _Verificacion()
    mon = cfg["monitoreo"]
    tol = mon.get("tolerancia_calidad", {})

    con_perfil = [c for c in corridas if c.get("perfil_calidad")]
    if con_perfil:
        act = con_perfil[-1]["perfil_calidad"]
        v.detalle["perfil_ultima_corrida"] = act
    if len(con_perfil) >= 2:
        prev = con_perfil[-2]["perfil_calidad"]
        v.detalle["comparada_con"] = con_perfil[-2].get("run_id")
        cambios = {}
        for clave, nombre in _NOMBRES.items():
            a, b = prev.get(clave), act.get(clave)
            if a is None or b is None:
                if a is not None and b is None:
                    v.alerta(f"No se pudieron contar los {nombre} en la ultima corrida "
                             "(falta una columna)")
                continue
            cambios[clave] = b - a
            if b - a > tol.get(clave, 0):
                v.alerta(f"Aumentaron los {nombre}: {a} -> {b}")
        v.detalle["cambios_vs_anterior"] = cambios

    seguidas = 0
    for c in reversed(corridas):
        if c.get("estado") == "aprobado":
            break
        seguidas += 1
    v.detalle["corridas_sin_aprobar_seguidas"] = seguidas
    if seguidas >= mon["max_corridas_fallidas_seguidas"]:
        v.alerta(f"{seguidas} corridas seguidas sin aprobar; revisar fuente y controles")
    return v.resultado()


# ----------------------------------------------------------------------
# 3. Resultados
# ----------------------------------------------------------------------
def verificar_resultados(cfg, meta, est, corridas):
    v = _Verificacion()
    mon = cfg["monitoreo"]
    if est is not None and len(est):
        est = est.assign(periodo=pd.to_datetime(est["periodo_estimado"]),
                         valor=pd.to_numeric(est["valor"], errors="coerce")
                         .astype("float64")).sort_values("periodo")
        estm = est[est["tipo"] == "estimacion"]
        neg = estm[estm["valor"] < 0]
        nofin = estm[~estm["valor"].map(math.isfinite)]
        if len(neg):
            v.alerta(f"Estimaciones negativas en {_lista(neg['periodo'])}")
        if len(nofin):
            v.alerta(f"Estimaciones no finitas o vacias en {_lista(nofin['periodo'])}")

        umbral = mon["umbral_variacion_relativa"]
        previo = est["valor"].shift(1)
        var = ((est["valor"] - previo).abs() / previo).where(previo > 0)
        altas = est[(est["tipo"] == "estimacion") & (var > umbral)]
        v.detalle["variacion_maxima_estimaciones"] = (
            round(float(var[est["tipo"] == "estimacion"].max()), 4)
            if var[est["tipo"] == "estimacion"].notna().any() else None)
        for r in altas.itertuples():
            v.alerta(f"Estimacion de {r.periodo:%Y-%m} varia {var[r.Index]:.0%} respecto "
                     f"del mes anterior (> {umbral:.0%}); revisar, no implica por si "
                     "sola perdida de precision")

    # Error predictivo: solo entre aprobadas evaluadas con observados comparables
    aprobadas = [c for c in corridas if c.get("estado") == "aprobado" and c.get("MAE")]
    if len(aprobadas) >= 2:
        prev, act = aprobadas[-2]["MAE"], aprobadas[-1]["MAE"]
        cambio = (act - prev) / prev
        v.detalle["cambio_relativo_MAE"] = round(cambio, 4)
        if cambio > mon["degradacion_mae_relativa"]:
            v.alerta(f"MAE empeoro {cambio:.0%} respecto de la aprobada anterior")
    if meta and meta.get("metricas"):
        v.detalle["MAE_vigente"] = meta["metricas"]["procedimiento"]["MAE"]
    return v.resultado()


def _lista(periodos):
    return ", ".join(f"{p:%Y-%m}" for p in periodos)


# ----------------------------------------------------------------------
def evaluar(cfg, ahora=None):
    ahora = ahora or datetime.now(timezone.utc)
    sal = cfg["salida"]
    advertencias, info = [], {}

    meta, est = None, None
    ruta_meta = os.path.join(sal["carpeta_aprobada"], sal["archivo_metadatos"])
    ruta_est = os.path.join(sal["carpeta_aprobada"], sal["archivo_estimaciones"])
    if os.path.exists(ruta_meta):
        with open(ruta_meta, encoding="utf-8") as f:
            meta = json.load(f)
        info["version_vigente"] = meta.get("run_id")
        if (meta.get("fuente") or {}).get("es_muestra_sintetica"):
            advertencias.append("La version vigente se genero con la muestra sintetica, "
                                "no con datos institucionales")
    if os.path.exists(ruta_est):
        est = pd.read_csv(ruta_est)

    corridas = [c for c in _leer_registro(sal["registro_corridas"])
                if c.get("evento") != "restauracion"]
    info["corridas_registradas"] = len(corridas)
    if corridas:
        ult = corridas[-1]
        info["ultima_corrida"] = {k: ult.get(k) for k in
                                  ("run_id", "estado", "fin", "controles", "razones_rechazo")}

    verif = {"actualizacion": verificar_actualizacion(cfg, meta, est, corridas, ahora),
             "calidad": verificar_calidad(cfg, corridas),
             "resultados": verificar_resultados(cfg, meta, est, corridas)}
    alertas = [f"[{k}] {a}" for k, r in verif.items() for a in r["alertas"]]
    # Detalle plano para el tablero (V23) ademas del detalle por verificacion
    for r in verif.values():
        info.update({k: x for k, x in r["detalle"].items() if not isinstance(x, dict)})

    return {"generado": ahora.isoformat(), "estado": "alerta" if alertas else "ok",
            "alertas": alertas, "advertencias": advertencias,
            "verificaciones": verif, "detalle": info}


def main():
    ap = argparse.ArgumentParser(description="Monitoreo del pipeline")
    ap.add_argument("--config", default="config/config.yaml")
    args = ap.parse_args()
    with open(args.config, encoding="utf-8") as f:
        cfg = yaml.safe_load(f)
    rep = evaluar(cfg)
    ruta = cfg["monitoreo"]["reporte"]
    os.makedirs(os.path.dirname(ruta) or ".", exist_ok=True)
    with open(ruta, "w", encoding="utf-8") as f:
        json.dump(rep, f, indent=2, ensure_ascii=False, default=str)
    print(json.dumps(rep, indent=2, ensure_ascii=False, default=str))
    sys.exit(1 if rep["alertas"] else 0)


if __name__ == "__main__":
    main()

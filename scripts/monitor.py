"""
Monitoreo del flujo: actualizacion, calidad y resultados.

Lee la version aprobada vigente y el registro de corridas, y responde tres
preguntas que un responsable debe poder contestar sin abrir el codigo:

  1. Actualizacion: la version que ve el tablero esta al dia?
  2. Calidad: las ultimas corridas pasan los controles o se estan deteniendo?
  3. Resultados: el error del procedimiento empeoro respecto de la version
     aprobada anterior?

Escribe results/monitoreo.json (el tablero lo muestra) y sale con codigo 1 si
hay alguna alerta, para poder usarlo en un cron o en CI. Las advertencias
(p. ej. que se uso la muestra sintetica) se informan pero no cambian el codigo.

Uso:
    python scripts/monitor.py --config config/config.yaml
"""
from __future__ import annotations
import argparse
import json
import os
import sys
from datetime import datetime, timezone

import yaml


def _leer_registro(ruta):
    if not os.path.exists(ruta):
        return []
    with open(ruta, encoding="utf-8") as f:
        return [json.loads(x) for x in f if x.strip()]


def evaluar(cfg, ahora=None):
    ahora = ahora or datetime.now(timezone.utc)
    sal, mon = cfg["salida"], cfg["monitoreo"]
    alertas, advertencias, info = [], [], {}

    # 1. Actualizacion
    ruta_meta = os.path.join(sal["carpeta_aprobada"], sal["archivo_metadatos"])
    if not os.path.exists(ruta_meta):
        alertas.append("No hay version aprobada: el tablero muestra 'estimaciones no disponibles'")
        meta = {}
    else:
        with open(ruta_meta, encoding="utf-8") as f:
            meta = json.load(f)
        fin = datetime.fromisoformat(meta.get("fin") or meta["inicio"])
        dias = (ahora - fin).total_seconds() / 86400
        info["version_vigente"] = meta.get("run_id")
        info["dias_desde_actualizacion"] = round(dias, 1)
        if dias > mon["dias_max_sin_actualizar"]:
            alertas.append(f"Version aprobada con {dias:.0f} dias sin actualizar "
                           f"(> {mon['dias_max_sin_actualizar']})")
        if (meta.get("fuente") or {}).get("es_muestra_sintetica"):
            advertencias.append("La version vigente se genero con la muestra sintetica, "
                                "no con datos institucionales")

    # 2. Calidad de las corridas recientes
    corridas = [c for c in _leer_registro(sal["registro_corridas"])
                if c.get("evento") != "restauracion"]
    info["corridas_registradas"] = len(corridas)
    seguidas = 0
    for c in reversed(corridas):
        if c.get("estado") in ("aprobado",):
            break
        seguidas += 1
    info["corridas_sin_aprobar_seguidas"] = seguidas
    if corridas:
        ult = corridas[-1]
        info["ultima_corrida"] = {k: ult.get(k) for k in
                                  ("run_id", "estado", "fin", "controles", "razones_rechazo")}
    if seguidas >= mon["max_corridas_fallidas_seguidas"]:
        alertas.append(f"{seguidas} corridas seguidas sin aprobar; revisar fuente y controles")

    # 3. Resultados: degradacion del error frente a la aprobada anterior
    aprobadas = [c for c in corridas if c.get("estado") == "aprobado" and c.get("MAE")]
    if len(aprobadas) >= 2:
        prev, act = aprobadas[-2]["MAE"], aprobadas[-1]["MAE"]
        cambio = (act - prev) / prev
        info["cambio_relativo_MAE"] = round(cambio, 4)
        if cambio > mon["degradacion_mae_relativa"]:
            alertas.append(f"MAE empeoro {cambio:.0%} respecto de la aprobada anterior")
    if meta.get("metricas"):
        info["MAE_vigente"] = meta["metricas"]["procedimiento"]["MAE"]

    return {"generado": ahora.isoformat(), "estado": "alerta" if alertas else "ok",
            "alertas": alertas, "advertencias": advertencias, "detalle": info}


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
        json.dump(rep, f, indent=2, ensure_ascii=False)
    print(json.dumps(rep, indent=2, ensure_ascii=False))
    sys.exit(1 if rep["alertas"] else 0)


if __name__ == "__main__":
    main()

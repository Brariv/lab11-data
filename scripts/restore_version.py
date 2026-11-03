"""
Restauracion documentada de una version aprobada anterior.

Cada version aprobada se guarda de forma inmutable en results/versions/<run_id>/.
Este script lista esas versiones y vuelve a publicar una de ellas como la
version vigente que lee el tablero (results/approved/). La restauracion queda
registrada en results/registro_corridas.jsonl y en results/approved/restauracion.json.

No vuelve a ajustar nada: solo copia archivos ya aprobados.

Uso:
    python scripts/restore_version.py --listar
    python scripts/restore_version.py --run-id run-20261101T180000123456Z
    python scripts/restore_version.py --anterior      # la aprobada previa a la vigente
"""
from __future__ import annotations
import argparse
import json
import os
import shutil
import sys
from datetime import datetime, timezone

import yaml


def versiones(cfg):
    carpeta = cfg["salida"]["carpeta_versiones"]
    if not os.path.isdir(carpeta):
        return []
    return sorted(d for d in os.listdir(carpeta)
                  if os.path.isfile(os.path.join(carpeta, d, cfg["salida"]["archivo_estimaciones"])))


def vigente(cfg):
    ruta = os.path.join(cfg["salida"]["carpeta_aprobada"], cfg["salida"]["archivo_metadatos"])
    if not os.path.exists(ruta):
        return None
    with open(ruta, encoding="utf-8") as f:
        return json.load(f).get("run_id")


def restaurar(cfg, run_id, motivo="restauracion manual"):
    sal = cfg["salida"]
    origen = os.path.join(sal["carpeta_versiones"], run_id)
    if not os.path.isdir(origen):
        raise FileNotFoundError(f"No existe la version {run_id} en {sal['carpeta_versiones']}")
    apr = sal["carpeta_aprobada"]
    os.makedirs(apr, exist_ok=True)
    previa = vigente(cfg)
    archivos = sorted(os.listdir(origen), key=lambda a: a == sal["archivo_estimaciones"])
    for a in archivos:  # la tabla de estimaciones se reemplaza al final
        shutil.copy2(os.path.join(origen, a), os.path.join(apr, a + ".tmp"))
        os.replace(os.path.join(apr, a + ".tmp"), os.path.join(apr, a))
    # Un archivo de la version vigente que la restaurada no tiene (p. ej. una
    # version previa a parametros_ajustados.json) se quita para no mezclarlas.
    for a in (sal["archivo_backtest"], sal["reporte_calidad"], sal.get("archivo_parametros")):
        if a and a not in archivos and os.path.exists(os.path.join(apr, a)):
            os.remove(os.path.join(apr, a))

    evento = {"evento": "restauracion", "ts": datetime.now(timezone.utc).isoformat(),
              "run_id": run_id, "reemplaza_a": previa, "motivo": motivo,
              "estado": "restaurado", "aprobado": True}
    with open(os.path.join(apr, "restauracion.json"), "w", encoding="utf-8") as f:
        json.dump(evento, f, indent=2, ensure_ascii=False)
    os.makedirs(os.path.dirname(sal["registro_corridas"]) or ".", exist_ok=True)
    with open(sal["registro_corridas"], "a", encoding="utf-8") as f:
        f.write(json.dumps(evento, ensure_ascii=False) + "\n")
    return evento


def main():
    ap = argparse.ArgumentParser(description="Restaura una version aprobada anterior")
    ap.add_argument("--config", default="config/config.yaml")
    g = ap.add_mutually_exclusive_group(required=True)
    g.add_argument("--listar", action="store_true")
    g.add_argument("--run-id")
    g.add_argument("--anterior", action="store_true",
                   help="Restaura la version aprobada inmediatamente anterior a la vigente")
    ap.add_argument("--motivo", default="restauracion manual")
    args = ap.parse_args()

    with open(args.config, encoding="utf-8") as f:
        cfg = yaml.safe_load(f)
    vs, act = versiones(cfg), vigente(cfg)

    if args.listar:
        if not vs:
            print("No hay versiones guardadas en", cfg["salida"]["carpeta_versiones"])
        for v in vs:
            print(("* " if v == act else "  ") + v)
        return

    if args.anterior:
        if act not in vs or vs.index(act) == 0:
            print("No hay una version aprobada anterior a la vigente", file=sys.stderr)
            sys.exit(1)
        run_id = vs[vs.index(act) - 1]
    else:
        run_id = args.run_id

    ev = restaurar(cfg, run_id, args.motivo)
    print(f"Restaurada {ev['run_id']} (reemplaza a {ev['reemplaza_a']}) en "
          f"{cfg['salida']['carpeta_aprobada']}")


if __name__ == "__main__":
    main()

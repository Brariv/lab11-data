"""
Registro de cada ejecucion en MLflow Tracking (Laboratorio 11, MLOps).

Por corrida se guarda: codigo (commit), fuentes (ruta + huella), parametros,
periodos, umbrales, metricas del backtesting y de los meses ocultos, estado de
los seis controles, decision de la regla de aceptacion y los artefactos
(configuracion, reporte de calidad, estimaciones, backtest, metadatos, log).

Se registran TODAS las corridas, tambien las detenidas por un control critico
o las rechazadas: eso es lo que permite monitorear la calidad en el tiempo.

La URI del servidor se toma de MLFLOW_TRACKING_URI si existe (Docker Compose
apunta al servicio `mlflow`); si no, de config.yaml (sqlite local en mlruns/).
Si MLflow no esta instalado o el servidor no responde, el pipeline sigue y lo
advierte: el registro nunca decide si se publica o no.
"""
from __future__ import annotations
import json
import os
from pathlib import Path


def _plano(d, prefijo=""):
    """Aplana diccionarios anidados para usarlos como parametros de MLflow."""
    out = {}
    for k, v in (d or {}).items():
        clave = f"{prefijo}{k}"
        if isinstance(v, dict):
            out.update(_plano(v, clave + "."))
        elif isinstance(v, (list, tuple)):
            out[clave] = ",".join(map(str, v))
        else:
            out[clave] = v
    return out


def _preparar_destino(cfg_ml):
    """Devuelve (tracking_uri, artifact_location) listos para usar."""
    uri = os.environ.get("MLFLOW_TRACKING_URI") or cfg_ml["tracking_uri"]
    artefactos = None
    if uri.startswith("sqlite:///"):
        Path(uri[len("sqlite:///"):]).parent.mkdir(parents=True, exist_ok=True)
    if not uri.startswith("http"):
        # Con servidor remoto, el servidor decide donde guarda los artefactos
        carpeta = Path(cfg_ml.get("artifact_location", "mlruns/artifacts")).resolve()
        carpeta.mkdir(parents=True, exist_ok=True)
        artefactos = carpeta.as_uri()
    return uri, artefactos


def registrar_corrida(cfg, config_path, metadatos, reg):
    """Registra la corrida y devuelve el id de MLflow (o None si no se pudo)."""
    cfg_ml = cfg.get("mlflow", {})
    if not cfg_ml.get("activo", False):
        return None
    try:
        import mlflow
    except ImportError:
        _aviso(reg, "MLflow no esta instalado; la corrida no se registra en Tracking")
        return None

    try:
        uri, artefactos = _preparar_destino(cfg_ml)
        mlflow.set_tracking_uri(uri)
        nombre = cfg_ml["experimento"]
        if mlflow.get_experiment_by_name(nombre) is None:
            mlflow.create_experiment(nombre, artifact_location=artefactos)
        mlflow.set_experiment(nombre)

        estado = metadatos.get("estado", "error")
        fallida = estado in ("detenido_por_control_critico", "error")
        sal = cfg["salida"]
        with mlflow.start_run(run_name=metadatos["run_id"]) as run:
            mlflow.set_tags({
                "run_id_pipeline": metadatos["run_id"],
                "estado": estado,
                "aprobado": str(metadatos.get("aprobado", False)),
                "mlflow.source.git.commit": metadatos.get("commit"),
                "commit": metadatos.get("commit"),
                "version_procedimiento": metadatos.get("version_procedimiento"),
                "huella_config": metadatos.get("huella_config"),
                "fuente.ruta": (metadatos.get("fuente") or {}).get("ruta"),
                "fuente.huella": (metadatos.get("fuente") or {}).get("huella"),
                "fuente.es_muestra_sintetica": str(
                    (metadatos.get("fuente") or {}).get("es_muestra_sintetica")),
                "razones_rechazo": "; ".join(metadatos.get("razones_rechazo") or []),
            })
            params = {"semilla": cfg["proyecto"]["semilla"],
                      "destino": cfg["proyecto"]["destino"]}
            params.update(_plano(cfg["procedimiento"], "proc."))
            params.update(_plano(cfg["periodos"], "periodo."))
            params.update(_plano(cfg["aceptacion"], "umbral."))
            params.pop("proc.factor_reparto.descripcion", None)
            mlflow.log_params({k: str(v)[:500] for k, v in params.items()})

            metricas = {}
            for nombre_proc, m in (metadatos.get("metricas") or {}).items():
                for k, v in m.items():
                    metricas[f"backtest.{nombre_proc}.{k}"] = v
            for nombre_proc, m in (metadatos.get("metricas_meses_ocultos") or {}).items():
                for k, v in m.items():
                    metricas[f"ocultos.{nombre_proc}.{k}"] = v
            for k, v in (metadatos.get("controles") or {}).items():
                metricas[f"controles.{k}"] = v
            metricas["aprobado"] = 1.0 if metadatos.get("aprobado") else 0.0
            metricas["codigo_salida"] = metadatos.get("codigo_salida", -1)
            mlflow.log_metrics({k: float(v) for k, v in metricas.items() if v is not None})

            mlflow.log_artifact(config_path, artifact_path="config")
            cand = sal["carpeta_candidata"]
            if os.path.isdir(cand):
                for f in sorted(os.listdir(cand)):
                    mlflow.log_artifact(os.path.join(cand, f), artifact_path="candidata")
            mlflow.log_text("\n".join(json.dumps(x, ensure_ascii=False) for x in reg),
                            "log_corrida.jsonl")
            run_mlflow = run.info.run_id
        if fallida:
            mlflow.MlflowClient().set_terminated(run_mlflow, status="FAILED")
        reg.append({"etapa": "tracking", "nivel": "INFO",
                    "msg": f"Registrado en MLflow ({uri}) run={run_mlflow}"})
        print(f"[INFO] tracking: Registrado en MLflow ({uri}) run={run_mlflow}")
        return run_mlflow
    except Exception as e:  # el registro nunca debe tumbar la publicacion
        _aviso(reg, f"No se pudo registrar en MLflow: {e}")
        return None


def _aviso(reg, msg):
    reg.append({"etapa": "tracking", "nivel": "ADVERTENCIA", "msg": msg})
    print(f"[ADVERTENCIA] tracking: {msg}")

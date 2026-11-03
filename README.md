# Laboratorio 11 - MLOps - Observatorio de Inteligencia Turistica

Flujo reproducible para preparar datos, validar su calidad, ejecutar y evaluar
un procedimiento de estimacion, registrar cada corrida en **MLflow Tracking** y
publicar una **version aprobada** que consulta el tablero del Laboratorio 10.
Incluye monitoreo, restauracion de versiones anteriores y contenerizacion con
**Docker Compose**.

Integrantes: Javier Lopez (23415) · Pedro Avila (23089) · Brandon Rivera (23088)

## Inicio rapido

### Opcion A: Docker (recomendada, desde una copia limpia)
```bash
docker compose up --build -d          # o: make docker-up
```
| Servicio    | Que hace                                                 | URL                    |
|-------------|----------------------------------------------------------|------------------------|
| `mlflow`    | Servidor de MLflow Tracking con persistencia             | http://localhost:5000  |
| `pipeline`  | Corre el pipeline una vez y el monitoreo; luego termina  | -                      |
| `dashboard` | Tablero Streamlit (Lab 10 + seccion *Estimaciones oficiales*) | http://localhost:8501 |

```bash
docker compose run --rm pipeline                    # nueva corrida (actualizacion)
docker compose run --rm pipeline python scripts/restore_version.py --listar
docker compose run --rm pipeline python scripts/restore_version.py --anterior
docker compose up -d mlflow dashboard               # levantar sin correr el pipeline
docker compose down                                 # conserva volumenes (MLflow y versiones)
```
Los volumenes `ots_mlflow`, `ots_resultados` y `ots_logs` sobreviven a
`docker compose down`; solo `docker compose down -v` los borra.

### Opcion B: local (Python 3.11+)
```bash
pip install -r requirements.txt                     # o: make setup
python -m src.run_pipeline --config config/config.yaml   # o: make run
python scripts/monitor.py                           # o: make monitor
mlflow ui --backend-store-uri sqlite:///mlruns/mlflow.db  # o: make mlflow-ui
pip install -r dashboard/requirements.txt && streamlit run dashboard/app/app.py
python -m pytest -q tests                           # o: make test
```

## Estructura
```
config/config.yaml            Parametros, rutas, periodos, umbrales, semilla, MLflow, monitoreo
src/run_pipeline.py           Orquestador: las 8 etapas con un solo comando
src/quality.py                Los 6 controles de calidad
src/tracking.py               Registro de cada corrida en MLflow Tracking
scripts/make_sample_data.py   Genera la muestra sintetica (no institucional)
scripts/inject_fault.py       Inyecta una falla para la prueba controlada
scripts/restore_version.py    Lista y restaura versiones aprobadas anteriores
scripts/monitor.py            Monitoreo de actualizacion, calidad y resultados
dashboard/                    Tablero del Lab 10 + seccion "Estimaciones oficiales" (V21-V23)
data/institucional/           Datos reales (montados, NO versionados, NO en Docker)
data/sample/                  Muestra sintetica para correr de punta a punta
results/approved/             Version APROBADA vigente que lee el tablero
results/versions/<run_id>/    Copia inmutable de cada version aprobada (restauracion)
results/candidate/            Ultima candidata + reporte de calidad
results/registro_corridas.jsonl  Una linea por corrida o restauracion (insumo del monitoreo)
logs/<run_id>.jsonl           Log estructurado de cada corrida
mlruns/                       MLflow local (sqlite + artefactos)
docs/                         Informes, diagramas y evidencia de ejecucion
Dockerfile, docker-compose.yml, dashboard/Dockerfile
```

## Datos institucionales
Coloque el CSV mensual en `data/institucional/migracion_mensual.csv` (ruta
configurable en `config/config.yaml`). Si no existe, el pipeline usa la muestra
sintetica y lo advierte (tambien el tablero y el monitoreo). La carpeta esta
excluida de git (`.gitignore`) y de las imagenes (`.dockerignore`); en Docker
Compose se monta en solo lectura.

## Pipeline
`python -m src.run_pipeline --config config/config.yaml`

1. **Lectura** y huella SHA-256 de la fuente y de la configuracion.
2. **Validacion**: 6 controles (ver abajo). *Punto de validacion.*
3. **Preparacion**: serie mensual y factor de reparto (supuesto documentado).
4. **Estimacion**: `baseline_estacional` (nivel de 12 meses x indice estacional),
   usando solo meses anteriores al estimado.
5. **Evaluacion**: backtesting con origen movil sobre 2021-04 a 2025-12 (57 meses)
   frente a dos referencias (ultimo valor y promedio historico). *Punto de evaluacion.*
   MAE y RMSE usan todos los meses evaluados; el MAPE excluye los meses con
   observado igual a cero (el error relativo no esta definido) y reporta cuantos
   meses entraron (`n_meses_mape`).
6. **Estimaciones** con el esquema del tablero: meses observados, meses ocultos
   (2025-11, 2025-12, con su observado para contrastar) y horizonte de 2 meses
   futuros (2026-01, 2026-02, sin error calculable).
7. **Almacenamiento** de la version candidata.
8. **Publicacion** solo si la regla lo autoriza; copia inmutable en
   `results/versions/<run_id>/`. *Punto de autorizacion.*

El ajuste (paso 4) guarda en `parametros_ajustados.json` la formula del
procedimiento, el nivel y los 12 indices estacionales con los que se calculan
los meses futuros, para reproducir la estimacion sin volver a correr el codigo:
`estimacion(t) = max(0, nivel * indice_estacional[mes(t)])`.

Cada corrida deja `logs/<run_id>.jsonl`; su ultima linea (`"etapa": "resumen"`)
tiene hora de inicio y fin, etapas completadas, advertencias, errores y
resultado de la publicacion.

Codigos de salida: `0` aprobada y publicada · `1` rechazada por la regla ·
`2` detenida por control critico · `3` error no controlado. En los casos 1-3
la version aprobada vigente **no se toca**.

## Controles de calidad (6)
| # | Control | Advertencia (continua) | Detiene |
|---|---------|------------------------|---------|
| 1 | Columnas y tipos | - | Falta una columna o tipo incompatible |
| 2 | Fechas y cobertura | Periodo sin datos o cobertura < 20 dias | Fecha invalida |
| 3 | Unicidad (periodo, destino) | - | Cualquier duplicado |
| 4 | Valores faltantes | NA en `dias_fuente` | NA en periodo, destino o viajeros |
| 5 | Valores y denominadores | - | Negativos, inf/NaN, `dias_fuente` = 0 |
| 6 | Regla metodologica | - | Algun mes proviene de `diaria_agregada` |

Los periodos sin cobertura nunca se convierten en cero.

## Regla de aceptacion
Una candidata se publica solo si se cumplen **todas**:
- ningun control critico fallo;
- la salida esta completa (sin estimaciones faltantes);
- el backtesting evaluo al menos 24 meses;
- MAE <= 120 000 y RMSE <= 160 000 personas/mes;
- el MAE no es peor que el de la mejor referencia simple.

Resultado con la muestra: MAE 44 941 (procedimiento) frente a 49 947 (ultimo
valor) y 53 666 (promedio historico) en 57 meses: **aprobada**.

## MLflow Tracking
Cada corrida, **incluidas las detenidas y las rechazadas**, se registra en el
experimento `observatorio_flujo_mensual_nacional` con:
- tags: commit, run_id del pipeline, estado, ruta y huella de la fuente, huella de la configuracion, etapas completadas, ultimo periodo de la fuente;
- parametros: metodo, ventana, factor de reparto, periodos, umbrales, semilla;
- metricas: MAE/RMSE/MAPE del backtesting y de los meses ocultos (procedimiento y referencias), conteo de controles, perfil de calidad (faltantes, duplicados, cobertura), aprobado;
- artefactos: `config.yaml`, reporte de calidad, estimaciones, backtest, parametros ajustados, metadatos y log.

Las corridas detenidas por un control critico quedan con estado `FAILED`.
La URI se toma de `MLFLOW_TRACKING_URI` (Docker: `http://mlflow:5000`) o de
`config.yaml` (local: `sqlite:///mlruns/mlflow.db`).

## Tablero
La seccion **Estimaciones oficiales** del tablero (`dashboard/`) solo lee
`results/approved/`; cambiar un filtro nunca vuelve a ajustar el modelo.
- **V21**: observado (linea continua azul) frente a estimacion (punteada morada), con el observado real de los meses ocultos.
- **V22**: backtesting del procedimiento frente a las referencias, con tabla de MAE/RMSE/MAPE.
- **V23**: estado de los 6 controles, monitoreo y trazabilidad (run, commit, huellas, id de MLflow).
- Encabezado con fecha de actualizacion, version, MAE, proxima estimacion y avisos (muestra sintetica, version restaurada).
- Sin version aprobada muestra **"Estimaciones no disponibles"**.

## Monitoreo y restauracion
```bash
python scripts/monitor.py                      # escribe results/monitoreo.json; codigo 1 si hay alerta
python scripts/restore_version.py --listar     # * marca la vigente
python scripts/restore_version.py --anterior --motivo "..."
python scripts/restore_version.py --run-id run-...
```
El monitoreo hace tres verificaciones (umbrales en `config.yaml`, seccion `monitoreo`):

| Verificacion | Alerta si |
|---|---|
| **Actualizacion** | la fuente de la ultima corrida o los observados publicados no llegan a `fin_serie` (2025-12); la version no estima los `horizonte_meses` siguientes; o tiene mas de 45 dias sin renovarse |
| **Calidad** | aumentaron los faltantes, duplicados, periodos sin informacion o meses con cobertura parcial respecto de la corrida anterior; o hay 2 o mas corridas seguidas sin aprobar |
| **Resultados** | hay estimaciones negativas o no finitas; una estimacion varia mas de 80 % respecto del mes anterior; o el MAE empeoro mas de 25 % frente a la aprobada anterior (solo entre versiones evaluadas con observados comparables) |

Una alerta pide revision: no cambia la version publicada, y una variacion alta
no demuestra por si sola perdida de precision. El umbral de 80 % sale de la
serie: el 95 % de los cambios mes a mes es menor a 28 % y solo los meses de la
pandemia (2020-04 a 2020-07) lo superan.

La restauracion copia una version ya aprobada (no reajusta
nada) y queda registrada en `results/registro_corridas.jsonl` y en
`results/approved/restauracion.json`, que el tablero muestra como aviso.

## Prueba controlada (deteccion y recuperacion)
```bash
python scripts/inject_fault.py columna_ausente      # tambien: clave_duplicada, denominador_cero, origen_diario
python -m src.run_pipeline --fuente data/sample/migracion_con_falla.csv   # codigo 2, conserva la aprobada
python scripts/inject_fault.py metrica_degradada
python -m src.run_pipeline --fuente data/sample/migracion_con_falla.csv   # codigo 1, conserva la aprobada
python -m src.run_pipeline                                                # recuperacion: vuelve a aprobar
```
`make falla` y `make falla-regla` hacen lo mismo. La salida de una ejecucion
real de toda la secuencia esta en `docs/evidencia/`.

## Pruebas automaticas
`python -m pytest -q tests`: 27 pruebas (controles, publicacion con el esquema del
tablero, corridas equivalentes, detencion por cada control critico, rechazo por
la regla, restauracion, log por corrida, parametros reproducibles, MAPE con
ceros y las tres verificaciones de monitoreo). Escriben en directorios temporales y no
tocan `results/approved`.

## Salida que consume el tablero
`results/approved/estimaciones.csv`: destino, periodo_estimado, valor,
valor_observado, unidad, tipo (observado | estimacion), run_id,
fecha_generacion, version_procedimiento, metodo y metrica_validacion_MAE.
Junto a ella: `run_metadata.json`, `backtest.csv`, `reporte_calidad.json` y
`parametros_ajustados.json`.

## Limitaciones
- La version publicada en el repo se genero con la **muestra sintetica**: sirve para mostrar el flujo, no es dato oficial.
- El procedimiento es un baseline estacional; no incorpora rutas nuevas, crisis ni campanas.
- Enero y febrero de 2026 se publican como estimacion sin error calculable (la clasificacion de la base cambio en 2023).

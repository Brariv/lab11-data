# Laboratorio 11 - MLOps - Observatorio de Inteligencia Turistica

Flujo reproducible para preparar datos, ejecutar un procedimiento de estimacion,
evaluarlo y publicar una version aprobada que consulta el tablero. Este es el
**avance** (alcance, diagrama, pipeline inicial y controles de calidad).

## Requisitos previos
- Python 3.10+
- Instalar dependencias:  `pip install -r requirements.txt`

## Estructura
```
config/config.yaml        Parametros, rutas, periodos, umbrales, semilla
src/run_pipeline.py       Orquestador (un solo comando)
src/quality.py            Los 6 controles de calidad
scripts/make_sample_data.py   Genera una muestra sintetica (no institucional)
scripts/inject_fault.py       Inyecta una falla para la prueba controlada
data/institucional/       Datos reales (montados, NO versionados, NO en Docker)
data/sample/              Muestra sintetica para correr de punta a punta
results/approved/         Version APROBADA que lee el tablero (se conserva)
results/candidate/        Version candidata + reporte de calidad
logs/                     Un registro JSONL por ejecucion
docs/                     Diagrama e informe de avance
```

## Ubicacion de los datos institucionales
Coloque el CSV mensual en `data/institucional/migracion_mensual.csv` (ruta
configurable en `config/config.yaml`). Si no existe, el pipeline usa la muestra
sintetica y lo advierte. Los datos institucionales no se suben al repositorio ni
a las imagenes Docker.

## Como ejecutar
```bash
pip install -r requirements.txt          # o: make setup
python scripts/make_sample_data.py       # o: make sample
python -m src.run_pipeline --config config/config.yaml   # o: make run
```
El pipeline no modifica archivos intermedios a mano ni depende de la memoria de
una sesion. Cambiar un filtro en el tablero no vuelve a ajustar el modelo: el
tablero solo lee `results/approved/estimaciones.csv`.

## Controles de calidad (6)
1. Columnas y tipos  2. Fechas y cobertura  3. Unicidad
4. Valores faltantes 5. Valores y denominadores 6. Regla metodologica

Si falla un control critico, el pipeline se detiene (codigo de salida 2) **antes**
de reemplazar la version del tablero. Los periodos sin cobertura no se convierten
en cero.

## Prueba controlada (deteccion y recuperacion)
```bash
python scripts/make_sample_data.py
python scripts/inject_fault.py columna_ausente
cp data/sample/migracion_con_falla.csv data/institucional/migracion_mensual.csv
python -m src.run_pipeline --config config/config.yaml   # se detiene; conserva la aprobada
```

## Salida que consume el tablero
`results/approved/estimaciones.csv` con: destino, periodo_estimado, valor, unidad,
tipo (observado | estimacion), run_id, fecha_generacion, version_procedimiento y
metrica_validacion_MAE. Metadatos en `run_metadata.json`.

## Pendiente para el trabajo final (1 nov)
MLflow Tracking, regla de aceptacion formal, integracion con el tablero,
monitoreo y recuperacion, y contenerizacion con Docker / Docker Compose.

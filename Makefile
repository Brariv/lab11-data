# Comandos documentados del pipeline (Lab 11 - MLOps)
.PHONY: setup sample run run-muestra test falla falla-regla restaurar versiones \
        monitor mlflow-ui tablero docker-up docker-run docker-down clean

setup:
	pip install -r requirements.txt

sample:
	python scripts/make_sample_data.py

run:            ## ejecuta el pipeline completo (un solo comando)
	python -m src.run_pipeline --config config/config.yaml

run-muestra:    ## fuerza el uso de la muestra sintetica
	python -m src.run_pipeline --config config/config.yaml --usar-muestra

test:
	python -m pytest -q tests

falla:          ## columna ausente: el pipeline debe detenerse (codigo 2) y conservar la aprobada
	python scripts/inject_fault.py columna_ausente
	-python -m src.run_pipeline --config config/config.yaml --fuente data/sample/migracion_con_falla.csv

falla-regla:    ## datos validos pero erraticos: la regla de aceptacion debe rechazar (codigo 1)
	python scripts/inject_fault.py metrica_degradada
	-python -m src.run_pipeline --config config/config.yaml --fuente data/sample/migracion_con_falla.csv

versiones:      ## lista las versiones aprobadas guardadas (* = vigente)
	python scripts/restore_version.py --listar

restaurar:      ## vuelve a publicar la version aprobada anterior
	python scripts/restore_version.py --anterior --motivo "restauracion desde make"

monitor:
	python scripts/monitor.py --config config/config.yaml

mlflow-ui:
	mlflow ui --backend-store-uri sqlite:///mlruns/mlflow.db --port 5000

tablero:        ## requiere: pip install -r dashboard/requirements.txt
	streamlit run dashboard/app/app.py

docker-up:      ## MLflow + pipeline + tablero desde una copia limpia
	GIT_COMMIT=$$(git rev-parse --short HEAD) docker compose up --build -d

docker-run:     ## nueva corrida del pipeline dentro de Docker
	docker compose run --rm pipeline

docker-down:
	docker compose down

clean:
	rm -rf results/candidate logs mlruns results/versions results/registro_corridas.jsonl results/monitoreo.json

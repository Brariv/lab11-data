# Comandos documentados del pipeline (avance Lab 11)
.PHONY: setup sample run run-muestra test falla clean

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

falla:          ## inyecta una columna ausente y corre el pipeline (debe detenerse)
	python scripts/inject_fault.py columna_ausente

clean:
	rm -rf results/candidate/* logs/*.jsonl

# Imagen del pipeline (y del servidor MLflow, que reutiliza la misma imagen
# para no depender de una version distinta de MLflow).
# Los datos institucionales NO se copian: se montan en tiempo de ejecucion.
FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

WORKDIR /app

COPY requirements.txt .
RUN pip install -r requirements.txt

COPY config/ config/
COPY src/ src/
COPY scripts/ scripts/
COPY tests/ tests/
COPY data/sample/migracion_mensual_sample.csv data/sample/
COPY data/institucional/README.md data/institucional/
# Ultima version aprobada versionada en git: siembra el volumen de resultados
# la primera vez, para que el tablero tenga algo que mostrar desde el inicio.
COPY results/approved/ results/approved/

# Commit del repo (dentro del contenedor no hay .git)
ARG GIT_COMMIT=sin-git
ENV GIT_COMMIT=${GIT_COMMIT}

CMD ["sh", "-c", "python -m src.run_pipeline --config config/config.yaml; c=$?; python scripts/monitor.py --config config/config.yaml > /dev/null; exit $c"]

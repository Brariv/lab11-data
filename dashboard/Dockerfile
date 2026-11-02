# Imagen del tablero. Solo LEE la version aprobada, montada en /resultados.
FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    OTS_RESULTADOS=/resultados

WORKDIR /app
COPY requirements.txt .
RUN pip install -r requirements.txt
COPY .streamlit/ .streamlit/
COPY app/ app/
COPY data/ data/

EXPOSE 8501
HEALTHCHECK CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:8501/_stcore/health')"
CMD ["streamlit", "run", "app/app.py", "--server.port=8501", "--server.address=0.0.0.0"]

"""
Genera docs/Informe_Final_Lab11.docx (y el PDF, si hay Microsoft Word).

Parte del informe de avance como plantilla (portada, logo y estilos) y lee las
cifras de la version aprobada vigente (results/approved/run_metadata.json) y
del registro de corridas, para que el informe no tenga numeros escritos a mano.

Uso (desde la raiz del repositorio):
    python docs/generar_informe_final.py
"""
from __future__ import annotations

import json
import os
import subprocess
import sys

from docx import Document
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.oxml import OxmlElement
from docx.oxml.ns import qn
from docx.shared import Inches, Pt, RGBColor

PLANTILLA = "docs/Informe_Avance_Lab11.docx"
SALIDA = "docs/Informe_Final_Lab11.docx"
PARRAFOS_PORTADA = 15          # la portada del avance ocupa los primeros 15 parrafos
AZUL_TABLA = "0E4D64"

META = json.load(open("results/approved/run_metadata.json", encoding="utf-8"))
M, MO = META["metricas"], META["metricas_meses_ocultos"]


def miles(x):
    return f"{x:,.0f}"


# --------------------------------------------------------------------------
# Utilidades de formato (mismo estilo que el avance)
# --------------------------------------------------------------------------
def preparar_documento():
    doc = Document(PLANTILLA)
    cuerpo = doc.element.body
    hijos = [c for c in cuerpo if c.tag != qn("w:sectPr")]
    parrafos = [c for c in hijos if c.tag == qn("w:p")]
    corte = parrafos[PARRAFOS_PORTADA - 1]
    borrar = False
    for c in hijos:
        if borrar:
            cuerpo.remove(c)
        if c is corte:
            borrar = True
    for p in doc.paragraphs[:PARRAFOS_PORTADA]:
        for r in p.runs:
            if r.text.startswith("Avance:"):
                r.text = "Trabajo final: MLflow, aceptacion, tablero, monitoreo y Docker"
            if r.text.startswith("Guatemala,"):
                r.text = "Guatemala, 1 de noviembre de 2026"
    return doc


def h1(doc, t):
    doc.add_heading(t, level=1)


def h2(doc, t):
    doc.add_heading(t, level=2)


def p(doc, texto, cursiva=False, negrita_inicio=None):
    par = doc.add_paragraph()
    if negrita_inicio:
        par.add_run(negrita_inicio).bold = True
    r = par.add_run(texto)
    r.italic = cursiva
    return par


def vinetas(doc, items):
    for it in items:
        doc.add_paragraph(it, style="List Bullet")


def codigo(doc, lineas):
    for ln in lineas:
        par = doc.add_paragraph()
        par.paragraph_format.space_after = Pt(0)
        par.paragraph_format.left_indent = Inches(0.25)
        r = par.add_run(ln)
        r.font.name = "Consolas"
        r.font.size = Pt(9.5)
        r.font.color.rgb = RGBColor(0x0E, 0x4D, 0x64)
    doc.add_paragraph()


def tabla(doc, encabezado, filas, anchos=None):
    t = doc.add_table(rows=1, cols=len(encabezado))
    t.style = "Table Grid"
    for i, e in enumerate(encabezado):
        c = t.rows[0].cells[i]
        shd = OxmlElement("w:shd")
        shd.set(qn("w:val"), "clear")
        shd.set(qn("w:fill"), AZUL_TABLA)
        c._tc.get_or_add_tcPr().append(shd)
        r = c.paragraphs[0].add_run(str(e))
        r.bold, r.font.size = True, Pt(10)
        r.font.color.rgb = RGBColor(0xFF, 0xFF, 0xFF)
    for fila in filas:
        celdas = t.add_row().cells
        for i, v in enumerate(fila):
            r = celdas[i].paragraphs[0].add_run(str(v))
            r.font.size = Pt(10)
    if anchos:
        for fila in t.rows:
            for i, w in enumerate(anchos):
                fila.cells[i].width = Inches(w)
    doc.add_paragraph()
    return t


def figura(doc, ruta, pie, ancho=5.6):
    doc.add_picture(ruta, width=Inches(ancho))
    doc.paragraphs[-1].alignment = WD_ALIGN_PARAGRAPH.CENTER
    par = p(doc, pie, cursiva=True)
    par.alignment = WD_ALIGN_PARAGRAPH.CENTER


def corridas():
    filas = []
    ruta = "results/registro_corridas.jsonl"
    if not os.path.exists(ruta):
        return filas
    for linea in open(ruta, encoding="utf-8"):
        d = json.loads(linea)
        estado = d.get("estado") or d.get("evento")
        mae = miles(d["MAE"]) if d.get("MAE") else "-"
        filas.append([d.get("run_id", "")[4:22], estado, d.get("codigo_salida", "-"), mae])
    return filas


# --------------------------------------------------------------------------
# Contenido
# --------------------------------------------------------------------------
def contenido(doc):
    proc, ult, prom = M["procedimiento"], M["ref_ultimo_valor"], M["ref_promedio_hist"]
    mejora = (1 - proc["MAE"] / min(ult["MAE"], prom["MAE"])) * 100

    h1(doc, "1. Objetivo y alcance")
    p(doc, "El Observatorio de Inteligencia Turistica necesita actualizar sus estimaciones "
           "de forma controlada y reproducible, y poder responder en todo momento que datos, "
           "que codigo y que configuracion produjeron la cifra que consulta un directivo. "
           "El avance entrego el alcance, el diagrama, un pipeline ejecutable con un solo "
           "comando y los seis controles de calidad. Este trabajo final completa el flujo:")
    vinetas(doc, [
        "Registro de cada ejecucion en MLflow Tracking (codigo, fuentes, parametros, "
        "metricas, controles y artefactos), incluidas las corridas detenidas o rechazadas.",
        "Regla de aceptacion formal sobre 57 meses de backtesting con origen movil y "
        "comparacion sistematica contra dos procedimientos de referencia.",
        "Integracion con el tablero del Laboratorio 10: nueva seccion Estimaciones "
        "oficiales que solo lee la version aprobada.",
        "Monitoreo de actualizacion, calidad y resultados, y restauracion documentada "
        "de versiones anteriores.",
        "Contenerizacion con Docker Compose (MLflow, pipeline y tablero) con persistencia, "
        "reproducible desde una copia limpia del repositorio.",
    ])
    p(doc, "La variable, la fuente, las columnas, la clave de unicidad y los periodos se "
           "mantienen como se definieron en el avance: movimientos mensuales de viajeros "
           "(personas), serie flujo_mensual_nacional, Base de Migracion 2009-2026 en su "
           "version mensual, clave (periodo, destino).")

    h1(doc, "2. Diagrama del flujo final")
    figura(doc, "docs/diagrama_flujo_final.png",
           "Figura 1. Ocho etapas automatizadas, tres puntos de control (validacion, "
           "evaluacion y autorizacion) y los componentes de registro, monitoreo y "
           "restauracion.", ancho=5.0)

    h1(doc, "3. Pipeline reproducible")
    p(doc, "Todo el flujo se ejecuta con un solo comando y toda ruta, periodo, parametro y "
           "umbral vive en config/config.yaml:")
    codigo(doc, ["python -m src.run_pipeline --config config/config.yaml",
                 "docker compose up --build -d        # flujo completo en contenedores"])
    tabla(doc, ["Etapa", "Responsabilidad"], [
        ["1. Lectura", "Carga la fuente y calcula la huella SHA-256 de la fuente y de la configuracion"],
        ["2. Validacion", "Seis controles; si uno critico falla se detiene (codigo 2)"],
        ["3. Preparacion", "Serie mensual y factor de reparto (supuesto documentado)"],
        ["4. Estimacion", "baseline_estacional: nivel de 12 meses por indice estacional, solo con meses anteriores"],
        ["5. Evaluacion", "Backtesting 2021-04 a 2025-12 y regla de aceptacion"],
        ["6. Estimaciones", "Tabla con el esquema del tablero: observados, meses ocultos y 2 meses futuros"],
        ["7. Almacenamiento", "Version candidata con reporte de calidad, backtest y metadatos"],
        ["8. Publicacion", "Solo si la regla autoriza; copia inmutable en results/versions/<run_id>"],
    ], anchos=[1.6, 4.6])
    p(doc, "Medidas de reproducibilidad: dependencias con version fijada (requirements.txt y "
           "dashboard/requirements.txt), semilla 42, imagen base python:3.12-slim, commit de "
           "Git y huellas registrados en cada corrida, escritura atomica de los archivos "
           "publicados y codigos de salida documentados (0 aprobada, 1 rechazada por la "
           "regla, 2 detenida por control critico, 3 error). Dos corridas equivalentes "
           "producen la misma huella de fuente, la misma huella de configuracion y las "
           "mismas metricas (seccion 9).")

    h1(doc, "4. Controles automaticos de calidad")
    tabla(doc, ["#", "Control", "Advertencia", "Detiene"], [
        ["1", "Columnas y tipos", "-", "Falta una columna o tipo incompatible"],
        ["2", "Fechas y cobertura", "Periodo sin datos o cobertura < 20 dias", "Fecha invalida"],
        ["3", "Unicidad", "-", "Duplicado por (periodo, destino)"],
        ["4", "Valores faltantes", "NA en dias_fuente", "NA en periodo, destino o viajeros"],
        ["5", "Valores y denominadores", "-", "Negativos, inf/NaN o dias_fuente = 0"],
        ["6", "Regla metodologica", "-", "Algun mes proviene de 'diaria_agregada'"],
    ], anchos=[0.3, 1.6, 2.1, 2.2])
    p(doc, "Respecto del avance se corrigio el control 5: ante una columna ausente fallaba "
           "por una excepcion interna; ahora reporta el problema de forma explicita. Los "
           "periodos sin cobertura nunca se convierten en cero.")

    h1(doc, "5. Evaluacion y regla de aceptacion")
    p(doc, f"El procedimiento se evalua con origen movil sobre {proc['n_meses']} meses "
           "(2021-04 a 2025-12): cada mes se estima solo con los meses anteriores, como se "
           "haria en produccion. Se compara contra el ultimo valor observado y el promedio "
           "historico sobre los mismos meses.")
    tabla(doc, ["Procedimiento", "MAE", "RMSE", "MAPE", "Meses"], [
        ["baseline_estacional (oficial)", miles(proc["MAE"]), miles(proc["RMSE"]),
         f"{proc['MAPE']:.1f} %", proc["n_meses"]],
        ["Referencia: ultimo valor", miles(ult["MAE"]), miles(ult["RMSE"]),
         f"{ult['MAPE']:.1f} %", ult["n_meses"]],
        ["Referencia: promedio historico", miles(prom["MAE"]), miles(prom["RMSE"]),
         f"{prom['MAPE']:.1f} %", prom["n_meses"]],
    ], anchos=[2.4, 1.0, 1.0, 0.9, 0.8])
    p(doc, f"El procedimiento oficial se equivoca {mejora:.0f} % menos que la mejor "
           "referencia. Sobre los dos meses ocultos que ve el tablero (2025-11 y 2025-12) el "
           f"MAE es {miles(MO['procedimiento']['MAE'])} frente a "
           f"{miles(MO['ref_ultimo_valor']['MAE'])} y {miles(MO['ref_promedio_hist']['MAE'])}. "
           "Enero y febrero de 2026 se publican como estimacion sin error calculable, porque "
           "no hay observados comparables.")
    p(doc, "Regla de aceptacion (verificable y previa a publicar). Una candidata se publica "
           "solo si se cumplen todas las condiciones:", negrita_inicio="")
    a = META["umbrales"]
    vinetas(doc, [
        "Ningun control critico de calidad fallo.",
        "La salida esta completa: ninguna estimacion faltante.",
        f"El backtesting evaluo al menos {a['meses_minimos_backtest']} meses.",
        f"MAE <= {miles(a['mae_maximo'])} y RMSE <= {miles(a['rmse_maximo'])} personas/mes "
        "(umbrales fijados segun la escala de la variable).",
        "El MAE no es peor que el de la mejor referencia simple.",
    ])
    p(doc, "Si la regla no se cumple, la candidata queda en results/candidate para inspeccion, "
           "la corrida se registra con sus razones y la version vigente del tablero no cambia.")

    h1(doc, "6. Registro en MLflow Tracking")
    p(doc, "src/tracking.py registra cada corrida en el experimento "
           "observatorio_flujo_mensual_nacional. Se registran todas, tambien las detenidas "
           "(estado FAILED) y las rechazadas, porque son las que permiten monitorear la "
           "calidad en el tiempo.")
    tabla(doc, ["Elemento", "Que se registra"], [
        ["Codigo", "Commit de Git (tag mlflow.source.git.commit) y version del procedimiento"],
        ["Fuentes", "Ruta, huella SHA-256 y si es la muestra sintetica"],
        ["Parametros", "Metodo, ventana, factor de reparto, periodos, umbrales y semilla"],
        ["Metricas", "MAE, RMSE y MAPE del backtesting y de los meses ocultos (oficial y referencias), conteo de controles, aprobado, codigo de salida"],
        ["Controles", "Resumen como metricas y reporte completo como artefacto"],
        ["Artefactos", "config.yaml, reporte_calidad.json, estimaciones.csv, backtest.csv, run_metadata.json y log de la corrida"],
    ], anchos=[1.3, 4.9])
    p(doc, "En local el registro usa sqlite (mlruns/mlflow.db). En Docker Compose el pipeline "
           "apunta al servicio mlflow (MLFLOW_TRACKING_URI=http://mlflow:5000), que guarda "
           "base y artefactos en un volumen persistente. El identificador de MLflow se anota "
           "en los metadatos de la version publicada, y el tablero lo muestra.")

    h1(doc, "7. Integracion con el tablero")
    p(doc, "El tablero del Laboratorio 10 se incorporo al repositorio (carpeta dashboard/) con "
           "una nueva seccion Estimaciones oficiales. La seccion solo lee results/approved: "
           "cambiar un filtro nunca vuelve a ajustar el modelo.")
    vinetas(doc, [
        "Encabezado: fecha de actualizacion, version del procedimiento, MAE de validacion, "
        "proxima estimacion y estado de la version.",
        "V21: observado (linea continua azul) frente a estimacion (linea punteada morada), con "
        "el observado real de los meses ocultos para contrastar.",
        "V22: backtesting del procedimiento frente a las referencias, con tabla de MAE, RMSE y MAPE.",
        "V23: estado de los seis controles, resultado del monitoreo y trazabilidad (run, "
        "commit, huellas e identificador de MLflow).",
        "Advertencias de limitaciones: uso de la muestra sintetica, version restaurada, "
        "meses sin error calculable.",
        "Sin version aprobada muestra \"Estimaciones no disponibles\" en lugar de ceros.",
    ])

    h1(doc, "8. Monitoreo y recuperacion")
    tabla(doc, ["Dimension", "Alerta cuando"], [
        ["Actualizacion", "La version aprobada tiene mas de 45 dias o no existe"],
        ["Calidad", "Hay 2 o mas corridas seguidas sin aprobar (controles o regla)"],
        ["Resultados", "El MAE empeora mas de 25 % respecto de la aprobada anterior"],
    ], anchos=[1.5, 4.7])
    p(doc, "scripts/monitor.py escribe results/monitoreo.json (lo muestra el tablero) y sale "
           "con codigo 1 si hay alerta, para poder usarse en un cron o en CI. Cada version "
           "aprobada se guarda de forma inmutable en results/versions/<run_id>/; "
           "scripts/restore_version.py la vuelve a publicar sin reajustar nada y deja "
           "constancia en el registro de corridas y en results/approved/restauracion.json.")
    codigo(doc, ["python scripts/monitor.py",
                 "python scripts/restore_version.py --listar",
                 "python scripts/restore_version.py --anterior --motivo \"...\""])

    h1(doc, "9. Evidencia de ejecucion")
    p(doc, "Secuencia ejecutada desde cero (salidas completas en docs/evidencia/): dos "
           "corridas equivalentes, falla critica, falla de la regla, restauracion, "
           "recuperacion y monitoreo.")
    tabla(doc, ["Corrida", "Estado", "Codigo", "MAE"], corridas(), anchos=[1.9, 2.5, 0.8, 1.0])
    vinetas(doc, [
        "Corridas equivalentes: misma huella de fuente (ec60d714ed6df774), misma huella de "
        "configuracion y metricas identicas; ambas registradas en MLflow.",
        "Columna ausente: los controles 1 y 5 fallan, el pipeline se detiene con codigo 2 y "
        "la version aprobada no cambia.",
        "Metrica degradada (datos validos pero erraticos): los controles pasan, pero la regla "
        "rechaza (MAE y RMSE sobre el umbral), codigo 1, sin publicar.",
        "Restauracion de la version anterior y, al corregir los datos, recuperacion con una "
        "nueva version aprobada. El monitoreo termina sin alertas.",
        "Docker Compose: el mismo flujo se verifico en contenedores, y los volumenes de "
        "MLflow y de versiones persistieron tras docker compose down / up.",
        "19 pruebas automaticas (pytest) cubren controles, publicacion, equivalencia, "
        "detencion, rechazo, restauracion y monitoreo.",
    ])

    h1(doc, "10. Contenerizacion")
    tabla(doc, ["Servicio", "Funcion", "Persistencia"], [
        ["mlflow", "Servidor de MLflow Tracking (puerto 5000)", "Volumen ots_mlflow"],
        ["pipeline", "Corre el pipeline y el monitoreo; termina", "Volumenes ots_resultados y ots_logs"],
        ["dashboard", "Tablero Streamlit (puerto 8501), solo lectura", "Lee ots_resultados"],
    ], anchos=[1.1, 3.1, 2.0])
    p(doc, "Los datos institucionales no se copian en ninguna imagen (.dockerignore); se "
           "montan en solo lectura desde data/institucional. El servidor MLflow reutiliza la "
           "imagen del pipeline para usar exactamente la misma version de MLflow. La version "
           "aprobada versionada en Git siembra el volumen la primera vez, para que el tablero "
           "tenga algo que mostrar desde el inicio.")
    codigo(doc, ["git clone <repo> && cd lab11-data",
                 "docker compose up --build -d",
                 "docker compose run --rm pipeline       # nueva actualizacion"])

    h1(doc, "11. Limitaciones")
    vinetas(doc, [
        "La version publicada en el repositorio se genero con la muestra sintetica: ilustra el "
        "flujo, no es dato oficial. Con la base institucional montada el flujo es el mismo.",
        "El procedimiento es un baseline estacional; no incorpora rutas nuevas, crisis ni "
        "campanas de promocion.",
        "El error del backtesting es mayor que el de los meses ocultos porque incluye la "
        "recuperacion pospandemia y el cambio de clasificacion de 2023.",
        "Los umbrales de aceptacion y de monitoreo son decisiones del equipo segun la escala "
        "de la variable; estan en config.yaml y se pueden auditar y ajustar.",
    ])

    h1(doc, "Referencias")
    for ref in ["MLflow. (2026). MLflow Tracking. https://mlflow.org/docs/latest/ml/tracking",
                "Docker. (2026). Docker Compose. https://docs.docker.com/compose/",
                "Streamlit. (2026). Streamlit documentation. https://docs.streamlit.io/",
                "INGUAT / IGM. Base de Migracion 2009 - junio 2026 (datos compartidos con fines academicos)."]:
        par = doc.add_paragraph()
        r = par.add_run(ref)
        r.font.size = Pt(9)


def a_pdf(docx):
    """Exporta a PDF con Microsoft Word (Windows). Si no hay Word, lo omite."""
    if sys.platform != "win32":
        print("PDF omitido: requiere Microsoft Word en Windows")
        return
    entrada, salida = os.path.abspath(docx), os.path.abspath(docx[:-5] + ".pdf")
    ps = (f"$w = New-Object -ComObject Word.Application; $w.Visible = $false; "
          f"$d = $w.Documents.Open('{entrada}'); $d.SaveAs([ref]'{salida}', [ref]17); "
          f"$d.Close(); $w.Quit()")
    try:
        subprocess.run(["powershell", "-NoProfile", "-Command", ps], check=True, timeout=180)
        print("PDF:", salida)
    except Exception as e:
        print("No se pudo exportar a PDF:", e)


def main():
    doc = preparar_documento()
    contenido(doc)
    doc.save(SALIDA)
    print("DOCX:", SALIDA)
    a_pdf(SALIDA)


if __name__ == "__main__":
    main()

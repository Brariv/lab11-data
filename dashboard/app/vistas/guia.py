"""
Seccion Guia de lectura: alcance, codigo de color, glosario, uso del tablero,
limitaciones y origen de los datos. No lleva graficas.
"""

from __future__ import annotations

import streamlit as st

from componentes import aviso, grupo, lectura, nota
from config import (AZUL, CELESTE, DIVERGENTE, GRIS, MORADO, NARANJA, ROSA,
                    SALMON, SECUENCIAL, SEMAFORO, TINTA, VERDE, VIOLETA,
                    COLOR_DESTINO, COLOR_MODELO)

COLORES = [
    (AZUL, "Azul", "Demanda: visitantes, llegadas, volumen"),
    (NARANJA, "Naranja", "Economia: gasto, ingresos, empleo"),
    (VERDE, "Verde", "Sostenibilidad en buen estado / resultado favorable"),
    (ROSA, "Rosa", "Presion, alerta, resultado desfavorable"),
    (MORADO, "Morado", "Estimaciones y pronosticos de modelos"),
    (CELESTE, "Celeste", "Serie de apoyo o contexto"),
    (VIOLETA, "Violeta", "Navegacion y encabezados"),
    (SALMON, "Salmon", "Categoria complementaria de baja prioridad"),
    (GRIS, "Gris", "Referencia: total, promedio o historico de contexto"),
]

GLOSARIO = [
    ("Presion turistica", "Llegadas del mes divididas entre la capacidad de carga del "
     "destino. 1.0 significa que el destino recibe exactamente lo que soporta; por "
     "encima de 1.0 opera saturado."),
    ("Capacidad de carga", "Numero de visitantes al mes que un sitio puede recibir sin "
     "deterioro inaceptable, segun estudios de sitio. En el tablero es un parametro de "
     "entrada, no un calculo propio."),
    ("Derrama economica", "Gasto total que dejan los visitantes en el destino "
     "(alojamiento, alimentacion, transporte, actividades y artesanias), en US$."),
    ("Gasto por visitante", "Derrama dividida entre llegadas. Mide el valor de cada "
     "visita, no el volumen."),
    ("Estancia promedio", "Noches que pasa, en promedio, cada visitante en el destino."),
    ("Mercado emisor", "Pais o region de procedencia del visitante."),
    ("Estacionalidad", "Patron que se repite cada ano: meses de temporada alta y baja."),
    ("Desacoplamiento", "Cuando la visita crece mas rapido que la huella ambiental "
     "(residuos, agua, CO2). Es relativo si la huella sigue creciendo, aunque mas "
     "despacio; absoluto solo si la huella baja."),
    ("Asociacion", "Dos variables que se mueven juntas. No implica que una cause la "
     "otra: el tablero no mide efectos causales."),
    ("Pronostico", "Estimacion de los meses futuros a partir del patron historico. "
     "Se dibuja en morado con linea punteada."),
    ("Intervalo de confianza", "Banda alrededor del pronostico donde se espera que "
     "caiga el valor real con una probabilidad dada (por ejemplo, 95%). Mas ancha = "
     "mas incertidumbre."),
    ("MAE", "Error absoluto medio: cuantos visitantes, en promedio, se equivoca el "
     "modelo por mes."),
    ("RMSE", "Raiz del error cuadratico medio: como el MAE, pero castiga mas los "
     "errores grandes."),
    ("MAPE", "Error porcentual absoluto medio: en que porcentaje se equivoca el modelo, "
     "en promedio. Es la metrica que se comunica por ser la mas facil de leer."),
    ("Promotor", "Visitante que declara que recomendaria el destino. Es la variable "
     "que los modelos de clasificacion intentan anticipar."),
    ("Matriz de confusion", "Tabla que cruza lo que paso en realidad con lo que dijo "
     "el modelo. Muestra aciertos y los dos tipos de error: falsa alarma y oportunidad "
     "perdida."),
    ("Exactitud, precision y exhaustividad", "Exactitud: porcentaje total de aciertos. "
     "Precision: de los que el modelo marca como promotores, cuantos lo son. "
     "Exhaustividad: de los promotores reales, cuantos detecta. F1 combina las dos "
     "ultimas."),
    ("Curva ROC", "Muestra, para todos los umbrales posibles, cuantos promotores "
     "detecta el modelo frente a cuantas falsas alarmas genera. La diagonal es el azar."),
    ("AUC", "Area bajo la curva ROC. 0.5 = adivinar al azar; 1.0 = discriminacion "
     "perfecta. Permite comparar modelos sin elegir umbral."),
    ("Curva de aprendizaje", "Desempeno del modelo segun cuantas encuestas usa para "
     "aprender. Si se aplana, mas encuestas del mismo tipo no mejoran el resultado."),
    ("Fuga de informacion", "Usar como predictor un dato que solo se conoce despues "
     "del hecho a anticipar. Por eso la calificacion general no entra en los modelos."),
]

LIMITACIONES = [
    ("Antigua Guatemala y Semuc Champey operan por encima de su capacidad de carga "
     "estimada (V12).",
     "Revisar aforos y escalonar horarios de acceso.",
     "La capacidad de carga es una estimacion de estudios de sitio, no una medicion; "
     "la recomendacion es revisar, no cerrar."),
    ("La huella ambiental crece mas despacio que la visita (V11): hay desacople "
     "relativo.",
     "Sostener las medidas de eficiencia y fijar metas de reduccion absoluta.",
     "Desacople relativo no es reduccion absoluta; el total de emisiones sigue subiendo."),
    ("Dentro de cada destino, ocupacion y gasto diario apenas se asocian (V8): la "
     "relacion que se ve al mezclar destinos refleja sobre todo diferencias entre ellos.",
     "No usar las metas de ocupacion como sustituto de metas de derrama.",
     "Es una asociacion observada, no una relacion causal."),
    ("Las actividades de naturaleza (a favor) y las incidencias durante el viaje (en "
     "contra) aparecen entre los factores mas ligados a la recomendacion en los tres "
     "modelos (V20).",
     "Priorizar la oferta de naturaleza y la atencion que evita incidencias.",
     "El modelo mide asociacion en una encuesta; el efecto real debe verificarse con "
     "una medicion posterior a la intervencion."),
]


def _swatch(color: str, ancho: int = 22, alto: int = 22, extra: str = "") -> str:
    return (f'<span style="display:inline-block;width:{ancho}px;height:{alto}px;'
            f'border-radius:6px;background:{color};vertical-align:middle;'
            f'margin-right:10px;{extra}"></span>')


def _fila(swatch: str, nombre: str, significado: str) -> str:
    return (f'<div style="display:flex;align-items:center;margin:6px 0;'
            f'font-size:.9rem;color:{TINTA}">{swatch}'
            f'<b style="min-width:150px;display:inline-block">{nombre}</b>'
            f'<span>{significado}</span></div>')


def _degradado(colores: list[str]) -> str:
    return (f'<span style="display:inline-block;width:120px;height:14px;'
            f'border-radius:7px;vertical-align:middle;margin-right:10px;'
            f'background:linear-gradient(90deg,{",".join(colores)})"></span>')


def _linea(color: str, punteada: bool) -> str:
    estilo = "dashed" if punteada else "solid"
    return (f'<span style="display:inline-block;width:46px;height:0;'
            f'border-top:3px {estilo} {color};vertical-align:middle;'
            f'margin-right:10px"></span>')


def _lista(items: list[str]) -> str:
    return ('<ul style="margin:4px 0 4px 18px;padding:0;font-size:.9rem;'
            f'color:{TINTA};line-height:1.5">'
            + "".join(f"<li>{i}</li>" for i in items) + "</ul>")


def _html(texto: str) -> None:
    st.markdown(texto, unsafe_allow_html=True)


# --------------------------------------------------------------------------
def _alcance() -> None:
    grupo("ALCANCE DEL TABLERO")
    lectura("Dirigido a directivos y tomadores de decision del sector turistico "
            "(direccion de INGUAT, mancomunidades, camaras de turismo, gerencias de "
            "destino). No hace falta formacion estadistica para leerlo.")
    izq, der = st.columns(2, gap="small")
    with izq, st.container(border=True):
        _html(f'<div class="ots-vt" style="color:{VERDE}">Que cubre</div>')
        _html(_lista([
            "7 destinos: Antigua Guatemala, Lago de Atitlan, Tikal y Peten, Rio Dulce "
            "y Livingston, Quetzaltenango, Semuc Champey y Ciudad de Guatemala.",
            "Serie mensual 2017-2025 de demanda, economia, empleo y huella ambiental.",
            "Encuesta a pie de destino 2023-2025 (9 000 cuestionarios) para el perfil "
            "del visitante.",
            "Pronostico de demanda a 12 meses y clasificacion de visitantes promotores, "
            "reutilizando los modelos de los laboratorios 1 y 2.",
        ]))
    with der, st.container(border=True):
        _html(f'<div class="ots-vt" style="color:{ROSA}">Que no cubre</div>')
        _html(_lista([
            "No sustituye un estudio de impacto ambiental ni una evaluacion de "
            "capacidad de carga: la capacidad de carga entra como parametro.",
            "No mide efectos causales de politicas: todo lo que muestra son "
            "<b>asociaciones</b>.",
            "No contiene datos de empresas individuales.",
            "Los pronosticos proyectan la continuidad del patron historico: no "
            "incorporan nuevas rutas aereas, crisis sanitarias ni campanas de promocion.",
        ]))


def _codigo_color(completo: bool) -> None:
    grupo("CODIGO DE COLOR")
    with st.container(border=True):
        _html('<div class="ots-vt">Un color, un significado, en todo el tablero</div>'
              '<div class="ots-vp">Si el azul es demanda en Panorama, es demanda en '
              'Modelos. Ninguna lectura depende solo del color: siempre hay etiqueta, '
              'texto o tipo de linea.</div>')
        _html("".join(_fila(_swatch(c), n, s) for c, n, s in COLORES))

        _html('<div class="ots-vt" style="margin-top:14px">Tipo de linea</div>')
        _html(_fila(_linea(AZUL, False), "Linea continua", "Dato observado")
              + _fila(_linea(MORADO, True), "Linea punteada morada",
                      "Estimacion o pronostico de un modelo"))

        _html('<div class="ots-vt" style="margin-top:14px">Escalas</div>')
        _html(_fila(_degradado(DIVERGENTE), "Presion turistica",
                    "Verde = holgura, naranja = cerca del limite (1.0), rosa = "
                    "saturacion. Se usa en V1 y V12.")
              + _fila(_degradado(SECUENCIAL), "Secuencial azul",
                      "Una sola magnitud de menos a mas (V6, V7, V17).")
              + _fila("".join(_swatch(SEMAFORO[k], 14, 14, "margin-right:3px;")
                              for k in ("bajo", "medio", "alto"))
                      + '<span style="margin-right:7px"></span>', "Semaforo",
                      "Holgura / Al limite / Saturacion, siempre con la palabra escrita."))

        if completo:
            _html('<div class="ots-vt" style="margin-top:14px">Color por destino</div>')
            _html("".join(_fila(_swatch(c, 14, 14), d, "") for d, c in COLOR_DESTINO.items()))
            _html('<div class="ots-vt" style="margin-top:14px">Color por modelo</div>')
            _html("".join(_fila(_swatch(c, 14, 14), mo, "") for mo, c in COLOR_MODELO.items()))
            nota("Los colores de modelo se repiten entre pronostico y clasificacion "
                 "porque nunca aparecen en la misma grafica. La paleta no es segura para "
                 "daltonismo (azul y morado se confunden en deuteranopia), por eso cada "
                 "serie lleva etiqueta directa y las estimaciones usan linea punteada.")


def _glosario() -> None:
    grupo("GLOSARIO")
    with st.container(border=True):
        filas = [f'<div style="margin:8px 0;font-size:.9rem;color:{TINTA};'
                 f'line-height:1.45"><b>{termino}.</b> {definicion}</div>'
                 for termino, definicion in GLOSARIO]
        _html("".join(filas))


def _uso() -> None:
    grupo("COMO USAR EL TABLERO")
    with st.container(border=True):
        _html(_lista([
            "<b>Secciones.</b> El control de arriba cambia entre Panorama, Explorar, "
            "Sostenibilidad, Modelos y esta Guia.",
            "<b>Periodo y Lugar.</b> Acotan todo el tablero a un rango de anos, a "
            "regiones o a destinos concretos. La etiqueta de cada pildora muestra el "
            "valor activo.",
            "<b>Detalle.</b> Agregacion temporal (Ano, Trimestre o Mes) para las "
            "series, y profundidad del contenido: <i>Resumen ejecutivo</i> deja solo "
            "la lectura principal; <i>Analisis completo</i> agrega las notas "
            "metodologicas.",
            "<b>Graficas.</b> Enciende o apaga cada visualizacion de la seccion actual.",
            "<b>Enlace V3.</b> En Panorama, toque una barra del ranking de destinos: el "
            "mapa V1 la resalta con un anillo, la serie V2 dibuja su linea sobre el "
            "total y las secciones Explorar y Sostenibilidad se recalculan solo para ese "
            "destino.",
            "<b>Enlace V5.</b> En Explorar, toque un mercado emisor: el calendario V6 "
            "muestra solo la estacionalidad de ese mercado.",
            "<b>Enfoque visible.</b> Todo enfoque activo aparece como chip bajo la "
            "barra; el boton <i>Quitar enfoque</i> lo elimina.",
            "<b>Restablecer.</b> Vuelve a la vista inicial: borra filtros, enfoques y "
            "graficas ocultas.",
        ]))
        lectura("Cada grafica indica su numero, la pregunta de gestion que responde y "
                "si esta enlazada. Pase el cursor sobre los puntos o barras para ver "
                "las cifras exactas.")


def _limitaciones() -> None:
    grupo("RECOMENDACIONES Y SUS LIMITES")
    for i, (hallazgo, rec, limite) in enumerate(LIMITACIONES, start=1):
        with st.container(border=True):
            _html(f'<div class="ots-vt"><span class="ots-vn">{i}</span> &nbsp;'
                  f'{hallazgo}</div>')
            lectura(f"<b>Recomendacion:</b> {rec}")
            aviso(f"<b>Limitacion:</b> {limite}")


def _origen() -> None:
    grupo("ORIGEN DE LOS DATOS")
    with st.container(border=True):
        aviso("Los datos de este tablero son <b>sinteticos</b>: no son cifras "
              "oficiales.")
        _html(f'<div style="font-size:.9rem;color:{TINTA};line-height:1.5;'
              f'margin-top:8px">Las tres tablas (serie mensual, mercados emisores y '
              f'encuesta de visitantes) se generan con <code>data/generar_datos.py</code> '
              f'y semilla fija, de modo que son reproducibles. Imitan la estacionalidad, '
              f'la caida por pandemia y los ordenes de magnitud reportados por INGUAT y '
              f'la OMT. La capa de datos esta aislada en <code>app/datos.py</code>: al '
              f'sustituir los CSV por registros oficiales con las mismas columnas '
              f'(<code>docs/codebook.md</code>) el tablero funciona sin otro cambio.</div>')
        nota("La encuesta a visitantes solo cubre 2023-2025: si el periodo elegido es "
             "anterior, las graficas basadas en ella muestran un aviso en lugar de datos.")


# --------------------------------------------------------------------------
def render(ctx: dict) -> None:
    completo = ctx.get("detalle", "Analisis completo") == "Analisis completo"
    _alcance()
    _codigo_color(completo)
    _uso()
    _glosario()
    _limitaciones()
    _origen()

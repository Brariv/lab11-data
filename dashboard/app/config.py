"""
Identidad visual del Observatorio: paleta, tipografia y estilos.

PALETA
------
Se usa la paleta institucional del equipo (esquema principal de 8 colores mas
las familias extendidas de rosas, azules y morados, y el semaforo de tres
colores). Es una paleta de alto croma, asi que el tablero la aplica con tres
reglas para que siga siendo legible para directivos:

1. Un color = un significado, en todas las pantallas. Si el azul es demanda en
   la portada, es demanda en la seccion de modelos.
2. El color saturado se reserva para el dato. Fondos, rejilla y texto usan los
   tonos neutros derivados de la familia azul (B5BDE3 / 2E3B73), nunca los
   colores del esquema principal, para que la tinta de color no compita con la
   informacion.
3. Ninguna lectura depende solo del color: las series llevan etiqueta directa,
   el semaforo lleva texto ("Holgura / Equilibrio / Saturacion") y las
   estimaciones se distinguen ademas por linea punteada.

Regla de lectura que atraviesa todo el tablero:
    linea continua  = dato observado
    linea punteada  = estimacion / pronostico (color morado A2158D)
"""

from __future__ import annotations

# --------------------------------------------------------------------------
# Esquema principal (los 8 colores de la paleta) con significado fijo
# --------------------------------------------------------------------------
AZUL     = "#4361EE"   # demanda: llegadas, visitantes, volumen
NARANJA  = "#FFA630"   # economia: gasto, ingresos, empleo
VERDE    = "#60A125"   # sostenibilidad en buen estado / resultado favorable
ROSA     = "#F72585"   # presion, alerta, resultado desfavorable
MORADO   = "#A2158D"   # estimaciones y pronosticos de modelos
VIOLETA  = "#4D0A99"   # encabezados y acentos de navegacion
CELESTE  = "#4CC9F0"   # serie de apoyo / segundo plano informativo
SALMON   = "#FFA5A3"   # categoria complementaria de baja prioridad

# Familias extendidas (se usan para escalas y para los neutros del tablero)
ROSAS    = ["#F72585", "#FA0F79", "#F877B1", "#BA5683", "#7D043A"]
AZULES   = ["#B5BDE3", "#7487DB", "#4361EE", "#2E3B73", "#0B2183"]
MORADOS  = ["#D27BF4", "#A616DF", "#8C25FA", "#CF1BB4", "#A2158D"]
SEMAFORO = {"alto": "#F72585", "medio": "#FFA630", "bajo": "#60A125"}

# Neutros derivados de la familia azul: no son grises puros, lo que mantiene
# la coherencia con la paleta sin robarle protagonismo al dato.
TINTA    = "#2E3B73"   # texto principal  (contraste 8.9:1 sobre blanco)
TINTA_2  = "#5A6798"   # texto secundario (contraste 5.1:1 sobre blanco)
GRIS     = "#8089A8"   # referencia historica, elementos de contexto
LINEA    = "#DFE3F2"   # bordes y rejilla
FONDO    = "#FFFFFF"
FONDO_2  = "#F5F6FD"   # tarjetas y paneles

# Serie categorica. El orden alterna familias (azul -> verde -> naranja ->
# celeste -> morado -> rosa) para que dos categorias contiguas nunca sean
# vecinas en tono; aun asi toda grafica categorica lleva etiqueta directa.
CATEGORICA = [AZUL, VERDE, NARANJA, CELESTE, MORADO, ROSA, VIOLETA, SALMON]

# Escala secuencial (una sola magnitud, de menos a mas): familia azul
SECUENCIAL = ["#EDEFFA", "#B5BDE3", "#7487DB", "#4361EE", "#2E3B73", "#0B2183"]

# Escala divergente para presion turistica: el semaforo de la paleta
# (verde = holgura, naranja = equilibrio, rosa = saturacion)
DIVERGENTE = ["#60A125", "#A8C96B", "#FFA630", "#FA6B8A", "#F72585"]

# Color por destino, fijo en todo el tablero
COLOR_DESTINO = {
    "Antigua Guatemala": AZUL,
    "Lago de Atitlan": VERDE,
    "Tikal y Peten": NARANJA,
    "Rio Dulce y Livingston": CELESTE,
    "Quetzaltenango": MORADO,
    "Semuc Champey": ROSA,
    "Ciudad de Guatemala": VIOLETA,
}

# Color por modelo, fijo en la seccion de modelos
COLOR_MODELO = {
    "Tendencia + estacionalidad": AZUL,
    "Suavizamiento (Holt-Winters)": NARANJA,
    "SARIMA": MORADO,
    "Regresion logistica": AZUL,
    "Arbol de decision": NARANJA,
    "K vecinos cercanos": MORADO,
}

# --------------------------------------------------------------------------
# Tipografia: pila del sistema (SF Pro en Apple) con Inter como respaldo.
# Es la fuente que el usuario ya lee en su telefono: cero costo de aprendizaje.
# --------------------------------------------------------------------------
TIPOGRAFIA = ('-apple-system, BlinkMacSystemFont, "SF Pro Text", "SF Pro Display", '
              'Inter, "Helvetica Neue", Arial, sans-serif')

# Grises del sistema iOS, usados para fondo, separadores y texto secundario
IOS_FONDO     = "#F2F2F7"   # systemGroupedBackground
IOS_TARJETA   = "#FFFFFF"
IOS_SEPARADOR = "rgba(60,60,67,0.12)"
IOS_SEC       = "#6E6E73"   # label secundario


def plantilla_plotly() -> dict:
    """Layout base de todas las graficas: menos tinta, mas dato."""
    return dict(
        font=dict(family=TIPOGRAFIA, size=13, color=TINTA),
        title=dict(font=dict(size=16, color=TINTA), x=0, xanchor="left"),
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        margin=dict(l=8, r=8, t=34, b=8),
        hoverlabel=dict(font=dict(family=TIPOGRAFIA, size=12), bgcolor="white",
                        bordercolor=LINEA),
        legend=dict(orientation="h", yanchor="bottom", y=1.02,
                    xanchor="left", x=0, title_text="",
                    font=dict(size=12)),
        xaxis=dict(gridcolor=LINEA, zerolinecolor=LINEA, linecolor=LINEA,
                   title_font=dict(size=12, color=IOS_SEC),
                   tickfont=dict(size=11, color=IOS_SEC)),
        yaxis=dict(gridcolor=LINEA, zerolinecolor=LINEA, linecolor=LINEA,
                   title_font=dict(size=12, color=IOS_SEC),
                   tickfont=dict(size=11, color=IOS_SEC)),
        colorway=CATEGORICA,
    )


def tema_altair() -> dict:
    """Mismo lenguaje visual para las graficas de Altair (las que responden al toque)."""
    return {
        "config": {
            "background": "transparent",
            "view": {"strokeWidth": 0, "continuousHeight": 300},
            "font": TIPOGRAFIA,
            "axis": {"labelColor": IOS_SEC, "titleColor": IOS_SEC,
                     "labelFontSize": 11, "titleFontSize": 12,
                     "gridColor": LINEA, "domainColor": LINEA,
                     "tickColor": LINEA, "labelFont": TIPOGRAFIA,
                     "titleFont": TIPOGRAFIA, "titlePadding": 10},
            "legend": {"labelColor": TINTA, "titleColor": IOS_SEC,
                       "labelFontSize": 12, "titleFontSize": 11,
                       "labelFont": TIPOGRAFIA, "titleFont": TIPOGRAFIA},
            "range": {"category": CATEGORICA},
        }
    }


CSS = f"""
<style>
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&display=swap');

/* ---------------------------------------------------------------- base --
   Lenguaje visual iOS: fondo gris agrupado, tarjetas blancas con esquinas
   continuas, separadores de un pixel y tipografia del sistema.           */
html, body, [class*="css"] {{ font-family: {TIPOGRAFIA}; color: {TINTA};
    -webkit-font-smoothing: antialiased; }}
.stApp {{ background: {IOS_FONDO}; }}
section[data-testid="stSidebar"], div[data-testid="stSidebarCollapsedControl"] {{
    display: none !important; }}
.block-container {{ padding-top: 1.1rem; padding-bottom: 3rem;
    max-width: 1500px; }}

/* ------------------------------------------------------- barra superior --
   Nav bar translucida fija, como la de una app de iOS.                   */
.ots-nav {{
    position: sticky; top: 0; z-index: 99;
    display: flex; align-items: center; gap: 12px;
    padding: 10px 18px; margin: -10px -6px 10px -6px;
    background: rgba(242,242,247,0.82);
    backdrop-filter: saturate(180%) blur(20px);
    -webkit-backdrop-filter: saturate(180%) blur(20px);
    border-bottom: 1px solid {IOS_SEPARADOR};
}}
.ots-marca {{
    display: inline-flex; align-items: center; justify-content: center;
    width: 30px; height: 30px; border-radius: 9px; font-size: 16px;
    background: linear-gradient(145deg, {VIOLETA}, {AZUL} 70%, {CELESTE});
    color: #fff; box-shadow: 0 2px 6px rgba(67,97,238,.35);
}}
.ots-marca-txt {{ font-size: .95rem; font-weight: 650; letter-spacing: -.01em; }}
.ots-marca-sub {{ font-size: .74rem; color: {IOS_SEC}; margin-left: 2px; }}

/* --------------------------------------------------------- titulo grande --
   Patron "Large Title" de iOS: titulo de 34 px y bajada discreta.        */
.ots-titulo {{ font-size: 2.05rem; font-weight: 700; letter-spacing: -.022em;
    margin: 6px 0 2px 0; line-height: 1.1; }}
.ots-bajada {{ font-size: .95rem; color: {IOS_SEC}; margin: 0 0 10px 0; }}

/* ---------------------------------------------------------- encabezados --
   Rotulo de grupo en mayusculas, como las listas agrupadas de Ajustes.   */
.ots-grupo {{ font-size: .76rem; font-weight: 600; letter-spacing: .05em;
    text-transform: uppercase; color: {IOS_SEC}; margin: 18px 0 6px 2px; }}

/* ------------------------------------------------------------- tarjetas --
   st.container(border=True) se convierte en una tarjeta iOS.             */
div[data-testid="stVerticalBlockBorderWrapper"] {{
    background: {IOS_TARJETA}; border: 1px solid {IOS_SEPARADOR};
    border-radius: 18px; padding: 14px 16px;
    box-shadow: 0 1px 2px rgba(16,24,40,.04), 0 10px 28px rgba(45,55,120,.05);
}}

/* ------------------------------------------------------- tarjeta de dato --
   Formato "widget": glifo, rotulo pequeno y cifra grande.                */
.ots-kpi {{ display: flex; flex-direction: column; gap: 2px; }}
.ots-kpi .gl {{ width: 28px; height: 28px; border-radius: 8px; display: flex;
    align-items: center; justify-content: center; font-size: 14px;
    margin-bottom: 6px; }}
.ots-kpi .rot {{ font-size: .78rem; color: {IOS_SEC}; font-weight: 500; }}
.ots-kpi .val {{ font-size: 1.75rem; font-weight: 700; letter-spacing: -.02em;
    font-variant-numeric: tabular-nums; line-height: 1.15; }}
.ots-kpi .sub {{ font-size: .78rem; color: {IOS_SEC}; }}
.ots-kpi .sube {{ color: {VERDE}; font-weight: 600; }}
.ots-kpi .baja {{ color: {ROSA}; font-weight: 600; }}

/* ------------------------------------------------- textos de apoyo (iOS) --
   Bloques tipo "footnote" de una lista agrupada.                         */
.ots-nota, .ots-lectura, .ots-aviso {{
    font-size: .86rem; line-height: 1.45; border-radius: 12px;
    padding: 10px 13px; margin: 8px 0 2px 0; }}
.ots-nota    {{ background: #F7F7FA; color: {IOS_SEC}; }}
.ots-lectura {{ background: rgba(67,97,238,.08); color: {TINTA};
    border-left: 3px solid {AZUL}; }}
.ots-aviso   {{ background: rgba(255,166,48,.14); color: {TINTA};
    border-left: 3px solid {NARANJA}; }}
.ots-vacio {{ background: #F7F7FA; border: 1px dashed {IOS_SEPARADOR};
    border-radius: 14px; padding: 26px; text-align: center;
    color: {IOS_SEC}; font-size: .92rem; }}

/* ---------------------------------------------------------------- chips --
   Pildoras de iOS: estado del filtro y tipo de grafica.                  */
.ots-etq {{ display: inline-block; font-size: .7rem; font-weight: 600;
    padding: 3px 9px; border-radius: 999px; background: #F0F0F5;
    color: {IOS_SEC}; margin-right: 6px; }}
.ots-etq.enlazada {{ background: rgba(255,166,48,.18); color: #9A5B00; }}
.ots-etq.estimacion {{ background: rgba(162,21,141,.12); color: {MORADO}; }}
.ots-chip {{ display: inline-flex; align-items: center; gap: 6px;
    font-size: .8rem; font-weight: 550; padding: 5px 12px; border-radius: 999px;
    background: rgba(67,97,238,.12); color: {AZUL}; margin: 0 6px 6px 0; }}

/* ------------------------------------------------- titulo de visualizacion */
.ots-vt {{ font-size: 1.02rem; font-weight: 650; letter-spacing: -.01em;
    margin: 0 0 2px 0; }}
.ots-vp {{ font-size: .84rem; color: {IOS_SEC}; margin: 0 0 8px 0; }}
.ots-vn {{ font-size: .72rem; font-weight: 700; color: {AZUL};
    letter-spacing: .04em; }}

/* -------------------------------------------------- controles de Streamlit */
div[data-testid="stSegmentedControl"] button {{
    border-radius: 999px !important; font-weight: 550; }}
div[data-testid="stPopover"] > button, div[data-testid="stPopover"] button {{
    border-radius: 999px !important; border: 1px solid {IOS_SEPARADOR} !important;
    background: #FFFFFF !important; font-weight: 550; }}
button[kind="secondary"] {{ border-radius: 999px !important; }}
div[data-testid="stPlotlyChart"], div[data-testid="stVegaLiteChart"] {{
    border-radius: 14px; overflow: hidden; }}
div[data-testid="stExpander"] details {{ border-radius: 14px;
    border: 1px solid {IOS_SEPARADOR}; background: #fff; }}
hr {{ border-color: {IOS_SEPARADOR}; }}
h2, h3, h4 {{ color: {TINTA}; letter-spacing: -.015em; }}
div[data-testid="stMetricValue"] {{ font-variant-numeric: tabular-nums; }}
#MainMenu, footer, header[data-testid="stHeader"] {{ visibility: hidden; height: 0; }}
</style>
"""

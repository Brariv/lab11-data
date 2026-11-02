"""
Generador del conjunto de datos del Observatorio de Turismo Sostenible.

Produce tres tablas reproducibles (semilla fija) que alimentan el tablero:

    turismo_mensual.csv   serie mensual por destino (demanda, economia, presion)
    mercados.csv          llegadas mensuales por mercado emisor y destino
    visitantes.csv        encuesta a pie de destino, una fila por visitante

Los valores son SINTETICOS: reproducen la estacionalidad, la caida por la
pandemia y los ordenes de magnitud que reportan INGUAT y la OMT para los
destinos de Guatemala, pero no son cifras oficiales. Para enchufar datos
reales basta con reemplazar los CSV respetando los nombres de columna del
codebook (docs/codebook.md); el tablero no necesita ningun otro cambio.

Uso:
    python data/generar_datos.py
"""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd

SEMILLA = 2026
CARPETA = Path(__file__).resolve().parent

INICIO = "2017-01-01"
FIN = "2025-12-01"

# --------------------------------------------------------------------------
# Catalogo de destinos
# --------------------------------------------------------------------------
# llegadas_base  -> visitantes por mes en un mes promedio de 2019
# estancia       -> noches promedio por visitante
# gasto          -> gasto diario por visitante en USD (nivel 2019)
# ocupacion      -> ocupacion hotelera base (%)
# carga          -> capacidad de carga estimada (visitantes/mes) para la
#                   presion turistica; viene de estudios de capacidad del sitio
DESTINOS = [
    # nombre, region, lat, lon, llegadas_base, estancia, gasto, ocupacion, carga, perfil
    ("Antigua Guatemala", "Altiplano Central", 14.5586, -90.7295, 62000, 2.8, 95, 68, 78000, "cultural"),
    ("Lago de Atitlan",   "Altiplano Occidental", 14.6907, -91.2025, 41000, 3.2, 88, 61, 62000, "naturaleza"),
    ("Tikal y Peten",     "Peten", 17.2220, -89.6237, 28000, 2.4, 110, 57, 42000, "arqueologico"),
    ("Rio Dulce y Livingston", "Caribe", 15.6600, -88.7500, 15000, 3.5, 80, 52, 26000, "naturaleza"),
    ("Quetzaltenango",    "Altiplano Occidental", 14.8347, -91.5180, 12000, 2.2, 65, 48, 25000, "cultural"),
    ("Semuc Champey",     "Verapaces", 15.5340, -89.9560, 9000, 2.0, 60, 44, 11000, "naturaleza"),
    ("Ciudad de Guatemala", "Area Metropolitana", 14.6349, -90.5069, 85000, 1.9, 105, 64, 170000, "urbano"),
]

MERCADOS = ["Estados Unidos", "El Salvador", "Mexico", "Honduras",
            "Europa", "Canada", "Sudamerica", "Asia y otros"]

# Participacion de cada mercado por perfil de destino (suma 1)
MEZCLA_MERCADO = {
    "cultural":     [0.33, 0.14, 0.11, 0.09, 0.18, 0.06, 0.06, 0.03],
    "naturaleza":   [0.29, 0.12, 0.09, 0.07, 0.24, 0.07, 0.08, 0.04],
    "arqueologico": [0.31, 0.07, 0.10, 0.05, 0.26, 0.08, 0.09, 0.04],
    "urbano":       [0.30, 0.22, 0.14, 0.14, 0.09, 0.04, 0.05, 0.02],
}

# Estacionalidad mensual del destino (enero..diciembre).
# Picos: Semana Santa (marzo-abril), vacaciones de medio anio (julio-agosto)
# y temporada navidena (diciembre).
ESTACION = {
    "cultural":     [1.08, 0.94, 1.18, 1.16, 0.93, 0.85, 1.14, 1.10, 0.84, 0.88, 0.97, 1.28],
    "naturaleza":   [1.10, 0.97, 1.12, 1.10, 0.92, 0.82, 1.20, 1.16, 0.83, 0.86, 0.95, 1.22],
    "arqueologico": [1.14, 1.02, 1.10, 1.05, 0.88, 0.78, 1.18, 1.14, 0.80, 0.84, 0.96, 1.26],
    "urbano":       [1.02, 0.98, 1.06, 1.04, 0.98, 0.95, 1.08, 1.06, 0.94, 0.96, 1.00, 1.14],
}

# Factor de la pandemia por anio-mes (1 = normalidad)
def factor_covid(fecha: pd.Timestamp) -> float:
    y, m = fecha.year, fecha.month
    if y < 2020:
        return 1.0
    if y == 2020:
        if m <= 2:
            return 1.0
        if m == 3:
            return 0.45
        if m <= 7:
            return 0.07
        return 0.07 + 0.05 * (m - 7)          # reapertura gradual
    if y == 2021:
        return min(0.95, 0.38 + 0.045 * m)
    if y == 2022:
        return min(1.0, 0.86 + 0.015 * m)
    return 1.0


def construir_mensual(rng: np.random.Generator) -> pd.DataFrame:
    fechas = pd.date_range(INICIO, FIN, freq="MS")
    filas = []

    for (nombre, region, lat, lon, base, estancia, gasto, ocup, carga, perfil) in DESTINOS:
        est = ESTACION[perfil]
        for fecha in fechas:
            t = (fecha.year - 2017) + (fecha.month - 1) / 12

            # --- demanda -------------------------------------------------
            tendencia = (1.042 ** t)                       # +4.2% anual
            estacional = est[fecha.month - 1]
            ruido = rng.normal(1.0, 0.055)
            llegadas = base * tendencia * estacional * factor_covid(fecha) * ruido
            llegadas = max(60, llegadas)

            # --- estancia y ocupacion ------------------------------------
            noches = max(1.0, estancia * rng.normal(1.0, 0.06))
            presion = llegadas / carga
            ocupacion = np.clip(
                ocup * (0.55 + 0.75 * presion) * rng.normal(1.0, 0.05), 8, 96
            )

            # --- economia -------------------------------------------------
            inflacion = 1.032 ** t
            gasto_dia = gasto * inflacion * rng.normal(1.0, 0.045)
            gasto_total = llegadas * noches * gasto_dia

            # reparto del gasto por categoria (varia por perfil)
            if perfil == "urbano":
                reparto = np.array([0.34, 0.27, 0.17, 0.12, 0.10])
            elif perfil == "naturaleza":
                reparto = np.array([0.30, 0.22, 0.16, 0.24, 0.08])
            elif perfil == "arqueologico":
                reparto = np.array([0.29, 0.21, 0.19, 0.24, 0.07])
            else:
                reparto = np.array([0.32, 0.25, 0.14, 0.17, 0.12])
            reparto = reparto * rng.normal(1.0, 0.04, size=5)
            reparto = reparto / reparto.sum()

            # --- empleo y sostenibilidad ----------------------------------
            empleos = llegadas * noches / 95 * rng.normal(1.0, 0.05)
            empleo_local = np.clip(
                {"cultural": 71, "naturaleza": 64, "arqueologico": 58, "urbano": 77}[perfil]
                + 1.1 * t + rng.normal(0, 2.2), 35, 93
            )
            certificados = np.clip(
                {"cultural": 22, "naturaleza": 18, "arqueologico": 15, "urbano": 26}[perfil]
                + 2.6 * t + rng.normal(0, 1.6), 5, 85
            )

            noches_totales = llegadas * noches
            # kg de residuos por visitante-noche, m3 de agua, kg CO2
            kg_residuo = {"cultural": 1.6, "naturaleza": 1.9, "arqueologico": 1.7, "urbano": 1.4}[perfil]
            residuos = noches_totales * kg_residuo * (1 - 0.012 * t) / 1000     # toneladas
            agua = noches_totales * {"cultural": 0.31, "naturaleza": 0.38,
                                     "arqueologico": 0.34, "urbano": 0.27}[perfil]
            co2 = noches_totales * {"cultural": 11.5, "naturaleza": 14.0,
                                    "arqueologico": 16.5, "urbano": 9.5}[perfil] \
                * (1 - 0.015 * t) / 1000                                        # toneladas

            satisfaccion = np.clip(
                4.35 - 0.9 * max(0.0, presion - 0.85) + 0.012 * certificados / 10
                + rng.normal(0, 0.09), 2.8, 4.95
            )

            filas.append({
                "fecha": fecha,
                "anio": fecha.year,
                "mes": fecha.month,
                "trimestre": f"{fecha.year}-T{(fecha.month - 1) // 3 + 1}",
                "destino": nombre,
                "region": region,
                "perfil": perfil,
                "lat": lat,
                "lon": lon,
                "llegadas": round(llegadas),
                "estancia_promedio": round(noches, 2),
                "noches_totales": round(noches_totales),
                "ocupacion_hotelera": round(ocupacion, 1),
                "gasto_diario_usd": round(gasto_dia, 2),
                "gasto_total_usd": round(gasto_total, 0),
                "gasto_alojamiento_usd": round(gasto_total * reparto[0], 0),
                "gasto_alimentacion_usd": round(gasto_total * reparto[1], 0),
                "gasto_transporte_usd": round(gasto_total * reparto[2], 0),
                "gasto_actividades_usd": round(gasto_total * reparto[3], 0),
                "gasto_artesanias_usd": round(gasto_total * reparto[4], 0),
                "empleos_turisticos": round(empleos),
                "empleo_local_pct": round(empleo_local, 1),
                "empresas_certificadas_pct": round(certificados, 1),
                "residuos_ton": round(residuos, 2),
                "agua_miles_m3": round(agua / 1000, 2),
                "co2_ton": round(co2, 2),
                "capacidad_carga": carga,
                "presion_turistica": round(presion, 3),
                "satisfaccion_promedio": round(satisfaccion, 2),
            })

    return pd.DataFrame(filas)


def construir_mercados(mensual: pd.DataFrame, rng: np.random.Generator) -> pd.DataFrame:
    filas = []
    for fila in mensual.itertuples():
        base = np.array(MEZCLA_MERCADO[fila.perfil], dtype=float)
        # Europa y Canada pesan mas en temporada seca (nov-mar);
        # los mercados centroamericanos pesan mas en Semana Santa y julio.
        ajuste = np.ones(len(MERCADOS))
        if fila.mes in (11, 12, 1, 2, 3):
            ajuste[4] = 1.30   # Europa
            ajuste[5] = 1.35   # Canada
        if fila.mes in (3, 4, 7, 8):
            ajuste[1] = 1.28   # El Salvador
            ajuste[3] = 1.25   # Honduras
            ajuste[2] = 1.12   # Mexico
        mezcla = base * ajuste * rng.normal(1.0, 0.05, size=len(MERCADOS))
        mezcla = np.clip(mezcla, 0.001, None)
        mezcla = mezcla / mezcla.sum()

        for mercado, parte in zip(MERCADOS, mezcla):
            filas.append({
                "fecha": fila.fecha,
                "anio": fila.anio,
                "mes": fila.mes,
                "destino": fila.destino,
                "region": fila.region,
                "mercado": mercado,
                "llegadas": round(fila.llegadas * parte),
            })
    return pd.DataFrame(filas)


def construir_visitantes(mensual: pd.DataFrame, rng: np.random.Generator,
                         n: int = 9000) -> pd.DataFrame:
    """Encuesta a pie de destino: una fila por visitante entrevistado.

    El muestreo se concentra en 2023-2025 (los anios con operativo de campo)
    y es proporcional a las llegadas de cada destino-mes.
    """
    marco = mensual[mensual["anio"] >= 2023].reset_index(drop=True)
    pesos = marco["llegadas"].to_numpy(dtype=float)
    pesos = pesos / pesos.sum()
    idx = rng.choice(len(marco), size=n, p=pesos)

    grupos = ["Solo", "Pareja", "Familia", "Amigos", "Negocios"]
    p_grupo = {
        "cultural":     [0.18, 0.34, 0.26, 0.18, 0.04],
        "naturaleza":   [0.22, 0.30, 0.20, 0.26, 0.02],
        "arqueologico": [0.20, 0.31, 0.23, 0.23, 0.03],
        "urbano":       [0.21, 0.22, 0.22, 0.14, 0.21],
    }
    alojamientos = ["Hotel", "Hostal", "Airbnb / casa", "Ecolodge", "Casa de familiares"]
    transportes = ["Tour operador", "Vehiculo propio", "Transporte publico", "Shuttle turistico"]

    filas = []
    for k, i in enumerate(idx):
        f = marco.iloc[i]
        perfil = f["perfil"]
        mezcla = np.array(MEZCLA_MERCADO[perfil], dtype=float)
        mercado = rng.choice(MERCADOS, p=mezcla / mezcla.sum())
        grupo = rng.choice(grupos, p=p_grupo[perfil])

        edad = int(np.clip(rng.normal(41 if grupo != "Amigos" else 31, 13), 18, 79))
        noches = int(np.clip(rng.poisson(f["estancia_promedio"]) + 1, 1, 21))
        gasto_dia = float(np.clip(rng.normal(f["gasto_diario_usd"], f["gasto_diario_usd"] * 0.30), 18, None))
        alojamiento = rng.choice(
            alojamientos,
            p=[0.42, 0.16, 0.22, 0.12, 0.08] if perfil != "urbano" else [0.56, 0.08, 0.22, 0.03, 0.11],
        )
        transporte = rng.choice(transportes, p=[0.34, 0.24, 0.19, 0.23])
        anticipacion = int(np.clip(rng.gamma(2.2, 18), 0, 240))
        guia_local = int(rng.random() < (0.58 if perfil in ("arqueologico", "naturaleza") else 0.34))
        act_cultura = int(np.clip(rng.poisson(2.4 if perfil == "cultural" else 1.2), 0, 8))
        act_naturaleza = int(np.clip(rng.poisson(2.6 if perfil == "naturaleza" else 1.0), 0, 8))
        incidencias = int(rng.random() < 0.17) + int(rng.random() < 0.06)
        gasto_total = gasto_dia * noches

        # Variable latente -> promotor del destino (recomendaria el destino).
        # La calificacion observada se genera del mismo latente, por eso NO se
        # usa como predictora en los modelos (seria fuga de informacion).
        z = (
            -0.85
            + 0.55 * guia_local
            + 0.22 * act_cultura
            + 0.26 * act_naturaleza
            + 0.013 * (gasto_dia - 85)
            + 0.14 * noches
            - 0.95 * incidencias
            - 1.35 * max(0.0, f["presion_turistica"] - 0.9)
            + 0.011 * (f["empresas_certificadas_pct"] - 25)
            + (0.30 if alojamiento == "Ecolodge" else 0.0)
            + (-0.25 if grupo == "Negocios" else 0.0)
            + rng.normal(0, 0.85)
        )
        prob = 1 / (1 + np.exp(-z))
        promotor = int(rng.random() < prob)
        calificacion = int(np.clip(round(3.1 + 1.5 * prob + rng.normal(0, 0.55)), 1, 5))

        filas.append({
            "id_visitante": 100000 + k,
            "fecha": f["fecha"],
            "anio": int(f["anio"]),
            "mes": int(f["mes"]),
            "destino": f["destino"],
            "region": f["region"],
            "mercado": mercado,
            "edad": edad,
            "grupo_viaje": grupo,
            "noches": noches,
            "gasto_diario_usd": round(gasto_dia, 2),
            "gasto_total_usd": round(gasto_total, 2),
            "tipo_alojamiento": alojamiento,
            "transporte_principal": transporte,
            "anticipacion_reserva_dias": anticipacion,
            "uso_guia_local": guia_local,
            "actividades_culturales": act_cultura,
            "actividades_naturaleza": act_naturaleza,
            "incidencias_reportadas": incidencias,
            "presion_destino": round(float(f["presion_turistica"]), 3),
            "certificacion_destino_pct": round(float(f["empresas_certificadas_pct"]), 1),
            "calificacion_general": calificacion,
            "promotor": promotor,
        })

    return pd.DataFrame(filas)


def main() -> None:
    rng = np.random.default_rng(SEMILLA)
    mensual = construir_mensual(rng)
    mercados = construir_mercados(mensual, rng)
    visitantes = construir_visitantes(mensual, rng)

    CARPETA.mkdir(parents=True, exist_ok=True)
    mensual.to_csv(CARPETA / "turismo_mensual.csv", index=False)
    mercados.to_csv(CARPETA / "mercados.csv", index=False)
    visitantes.to_csv(CARPETA / "visitantes.csv", index=False)

    print(f"turismo_mensual.csv  {len(mensual):>6} filas")
    print(f"mercados.csv         {len(mercados):>6} filas")
    print(f"visitantes.csv       {len(visitantes):>6} filas")


if __name__ == "__main__":
    main()

"""
Genera una muestra sintetica de la serie mensual de viajeros, consistente con
las cifras documentadas del proyecto (Base de Migracion 2009-2026). NO son datos
institucionales: sirven para ejecutar el pipeline de punta a punta y para las
pruebas controladas de monitoreo/recuperacion.

Uso:
    python scripts/make_sample_data.py
"""
import csv
import os
import math
from datetime import date

OUT = os.path.join("data", "sample", "migracion_mensual_sample.csv")
DESTINO = "flujo_mensual_nacional"
SEED = 42

# Indice estacional mensual documentado (base 1.0)
SEAS = {1: 1.03, 2: 0.83, 3: 1.06, 4: 1.06, 5: 0.86, 6: 0.93,
        7: 1.05, 8: 1.06, 9: 0.79, 10: 0.91, 11: 1.06, 12: 1.36}


def nivel_anual(y):
    # 2.03M en 2009 creciendo 8.72%/anio hasta 4.69M en 2019
    return 2.03e6 * (1.0872 ** (y - 2009))


def viajeros_mes(y, m):
    if y <= 2019:
        mean = nivel_anual(y) / 12.0
        return mean * (1 + (SEAS[m] - 1) * 0.72)
    if y == 2020:
        crash = {1: 350000, 2: 330000, 3: 230000, 4: 40000, 5: 9779, 6: 22000,
                 7: 45000, 8: 70000, 9: 72000, 10: 95000, 11: 120000, 12: 150000}
        return crash[m]
    if y == 2021:
        rec = {1: 140000, 2: 150000, 3: 185000, 4: 195000, 5: 205000, 6: 235000,
               7: 270000, 8: 290000, 9: 250000, 10: 300000, 11: 340000, 12: 430000}
        return rec[m]
    base = 360000
    val = base * SEAS[m]
    if y == 2022 and m == 12:
        val = 526190
    if y >= 2023:
        val *= 0.753 * (1.05 if y == 2024 else (1.08 if y >= 2025 else 1.0))
    return val


def main():
    rows = []
    for y in range(2009, 2026):
        for m in range(1, 13):
            periodo = date(y, m, 1).isoformat()
            v = int(round(viajeros_mes(y, m)))
            dias = 30 if m != 2 else 28
            rows.append({
                "periodo": periodo,
                "destino": DESTINO,
                "viajeros": v,
                "dias_fuente": dias,
                "origen_fuente": "mensual",
            })
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    with open(OUT, "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=["periodo", "destino", "viajeros",
                                          "dias_fuente", "origen_fuente"])
        w.writeheader()
        w.writerows(rows)
    print(f"Muestra escrita en {OUT} ({len(rows)} filas)")


if __name__ == "__main__":
    main()

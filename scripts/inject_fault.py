"""
Prueba controlada de calidad / recuperacion.
Toma una COPIA de la muestra, le introduce un problema y la deja lista para
ejecutar el pipeline contra ella. Sirve para demostrar que los controles
detienen la publicacion y que la version aprobada sigue disponible.

Uso:
    python scripts/inject_fault.py columna_ausente
    python scripts/inject_fault.py clave_duplicada
    python scripts/inject_fault.py denominador_cero
    python scripts/inject_fault.py origen_diario   # rompe la regla metodologica
    python scripts/inject_fault.py metrica_degradada  # pasa controles, falla la regla

Luego (la copia nunca reemplaza la fuente original):
    python -m src.run_pipeline --fuente data/sample/migracion_con_falla.csv
"""
import sys
import os
import pandas as pd

SRC = "data/sample/migracion_mensual_sample.csv"
OUT = "data/sample/migracion_con_falla.csv"


def main():
    if len(sys.argv) < 2:
        print(__doc__)
        sys.exit(1)
    tipo = sys.argv[1]
    df = pd.read_csv(SRC)

    if tipo == "columna_ausente":
        df = df.drop(columns=["viajeros"])
    elif tipo == "clave_duplicada":
        df = pd.concat([df, df.iloc[[10]]], ignore_index=True)
    elif tipo == "denominador_cero":
        df.loc[5, "dias_fuente"] = 0
    elif tipo == "origen_diario":
        df.loc[20, "origen_fuente"] = "diaria_agregada"
    elif tipo == "metrica_degradada":
        # Datos validos pero erraticos en el periodo de evaluacion: los
        # controles pasan y es la regla de aceptacion la que debe rechazar.
        ev = pd.to_datetime(df["periodo"]) >= "2021-04-01"
        df.loc[ev, "viajeros"] = (df.loc[ev, "viajeros"]
                                  * [3.0 if i % 2 else 0.3 for i in range(ev.sum())]).round().astype(int)
    else:
        print(f"Tipo desconocido: {tipo}")
        sys.exit(1)

    df.to_csv(OUT, index=False)
    print(f"Falla '{tipo}' inyectada -> {OUT}")
    print(f"Ejecute: python -m src.run_pipeline --fuente {OUT}")


if __name__ == "__main__":
    main()

"""
Modelos del tablero. NO se construyen modelos nuevos para este laboratorio:
se reutilizan las familias trabajadas en los laboratorios 1 y 2 del curso
(regresion con estacionalidad, suavizamiento exponencial y SARIMA para serie
de tiempo; regresion logistica, arbol de decision y k-vecinos para
clasificacion). Aqui solo se re-entrenan sobre los datos del observatorio y se
exponen sus resultados para que el tablero los muestre.

Todo lo que sale de este modulo es ESTIMACION, no dato observado; el tablero
lo dibuja siempre en morado y con linea punteada.
"""

from __future__ import annotations

import warnings
from dataclasses import dataclass, field

import numpy as np
import pandas as pd
import streamlit as st
from sklearn.compose import ColumnTransformer
from sklearn.linear_model import LinearRegression, LogisticRegression
from sklearn.metrics import (accuracy_score, confusion_matrix, f1_score,
                             precision_score, recall_score, roc_auc_score,
                             roc_curve)
from sklearn.model_selection import learning_curve, train_test_split
from sklearn.neighbors import KNeighborsClassifier
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import OneHotEncoder, StandardScaler
from sklearn.tree import DecisionTreeClassifier

warnings.filterwarnings("ignore")

HORIZONTE = 12          # meses a pronosticar
PRUEBA = 12             # meses reservados para evaluar

MODELOS_SERIE = ["Tendencia + estacionalidad", "Suavizamiento (Holt-Winters)", "SARIMA"]
MODELOS_CLASE = ["Regresion logistica", "Arbol de decision", "K vecinos cercanos"]

EXPLICACION_SERIE = {
    "Tendencia + estacionalidad":
        "Ajusta una linea de crecimiento y un efecto fijo por mes. Es el modelo "
        "mas transparente: dice cuanto crece el destino al ano y cuanto aporta "
        "cada mes del calendario.",
    "Suavizamiento (Holt-Winters)":
        "Da mas peso a lo reciente y arrastra nivel, tendencia y patron anual. "
        "Reacciona rapido a cambios del ultimo ano.",
    "SARIMA":
        "Modela la serie a partir de su propia historia y de la del mismo mes "
        "del ano anterior. Es el unico que entrega un intervalo de confianza "
        "calculado, no aproximado.",
}

EXPLICACION_CLASE = {
    "Regresion logistica":
        "Estima la probabilidad de que el visitante recomiende el destino y "
        "muestra, con signo, cuanto suma o resta cada factor.",
    "Arbol de decision":
        "Parte a los visitantes con reglas encadenadas del tipo 'si uso guia "
        "local y se quedo 3 o mas noches...'. Es el mas facil de explicar a un "
        "equipo operativo.",
    "K vecinos cercanos":
        "Clasifica a cada visitante segun los visitantes mas parecidos a el. "
        "No asume ninguna forma funcional, pero no explica el porque.",
}

VARIABLES_CLASE_NUM = ["edad", "noches", "gasto_diario_usd",
                       "anticipacion_reserva_dias", "uso_guia_local",
                       "actividades_culturales", "actividades_naturaleza",
                       "incidencias_reportadas", "presion_destino",
                       "certificacion_destino_pct"]
VARIABLES_CLASE_CAT = ["destino", "mercado", "grupo_viaje",
                       "tipo_alojamiento", "transporte_principal"]

ETIQUETAS_VARIABLE = {
    "edad": "Edad del visitante",
    "noches": "Noches de estancia",
    "gasto_diario_usd": "Gasto diario (USD)",
    "anticipacion_reserva_dias": "Dias de anticipacion de la reserva",
    "uso_guia_local": "Uso de guia local",
    "actividades_culturales": "Actividades culturales",
    "actividades_naturaleza": "Actividades de naturaleza",
    "incidencias_reportadas": "Incidencias reportadas",
    "presion_destino": "Presion turistica del destino",
    "certificacion_destino_pct": "% de empresas certificadas",
}


# ==========================================================================
# 1. Pronostico de demanda
# ==========================================================================
@dataclass
class ResultadoSerie:
    nombre: str
    prueba: pd.DataFrame            # fecha, real, estimado
    futuro: pd.DataFrame            # fecha, estimado, inferior, superior
    metricas: dict
    ajuste: pd.DataFrame = field(default_factory=pd.DataFrame)  # fecha, estimado


def _metricas_serie(real: np.ndarray, estimado: np.ndarray) -> dict:
    err = real - estimado
    return {
        "MAE": float(np.mean(np.abs(err))),
        "RMSE": float(np.sqrt(np.mean(err ** 2))),
        "MAPE": float(np.mean(np.abs(err / real)) * 100),
    }


def _matriz_calendario(fechas: pd.Series, origen: pd.Timestamp) -> np.ndarray:
    t = ((fechas.dt.year - origen.year) * 12 + (fechas.dt.month - origen.month)).to_numpy()
    meses = pd.get_dummies(fechas.dt.month, prefix="m").reindex(
        columns=[f"m_{i}" for i in range(1, 13)], fill_value=0).to_numpy(dtype=float)
    return np.column_stack([t, meses[:, 1:]])      # enero = categoria base


@st.cache_data(show_spinner="Entrenando modelos de pronostico...")
def pronosticar(serie: pd.DataFrame) -> dict[str, ResultadoSerie]:
    """serie: columnas 'fecha' y 'llegadas', mensual y ordenada."""
    serie = serie.sort_values("fecha").reset_index(drop=True)
    entrena, valida = serie.iloc[:-PRUEBA], serie.iloc[-PRUEBA:]
    origen = serie["fecha"].iloc[0]
    futuro_fechas = pd.date_range(serie["fecha"].iloc[-1] + pd.offsets.MonthBegin(1),
                                  periods=HORIZONTE, freq="MS")
    resultados: dict[str, ResultadoSerie] = {}

    # ---- 1. Regresion lineal: tendencia + estacionalidad -----------------
    Xe = _matriz_calendario(entrena["fecha"], origen)
    Xv = _matriz_calendario(valida["fecha"], origen)
    Xt = _matriz_calendario(serie["fecha"], origen)
    Xf = _matriz_calendario(pd.Series(futuro_fechas), origen)

    lr = LinearRegression().fit(Xe, np.log(entrena["llegadas"]))
    pred_v = np.exp(lr.predict(Xv))

    lr_full = LinearRegression().fit(Xt, np.log(serie["llegadas"]))
    ajuste = np.exp(lr_full.predict(Xt))
    pred_f = np.exp(lr_full.predict(Xf))
    sigma = np.std(np.log(serie["llegadas"]) - lr_full.predict(Xt), ddof=Xt.shape[1])

    resultados["Tendencia + estacionalidad"] = ResultadoSerie(
        nombre="Tendencia + estacionalidad",
        prueba=pd.DataFrame({"fecha": valida["fecha"].values,
                             "real": valida["llegadas"].values, "estimado": pred_v}),
        futuro=pd.DataFrame({"fecha": futuro_fechas, "estimado": pred_f,
                             "inferior": pred_f * np.exp(-1.96 * sigma),
                             "superior": pred_f * np.exp(1.96 * sigma)}),
        metricas=_metricas_serie(valida["llegadas"].to_numpy(dtype=float), pred_v),
        ajuste=pd.DataFrame({"fecha": serie["fecha"], "estimado": ajuste}),
    )

    # ---- 2. Holt-Winters --------------------------------------------------
    from statsmodels.tsa.holtwinters import ExponentialSmoothing

    hw = ExponentialSmoothing(entrena["llegadas"].to_numpy(dtype=float),
                              trend="add", seasonal="add",
                              seasonal_periods=12,
                              initialization_method="estimated").fit()
    pred_v = np.asarray(hw.forecast(PRUEBA))

    hw_full = ExponentialSmoothing(serie["llegadas"].to_numpy(dtype=float),
                                   trend="add", seasonal="add",
                                   seasonal_periods=12,
                                   initialization_method="estimated").fit()
    pred_f = np.asarray(hw_full.forecast(HORIZONTE))
    res_sd = float(np.std(hw_full.resid, ddof=1))
    # el error se ensancha con el horizonte
    amplitud = 1.96 * res_sd * np.sqrt(np.arange(1, HORIZONTE + 1))

    resultados["Suavizamiento (Holt-Winters)"] = ResultadoSerie(
        nombre="Suavizamiento (Holt-Winters)",
        prueba=pd.DataFrame({"fecha": valida["fecha"].values,
                             "real": valida["llegadas"].values, "estimado": pred_v}),
        futuro=pd.DataFrame({"fecha": futuro_fechas, "estimado": pred_f,
                             "inferior": pred_f - amplitud, "superior": pred_f + amplitud}),
        metricas=_metricas_serie(valida["llegadas"].to_numpy(dtype=float), pred_v),
        ajuste=pd.DataFrame({"fecha": serie["fecha"],
                             "estimado": np.asarray(hw_full.fittedvalues)}),
    )

    # ---- 3. SARIMA --------------------------------------------------------
    from statsmodels.tsa.statespace.sarimax import SARIMAX

    orden, estacional = (1, 1, 1), (1, 1, 1, 12)
    sa = SARIMAX(np.log(entrena["llegadas"].to_numpy(dtype=float)),
                 order=orden, seasonal_order=estacional,
                 enforce_stationarity=False, enforce_invertibility=False).fit(disp=False)
    pred_v = np.exp(np.asarray(sa.forecast(PRUEBA)))

    sa_full = SARIMAX(np.log(serie["llegadas"].to_numpy(dtype=float)),
                      order=orden, seasonal_order=estacional,
                      enforce_stationarity=False, enforce_invertibility=False).fit(disp=False)
    pron = sa_full.get_forecast(HORIZONTE)
    ic = pron.conf_int(alpha=0.05)
    ic = np.asarray(ic)

    resultados["SARIMA"] = ResultadoSerie(
        nombre="SARIMA",
        prueba=pd.DataFrame({"fecha": valida["fecha"].values,
                             "real": valida["llegadas"].values, "estimado": pred_v}),
        futuro=pd.DataFrame({"fecha": futuro_fechas,
                             "estimado": np.exp(np.asarray(pron.predicted_mean)),
                             "inferior": np.exp(ic[:, 0]), "superior": np.exp(ic[:, 1])}),
        metricas=_metricas_serie(valida["llegadas"].to_numpy(dtype=float), pred_v),
        ajuste=pd.DataFrame({"fecha": serie["fecha"],
                             "estimado": np.exp(np.asarray(sa_full.fittedvalues))}),
    )
    return resultados


def tabla_serie(resultados: dict[str, ResultadoSerie]) -> pd.DataFrame:
    filas = []
    for nombre, r in resultados.items():
        filas.append({"Modelo": nombre,
                      "Error medio (visitantes)": round(r.metricas["MAE"]),
                      "RMSE": round(r.metricas["RMSE"]),
                      "Error porcentual (MAPE)": round(r.metricas["MAPE"], 2)})
    tabla = pd.DataFrame(filas).sort_values("Error porcentual (MAPE)")
    return tabla.reset_index(drop=True)


# ==========================================================================
# 2. Clasificacion: quien recomienda el destino
# ==========================================================================
@dataclass
class ResultadoClase:
    nombre: str
    matriz: np.ndarray
    metricas: dict
    roc: tuple[np.ndarray, np.ndarray]
    curva_aprendizaje: pd.DataFrame
    importancia: pd.DataFrame
    tipo_importancia: str


def _preprocesador() -> ColumnTransformer:
    return ColumnTransformer([
        ("num", StandardScaler(), VARIABLES_CLASE_NUM),
        ("cat", OneHotEncoder(handle_unknown="ignore", drop="first"), VARIABLES_CLASE_CAT),
    ])


def _nombres_variables(prep: ColumnTransformer) -> list[str]:
    nombres = [ETIQUETAS_VARIABLE.get(c, c) for c in VARIABLES_CLASE_NUM]
    oh = prep.named_transformers_["cat"]
    nombres += [n.replace("_", ": ", 1) for n in oh.get_feature_names_out(VARIABLES_CLASE_CAT)]
    return nombres


@st.cache_data(show_spinner="Entrenando modelos de clasificacion...")
def clasificar(visitantes: pd.DataFrame) -> dict[str, ResultadoClase]:
    df = visitantes.dropna(subset=VARIABLES_CLASE_NUM + VARIABLES_CLASE_CAT + ["promotor"])
    X = df[VARIABLES_CLASE_NUM + VARIABLES_CLASE_CAT]
    y = df["promotor"].astype(int)
    X_tr, X_te, y_tr, y_te = train_test_split(X, y, test_size=0.25,
                                              random_state=42, stratify=y)

    definiciones = {
        "Regresion logistica": LogisticRegression(max_iter=2000, C=1.0),
        "Arbol de decision": DecisionTreeClassifier(max_depth=5, min_samples_leaf=40,
                                                    random_state=42),
        "K vecinos cercanos": KNeighborsClassifier(n_neighbors=35, weights="distance"),
    }

    salida: dict[str, ResultadoClase] = {}
    for nombre, estimador in definiciones.items():
        tuberia = Pipeline([("prep", _preprocesador()), ("modelo", estimador)])
        tuberia.fit(X_tr, y_tr)
        pred = tuberia.predict(X_te)
        prob = tuberia.predict_proba(X_te)[:, 1]

        fpr, tpr, _ = roc_curve(y_te, prob)
        metricas = {
            "Exactitud": accuracy_score(y_te, pred),
            "Precision": precision_score(y_te, pred, zero_division=0),
            "Exhaustividad": recall_score(y_te, pred, zero_division=0),
            "F1": f1_score(y_te, pred, zero_division=0),
            "AUC": roc_auc_score(y_te, prob),
        }

        tam, punt_tr, punt_va = learning_curve(
            tuberia, X, y, cv=4, scoring="roc_auc", n_jobs=1,
            train_sizes=np.linspace(0.15, 1.0, 6), random_state=42)
        curva = pd.DataFrame({
            "tamano": tam,
            "entrenamiento": punt_tr.mean(axis=1),
            "validacion": punt_va.mean(axis=1),
            "validacion_sd": punt_va.std(axis=1),
        })

        nombres = _nombres_variables(tuberia.named_steps["prep"])
        if nombre == "Regresion logistica":
            peso = tuberia.named_steps["modelo"].coef_[0]
            tipo = "coeficiente"
        elif nombre == "Arbol de decision":
            peso = tuberia.named_steps["modelo"].feature_importances_
            tipo = "importancia"
        else:
            from sklearn.inspection import permutation_importance
            sub = X_te.sample(min(900, len(X_te)), random_state=42)
            sub_y = y_te.loc[sub.index]
            pi = permutation_importance(tuberia, sub, sub_y, n_repeats=4,
                                        random_state=42, scoring="roc_auc")
            # la permutacion se calcula sobre las columnas originales
            nombres = [ETIQUETAS_VARIABLE.get(c, c.capitalize())
                       for c in (VARIABLES_CLASE_NUM + VARIABLES_CLASE_CAT)]
            peso = pi.importances_mean
            tipo = "permutacion"

        importancia = (pd.DataFrame({"variable": nombres, "peso": peso})
                       .assign(magnitud=lambda d: d["peso"].abs())
                       .sort_values("magnitud", ascending=False)
                       .head(12).reset_index(drop=True))

        salida[nombre] = ResultadoClase(
            nombre=nombre,
            matriz=confusion_matrix(y_te, pred),
            metricas=metricas,
            roc=(fpr, tpr),
            curva_aprendizaje=curva,
            importancia=importancia,
            tipo_importancia=tipo,
        )
    return salida


def tabla_clase(resultados: dict[str, ResultadoClase]) -> pd.DataFrame:
    filas = []
    for nombre, r in resultados.items():
        fila = {"Modelo": nombre}
        fila.update({k: round(v, 3) for k, v in r.metricas.items()})
        filas.append(fila)
    return pd.DataFrame(filas).sort_values("AUC", ascending=False).reset_index(drop=True)

"""
gdp_feature_screening.py
--------------------------
Evalúa, una por una, las series candidatas a COMPLEMENTAR una
proyección: cuánto aporta cada una por encima de lo que ya se sabe.

Se usa de dos formas:

  1. COMO FILTRO (modo auto_select, caso PIB de Colombia). Hay muchas
     candidatas y pocas observaciones, así que se prueban de a una y solo
     entran al modelo las que aportan.

  2. COMO DIAGNÓSTICO (modo fixed_features, tablas de Samuel). Los
     predictores ya los definió research y entran todos. Acá el tamizaje
     no descarta nada: solo muestra qué tanto aporta cada uno.

Por qué de a una y no todas juntas
-----------------------------------
El dataset del PIB tiene ~80 observaciones trimestrales. Meterle 18
predictores a la vez no produce un modelo mejor: produce un modelo que
memoriza el pasado y falla en el futuro. Con 80 filas, la regla práctica
sana es no pasar de ~5-8 predictores en total. (En los objetivos
MENSUALES el problema es mucho menor: 240 meses aguantan sin drama los
4-9 predictores que definió Samuel por tabla, y por eso ahí el modo por
defecto es usarlos todos.)

Los filtros
------------
1. SIGNIFICANCIA: p-value del coeficiente de la candidata < 0.05 en el
   modelo aumentado, y VIF por debajo del umbral (si la candidata es casi
   una copia del predictor principal, el "aporte" es ruido de
   colinealidad).
2. BACKTEST WALK-FORWARD: la candidata REDUCE el RMSE fuera de muestra
   frente al modelo base.

CAMBIO (ago-2026, comentario de Nicolás en la reunión)
-------------------------------------------------------
"No sé por qué la descartas si el p-valor es de 0.009. Al menos debió
haber utilizado aquí la de vehículos... estas tres tienen un valor
positivo, o sea funcional."

Tenía razón en el punto de fondo: exigir los DOS filtros siempre es una
decisión de riesgo, no una verdad estadística. Un filtro de backtest
sobre 30-40 ventanas rechaza cosas que sí aportan solo porque la mejora
es pequeña y ruidosa. Ahora el criterio es un parámetro (modo):

  "estricto"      -> los dos filtros. Lo más conservador. Era el único
                     comportamiento antes.
  "significancia" -> solo p-value + VIF. Deja entrar lo que Nicolás
                     señaló.
  "diagnostico"   -> no descarta nada; la tabla es informativa.

El filtro de backtest se sigue CALCULANDO en todos los modos y se sigue
mostrando en la tabla, porque es información honesta: el precio de
exportación de petróleo pasó significancia (p=0.030 en h=3) y aun así
empeoró el backtest. Lo que cambió es que ahora esa señal se muestra en
vez de decidir en silencio.

Sobre el rezago
----------------
Cada candidata solo se prueba en los horizontes que su rezago reportado
alcanza a cubrir (ver candidatos_para_horizonte en indicator_catalog.py).
Esto reduce el número de pruebas: al 5% de significancia, unas 3-4 de 72
saldrían "significativas" por puro azar.
"""

import numpy as np
import pandas as pd
import statsmodels.api as sm
from statsmodels.stats.outliers_influence import variance_inflation_factor

from indicator_catalog import candidatos_para_horizonte

VIF_MAX = 5.0
P_MAX = 0.05
MIN_OBS = 25
MIN_TRAIN_OBS = 25

MODOS = ("estricto", "significancia", "diagnostico")


# ----------------------------------------------------------------------
# Preparación de series
# ----------------------------------------------------------------------
def preparar_candidata(manager, spec, start_date="2005-01-01", freq="Q"):
    """
    Trae una serie de CEIC y la deja en la frecuencia base del modelo con
    la transformación que declara el catálogo. Devuelve (preparada,
    cruda), o (None, cruda) si no hay datos.

    La serie CRUDA se devuelve además de la transformada porque la tabla
    de extracción tiene que mostrar TODAS las series que se descargaron,
    no solo el objetivo y el indicador principal.

    freq: "Q" o "M". Las series de mayor frecuencia (TRM y gasolina son
    diarias, la gasolina de Brasil es semanal) se promedian al período
    base — resample no distingue la frecuencia de origen.
    """
    raw = manager.fetch_series(spec["series_id"], start_date=start_date)
    if raw.empty:
        return None, raw

    base = manager.to_base_frequency(raw, freq=freq)
    transform = spec.get("transform", "yoy")

    if transform in ("already_yoy", "level"):
        # already_yoy: ya viene en % interanual desde CEIC — recalcularla
        #   sería el error que ya cometimos con el Domestic Credit.
        # level: tasas y saldos de opinión, donde el nivel ES la variable
        #   con sentido.
        return base.rename(columns={"value": "growth"})[["date", "growth"]], raw
    return manager.to_growth_rate(
        base, frequency=freq, method="yoy"
    )[["date", "growth"]], raw


# ----------------------------------------------------------------------
# Evaluación de una candidata en un horizonte
# ----------------------------------------------------------------------
def _frame_horizonte(dataset, columna_candidata, h, base_cols, target_col="gdp_growth"):
    df = dataset.sort_values("date").reset_index(drop=True).copy()
    df["target"] = df[target_col].shift(-h)
    df["gdp_growth_now"] = df[target_col]
    necesarias = ["target", columna_candidata] + [c for c in base_cols if c in df.columns]
    return df.dropna(subset=necesarias).reset_index(drop=True)


def _backtest_par(df, base_cols, aug_cols, min_train_obs=MIN_TRAIN_OBS, h=1):
    """
    Walk-forward comparando base vs aumentado, SIN fuga de información:
    el entrenamiento corta en i-h, así ninguna fila de entrenamiento
    contiene un resultado posterior a la fecha que se está prediciendo
    (mismo arreglo que en multi_horizon_forecast.backtest).
    """
    err_base, err_aug, err_naive = [], [], []
    for i in range(min_train_obs + h, len(df)):
        train, test = df.iloc[: i - h + 1], df.iloc[[i]]
        if len(train) < min_train_obs:
            continue
        real = test["target"].values[0]

        for cols, errores in ((base_cols, err_base), (aug_cols, err_aug)):
            X = sm.add_constant(train[cols])
            fit = sm.OLS(train["target"], X).fit()
            Xt = sm.add_constant(test[cols], has_constant="add")[X.columns]
            errores.append(real - fit.predict(Xt).values[0])

        err_naive.append(real - test["gdp_growth_now"].values[0])

    def rmse(e):
        return float(np.sqrt(np.mean(np.square(e)))) if e else float("nan")

    return rmse(err_base), rmse(err_aug), rmse(err_naive), len(err_base)


def evaluar_candidata(dataset, columna_candidata, h, etiqueta,
                       base_cols=None, modo="estricto", target_col="gdp_growth"):
    """
    Corre los filtros para una candidata en un horizonte.

    base_cols: el modelo contra el que se compara. En el caso PIB es
    [indicador principal + PIB rezagado]; en fixed_features no hay
    "indicador principal", así que la base es solo el objetivo rezagado.
    """
    base_cols = list(base_cols or ["indicator_growth", "gdp_growth_now"])
    df = _frame_horizonte(dataset, columna_candidata, h, base_cols, target_col=target_col)
    base_cols = [c for c in base_cols if c in df.columns]
    aug_cols = base_cols + [columna_candidata]

    fila = {"candidata": etiqueta, "columna": columna_candidata,
            "horizonte": h, "n_obs": len(df)}

    if len(df) < MIN_OBS or not base_cols:
        return {**fila, "estado": "datos insuficientes", "pasa": False}

    X_aug = sm.add_constant(df[aug_cols])
    aug = sm.OLS(df["target"], X_aug).fit()
    base = sm.OLS(df["target"], sm.add_constant(df[base_cols])).fit()

    p = float(aug.pvalues[columna_candidata])
    vif = float(variance_inflation_factor(
        X_aug.values, list(X_aug.columns).index(columna_candidata)
    ))

    rmse_base, rmse_aug, rmse_naive, n_folds = _backtest_par(df, base_cols, aug_cols, h=h)
    mejora = 100 * (rmse_base - rmse_aug) / rmse_base if rmse_base else np.nan

    pasa_sig = (p < P_MAX) and (vif < VIF_MAX)
    pasa_bt = bool(rmse_aug < rmse_base)

    if modo == "diagnostico":
        pasa = True                      # no descarta: informa
    elif modo == "significancia":
        pasa = bool(pasa_sig)
    else:
        pasa = bool(pasa_sig and pasa_bt)

    return {
        **fila,
        "r2_adj_base": round(float(base.rsquared_adj), 4),
        "r2_adj_aumentado": round(float(aug.rsquared_adj), 4),
        "coeficiente": round(float(aug.params[columna_candidata]), 4),
        "p_value": round(p, 4),
        "vif": round(vif, 2),
        "n_folds": n_folds,
        "rmse_base": round(rmse_base, 4),
        "rmse_aumentado": round(rmse_aug, 4),
        "rmse_naive": round(rmse_naive, 4),
        "mejora_rmse_%": round(mejora, 2),
        "pasa_significancia": pasa_sig,
        "pasa_backtest": pasa_bt,
        "pasa": pasa,
        "estado": "ok",
    }


# ----------------------------------------------------------------------
# Corrida completa
# ----------------------------------------------------------------------
def tamizar_candidatas(manager, target_config, gdp_growth, ise_growth,
                        start_date="2005-01-01", progress=None,
                        modo="estricto", max_por_horizonte=3):
    """
    Descarga cada candidata, la evalúa en los horizontes que le
    corresponden por rezago, y devuelve (resultados, seleccion, series,
    crudas).

    resultados: DataFrame con una fila por (candidata, horizonte)
    seleccion:  dict {horizonte: [columnas que pasaron]}
    series:     dict {columna: DataFrame [date, growth]} ya preparadas
    crudas:     dict {slug: DataFrame crudo} para la tabla de extracción

    modo: "estricto" | "significancia" | "diagnostico" (ver el docstring
    del módulo). max_por_horizonte acota cuántas entran al modelo final.
    """
    def report(msg):
        if progress:
            progress(msg)

    freq = target_config.get("base_frequency", "Q")
    horizontes = target_config.get("horizons", [1, 2, 3, 4])
    candidatas = target_config.get("candidate_features", [])

    # Qué horizontes le tocan a cada candidata, según su rezago.
    por_slug = {}
    for h in horizontes:
        for spec in candidatos_para_horizonte(target_config, h):
            por_slug.setdefault(spec["slug"], {"spec": spec, "horizontes": []})
            por_slug[spec["slug"]]["horizontes"].append(h)

    resultados, series, crudas = [], {}, {}

    # Nicolás pidió acortar el cuadro de pasos: antes salía una línea por
    # serie ("Evaluando cartera al consumidor...", 18 veces). Ahora sale
    # una sola línea con el total.
    report(f"Evaluando {len(por_slug)} series adicionales de a una.")

    for slug, info in por_slug.items():
        spec = info["spec"]
        try:
            preparada, cruda = preparar_candidata(manager, spec,
                                                   start_date=start_date, freq=freq)
            if cruda is not None and not cruda.empty:
                crudas[slug] = cruda
        except Exception as e:
            resultados.append({"candidata": spec["label"], "columna": f"{slug}_growth",
                                "horizonte": None, "estado": f"error: {e}", "pasa": False})
            continue

        if preparada is None or preparada.empty:
            resultados.append({"candidata": spec["label"], "columna": f"{slug}_growth",
                                "horizonte": None, "estado": "sin datos", "pasa": False})
            continue

        series[f"{slug}_growth"] = preparada
        dataset = manager.build_model_dataset(
            gdp_growth, {"indicator": ise_growth, slug: preparada}, freq=freq
        )
        columna = f"{slug}_growth"
        if columna not in dataset.columns:
            continue

        for h in info["horizontes"]:
            fila = evaluar_candidata(dataset, columna, h, spec["label"], modo=modo)
            fila["bloque"] = spec.get("bloque", "")
            fila["lag_meses"] = spec.get("lag_meses")
            # Cuántos períodos quedan al cruzar con el objetivo: es la
            # explicación de las filas que salen "datos insuficientes".
            fila["periodos_utiles"] = len(dataset)
            resultados.append(fila)

    df = pd.DataFrame(resultados)

    seleccion = {}
    if not df.empty and "pasa" in df.columns:
        aprobadas = df[df["pasa"] == True]  # noqa: E712
        for h in horizontes:
            # Si varias pasan en el mismo horizonte, se ordenan por
            # mejora de backtest y se limita: con ~80 observaciones,
            # principal + objetivo rezagado + 3 extra ya son 5 predictores.
            del_h = aprobadas[aprobadas["horizonte"] == h].sort_values(
                "mejora_rmse_%", ascending=False
            )
            seleccion[h] = del_h["columna"].head(max_por_horizonte).tolist()

    n_pasan = len({c for cols in seleccion.values() for c in cols})
    report(f"{n_pasan} de {len(por_slug)} series entran al modelo final.")

    return df, seleccion, series, crudas


def diagnostico_fijas(dataset, especificaciones, horizontes, target_col="gdp_growth",
                       progress=None):
    """
    Aporte individual de cada predictor FIJO, para el modo
    fixed_features.

    A diferencia de tamizar_candidatas, acá no se descarta nada: todas
    las series que definió research entran al modelo. Esta tabla existe
    para responder la pregunta que hizo Nicolás mirando la pantalla —
    "¿cuáles de estas de verdad están aportando?" — sin que la respuesta
    cambie qué se ajusta.

    La comparación es contra el modelo más simple posible (solo el
    objetivo rezagado), que es la referencia que un cliente entiende:
    "¿esta serie agrega algo por encima de mirar el propio indicador?".
    """
    def report(msg):
        if progress:
            progress(msg)

    filas = []
    base_cols = ["gdp_growth_now"]
    report(f"Midiendo el aporte individual de {len(especificaciones)} series.")

    for spec in especificaciones:
        columna = f"{spec['slug']}_growth"
        if columna not in dataset.columns:
            continue
        for h in horizontes:
            fila = evaluar_candidata(dataset, columna, h, spec["label"],
                                      base_cols=base_cols, modo="diagnostico",
                                      target_col=target_col)
            fila["bloque"] = spec.get("bloque", "")
            fila["lag_meses"] = spec.get("lag_meses")
            filas.append(fila)

    return pd.DataFrame(filas)


def resumen_para_cliente(resultados):
    """Tabla corta y legible para el detalle técnico del dashboard."""
    if resultados.empty:
        return resultados
    cols = ["bloque", "candidata", "horizonte", "n_obs", "p_value", "mejora_rmse_%",
            "pasa_significancia", "pasa_backtest", "pasa", "estado"]
    cols = [c for c in cols if c in resultados.columns]
    out = resultados[cols].copy()
    orden = [c for c in ("pasa", "mejora_rmse_%") if c in out.columns]
    if not orden:
        return out
    return out.sort_values(orden, ascending=[False] * len(orden))

"""
gdp_feature_screening.py
--------------------------
Evalúa, una por una, las series que mandó Samuel como candidatas a
COMPLEMENTAR el pronóstico del PIB (lo que pidió Nicolás).

Por qué de a una y no todas juntas
-----------------------------------
El dataset del PIB tiene ~80 observaciones trimestrales. Meterle 18
predictores a la vez no produce un modelo mejor: produce un modelo que
memoriza el pasado y falla en el futuro. Con 80 filas, la regla práctica
sana es no pasar de ~5-8 predictores en total. Así que cada candidata se
prueba contra el modelo base (ISE + PIB rezagado) y solo sobreviven las
que aportan de verdad.

Los dos filtros (hay que pasar los DOS)
----------------------------------------
1. SIGNIFICANCIA: p-value del coeficiente de la candidata < 0.05 en el
   modelo aumentado, y VIF por debajo del umbral (si la candidata es casi
   una copia del ISE, el "aporte" es ruido de colinealidad).
2. BACKTEST WALK-FORWARD: la candidata tiene que REDUCIR el RMSE fuera de
   muestra frente al modelo base. Este es el filtro que de verdad manda.

El segundo existe porque ya nos pasó: el precio de exportación de petróleo
pasó la prueba de significancia (p=0.030 en h=3, p=0.011 en h=4) y aun así
no mejoró el backtest. Significancia dentro de muestra y capacidad
predictiva fuera de muestra no son lo mismo, y solo la segunda es lo que
se le promete a un cliente.

Sobre el rezago
----------------
Cada candidata solo se prueba en los horizontes que su rezago reportado
alcanza a cubrir (ver candidatos_para_horizonte en indicator_catalog.py).
Esto no es solo fidelidad al análisis de Samuel: reduce el número de
pruebas. Probando 18 candidatas en 4 horizontes son 72 pruebas, y al 5%
de significancia unas 3-4 saldrían "significativas" por puro azar.
Restringiendo por rezago bajan a ~34, y el filtro de backtest se lleva
casi todos los falsos positivos que queden.
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


# ----------------------------------------------------------------------
# Preparación de series
# ----------------------------------------------------------------------
def preparar_candidata(manager, spec, start_date="2005-01-01"):
    """
    Trae una serie de CEIC y la deja en frecuencia trimestral con la
    transformación que declara el catálogo. Devuelve (preparada, cruda),
    o (None, cruda) si no hay datos.

    La serie CRUDA se devuelve además de la transformada porque la tabla
    de extracción que pidió Nicolás tiene que mostrar las 18 series que se
    descargaron, no solo el objetivo y el indicador principal.

    Las series diarias (TRM, gasolina, Brent...) se promedian al trimestre
    igual que las mensuales: resample("QE") no distingue la frecuencia de
    origen.
    """
    raw = manager.fetch_series(spec["series_id"], start_date=start_date)
    if raw.empty:
        return None, raw

    trimestral = manager.monthly_to_quarterly(raw)
    transform = spec.get("transform", "yoy")

    if transform in ("already_yoy", "level"):
        # already_yoy: ya viene en % interanual desde CEIC — recalcularla
        #   sería el error que ya cometimos con el Domestic Credit.
        # level: tasas y saldos de opinión, donde el nivel ES la variable
        #   con sentido.
        return trimestral.rename(columns={"value": "growth"})[["date", "growth"]], raw
    return manager.to_growth_rate(
        trimestral, frequency="Q", method="yoy"
    )[["date", "growth"]], raw


# ----------------------------------------------------------------------
# Evaluación de una candidata en un horizonte
# ----------------------------------------------------------------------
def _frame_horizonte(dataset, columna_candidata, h, target_col="gdp_growth"):
    df = dataset.sort_values("date").reset_index(drop=True).copy()
    df["target"] = df[target_col].shift(-h)
    df["gdp_growth_now"] = df[target_col]
    return df.dropna(
        subset=["target", "indicator_growth", columna_candidata, "gdp_growth_now"]
    ).reset_index(drop=True)


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


def evaluar_candidata(dataset, columna_candidata, h, etiqueta):
    """Corre los dos filtros para una candidata en un horizonte."""
    df = _frame_horizonte(dataset, columna_candidata, h)
    base_cols = ["indicator_growth", "gdp_growth_now"]
    aug_cols = base_cols + [columna_candidata]

    fila = {"candidata": etiqueta, "columna": columna_candidata,
            "horizonte": h, "n_obs": len(df)}

    if len(df) < MIN_OBS:
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
        "pasa": bool(pasa_sig and pasa_bt),
        "estado": "ok",
    }


# ----------------------------------------------------------------------
# Corrida completa
# ----------------------------------------------------------------------
def tamizar_candidatas(manager, target_config, gdp_growth, ise_growth,
                        start_date="2005-01-01", progress=None):
    """
    Descarga cada candidata, la evalúa en los horizontes que le
    corresponden por rezago, y devuelve (resultados, seleccion, series).

    resultados: DataFrame con una fila por (candidata, horizonte)
    seleccion:  dict {horizonte: [columnas que pasaron]} — lo que el
                modelo final debería usar además del ISE
    series:     dict {columna: DataFrame [date, growth]} ya preparadas
    crudas:     dict {slug: DataFrame crudo} para la tabla de extracción
    """
    def report(msg):
        if progress:
            progress(msg)

    horizontes = target_config.get("horizons", [1, 2, 3, 4])
    candidatas = target_config.get("candidate_features", [])

    # Qué horizontes le tocan a cada candidata, según su rezago.
    por_slug = {}
    for h in horizontes:
        for spec in candidatos_para_horizonte(target_config, h):
            por_slug.setdefault(spec["slug"], {"spec": spec, "horizontes": []})
            por_slug[spec["slug"]]["horizontes"].append(h)

    resultados, series, crudas = [], {}, {}

    for slug, info in por_slug.items():
        spec = info["spec"]
        report(f"Evaluando {spec['label']}...")
        try:
            preparada, cruda = preparar_candidata(manager, spec, start_date=start_date)
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
            gdp_growth, {"indicator": ise_growth, slug: preparada}
        )
        columna = f"{slug}_growth"
        if columna not in dataset.columns:
            continue

        for h in info["horizontes"]:
            fila = evaluar_candidata(dataset, columna, h, spec["label"])
            fila["bloque"] = spec.get("bloque", "")
            fila["lag_meses"] = spec.get("lag_meses")
            # Cuántos trimestres quedan al cruzar con el PIB: es la
            # explicación de las filas que salen "datos insuficientes".
            fila["trimestres_utiles"] = len(dataset)
            resultados.append(fila)

    df = pd.DataFrame(resultados)

    seleccion = {}
    if not df.empty and "pasa" in df.columns:
        aprobadas = df[df["pasa"] == True]  # noqa: E712
        for h in horizontes:
            # Si varias pasan en el mismo horizonte, se ordenan por
            # mejora de backtest y se limita a 3: con ~80 observaciones,
            # ISE + PIB rezagado + 3 extra ya son 5 predictores.
            del_h = aprobadas[aprobadas["horizonte"] == h].sort_values(
                "mejora_rmse_%", ascending=False
            )
            seleccion[h] = del_h["columna"].head(3).tolist()

    return df, seleccion, series, crudas


def resumen_para_cliente(resultados):
    """Tabla corta y legible para el detalle técnico del dashboard."""
    if resultados.empty:
        return resultados
    cols = ["bloque", "candidata", "horizonte", "n_obs", "p_value", "mejora_rmse_%",
            "pasa_significancia", "pasa_backtest", "pasa", "estado"]
    cols = [c for c in cols if c in resultados.columns]
    out = resultados[cols].copy()
    return out.sort_values(["pasa", "mejora_rmse_%"], ascending=[False, False])

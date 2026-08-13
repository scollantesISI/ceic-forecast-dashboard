"""
nowcast_pipeline.py
---------------------
Nowcast del trimestre EN CURSO del PIB: estimar cuánto va a dar el
trimestre antes de que el DANE publique el dato oficial, usando los meses
de ISE que ya salieron.

Por qué este caso y no la proyección hacia adelante
----------------------------------------------------
Los diagnósticos con datos reales fueron claros: proyectar el PIB hacia
adelante desde el ISE no funciona. La correlación entre ambos es 0.9955,
así que el ISE no aporta información nueva sobre el PIB — y a un
trimestre vista ninguna especificación le gana de forma relevante a
simplemente repetir el crecimiento actual.

Pero esa misma correlación, aplicada a la pregunta correcta, da otra
cosa. Con walk-forward sobre 49 trimestres reales:

    1 mes de ISE  -> error típico 1.51 pp  (63% mejor que el último PIB)
    2 meses       -> error típico 1.01 pp  (76% mejor)
    3 meses       -> error típico 0.43 pp  (90% mejor)

Eso no es un pronóstico: es leer un dato antes que el mercado.

LA ADVERTENCIA IMPORTANTE
--------------------------
El valor de esto NO es la precisión sola: es la precisión MULTIPLICADA
por cuánto tiempo se gana. Y ahí hay un riesgo real: el ISE del tercer
mes del trimestre y el PIB de ese trimestre se publican casi al mismo
tiempo. Si eso es así, la fila de 3 meses —la más precisa— podría no
tener ninguna ventaja de calendario, y el número presentable sería el de
2 meses.

Por eso este módulo calcula la ventaja de calendario contra los datos
reales (ventaja_de_calendario) en vez de suponerla, y la app la muestra
al lado de la precisión. Un error de 0.43 pp sin ventaja de tiempo no
vale nada; uno de 1.01 pp con un mes de ventaja es un producto.

OTRA ADVERTENCIA, MENOR PERO REAL
----------------------------------
El backtest usa la serie de PIB tal como está HOY, ya revisada. En el
momento real solo existía la primera estimación, que después se corrige.
Es lo que en la literatura se llama backtest "pseudo tiempo real": tiende
a salir algo mejor que la operación real. No invalida el resultado —es
la práctica estándar— pero conviene decirlo antes de que lo pregunten.
"""

import numpy as np
import pandas as pd
import statsmodels.api as sm

from gdp_data_manager import GDPForecastDataManager, resumen_extraccion

MESES_A_PROBAR = (1, 2, 3)
MIN_TRAIN = 30
PIB_LAG = 1   # trimestres de rezago en la publicación del PIB


# ----------------------------------------------------------------------
# Series
# ----------------------------------------------------------------------
def _serie_pib(mgr, series_id, start_date):
    raw = mgr.fetch_series(series_id, start_date=start_date)
    if raw.empty:
        raise ValueError("La serie de PIB no devolvió datos.")
    crecimiento = mgr.to_growth_rate(raw, frequency="Q", method="yoy")
    serie = crecimiento.set_index(
        pd.PeriodIndex(crecimiento["date"], freq="Q")
    )["growth"].sort_index()
    return serie.rename("pib"), raw


def _ise_parcial(mgr, series_id, meses, start_date):
    """
    Crecimiento interanual del indicador mensual usando solo los primeros
    `meses` meses de cada trimestre.

    La comparación interanual es contra los MISMOS meses del año anterior
    (enero-febrero contra enero-febrero). Compararlo contra el trimestre
    completo del año pasado mezclaría información parcial con completa y
    el resultado saldría mejor de lo que realmente es.
    """
    raw = mgr.fetch_series(series_id, start_date=start_date)
    if raw.empty:
        raise ValueError("La serie mensual no devolvió datos.")

    df = raw[["date", "value"]].copy()
    df["trimestre"] = pd.PeriodIndex(df["date"], freq="Q")
    df["mes_del_trimestre"] = df.groupby("trimestre").cumcount() + 1

    recorte = df[df["mes_del_trimestre"] <= meses]
    parcial = recorte.groupby("trimestre")["value"].mean().sort_index()
    disponibles = recorte.groupby("trimestre").size()
    parcial = parcial[disponibles >= meses]

    return (parcial.pct_change(4) * 100).dropna().rename("indicador"), raw


# ----------------------------------------------------------------------
# Ventaja de calendario — lo que decide si el número sirve
# ----------------------------------------------------------------------
def ventaja_de_calendario(pib, raw_mensual):
    """
    Con los datos tal como están hoy: ¿cuántos meses del trimestre más
    reciente sin PIB publicado ya tienen dato mensual?

    Si el indicador mensual cubre meses de un trimestre cuyo PIB todavía
    no existe, esa es la ventaja real y medible. Si no cubre ninguno, el
    nowcast no le gana al calendario y hay que decirlo.
    """
    ultimo_pib = pib.index.max()
    fechas = pd.PeriodIndex(raw_mensual["date"], freq="Q")
    ultimo_mes = pd.Period(raw_mensual["date"].max(), freq="M")

    pendientes = sorted({q for q in fechas if q > ultimo_pib})
    if not pendientes:
        return {
            "trimestre_objetivo": None,
            "meses_disponibles": 0,
            "ultimo_pib_publicado": str(ultimo_pib),
            "ultimo_mes_indicador": str(ultimo_mes),
            "hay_ventaja": False,
            "mensaje": (
                f"El indicador mensual llega hasta {ultimo_mes} y el PIB hasta "
                f"{ultimo_pib}: no hay ningún trimestre con datos mensuales "
                "publicados y PIB pendiente. Sin ventaja de calendario, el "
                "nowcast no anticipa nada."
            ),
        }

    objetivo = pendientes[0]
    meses = int((fechas == objetivo).sum())
    return {
        "trimestre_objetivo": str(objetivo),
        "meses_disponibles": meses,
        "ultimo_pib_publicado": str(ultimo_pib),
        "ultimo_mes_indicador": str(ultimo_mes),
        "hay_ventaja": True,
        "mensaje": (
            f"Hoy hay {meses} mes(es) del {objetivo} ya publicados, y el PIB de "
            f"ese trimestre todavía no sale (el último es {ultimo_pib}). Esa es "
            "la ventaja: el número se puede estimar antes que el dato oficial."
        ),
    }


# ----------------------------------------------------------------------
# Evaluación walk-forward
# ----------------------------------------------------------------------
def evaluar(pib, indicador, meses, pib_lag=PIB_LAG, min_train=MIN_TRAIN):
    """
    Para cada trimestre t se entrena solo con trimestres cuyo PIB ya
    estaba publicado en ese momento (hasta t - pib_lag), y se estima el
    PIB de t con el indicador parcial de t.
    """
    df = pd.concat([pib, indicador], axis=1).dropna()
    df["pib_publicado"] = df["pib"].shift(pib_lag)
    df = df.dropna()

    registros = []
    for i in range(min_train + pib_lag, len(df)):
        entrena, prueba = df.iloc[: i - pib_lag + 1], df.iloc[[i]]
        if len(entrena) < min_train:
            continue
        X = sm.add_constant(entrena[["indicador"]])
        ajuste = sm.OLS(entrena["pib"], X).fit()
        Xt = sm.add_constant(prueba[["indicador"]], has_constant="add")[X.columns]
        registros.append({
            "trimestre": str(prueba.index[0]),
            "real": float(prueba["pib"].iloc[0]),
            "nowcast": float(ajuste.predict(Xt).iloc[0]),
            "ultimo_pib_publicado": float(prueba["pib_publicado"].iloc[0]),
            "promedio_historico": float(entrena["pib"].mean()),
        })

    res = pd.DataFrame(registros)
    if res.empty:
        return None, res, None

    def rmse(col, frame=res):
        return float(np.sqrt(((frame["real"] - frame[col]) ** 2).mean()))

    X_full = sm.add_constant(df[["indicador"]])
    ajuste_full = sm.OLS(df["pib"], X_full).fit()

    r_modelo, r_persist, r_media = rmse("nowcast"), rmse("ultimo_pib_publicado"), rmse("promedio_historico")
    duro = min(r_persist, r_media)

    # Sin 2020: covid domina cualquier RMSE y no representa la operación
    # normal, que es donde el cliente va a usar esto.
    limpio = res[~res["trimestre"].str.startswith("2020")]
    rmse_sin_covid = rmse("nowcast", limpio) if not limpio.empty else np.nan
    duro_sin_covid = min(rmse("ultimo_pib_publicado", limpio),
                          rmse("promedio_historico", limpio)) if not limpio.empty else np.nan

    resumen = {
        "meses_de_indicador": meses,
        "n_trimestres": len(res),
        "r2_ajustado": round(float(ajuste_full.rsquared_adj), 3),
        "p_value": float(ajuste_full.pvalues["indicador"]),
        "rmse": round(r_modelo, 3),
        "mae": round(float((res["real"] - res["nowcast"]).abs().mean()), 3),
        "rmse_sin_covid": round(rmse_sin_covid, 3),
        "rmse_ultimo_pib": round(r_persist, 3),
        "rmse_promedio": round(r_media, 3),
        "rmse_rival_mas_duro": round(duro, 3),
        "rival_mas_duro": "último PIB publicado" if r_persist <= r_media else "promedio histórico",
        "mejora_%": round(100 * (duro - r_modelo) / duro, 1),
        "mejora_sin_covid_%": round(100 * (duro_sin_covid - rmse_sin_covid) / duro_sin_covid, 1)
                               if duro_sin_covid == duro_sin_covid else np.nan,
        "le_gana": bool(r_modelo < duro),
    }
    return resumen, res, ajuste_full


# ----------------------------------------------------------------------
# Corrida completa
# ----------------------------------------------------------------------
def run_nowcast(ceic_client, target_config, start_date="2005-01-01",
                 progress_callback=None):
    def report(msg):
        if progress_callback:
            progress_callback(msg)

    mgr = GDPForecastDataManager(ceic_client, country_id=target_config["country_id"])
    objetivo = target_config["target"]
    mensual = target_config["indicador_mensual"]

    report(f"Trayendo {objetivo['label']}...")
    pib, pib_raw = _serie_pib(mgr, objetivo["series_id"], start_date)

    resumenes, detalles, ajustes, ise_raw = [], {}, {}, None
    for meses in target_config.get("meses_a_probar", MESES_A_PROBAR):
        report(f"Evaluando con {meses} mes(es) de {mensual['label']}...")
        indicador, ise_raw = _ise_parcial(mgr, mensual["series_id"], meses, start_date)
        resumen, res, ajuste = evaluar(pib, indicador, meses)
        if resumen is None:
            continue
        resumenes.append(resumen)
        detalles[meses] = res
        ajustes[meses] = (ajuste, indicador)

    if not resumenes:
        raise ValueError("No hubo trimestres suficientes para evaluar el nowcast.")

    tabla = pd.DataFrame(resumenes)
    calendario = ventaja_de_calendario(pib, ise_raw)

    # Estimación viva del trimestre pendiente, con los meses que de verdad
    # hay hoy. Si no hay ventaja de calendario, no se produce número.
    estimacion = None
    m_hoy = calendario["meses_disponibles"]
    if calendario["hay_ventaja"] and m_hoy in ajustes:
        ajuste, indicador = ajustes[m_hoy]
        objetivo_q = pd.Period(calendario["trimestre_objetivo"], freq="Q")
        if objetivo_q in indicador.index:
            x = float(indicador.loc[objetivo_q])
            X = sm.add_constant(pd.DataFrame({"indicador": [x]}), has_constant="add")
            pred = ajuste.get_prediction(X[ajuste.params.index]).summary_frame(alpha=0.05)
            fila = tabla[tabla["meses_de_indicador"] == m_hoy].iloc[0]
            estimacion = {
                "trimestre": calendario["trimestre_objetivo"],
                "meses_usados": m_hoy,
                "nowcast": float(pred["mean"].iloc[0]),
                "ci_95_lower": float(pred["obs_ci_lower"].iloc[0]),
                "ci_95_upper": float(pred["obs_ci_upper"].iloc[0]),
                "error_tipico": float(fila["rmse"]),
                "ultimo_pib": float(pib.iloc[-1]),
                "trimestre_ultimo_pib": str(pib.index.max()),
            }

    etiquetas = {"pib": objetivo["label"], "mensual": mensual["label"]}
    ids = {"pib": objetivo["series_id"], "mensual": mensual["series_id"]}

    return {
        "modo": "nowcast",
        "tabla_precision": tabla,
        "detalles": detalles,
        "calendario": calendario,
        "estimacion": estimacion,
        "pib": pib,
        "tabla_extraccion": resumen_extraccion(
            {"pib": pib_raw, "mensual": ise_raw}, etiquetas, ids
        ),
        "dataset": detalles[max(detalles)],
        "label_objetivo": objetivo["label"],
        "label_indicador": mensual["label"],
    }

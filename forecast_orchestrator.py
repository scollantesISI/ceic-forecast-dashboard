"""
forecast_orchestrator.py
--------------------------
Conecta indicator_catalog + gdp_data_manager + multi_horizon_forecast +
gdp_feature_screening para que el flujo completo sea: el usuario elige
QUÉ proyectar ("PIB de Colombia"), y el backend decide CÓMO — qué serie
oficial usar como objetivo, cuál indicador de alta frecuencia lleva el
peso, y cuáles de las series adicionales de Samuel aportan de verdad.

Nada de esto le muestra un series_id al usuario en el flujo principal.
Sí quedan visibles en el detalle técnico, que es justamente lo que pidió
Nicolás: mostrar el proceso de extracción, no esconderlo.

CAMBIO (ago-2026): el caso macro pasó de un modelo de UN período
(GDPBridgeModel) a MultiHorizonForecaster, porque Nicolás pidió al menos
4 trimestres hacia adelante. Ahora todos los casos usan el mismo motor,
el mismo fan chart y el mismo backtest sin fuga.

CAMBIO (ago-2026, reunión con Nicolás y Samuel): se agrega el modo
fixed_features. Cada tabla que mandó Samuel es un modelo propio —su
título es el objetivo y las series de abajo son SUS predictores— y en
ese modo entran todos al modelo en vez de pasar por el tamizaje. Es la
respuesta directa a los dos comentarios de la reunión: "esas series no
eran para pronosticar PIB" y "no sé por qué la descartas si el p-valor
es de 0.009".
"""

import numpy as np
import pandas as pd
import statsmodels.api as sm
from statsmodels.stats.outliers_influence import variance_inflation_factor

from gdp_data_manager import (GDPForecastDataManager, resumen_extraccion,
                               series_largas)
from multi_horizon_forecast import MultiHorizonForecaster
from gdp_feature_screening import (tamizar_candidatas, resumen_para_cliente,
                                    preparar_candidata, diagnostico_fijas)

# Un horizonte, en kwargs de pd.DateOffset, según la frecuencia base.
PASO_POR_FRECUENCIA = {"Q": {"months": 3}, "M": {"months": 1}, "W": {"weeks": 1}}

# Mínimos de muestra por frecuencia: 25 trimestres son ~6 años, pero 25
# meses son 2 — con datos mensuales hay que exigir bastante más antes de
# creerle a un backtest.
MIN_TRAIN_POR_FRECUENCIA = {"Q": 25, "M": 60, "W": 104}
MIN_OBS_POR_FRECUENCIA = {"Q": 15, "M": 36, "W": 52}


def run_forecast(ceic_client, target_config, **kwargs):
    """
    Punto de entrada único del dashboard. Decide el camino según el
    "mode" de la entrada del catálogo:

      nowcast       -> estimar el trimestre EN CURSO antes de que se
                       publique el dato oficial
                       ->  nowcast_pipeline.run_nowcast
      auto_select   -> caso macro (PIB): elegir el indicador principal
                       entre candidatos y tamizar las series adicionales
                       ->  run_auto_forecast (abajo)
      fixed_features-> las tablas de Samuel (inflación, vehículos,
                       exportaciones — Colombia y Brasil): objetivo y
                       predictores ya definidos, todos entran al modelo
                       ->  run_fixed_forecast (abajo)
      multi_feature -> caso commodity (acero en China): usar los
                       independientes que ya definió Nicolás, alineando
                       series de distinta frecuencia a grilla semanal
                       ->  steel_pipeline.run_steel_forecast

    La app solo llama a esta función; agregar un caso nuevo no la obliga
    a cambiar.
    """
    mode = target_config.get("mode", "auto_select")
    if mode == "nowcast":
        from nowcast_pipeline import run_nowcast  # import perezoso
        allowed = {"start_date", "progress_callback"}
        return run_nowcast(ceic_client, target_config,
                            **{k: v for k, v in kwargs.items() if k in allowed})
    if mode == "fixed_features":
        allowed = {"start_date", "progress_callback", "vif_max", "usar_diagnostico"}
        return run_fixed_forecast(ceic_client, target_config,
                                   **{k: v for k, v in kwargs.items() if k in allowed})
    if mode == "multi_feature":
        from steel_pipeline import run_steel_forecast  # import perezoso
        allowed = {"start_date", "max_horizon", "min_train_obs", "progress_callback"}
        return run_steel_forecast(ceic_client, target_config,
                                   **{k: v for k, v in kwargs.items() if k in allowed})
    allowed = {"start_date", "min_candidate_obs", "early_stop_r2",
               "usar_series_adicionales", "progress_callback", "modo_tamizaje"}
    return run_auto_forecast(ceic_client, target_config,
                              **{k: v for k, v in kwargs.items() if k in allowed})


def _filtrar_colineales(dataset, columnas, vif_max=10.0):
    """
    Saca predictores que son casi copias de otro, de a uno, empezando por
    el peor. Devuelve (columnas_que_quedan, descartadas).

    Existe por el PIB de Brasil: seis indicadores mensuales de actividad
    (actividad económica, producción industrial, ventas industriales,
    retail, electricidad) que se mueven prácticamente igual. Meterlos
    todos no agrega información, agrega inestabilidad — es el mismo
    fenómeno del ISE y el PIB, con VIF de 112 y coeficientes que se
    daban vuelta. Nicolás lo dijo mirando la pantalla: "estas dos siguen
    una tendencia muy similar, entonces terminan explicándose la una a
    la otra".

    El umbral es 10, no el 5 del tamizaje: acá no se está decidiendo si
    una serie aporta, solo se está evitando una matriz mal condicionada.
    Se conserva SIEMPRE al menos un predictor.
    """
    cols = [c for c in columnas if c in dataset.columns]
    descartadas = []
    while len(cols) > 1:
        X = sm.add_constant(dataset[cols].dropna())
        if len(X) <= len(cols) + 1:
            break
        try:
            vifs = {c: variance_inflation_factor(X.values, list(X.columns).index(c))
                    for c in cols}
        except Exception:
            break
        peor = max(vifs, key=vifs.get)
        if not np.isfinite(vifs[peor]) or vifs[peor] <= vif_max:
            break
        descartadas.append({"columna": peor, "vif": round(float(vifs[peor]), 1)})
        cols = [c for c in cols if c != peor]
    return cols, descartadas


def run_fixed_forecast(ceic_client, target_config, start_date="2005-01-01",
                        progress_callback=None, vif_max=10.0,
                        usar_diagnostico=True):
    """
    Un modelo por cada tabla de Samuel: el título de la tabla es el
    objetivo y las series de abajo son sus predictores.

    Diferencias con run_auto_forecast, y por qué:

    1. NO se elige indicador principal. Research ya lo definió; el
       dashboard no tiene por qué opinar.
    2. NO se descarta por significancia ni por backtest. Entran todos.
       Lo único que saca una serie es la colinealidad (dos series que
       dicen literalmente lo mismo), y eso se reporta en pantalla.
    3. El aporte individual de cada serie se calcula igual y se muestra
       como diagnóstico — la pregunta de Nicolás ("¿cuáles están
       aportando?") se responde sin que la respuesta cambie el modelo.

    Con objetivos MENSUALES esto es defendible: ~240 meses de historia
    contra 4-9 predictores. Con el PIB de Brasil (trimestral, ~80 obs y
    6 predictores) queda más justo, y por eso ahí el filtro de
    colinealidad hace más trabajo.
    """
    def report(msg):
        if progress_callback:
            progress_callback(msg)

    freq = target_config.get("base_frequency", "Q")
    horizontes = target_config.get("horizons", [1, 2, 3, 4])
    spec_objetivo = target_config["target"]
    specs = list(target_config.get("features", []))

    manager = GDPForecastDataManager(
        ceic_client,
        country_name=target_config.get("country_name"),
        country_id=target_config.get("country_id"),
    )

    crudas, etiquetas, ids, transformaciones = {}, {}, {}, {}

    # ------------------------------------------------------------------
    # 1. Serie objetivo
    # ------------------------------------------------------------------
    report(f"Descargando {spec_objetivo['label']} y {len(specs)} series predictoras.")
    objetivo, crudo_objetivo = preparar_candidata(
        manager, spec_objetivo, start_date=start_date, freq=freq
    )
    if objetivo is None or objetivo.empty:
        raise ValueError(
            f"La serie objetivo ({spec_objetivo['label']}, ID "
            f"{spec_objetivo['series_id']}) no devolvió datos."
        )

    slug_obj = spec_objetivo["slug"]
    crudas[slug_obj] = crudo_objetivo
    etiquetas[slug_obj] = f"{spec_objetivo['label']} (objetivo)"
    ids[slug_obj] = spec_objetivo["series_id"]
    transformaciones[slug_obj] = spec_objetivo.get("transform", "yoy")

    # ------------------------------------------------------------------
    # 2. Predictores
    # ------------------------------------------------------------------
    preparadas, sin_datos = {}, []
    for spec in specs:
        try:
            serie, cruda = preparar_candidata(manager, spec, start_date=start_date, freq=freq)
        except Exception as e:
            sin_datos.append({"serie": spec["label"], "motivo": f"error: {e}"})
            continue

        if cruda is not None and not cruda.empty:
            crudas[spec["slug"]] = cruda
            etiquetas[spec["slug"]] = spec["label"]
            ids[spec["slug"]] = spec["series_id"]
            transformaciones[spec["slug"]] = spec.get("transform", "yoy")

        if serie is None or serie.empty:
            sin_datos.append({"serie": spec["label"], "motivo": "sin datos en el período"})
            continue
        preparadas[spec["slug"]] = serie

    if not preparadas:
        raise ValueError("Ninguna de las series predictoras devolvió datos.")
    if sin_datos:
        report(f"{len(sin_datos)} serie(s) sin datos utilizables: "
               + ", ".join(s["serie"] for s in sin_datos))

    # ------------------------------------------------------------------
    # 3. Dataset y filtro de colinealidad
    # ------------------------------------------------------------------
    dataset = manager.build_model_dataset(objetivo, preparadas, freq=freq)
    if dataset.empty:
        raise ValueError(
            "El cruce de las series no dejó ninguna observación en común. "
            "Suele pasar cuando una serie arranca mucho después que el resto: "
            "prueba con una fecha de inicio más reciente."
        )

    columnas = [f"{slug}_growth" for slug in preparadas
                if f"{slug}_growth" in dataset.columns]
    columnas, descartadas_vif = _filtrar_colineales(dataset, columnas, vif_max=vif_max)

    if descartadas_vif:
        nombres = ", ".join(
            next((s["label"] for s in specs if f"{s['slug']}_growth" == d["columna"]),
                 d["columna"])
            for d in descartadas_vif
        )
        report(f"Se retiran por duplicar información de otra serie: {nombres}.")

    report(f"Dataset final: {len(dataset)} observaciones "
           f"({dataset['date'].min():%Y-%m} a {dataset['date'].max():%Y-%m}) "
           f"con {len(columnas)} predictores.")

    # ------------------------------------------------------------------
    # 4. Modelo multi-horizonte
    # ------------------------------------------------------------------
    model = MultiHorizonForecaster(
        horizons=horizontes,
        target_col="gdp_growth",
        min_obs_per_horizon=MIN_OBS_POR_FRECUENCIA.get(freq, 15),
        series_label=f"{spec_objetivo['label']} (YoY %)",
        y_title=target_config.get("unit_label", "Variación interanual (%)"),
        offset_kwargs=PASO_POR_FRECUENCIA.get(freq, {"months": 3}),
        cumulative_target=False,
        hac_lags="auto",
        benchmark="persist",
    ).fit(dataset, columnas)

    if not model.horizon_results:
        raise ValueError("No hubo observaciones suficientes para ajustar ningún horizonte.")

    path = model.forecast_path()

    min_train = MIN_TRAIN_POR_FRECUENCIA.get(freq, 25)
    report("Validando contra datos históricos (backtest).")
    bt_summary, bt_detail = model.backtest(dataset, columnas, min_train_obs=min_train)

    # ------------------------------------------------------------------
    # 5. Diagnóstico: qué aporta cada serie (no cambia el modelo)
    # ------------------------------------------------------------------
    etiquetas_modelo = {"target_now": f"{spec_objetivo['label']} del período actual",
                         "const": "Constante"}
    for spec in specs:
        etiquetas_modelo[f"{spec['slug']}_growth"] = spec["label"]

    diagnostico = pd.DataFrame()
    if usar_diagnostico:
        usables = [s for s in specs if f"{s['slug']}_growth" in dataset.columns]
        diagnostico = diagnostico_fijas(dataset, usables, horizontes, progress=report)

    h_min = min(model.horizon_results)
    vif_tabla, ajuste_conjunto = model.diagnostico_colinealidad(
        dataset, columnas, horizon=h_min, labels=etiquetas_modelo
    )

    return {
        "modo": "fixed_features",
        "model": model,
        "dataset": dataset,
        "forecast_path": path,
        "backtest_summary": bt_summary,
        "backtest_detail": bt_detail,
        "significance": model.significance_table(horizon=h_min, labels=etiquetas_modelo),
        "significance_horizon": h_min,
        "labels": etiquetas_modelo,
        "vif": vif_tabla,
        "ajuste_conjunto": ajuste_conjunto,
        "target_series_id": spec_objetivo["series_id"],
        "target_name": spec_objetivo["label"],
        "predictores_usados": [etiquetas_modelo.get(c, c) for c in columnas],
        "descartadas_por_colinealidad": [
            {"serie": etiquetas_modelo.get(d["columna"], d["columna"]), "vif": d["vif"]}
            for d in descartadas_vif
        ],
        "series_sin_datos": sin_datos,
        "diagnostico": diagnostico,
        "diagnostico_resumen": resumen_para_cliente(diagnostico) if not diagnostico.empty
                                else diagnostico,
        "cols_por_horizonte": {h: list(columnas) for h in horizontes},
        "tabla_extraccion": resumen_extraccion(crudas, etiquetas, ids, transformaciones),
        "series_crudas": series_largas(crudas, etiquetas, ids),
    }


def run_auto_forecast(ceic_client, target_config, start_date="2005-01-01",
                       min_candidate_obs=20, early_stop_r2=0.90,
                       usar_series_adicionales=True, progress_callback=None,
                       modo_tamizaje="estricto"):
    """
    Tres etapas:

    1. ELEGIR EL INDICADOR PRINCIPAL. Prueba los candidatos del catálogo
       EN ORDEN y se detiene apenas uno supera early_stop_r2 (0.90). Con
       datos reales el ISE ya pasa de 0.99, así que en el caso típico se
       prueba 1 en vez de 4 — esto es lo que arregló la espera de 5+
       minutos que tuvo Santi.

    2. TAMIZAR LAS SERIES ADICIONALES de Samuel (lo que pidió Nicolás:
       "agregar las series adicionales para complementar el pronóstico").
       Cada una se prueba de a una contra el modelo base y solo pasa si
       es significativa Y mejora el backtest walk-forward. Ver
       gdp_feature_screening.py para el porqué del doble filtro.

    3. AJUSTAR EL MODELO MULTI-HORIZONTE (4 trimestres) con el indicador
       principal más las candidatas que hayan pasado en cada horizonte.

    Es perfectamente posible —y no es una falla— que ninguna candidata
    pase y el modelo se quede solo con el ISE. Ya pasó antes con los 4
    indicadores líderes que probamos. Un modelo con un predictor que
    funciona vale más que uno con seis que no.
    """
    def report(msg):
        if progress_callback:
            progress_callback(msg)

    manager = GDPForecastDataManager(ceic_client, country_id=target_config["country_id"])
    horizontes = target_config.get("horizons", [1, 2, 3, 4])
    crudas, etiquetas, ids, transformaciones = {}, {}, {}, {}

    report(f"Proyección de {target_config['label']}.")

    # ------------------------------------------------------------------
    # 1. Serie objetivo
    # ------------------------------------------------------------------
    if target_config.get("target_series_id"):
        report("Descargando la serie oficial del objetivo.")
        target_row = {"id": target_config["target_series_id"],
                      "name": f"{target_config['label']} (ID fijo en el catálogo)"}
    else:
        report("Buscando la serie oficial del objetivo en CEIC.")
        target_row = manager.auto_resolve_target(
            target_config["target_keyword"], target_config["target_frequency"]
        )
    gdp_raw = manager.fetch_series(target_row["id"], start_date=start_date)
    report(f"{len(gdp_raw)} observaciones descargadas.")
    gdp_growth = manager.to_growth_rate(gdp_raw, frequency="Q", method="yoy")

    crudas["objetivo"] = gdp_raw
    etiquetas["objetivo"] = f"{target_config['label']} (objetivo)"
    ids["objetivo"] = target_row["id"]
    transformaciones["objetivo"] = "yoy"

    # ------------------------------------------------------------------
    # 2. Indicador principal
    # ------------------------------------------------------------------
    candidates_tried, best = [], None

    for candidate in target_config["candidate_indicators"]:
        label = candidate["label"]
        try:
            if candidate.get("series_id"):
                # ID fijo: ni se busca. Con el ISE fijo, el caso típico
                # resuelve en una sola llamada en vez de cuatro búsquedas
                # más cuatro descargas.
                series_row = {"id": candidate["series_id"], "name": label}
            else:
                series_row = manager.try_candidate_indicator(candidate["keyword"])
            if series_row is None:
                candidates_tried.append({"label": label, "r_squared_adj": None,
                                          "status": "sin resultados en CEIC"})
                continue

            raw = manager.fetch_series(series_row["id"], start_date=start_date)
            if raw.empty:
                candidates_tried.append({"label": label, "r_squared_adj": None,
                                          "status": "sin datos históricos"})
                continue

            quarterly = manager.monthly_to_quarterly(raw)
            growth = manager.to_growth_rate(quarterly, frequency="Q", method="yoy")

            trial_dataset = manager.build_model_dataset(gdp_growth, {"indicator": growth})
            if len(trial_dataset) < min_candidate_obs:
                candidates_tried.append({"label": label, "r_squared_adj": None,
                                          "status": "datos insuficientes"})
                continue

            # Ajuste rápido a 1 trimestre solo para comparar candidatos.
            prueba = MultiHorizonForecaster(
                horizons=[1], target_col="gdp_growth", min_obs_per_horizon=15,
            ).fit(trial_dataset, ["indicator_growth"])
            if 1 not in prueba.horizon_stats:
                candidates_tried.append({"label": label, "r_squared_adj": None,
                                          "status": "no se pudo ajustar"})
                continue
            adj_r2 = prueba.horizon_stats[1]["r_squared_adj"]
            # El R² de cada candidato NO se reporta en el cuadro de pasos:
            # Nicolás pidió sacarlo de ahí porque el mismo número queda
            # más abajo, en la tabla de elección del indicador principal.

            candidates_tried.append({"label": label, "r_squared_adj": adj_r2, "status": "ok"})

            if best is None or adj_r2 > best["r_squared_adj"]:
                best = {"label": label, "r_squared_adj": adj_r2, "growth": growth,
                        "dataset": trial_dataset, "series_row": series_row, "raw": raw}

            # Si el candidato traía ID fijo, es el que el equipo ya
            # validó a mano: no tiene sentido gastar tres búsquedas más
            # para confirmar lo que ya sabemos.
            if candidate.get("series_id") or adj_r2 >= early_stop_r2:
                report(f"Indicador principal: {label}.")
                break

        except Exception as e:
            candidates_tried.append({"label": label, "r_squared_adj": None,
                                      "status": f"error: {e}"})
            continue

    if best is None:
        raise ValueError(
            "Ninguno de los indicadores candidatos tuvo datos suficientes "
            "para ajustar el modelo. Candidatos probados: "
            + ", ".join(c["label"] for c in candidates_tried)
        )

    crudas["principal"] = best["raw"]
    etiquetas["principal"] = f"{best['label']} (indicador principal)"
    ids["principal"] = best["series_row"]["id"]
    transformaciones["principal"] = "yoy"

    # ------------------------------------------------------------------
    # 3. Tamizaje de las series adicionales de Samuel
    # ------------------------------------------------------------------
    screening, seleccion, series_extra = pd.DataFrame(), {}, {}
    if usar_series_adicionales and target_config.get("candidate_features"):

        salida = tamizar_candidatas(
            manager, target_config, gdp_growth, best["growth"],
            start_date=start_date, progress=report, modo=modo_tamizaje,
        )
        # tamizar_candidatas devolvía 3 valores antes de agregar las
        # series crudas para la tabla de extracción. Se aceptan las dos
        # formas: si alguien mezcla versiones de los archivos, el
        # resultado es una tabla de extracción incompleta, no un
        # "not enough values to unpack" que tumba toda la corrida.
        if len(salida) == 4:
            screening, seleccion, series_extra, crudas_extra = salida
        else:
            screening, seleccion, series_extra = salida
            crudas_extra = {}
            report("Aviso: gdp_feature_screening.py está desactualizado — "
                   "la tabla de extracción no incluirá las series adicionales.")

        if screening.empty:
            report("Series adicionales: ninguna combinación pudo evaluarse.")

        # Todas las series descargadas entran a la tabla de extracción,
        # hayan pasado el tamizaje o no: Nicolás pidió ver el proceso de
        # extracción completo, no solo las que sobrevivieron.
        for spec in target_config["candidate_features"]:
            if spec["slug"] in crudas_extra:
                crudas[spec["slug"]] = crudas_extra[spec["slug"]]
                etiquetas[spec["slug"]] = spec["label"]
                ids[spec["slug"]] = spec["series_id"]
                transformaciones[spec["slug"]] = spec.get("transform", "yoy")

    # ------------------------------------------------------------------
    # 4. Dataset final y modelo multi-horizonte
    # ------------------------------------------------------------------
    usadas = sorted({c for cols in seleccion.values() for c in cols})
    extras = {c.replace("_growth", ""): series_extra[c] for c in usadas if c in series_extra}


    dataset = manager.build_model_dataset(
        gdp_growth, {"indicator": best["growth"], **extras}
    )
    report(f"Dataset final: {len(dataset)} observaciones trimestrales "
           f"({dataset['date'].min():%Y-%m} a {dataset['date'].max():%Y-%m}).")

    # El tamizaje trabajó con un dataset por candidata; al juntarlas todas
    # el dropna puede recortar la muestra. Si una columna seleccionada se
    # perdió en el camino, se saca en vez de tumbar el ajuste.
    cols_por_h = {
        h: [c for c in ([f"indicator_growth"] + seleccion.get(h, []))
            if c in dataset.columns]
        for h in horizontes
    }

    report(f"Ajustando el modelo a {len(horizontes)} trimestres.")
    model = MultiHorizonForecaster(
        horizons=horizontes,
        target_col="gdp_growth",
        min_obs_per_horizon=15,
        series_label=f"{target_config['label']} (YoY %)",
        y_title=target_config.get("unit_label", "Crecimiento interanual (%)"),
        offset_kwargs={"months": 3},
        cumulative_target=False,
        hac_lags="auto",
        # Para una tasa de crecimiento el rival honesto es "seguirá
        # creciendo como ahora", no "crecerá 0%".
        benchmark="persist",
    ).fit(dataset, cols_por_h)

    if not model.horizon_results:
        raise ValueError("No hubo observaciones suficientes para ajustar ningún horizonte.")


    path = model.forecast_path()

    report("Validando contra datos históricos (backtest).")
    bt_summary, bt_detail = model.backtest(dataset, cols_por_h, min_train_obs=25)


    # Ordenar candidatos probados de mejor a peor para el detalle técnico.
    candidates_tried.sort(key=lambda c: (c["r_squared_adj"] is None, -(c["r_squared_adj"] or 0)))

    etiquetas_modelo = {"indicator_growth": best["label"],
                        "target_now": f"{target_config['label']} del trimestre actual",
                        "const": "Constante"}
    for spec in target_config.get("candidate_features", []):
        etiquetas_modelo[f"{spec['slug']}_growth"] = spec["label"]

    h_min = min(model.horizon_results)
    vif_tabla, ajuste_conjunto = model.diagnostico_colinealidad(
        dataset, cols_por_h, horizon=h_min, labels=etiquetas_modelo
    )
    return {
        "modo": "auto_select",
        "vif": vif_tabla,
        "ajuste_conjunto": ajuste_conjunto,
        "model": model,
        "dataset": dataset,
        "forecast_path": path,
        "backtest_summary": bt_summary,
        "backtest_detail": bt_detail,
        "significance": model.significance_table(horizon=h_min, labels=etiquetas_modelo),
        "significance_horizon": h_min,
        "labels": etiquetas_modelo,
        "chosen_indicator": best["label"],
        "chosen_series_id": best["series_row"]["id"],
        "candidates_tried": candidates_tried,
        "target_series_id": target_row["id"],
        "target_name": target_row["name"],
        "tabla_extraccion": resumen_extraccion(crudas, etiquetas, ids, transformaciones),
        "series_crudas": series_largas(crudas, etiquetas, ids),
        "screening": screening,
        "screening_resumen": resumen_para_cliente(screening) if not screening.empty else screening,
        "seleccion_por_horizonte": seleccion,
        "cols_por_horizonte": cols_por_h,
    }

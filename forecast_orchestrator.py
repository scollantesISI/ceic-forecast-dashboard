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
4 trimestres hacia adelante. Ahora los dos casos —PIB y acero— usan el
mismo motor, el mismo fan chart y el mismo backtest sin fuga.
"""

import pandas as pd

from gdp_data_manager import GDPForecastDataManager, resumen_extraccion
from multi_horizon_forecast import MultiHorizonForecaster
from gdp_feature_screening import tamizar_candidatas, resumen_para_cliente


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
    if mode == "multi_feature":
        from steel_pipeline import run_steel_forecast  # import perezoso
        allowed = {"start_date", "max_horizon", "min_train_obs", "progress_callback"}
        return run_steel_forecast(ceic_client, target_config,
                                   **{k: v for k, v in kwargs.items() if k in allowed})
    return run_auto_forecast(ceic_client, target_config, **kwargs)


def run_auto_forecast(ceic_client, target_config, start_date="2005-01-01",
                       min_candidate_obs=20, early_stop_r2=0.90,
                       usar_series_adicionales=True, progress_callback=None):
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
    crudas, etiquetas, ids = {}, {}, {}

    report(f"Iniciando proyección de {target_config['label']} "
           f"({len(target_config['candidate_indicators'])} indicadores candidatos a evaluar).")

    # ------------------------------------------------------------------
    # 1. Serie objetivo
    # ------------------------------------------------------------------
    if target_config.get("target_series_id"):
        report(f"Trayendo la serie oficial de {target_config['label']}...")
        target_row = {"id": target_config["target_series_id"],
                      "name": f"{target_config['label']} (ID fijo en el catálogo)"}
    else:
        report(f"Buscando la serie oficial de {target_config['label']}...")
        target_row = manager.auto_resolve_target(
            target_config["target_keyword"], target_config["target_frequency"]
        )
    gdp_raw = manager.fetch_series(target_row["id"], start_date=start_date)
    report(f"{target_config['label']}: {len(gdp_raw)} observaciones descargadas "
           f"(ID CEIC {target_row['id']}).")
    gdp_growth = manager.to_growth_rate(gdp_raw, frequency="Q", method="yoy")

    crudas["objetivo"] = gdp_raw
    etiquetas["objetivo"] = f"{target_config['label']} (objetivo)"
    ids["objetivo"] = target_row["id"]

    # ------------------------------------------------------------------
    # 2. Indicador principal
    # ------------------------------------------------------------------
    candidates_tried, best = [], None

    for candidate in target_config["candidate_indicators"]:
        label = candidate["label"]
        report(f"Probando indicador: {label}...")
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
            report(f"{label}: R² ajustado = {adj_r2:.1%} (a 1 trimestre, {len(trial_dataset)} obs.).")

            candidates_tried.append({"label": label, "r_squared_adj": adj_r2, "status": "ok"})

            if best is None or adj_r2 > best["r_squared_adj"]:
                best = {"label": label, "r_squared_adj": adj_r2, "growth": growth,
                        "dataset": trial_dataset, "series_row": series_row, "raw": raw}

            # Si el candidato traía ID fijo, es el que el equipo ya
            # validó a mano: no tiene sentido gastar tres búsquedas más
            # para confirmar lo que ya sabemos.
            if candidate.get("series_id") or adj_r2 >= early_stop_r2:
                report(f"{label}: elegido como indicador principal, no hace falta probar más.")
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

    # ------------------------------------------------------------------
    # 3. Tamizaje de las series adicionales de Samuel
    # ------------------------------------------------------------------
    screening, seleccion, series_extra = pd.DataFrame(), {}, {}
    if usar_series_adicionales and target_config.get("candidate_features"):
        report("Evaluando las series adicionales una por una...")
        salida = tamizar_candidatas(
            manager, target_config, gdp_growth, best["growth"],
            start_date=start_date, progress=report,
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

        if not screening.empty:
            n_unicas = len({c for cols in seleccion.values() for c in cols})
            report(f"Series adicionales: {len(screening)} combinaciones de serie/horizonte "
                   f"evaluadas, {n_unicas} pasaron los dos filtros y entran al modelo.")
        else:
            report("Series adicionales: ninguna combinación pudo evaluarse.")

        # Todas las series descargadas entran a la tabla de extracción,
        # hayan pasado el tamizaje o no: Nicolás pidió ver el proceso de
        # extracción completo, y son 18 series, no 2.
        for spec in target_config["candidate_features"]:
            if spec["slug"] in crudas_extra:
                crudas[spec["slug"]] = crudas_extra[spec["slug"]]
                etiquetas[spec["slug"]] = spec["label"]
                ids[spec["slug"]] = spec["series_id"]

    # ------------------------------------------------------------------
    # 4. Dataset final y modelo multi-horizonte
    # ------------------------------------------------------------------
    usadas = sorted({c for cols in seleccion.values() for c in cols})
    extras = {c.replace("_growth", ""): series_extra[c] for c in usadas if c in series_extra}

    report("Armando el dataset final...")
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

    report(f"Ajustando el modelo para {len(horizontes)} trimestres adelante...")
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
    report(f"Modelo ajustado: {len(model.horizon_results)} de {len(horizontes)} "
           f"horizontes con datos suficientes.")

    path = model.forecast_path()

    report("Validando el modelo contra datos históricos (backtest)...")
    bt_summary, bt_detail = model.backtest(dataset, cols_por_h, min_train_obs=25)
    report(f"Backtest completo: {len(bt_summary)} horizontes evaluados contra el benchmark.")

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
        "tabla_extraccion": resumen_extraccion(crudas, etiquetas, ids),
        "screening": screening,
        "screening_resumen": resumen_para_cliente(screening) if not screening.empty else screening,
        "seleccion_por_horizonte": seleccion,
        "cols_por_horizonte": cols_por_h,
    }

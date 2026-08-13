"""
steel_pipeline.py
------------------
Caso "Precio del acero en China" (pedido de Nicolás, ago-2026).

Diferencias de fondo con el caso del PIB, y por qué existe este archivo
en vez de reusar forecast_orchestrator tal cual:

1. No hay que DESCUBRIR los independientes — Nicolás ya los definió.
   Entonces no se prueba candidato por candidato: se usan los 5 juntos
   en un solo modelo.

2. Las 6 series no tienen la misma frecuencia, y las etiquetas de CEIC
   no son de fiar: varias dicen "Daily, Everyday" pero llegan cada 10
   días. Por eso el pipeline AUDITA el espaciado real de cada serie
   descargada (auditar_frecuencia) en vez de creerle al catálogo. Se
   alinea todo a una grilla SEMANAL
   (promedio de la semana para las diarias, último dato conocido para
   las más lentas). La semana es el mínimo común denominador honesto:
   forzar todo a diario obligaría a inventar datos que no se publicaron.

3. El objetivo es un PRECIO, no una tasa de crecimiento. Un precio es
   una serie no estacionaria: si se modela en niveles, el R² sale ~0.99
   y no significa nada (todas las series suben y bajan juntas con el
   tiempo). Todo el modelo trabaja sobre VARIACIONES, y el benchmark a
   vencer es el random walk (variación cero = "el precio se queda donde
   está"). Ese benchmark es duro en series de precios de alta frecuencia
   y hay que mirarlo antes de prometerle nada a un cliente — es la misma
   disciplina que ya aplicamos con el petróleo en el caso del PIB.

4. Horizonte hasta 26 semanas (~6 meses), como pidió Nicolás. A esa
   distancia los targets acumulados se solapan casi por completo (la
   ventana de una semana comparte 25 de 26 con la siguiente), así que el
   modelo usa errores estándar HAC/Newey-West: con OLS clásico los
   p-values y las bandas saldrían mucho más angostos de lo que
   corresponde. Y el backtest corta el entrenamiento en i-h para que
   ninguna fila de entrenamiento contenga un resultado posterior a la
   fecha que se está prediciendo.

El motor de modelo es el mismo MultiHorizonForecaster (regresión directa
por horizonte, con p-values e intervalos de predicción), solo que en modo
cumulative_target y con paso semanal.
"""

import numpy as np
import pandas as pd

from gdp_data_manager import GDPForecastDataManager, resumen_extraccion
from multi_horizon_forecast import MultiHorizonForecaster

BASE_FREQ = "W-FRI"          # grilla semanal, cierre viernes
FEATURE_CHANGE_PERIODS = 4   # variación de los independientes a 4 semanas
DEFAULT_START_DATE = "2015-01-01"


# ----------------------------------------------------------------------
# 1. Resolver las 6 series (una sola vez; después se fijan los IDs)
# ----------------------------------------------------------------------
def resolve_series(manager, target_config, progress=None):
    """
    Devuelve {slug: {"label", "series_id", "name", "frequency", "match_score"}}
    para el objetivo y los 5 independientes.

    Si el catálogo ya trae series_id, no se busca nada (arranque rápido).
    Si falta alguno, se busca por nombre y se elige el mejor match.
    Un independiente que no se encuentra NO tumba el proceso: se reporta
    y se sigue con los demás — pero si el que falta es el objetivo, sí
    para, porque sin objetivo no hay modelo.
    """
    def report(msg):
        if progress:
            progress(msg)

    def resolve_one(spec, required):
        if spec.get("series_id"):
            report(f"{spec['label']}: usando ID ya confirmado en el catálogo ({spec['series_id']}).")
            return {"label": spec["label"], "series_id": str(spec["series_id"]),
                    "name": spec["full_name"], "frequency": None, "match_score": None,
                    "status": "id fijo en el catálogo"}

        report(f"Buscando serie: {spec['label']}...")
        row = manager.resolve_series_by_name(
            spec["full_name"], spec.get("search_keyword")
        )
        if row is None:
            if required:
                raise ValueError(
                    f"No se encontró la serie objetivo '{spec['full_name']}' en CEIC. "
                    f"Corre discover_steel_series.py para ver los candidatos reales."
                )
            report(f"{spec['label']}: no se encontró en CEIC, se omite.")
            return {"label": spec["label"], "series_id": None, "name": None,
                    "frequency": None, "match_score": None, "status": "no encontrada"}

        report(f"{spec['label']}: encontrada -> {row['name']} "
               f"(match {row.get('match_score') or 0:.2f}, ID {row['id']}).")
        return {"label": spec["label"], "series_id": str(row["id"]), "name": row["name"],
                "frequency": row.get("frequency"), "match_score": row.get("match_score"),
                "status": "ok"}

    resolved = {target_config["target"]["slug"]: resolve_one(target_config["target"], required=True)}
    for feat in target_config["features"]:
        resolved[feat["slug"]] = resolve_one(feat, required=False)
    return resolved


# ----------------------------------------------------------------------
# 2. Dataset semanal alineado
# ----------------------------------------------------------------------
def auditar_frecuencia(raw, resolved):
    """
    Espaciado REAL de cada serie descargada, antes de alinear nada.

    CEIC marca varias de estas series como "Daily, Everyday" aunque no
    lleguen diarias — el inventario de productos de acero (384035557) es
    decadal en la práctica. Saberlo importa porque en la grilla semanal
    una serie decadal arrastra su último valor por ffill dos de cada tres
    semanas, y su variación se mueve a saltos. Esto no rompe el modelo,
    pero es la explicación de por qué un feature puede salir flojo, y es
    mejor tenerlo en la mesa que descubrirlo en la reunión.

    Usa el mismo helper que el caso del PIB para que la tabla que ve el
    cliente sea idéntica en los dos casos.
    """
    return resumen_extraccion(
        raw,
        etiquetas={slug: info["label"] for slug, info in resolved.items()},
        ids={slug: info["series_id"] for slug, info in resolved.items()},
    )


def _aplicar_transform(manager, levels, slug, transform, periods):
    """
    Lleva una columna de niveles a la forma en que entra al modelo,
    según lo que declare el catálogo. Devuelve un DataFrame [date, <col>].

    log_change  -> diferencia de logaritmos sobre 'periods' semanas
    level       -> el nivel tal cual (solo para tasas acotadas, como la
                   tasa de operación de altos hornos: sacarle variación %
                   a un porcentaje no aporta y sí distorsiona)
    diff        -> diferencia simple en puntos sobre 'periods' semanas
    """
    col = levels[["date", slug]].rename(columns={slug: "value"})
    if transform == "level":
        return col.rename(columns={"value": f"{slug}_nivel"})
    if transform == "diff":
        out = col.sort_values("date").copy()
        out[f"{slug}_diff"] = out["value"].diff(periods)
        return out.dropna(subset=[f"{slug}_diff"])[["date", f"{slug}_diff"]]
    return manager.period_change(
        col, periods=periods, method="log"
    ).rename(columns={"growth": f"{slug}_change"})


def build_steel_dataset(manager, resolved, target_config, start_date=DEFAULT_START_DATE,
                         freq=BASE_FREQ, feature_change_periods=FEATURE_CHANGE_PERIODS,
                         progress=None):
    """
    Descarga las series, las lleva a grilla semanal y aplica a cada una
    la transformación que declara el catálogo.
    Devuelve (levels, dataset, feature_cols, auditoria).

    levels  -> niveles semanales alineados (para el gráfico de precio)
    dataset -> [date, precio_acero_change, <feature>_change/_nivel...]
    """
    def report(msg):
        if progress:
            progress(msg)

    target_slug = target_config["target"]["slug"]
    specs = {target_config["target"]["slug"]: target_config["target"]}
    for f in target_config["features"]:
        specs[f["slug"]] = f

    raw = {}
    for slug, info in resolved.items():
        if not info["series_id"]:
            continue
        report(f"Descargando {info['label']}...")
        df = manager.fetch_series(info["series_id"], start_date=start_date)
        if df.empty:
            info["status"] = "sin datos en el rango"
            report(f"{info['label']}: sin datos en el rango pedido, se omite.")
            continue
        report(f"{info['label']}: {len(df)} observaciones descargadas.")
        raw[slug] = df

    if target_slug not in raw:
        raise ValueError("La serie objetivo no devolvió datos en el rango pedido.")

    auditoria = auditar_frecuencia(raw, resolved)

    report("Alineando series de distinta frecuencia a grilla semanal...")
    levels = manager.build_aligned_levels(
        raw, freq=freq, how="mean", ffill_limit=8, no_ffill=(target_slug,)
    )
    report(f"Grilla semanal lista: {len(levels)} semanas alineadas.")

    # Variación SEMANAL del precio (el target del modelo) y variación a
    # 4 semanas de cada independiente (su "momentum"): un cambio de una
    # sola semana en inventarios es casi todo ruido de publicación.
    dataset = pd.DataFrame({"date": levels["date"]})
    dataset = dataset.merge(
        _aplicar_transform(manager, levels, target_slug,
                           specs[target_slug].get("transform", "log_change"), periods=1),
        on="date", how="left",
    )

    feature_cols = []
    for slug in [s for s in raw if s != target_slug]:
        transform = specs[slug].get("transform", "log_change")
        col = _aplicar_transform(manager, levels, slug, transform,
                                 periods=feature_change_periods)
        nueva = [c for c in col.columns if c != "date"][0]
        feature_cols.append(nueva)
        dataset = dataset.merge(col, on="date", how="left")

    dataset = dataset.dropna().reset_index(drop=True)
    report(f"Dataset final: {len(dataset)} semanas con todas las variables completas.")
    return levels, dataset, feature_cols, auditoria


# ----------------------------------------------------------------------
# 3. Corrida completa
# ----------------------------------------------------------------------
def run_steel_forecast(ceic_client, target_config, start_date=DEFAULT_START_DATE,
                        max_horizon=None, min_train_obs=60, progress_callback=None):
    """
    Devuelve un dict con la misma forma que usa el dashboard:
    modelo ajustado, dataset, trayectoria de proyección (en variación y
    en precio), backtest contra random walk y tabla de significancia.

    Horizonte: hasta 26 semanas (~6 meses), como pidió Nicolás. Se ajustan
    solo los hitos mensuales del catálogo ([4, 9, 13, 17, 22, 26]) en vez
    de las 26 semanas una por una: son los que se muestran, y backtestear
    26 horizontes sobre ~550 semanas multiplica el tiempo sin agregar nada.
    """
    def report(msg):
        if progress_callback:
            progress_callback(msg)

    report(f"Iniciando proyección de {target_config['target']['label']} "
           f"({len(target_config.get('features', []))} independientes).")

    manager = GDPForecastDataManager(
        ceic_client,
        country_name=target_config.get("country_name", "China"),
        country_id=target_config.get("country_id"),
    )

    resolved = resolve_series(manager, target_config, progress=report)
    target_slug = target_config["target"]["slug"]

    levels, dataset, feature_cols, auditoria = build_steel_dataset(
        manager, resolved, target_config, start_date=start_date, progress=report
    )

    horizons = target_config.get("horizons") or [1, 2, 3, 4]
    max_horizon = max_horizon or target_config.get("max_horizon") or max(horizons)
    horizons = [h for h in horizons if h <= max_horizon]

    report(f"Ajustando el modelo hasta {max_horizon} semanas adelante...")
    target_col = f"{target_slug}_change"
    model = MultiHorizonForecaster(
        max_horizon=max_horizon,
        horizons=horizons,
        target_col=target_col,
        min_obs_per_horizon=30,
        series_label="Precio del acero (variación %)",
        y_title="Variación acumulada del precio (%)",
        offset_kwargs={"weeks": 1},
        cumulative_target=True,
        hac_lags="auto",   # targets solapados: sin esto, bandas irreales
    ).fit(dataset, feature_cols)

    if not model.horizon_results:
        raise ValueError(
            "No hubo observaciones suficientes para ajustar ningún horizonte. "
            "Prueba con un start_date más antiguo."
        )
    report(f"Modelo ajustado: {len(model.horizon_results)} horizontes con datos suficientes.")

    path = model.forecast_path()

    report("Validando contra datos históricos (backtest walk-forward)...")
    bt_summary, bt_detail = model.backtest(
        dataset, feature_cols, min_train_obs=min_train_obs
    )
    report(f"Backtest completo: {len(bt_summary)} horizontes evaluados contra random walk.")

    last_price = float(levels[target_slug].iloc[-1])
    price_path = path.copy()
    # De variación logarítmica acumulada a precio proyectado.
    for col, out in [("forecast", "precio"), ("ci_95_lower", "precio_lower"),
                      ("ci_95_upper", "precio_upper")]:
        price_path[out] = last_price * np.exp(price_path[col] / 100)
    price_path["meses"] = (price_path["horizon"] / 4.33).round(1)

    labels = {}
    for slug, info in resolved.items():
        for sufijo in ("_change", "_nivel", "_diff"):
            labels[f"{slug}{sufijo}"] = info["label"]
    labels["target_now"] = "Variación reciente del propio precio"
    labels["const"] = "Constante"

    h_min = min(model.horizon_results)
    return {
        "model": model,
        "levels": levels,
        "dataset": dataset,
        "auditoria_frecuencia": auditoria,
        "feature_cols": feature_cols,
        "target_slug": target_slug,
        "target_col": target_col,
        "last_price": last_price,
        "last_date": pd.to_datetime(levels["date"].iloc[-1]),
        "forecast_path": path,
        "price_path": price_path,
        "backtest_summary": bt_summary,
        "backtest_detail": bt_detail,
        "significance": model.significance_table(horizon=h_min, labels=labels),
        "significance_horizon": h_min,
        "labels": labels,
        "resolved_series": resolved,
    }


# ----------------------------------------------------------------------
# 4. Gráfico principal — precio real + precio proyectado
# ----------------------------------------------------------------------
def plot_price_fan_chart(result, history_weeks=104,
                          color_actual="#B33A0F", color_forecast="#FF5315",
                          color_band="rgba(255, 83, 21, 0.15)", color_grid="#eee"):
    """
    El gráfico que se le muestra al cliente: el precio del acero como lo
    conoce (en yuanes/tonelada), no una variación porcentual, con el
    abanico de proyección a 4 semanas. La banda se ensancha con el
    horizonte porque el intervalo es de predicción, no de la media.
    """
    import plotly.graph_objects as go

    levels = result["levels"].tail(history_weeks)
    slug = result["target_slug"]
    last_date, last_price = result["last_date"], result["last_price"]
    pp = result["price_path"]

    future_dates = [last_date + pd.DateOffset(weeks=int(h)) for h in pp["horizon"]]

    fig = go.Figure()
    fig.add_trace(go.Scatter(
        x=pd.to_datetime(levels["date"]), y=levels[slug],
        mode="lines", name="Precio observado",
        line=dict(color=color_actual, width=2.5),
    ))
    fig.add_trace(go.Scatter(
        x=[last_date] + future_dates + future_dates[::-1] + [last_date],
        y=([last_price] + pp["precio_upper"].tolist()
           + pp["precio_lower"].tolist()[::-1] + [last_price]),
        fill="toself", fillcolor=color_band, line=dict(color="rgba(0,0,0,0)"),
        name="Rango de confianza (95%)", hoverinfo="skip",
    ))
    fig.add_trace(go.Scatter(
        x=[last_date] + future_dates, y=[last_price] + pp["precio"].tolist(),
        mode="lines+markers", name="Proyección",
        line=dict(color=color_forecast, width=3, dash="dot"),
        marker=dict(size=9, color=color_forecast, symbol="diamond"),
    ))
    fig.update_layout(
        xaxis_title=None, yaxis_title="Precio (unidad de la serie CEIC)",
        hovermode="x unified", plot_bgcolor="white", paper_bgcolor="white",
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="left", x=0),
        margin=dict(t=10),
    )
    fig.update_xaxes(showgrid=False)
    fig.update_yaxes(showgrid=True, gridcolor=color_grid)
    return fig


if __name__ == "__main__":
    import os
    from ceic_api_client.pyceic import Ceic
    from indicator_catalog import TARGET_CATALOG

    Ceic.login(os.environ["CEIC_USER"], os.environ["CEIC_PASSWORD"])
    res = run_steel_forecast(Ceic, TARGET_CATALOG["acero_china"], progress_callback=print)

    print("\n=== Series usadas ===")
    for slug, info in res["resolved_series"].items():
        print(f"  {slug:22} {info['status']:24} {info['name']}")

    print(f"\nDataset: {len(res['dataset'])} semanas "
          f"({res['dataset']['date'].min().date()} a {res['dataset']['date'].max().date()})")

    print("\n=== Proyección (variación acumulada %) ===")
    print(res["forecast_path"].to_string(index=False))

    print("\n=== Precio proyectado ===")
    print(res["price_path"][["horizon", "meses", "precio", "precio_lower", "precio_upper"]].to_string(index=False))

    print("\n=== Backtest walk-forward vs. random walk ===")
    print(res["backtest_summary"].to_string(index=False))

    print("\n=== Auditoría de frecuencia real de las series ===")
    print(res["auditoria_frecuencia"].to_string(index=False))

    print(f"\n=== Significancia (h={res['significance_horizon']} semanas) ===")
    print(res["significance"].to_string(index=False))

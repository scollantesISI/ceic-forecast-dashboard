"""
multi_horizon_forecast.py
---------------------------
Extiende el modelo puente a VARIOS períodos hacia adelante, no solo el
siguiente. Usa "forecasting directo": un modelo SEPARADO por cada
horizonte h=1..max_horizon, cada uno prediciendo target(t+h) a partir de
lo que se conoce en el presente (t) — no un modelo recursivo que reutiliza
su propio forecast como insumo del siguiente paso.

Por qué directo y no recursivo: un modelo recursivo necesitaría "el ISE
del próximo trimestre" (o "el inventario de puerto de la próxima semana")
para proyectar dos períodos adelante, y esa es justamente la información
que no existe todavía. El enfoque directo evita ese problema por diseño,
y además no acumula el error de un paso sobre el siguiente.

Es normal y ESPERADO que la capacidad predictiva (R² ajustado) baje a
medida que el horizonte crece. Esto no se esconde: es justamente lo que
hace la proyección creíble frente a un cliente (un rango angosto cerca y
más ancho lejos, como los "fan charts" de los bancos centrales).

GENERALIZADO (ago-2026): la clase ya no está atada al PIB trimestral.
target_col, las etiquetas del gráfico y el paso de tiempo entre horizontes
son parámetros, para poder reusar exactamente el mismo motor con el precio
semanal del acero en China (ver steel_pipeline.py).
"""

import numpy as np
import pandas as pd
import statsmodels.api as sm


class MultiHorizonForecaster:
    def __init__(self, max_horizon=4, target_col="gdp_growth", min_obs_per_horizon=15,
                 series_label="PIB real (YoY %)",
                 y_title="Crecimiento interanual (%)",
                 offset_kwargs=None, cumulative_target=False,
                 horizons=None, hac_lags="auto", benchmark=None):
        """
        offset_kwargs: paso de tiempo de UN horizonte, como kwargs de
        pd.DateOffset. Trimestral -> {"months": 3} (default).
        Semanal -> {"weeks": 1}.

        horizons: lista explícita de horizontes a ajustar. Si es None se
        usan todos de 1 a max_horizon. Con el acero a 26 semanas conviene
        pasar solo los hitos ([4, 9, 13, 17, 22, 26]): ajustar los 26 y
        backtestearlos todos multiplica el tiempo sin agregar nada que se
        vaya a mostrar.

        cumulative_target: cómo se define "el target dentro de h períodos".
          False (default, caso PIB) -> el valor de la serie objetivo en
                t+h tal cual (el crecimiento YoY del PIB de ese trimestre).
          True (caso acero) -> la variación ACUMULADA entre t y t+h. Con
                el target en variaciones semanales, esto equivale a
                "cuánto se mueve el precio de acá a h semanas", que es la
                pregunta que de verdad hace un cliente de commodities, y
                deja el benchmark bien definido: variación cero = el
                precio se queda donde está (random walk).

        hac_lags: corrección de errores estándar por SOLAPAMIENTO del
        target.
          "auto" (default) -> HAC/Newey-West con h-1 rezagos cuando h>1,
                OLS clásico cuando h=1.
          None   -> sin corrección (OLS clásico siempre).
          int    -> número fijo de rezagos.

        Por qué importa: al proyectar h períodos adelante, la ventana del
        target de una fila se solapa con la de las h-1 filas siguientes
        (a 26 semanas, comparten 25 de 26). Los residuos quedan
        fuertemente autocorrelacionados por construcción, y OLS clásico
        entonces subestima los errores estándar — salen p-values
        demasiado optimistas y bandas de confianza demasiado angostas.
        Es el error clásico de las regresiones de horizonte largo; sin
        esto, el caso del acero a 6 meses se vería mucho más sólido de lo
        que es. La corrección NO cambia los coeficientes ni las
        proyecciones puntuales: solo la incertidumbre reportada.
        """
        self.max_horizon = max_horizon
        self.horizons = sorted(horizons) if horizons else list(range(1, max_horizon + 1))
        self.target_col = target_col
        self.min_obs_per_horizon = min_obs_per_horizon
        self.series_label = series_label
        self.y_title = y_title
        self.offset_kwargs = offset_kwargs or {"months": 3}
        self.cumulative_target = cumulative_target
        self.hac_lags = hac_lags
        # Contra qué se compara el modelo en el backtest.
        #   "persist" -> repetir el dato actual. Es el benchmark correcto
        #       para una TASA DE CRECIMIENTO: nadie proyecta que el PIB
        #       crecerá 0%, se proyecta que seguirá creciendo parecido a
        #       ahora. Medir contra cero infla artificialmente la mejora.
        #   "zero" -> variación cero, o sea "el precio se queda donde
        #       está". Es el benchmark correcto para un PRECIO, y es duro.
        #   "mean" -> el promedio histórico. A horizontes largos este es
        #       el rival de verdad: el crecimiento YoY revierte a la media
        #       dentro de un año, así que "repetir el dato actual" se
        #       vuelve un rival de paja y ganarle no prueba nada.
        # Por defecto se elige según el tipo de target, pero el backtest
        # reporta los TRES para que no se pueda elegir el más conveniente
        # después de ver los resultados.
        self.benchmark = benchmark or ("zero" if cumulative_target else "persist")
        self.horizon_results = {}   # h -> resultado de statsmodels
        self.horizon_stats = {}     # h -> dict con r_squared_adj, n_obs
        self._cols_por_horizonte = {}   # h -> columnas usadas en ese horizonte
        self._last_known = None

    def _fit_kwargs(self, h, n_obs):
        """Argumentos de .fit() de statsmodels para el horizonte h."""
        if self.hac_lags is None or h <= 1:
            return {}
        lags = h - 1 if self.hac_lags == "auto" else int(self.hac_lags)
        # Con muestras cortas, pedir más rezagos que ~1/4 de las
        # observaciones vuelve la matriz HAC inestable.
        lags = max(1, min(lags, max(1, n_obs // 4)))
        return {"cov_type": "HAC", "cov_kwds": {"maxlags": lags, "use_correction": True}}

    # ------------------------------------------------------------------
    # Ajuste
    # ------------------------------------------------------------------
    def _build_horizon_frame(self, dataset, feature_cols, h):
        """
        Arma el frame de un horizonte: features conocidos en t (incluido
        el propio target en t como término autorregresivo) y el target en
        t+h. Se usa en .fit(), en la proyección y en el backtest, para
        que los tres vean exactamente la misma construcción de datos.

        NO se eliminan acá las filas finales (las que todavía no tienen
        target_future): esas son justamente desde donde se proyecta.
        """
        df = dataset.sort_values("date").reset_index(drop=True).copy()
        s = df[self.target_col]

        if self.cumulative_target:
            # target_now  = variación acumulada de los últimos h períodos
            # target_fut. = variación acumulada de los próximos h períodos
            df["target_now"] = s.rolling(h).sum()
            df["target_future"] = s.rolling(h).sum().shift(-h)
        else:
            df["target_now"] = s
            df["target_future"] = s.shift(-h)

        cols = list(feature_cols) + ["target_now"]
        return df, cols

    @staticmethod
    def _cols_del_horizonte(feature_cols, h):
        """
        feature_cols puede ser una lista (las mismas columnas en todos los
        horizontes, caso acero) o un dict {h: [columnas]} (columnas
        distintas por horizonte, caso PIB).

        El caso del dict existe porque el tamizaje de candidatas del PIB
        selecciona distinto en cada horizonte: una serie con rezago de 4-6
        meses puede aportar a 2 trimestres y no aportar nada a 1. Forzar
        el mismo conjunto en todos obligaría a elegir entre meter ruido en
        unos horizontes o desperdiciar señal en otros.
        """
        if isinstance(feature_cols, dict):
            return list(feature_cols.get(h, []))
        return list(feature_cols)

    def fit(self, dataset, feature_cols):
        """
        dataset: DataFrame con columnas [date, <target_col>, <features>...]
        feature_cols: columnas de indicadores a usar como predictores.
                      Lista (iguales en todos los horizontes) o dict
                      {h: [columnas]} (distintas por horizonte).

        A cada horizonte se le agrega automáticamente el target actual
        como término autorregresivo (el dato conocido en t, igual para
        todos los horizontes).
        """
        self._last_known = {}   # h -> fila desde la que se proyecta

        for h in self.horizons:
            cols_h = self._cols_del_horizonte(feature_cols, h)
            frame, cols = self._build_horizon_frame(dataset, cols_h, h)
            self._cols_por_horizonte[h] = cols

            # Fila más reciente con TODOS los features disponibles: es el
            # punto de partida de la proyección (su target_future todavía
            # no existe — ese es el dato que queremos anticipar).
            known = frame.dropna(subset=cols)
            if known.empty:
                continue
            self._last_known[h] = known.iloc[-1][cols].to_dict()

            df_h = frame.dropna(subset=cols + ["target_future"]).reset_index(drop=True)
            if len(df_h) < self.min_obs_per_horizon:
                continue  # muy pocas observaciones para ese horizonte

            X = sm.add_constant(df_h[cols])
            y = df_h["target_future"]
            result = sm.OLS(y, X).fit(**self._fit_kwargs(h, len(df_h)))

            self.horizon_results[h] = result
            self.horizon_stats[h] = {
                "r_squared_adj": result.rsquared_adj,
                "n_obs": int(result.nobs),
                "errores": "HAC (Newey-West)" if h > 1 and self.hac_lags is not None else "OLS clásico",
            }

        return self

    # ------------------------------------------------------------------
    # Significancia — lo que Nicolás pidió mostrar explícitamente
    # ------------------------------------------------------------------
    def significance_table(self, horizon=1, labels=None):
        """
        Coeficiente, error estándar, t, p-value e IC 95% de cada variable
        en un horizonte dado. labels: dict opcional {columna: nombre
        legible} para mostrarle al cliente "Inventario de puerto" en vez
        de "iron_ore_inventory_change".
        """
        if horizon not in self.horizon_results:
            raise RuntimeError(f"No hay modelo ajustado para h={horizon}")

        r = self.horizon_results[horizon]
        ci = r.conf_int(alpha=0.05)
        table = pd.DataFrame({
            "variable": r.params.index,
            "coeficiente": r.params.values,
            "error_estandar": r.bse.values,
            "t_stat": r.tvalues.values,
            "p_value": r.pvalues.values,
            "ci_95_lower": ci[0].values,
            "ci_95_upper": ci[1].values,
        })
        table["significativo_95%"] = table["p_value"] < 0.05
        if labels:
            table["variable"] = table["variable"].map(lambda v: labels.get(v, v))
        return table

    def diagnostico_colinealidad(self, dataset, feature_cols, horizon=1, labels=None):
        """
        VIF de cada predictor más el test F conjunto del modelo.

        Existe porque hay un patrón que se lee mal sin esto: R² alto y
        NINGÚN predictor individualmente significativo, con errores
        estándar enormes. No significa que el modelo no sirva — significa
        que dos predictores dicen casi lo mismo y la regresión no puede
        repartirles el crédito. Es exactamente lo que pasa con el ISE y
        el PIB del trimestre actual: el ISE está construido para seguir
        al PIB, así que son casi la misma serie.

        Regla práctica: VIF > 10 es colinealidad severa. En ese caso lo
        honesto es quedarse con UNO de los dos, no reportar que "ninguna
        variable es significativa".
        """
        from statsmodels.stats.outliers_influence import variance_inflation_factor

        if horizon not in self.horizon_results:
            raise RuntimeError(f"No hay modelo ajustado para h={horizon}")

        cols_h = self._cols_del_horizonte(feature_cols, horizon)
        frame, cols = self._build_horizon_frame(dataset, cols_h, horizon)
        df_h = frame.dropna(subset=cols + ["target_future"]).reset_index(drop=True)
        X = sm.add_constant(df_h[cols])

        filas = []
        for i, col in enumerate(X.columns):
            if col == "const":
                continue
            vif = float(variance_inflation_factor(X.values, i))
            filas.append({
                "variable": (labels or {}).get(col, col),
                "vif": round(vif, 1),
                "colinealidad": ("severa" if vif > 10 else
                                 "moderada" if vif > 5 else "baja"),
            })

        r = self.horizon_results[horizon]
        return pd.DataFrame(filas), {
            "f_pvalue": float(r.f_pvalue) if r.f_pvalue == r.f_pvalue else None,
            "r_squared_adj": float(r.rsquared_adj),
            "n_obs": int(r.nobs),
        }

    # ------------------------------------------------------------------
    # Proyección
    # ------------------------------------------------------------------
    def forecast_path(self):
        """
        Trayectoria completa de proyección (h=1 hasta max_horizon), cada
        punto con su propio intervalo — no solo el período siguiente.
        Es el insumo para el "fan chart".
        """
        if not self.horizon_results:
            raise RuntimeError("Ajusta el modelo primero con .fit()")

        records = []
        for h, result in self.horizon_results.items():
            row = {col: self._last_known[h][col] for col in self._cols_por_horizonte[h]}
            X_new = sm.add_constant(pd.DataFrame([row]), has_constant="add")
            X_new = X_new[result.params.index]
            pred = result.get_prediction(X_new).summary_frame(alpha=0.05)

            records.append({
                "horizon": h,
                "forecast": pred["mean"].iloc[0],
                # OJO: se usa obs_ci (intervalo de PREDICCIÓN), no mean_ci
                # (intervalo de confianza de la media). mean_ci solo mide
                # qué tan bien se estima el promedio con los datos que
                # tenemos -- se mantiene angosto casi sin importar qué tan
                # malo sea el ajuste. obs_ci suma la varianza residual del
                # modelo, que es la pregunta real: "¿qué tan seguro puedo
                # estar del próximo dato?". Con R² bajo, obs_ci sale
                # varias veces más ancho que mean_ci en la práctica.
                "ci_95_lower": pred["obs_ci_lower"].iloc[0],
                "ci_95_upper": pred["obs_ci_upper"].iloc[0],
                "r_squared_adj": self.horizon_stats[h]["r_squared_adj"],
                "n_obs": self.horizon_stats[h]["n_obs"],
                "errores": self.horizon_stats[h]["errores"],
            })

        return pd.DataFrame(records).sort_values("horizon").reset_index(drop=True)

    # ------------------------------------------------------------------
    # Backtest walk-forward — la prueba que de verdad convence
    # ------------------------------------------------------------------
    def backtest(self, dataset, feature_cols, min_train_obs=40, horizons=None):
        """
        En cada paso histórico se entrena SOLO con datos cuyo resultado ya
        se conocía en ese momento, y se proyecta hacia adelante,
        comparando contra lo que realmente pasó. Mide generalización, no
        ajuste dentro de muestra.

        FUGA DE INFORMACIÓN CORREGIDA (ago-2026). Antes el entrenamiento
        era df_h.iloc[:i], o sea todas las filas anteriores a la fila de
        prueba. El problema: la fila j tiene como target lo que pasó en
        j+h, así que las últimas h filas del entrenamiento contenían
        resultados POSTERIORES a la fecha que se estaba prediciendo. Con
        h=1 el sesgo es menor, pero con h=26 el modelo estaba entrenando
        con medio año de futuro y cualquier "le gana al random walk" a 6
        meses habría sido falso. Ahora el entrenamiento corta en i-h: la
        fila j solo entra si j+h <= i, es decir, si su resultado ya era
        observable cuando había que decidir.

        Dos benchmarks, a propósito:
          - naive_persist: repetir la variación actual (persistencia)
          - naive_zero:    proyectar variación cero, o sea "el precio se
                           queda donde está" (random walk)

        El segundo es el benchmark duro para una serie de precios de alta
        frecuencia: si el modelo no le gana al random walk, no hay caso
        que presentar. Mejor descubrirlo acá que en la reunión.
        """
        horizons = horizons or self.horizons
        rows, detail = [], {}

        for h in horizons:
            cols_h = self._cols_del_horizonte(feature_cols, h)
            frame, cols = self._build_horizon_frame(dataset, cols_h, h)
            df_h = frame.dropna(subset=cols + ["target_future"]).reset_index(drop=True)
            if len(df_h) <= min_train_obs + h:
                continue

            records = []
            for i in range(min_train_obs + h, len(df_h)):
                # Solo filas cuyo target ya se había realizado en i.
                train, test = df_h.iloc[: i - h + 1], df_h.iloc[[i]]
                X_train = sm.add_constant(train[cols])
                step = sm.OLS(train["target_future"], X_train).fit()
                X_test = sm.add_constant(test[cols], has_constant="add")[X_train.columns]
                records.append({
                    "date": test["date"].values[0],
                    "actual": test["target_future"].values[0],
                    "model": step.predict(X_test).values[0],
                    "naive_persist": test["target_now"].values[0],
                    "naive_zero": 0.0,
                    # Promedio de lo observado hasta ese momento — nunca
                    # del futuro, o sería otra fuga.
                    "naive_mean": float(train["target_future"].mean()),
                })

            res = pd.DataFrame(records)
            detail[h] = res

            def rmse(col):
                return float(np.sqrt(((res["actual"] - res[col]) ** 2).mean()))

            rmse_model = rmse("model")
            rmses = {"zero": rmse("naive_zero"), "persist": rmse("naive_persist"),
                     "mean": rmse("naive_mean")}
            rmse_bench = rmses[self.benchmark]
            # El rival más duro de los tres: es contra el que hay que
            # medirse antes de prometerle algo a un cliente.
            mejor_bench = min(rmses, key=rmses.get)
            rows.append({
                "horizon": h,
                "n_folds": len(res),
                "rmse_model": round(rmse_model, 4),
                "rmse_naive_persist": round(rmses["persist"], 4),
                "rmse_naive_zero": round(rmses["zero"], 4),
                "rmse_naive_mean": round(rmses["mean"], 4),
                "benchmark": self.benchmark,
                "rmse_benchmark": round(rmse_bench, 4),
                "benchmark_mas_duro": mejor_bench,
                "rmse_mas_duro": round(rmses[mejor_bench], 4),
                "le_gana_al_mas_duro": bool(rmse_model < rmses[mejor_bench]),
                "mae_model": round(float((res["actual"] - res["model"]).abs().mean()), 4),
                "mejora_vs_benchmark_%": round(100 * (rmse_bench - rmse_model) / rmse_bench, 2)
                                          if rmse_bench else float("nan"),
                "le_gana_al_benchmark": bool(rmse_model < rmse_bench),
            })

        return pd.DataFrame(rows), detail

    # ------------------------------------------------------------------
    # Gráfico
    # ------------------------------------------------------------------
    def plot_fan_chart(self, dataset, date_col="date", history_periods=None,
                        color_actual="#B33A0F", color_forecast="#FF5315",
                        color_band="rgba(255, 83, 21, 0.15)", color_grid="#eee"):
        """
        Gráfico "fan chart": histórico real + la trayectoria proyectada
        completa (h=1..max_horizon), con el intervalo ensanchándose a
        medida que el horizonte crece — el mismo formato que usan los
        bancos centrales para comunicar que la certeza baja mientras más
        lejos se proyecta.

        history_periods: recorta el histórico a los últimos N períodos
        (con datos semanales, 500+ puntos aplastan visualmente la parte
        proyectada; ~104 semanas = 2 años se lee bien).
        """
        import plotly.graph_objects as go

        path = self.forecast_path()
        hist = dataset.sort_values(date_col)
        if history_periods:
            hist = hist.tail(history_periods)

        last_date = pd.to_datetime(hist[date_col].iloc[-1])
        last_value = hist[self.target_col].iloc[-1]
        future_dates = [last_date + pd.DateOffset(**{k: v * h for k, v in self.offset_kwargs.items()})
                        for h in path["horizon"]]

        fig = go.Figure()

        # Histórico real
        fig.add_trace(go.Scatter(
            x=pd.to_datetime(hist[date_col]), y=hist[self.target_col],
            mode="lines", name=self.series_label,
            line=dict(color=color_actual, width=2.5),
        ))

        # Banda de confianza (área entre upper y lower)
        band_x = [last_date] + future_dates + future_dates[::-1] + [last_date]
        band_y = (
            [last_value] + path["ci_95_upper"].tolist()
            + path["ci_95_lower"].tolist()[::-1] + [last_value]
        )
        fig.add_trace(go.Scatter(
            x=band_x, y=band_y, fill="toself", fillcolor=color_band,
            line=dict(color="rgba(0,0,0,0)"), name="Rango de confianza (95%)",
            hoverinfo="skip",
        ))

        # Línea central de la proyección
        fig.add_trace(go.Scatter(
            x=[last_date] + future_dates, y=[last_value] + path["forecast"].tolist(),
            mode="lines+markers+text", name="Proyección",
            line=dict(color=color_forecast, width=3, dash="dot"),
            marker=dict(size=10, color=color_forecast, symbol="diamond"),
            text=[""] + [f"{v:.1f}%" for v in path["forecast"]],
            textposition="top center", textfont=dict(size=13, color=color_forecast),
        ))

        fig.update_layout(
            xaxis_title=None, yaxis_title=self.y_title,
            hovermode="x unified", plot_bgcolor="white", paper_bgcolor="white",
            legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="left", x=0),
            margin=dict(t=10),
        )
        fig.update_xaxes(showgrid=False)
        fig.update_yaxes(showgrid=True, gridcolor=color_grid)
        return fig

    def plot_backtest_bars(self, backtest_detail_df, date_col="date",
                            color_actual="#B33A0F", color_forecast="#FF5315",
                            color_grid="#eee"):
        """
        Barras pareadas real vs. proyección, período a período, con el
        detalle de un horizonte del backtest. Más concreto para un
        cliente que un RMSE abstracto.
        """
        import plotly.graph_objects as go

        fig = go.Figure()
        fig.add_trace(go.Bar(
            x=backtest_detail_df[date_col], y=backtest_detail_df["actual"],
            name="Real", marker_color=color_actual,
        ))
        fig.add_trace(go.Bar(
            x=backtest_detail_df[date_col], y=backtest_detail_df["model"],
            name="Proyección del modelo", marker_color=color_forecast,
        ))
        fig.update_layout(
            barmode="group", title=None, yaxis_title=self.y_title,
            plot_bgcolor="white", paper_bgcolor="white",
            legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="left", x=0),
            margin=dict(t=10),
        )
        fig.update_xaxes(showgrid=False)
        fig.update_yaxes(showgrid=True, gridcolor=color_grid)
        return fig

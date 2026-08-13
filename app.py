# --- START OF FILE app.py ---
"""
Dashboard de proyección de indicadores económicos (ISI | CEIC).

Uso interno / showcase: el ingreso es con las credenciales de CEIC de
quien presenta, no con un acceso abierto para el prospecto.

Estructura de la pantalla de resultados, en el orden en que se cuenta la
historia frente a un cliente:
  1. El número (cuánto y para cuándo) + el gráfico de la trayectoria
  2. De dónde salieron los datos  -> tabla de extracción, lo que pidió
     Nicolás explícitamente
  3. Qué tan bien predice        -> backtest contra el benchmark
  4. El detalle estadístico       -> significancia, tamizaje, dataset
"""

import base64
import pandas as pd
import streamlit as st
from ceic_api_client.pyceic import Ceic
from datetime import date

from indicator_catalog import TARGET_CATALOG
from forecast_orchestrator import run_forecast
from steel_pipeline import plot_price_fan_chart
from theme import apply_custom_theme, render_badge, render_metric_card, render_hero_metric
from translation import t, selector_idioma

st.set_page_config(page_title="ISI | Proyección de indicadores", layout="wide")
apply_custom_theme()

# El caso macro usa historia larga; el del acero arranca en 2015 porque
# varias series de China Premium no existen antes y Nicolás pidió al
# menos 5 años de observaciones.
DEFAULT_START_DATE = {"auto_select": date(2005, 1, 1),
                      "multi_feature": date(2015, 1, 1),
                      "nowcast": date(2005, 1, 1)}

SEMANAS_POR_MES = 4.345
CACHE_TTL_SEGUNDOS = 60 * 60 * 6   # 6 horas: los datos de CEIC no cambian
                                    # dentro de una sesión de trabajo


# ======================================================================
# Caché — la diferencia entre una demo fluida y una espera incómoda
# ======================================================================
# El caso del PIB descarga 20 series y corre ~40 evaluaciones con
# backtest. La primera corrida se demora; repetirla no debería. Con esto,
# volver a un indicador ya proyectado es instantáneo, que es exactamente
# lo que pasa en una reunión cuando alguien pide "muéstralo otra vez".
#
# El guion bajo en _ceic le dice a Streamlit que no intente hashear el
# cliente de CEIC (no es hasheable y tumbaría el caché).
@st.cache_data(ttl=CACHE_TTL_SEGUNDOS, show_spinner=False)
def run_forecast_cacheado(_ceic, target_key, start_date, usar_extras):
    # Nota: esta función solo se ejecuta en un "cache miss" (primera vez que
    # se pide este indicador, o después de "Recargar datos"). El cuadro de
    # pasos de acá abajo se crea y se llena DENTRO de esta función a
    # propósito: @st.cache_data puede repetir los st.write() de una corrida
    # ya cacheada, pero solo si el cuadro que los contiene también se creó
    # adentro — si se crea afuera, Streamlit tira un error
    # (CacheReplayClosureError) la segunda vez que se pide el mismo
    # indicador. Con todo adentro, la próxima vez el cuadro de pasos se
    # vuelve a dibujar igual, sin recalcular nada.
    target_config = TARGET_CATALOG[target_key]

    with st.expander(f"Pasos de la proyección — {target_config['label']}", expanded=True):
        def reportar(mensaje):
            print(f"[Forecast] {mensaje}")
            st.write(mensaje)

        reportar(f"Indicador solicitado: {target_config['label']} "
                  f"(modo: {target_config.get('mode', 'auto_select')})")
        reportar(f"Usando datos desde: {start_date}")

        kwargs = {"start_date": start_date, "progress_callback": reportar}
        if target_config.get("mode", "auto_select") == "auto_select":
            kwargs["usar_series_adicionales"] = usar_extras
            reportar(f"Evaluar series adicionales del catálogo: {'sí' if usar_extras else 'no'}")

        resultado = run_forecast(_ceic, target_config, **kwargs)
        st.success(f"{target_config['label']}: proyección lista.")

    return resultado


# ======================================================================
# Helpers de presentación
# ======================================================================
def etiqueta_periodo(period_label, plural=False, capitalizar=False):
    """
    Traduce el nombre del período (trimestre/semana/mes/...) al idioma
    activo, con la pluralización correcta — "mes" en portugués es "mês",
    y su plural es "meses", no "mêss" (una simple concatenación con "s"
    rompería justo ese caso).
    """
    idioma = st.session_state.get("idioma", "es")
    if idioma == "pt":
        singular = {"mes": "mês", "trimestre": "trimestre", "semana": "semana",
                    "período": "período", "periodo": "período"}.get(period_label, period_label)
        texto = ("meses" if singular == "mês" else f"{singular}s") if plural else singular
    elif idioma == "en":
        singular = {"mes": "month", "trimestre": "quarter", "semana": "week",
                    "período": "period", "periodo": "period"}.get(period_label, period_label)
        texto = f"{singular}s" if plural else singular
    else:
        texto = f"{period_label}s" if plural else period_label
    return texto.capitalize() if capitalizar else texto


def etiqueta_mes(m):
    """'{m} mes(es)' en el idioma activo — separado de etiqueta_horizonte
    porque acá el número de meses YA es la unidad (no hay que convertir
    semanas ni trimestres)."""
    idioma = st.session_state.get("idioma", "es")
    if idioma == "pt":
        return f"{m} mês" if m == 1 else f"{m} meses"
    if idioma == "en":
        return f"{m} month" if m == 1 else f"{m} months"
    return f"{m} mes" if m == 1 else f"{m} meses"


def etiqueta_horizonte(h, period_label):
    """
    Traduce un horizonte a la unidad en la que piensa el negocio.

    El modelo del acero trabaja en semanas porque esa es la grilla donde
    las 6 series conviven honestamente, pero nadie pregunta "¿cómo va el
    acero en 22 semanas?". Se muestra en meses.
    """
    idioma = st.session_state.get("idioma", "es")

    if idioma == "pt":
        if period_label == "semana":
            meses = h / SEMANAS_POR_MES
            n = int(round(meses))
            return f"{n} mês" if n == 1 else f"{n} meses"
        if period_label == "trimestre":
            return "1 trimestre" if h == 1 else f"{h} trimestres"
        unidad = {"mes": "mês", "período": "período", "periodo": "período"}.get(period_label, period_label)
        if unidad == "mês":
            return "1 mês" if h == 1 else f"{h} meses"
        return f"{h} {unidad}s" if h != 1 else f"1 {unidad}"

    if idioma == "en":
        if period_label == "semana":
            meses = h / SEMANAS_POR_MES
            n = int(round(meses))
            return f"{n} month" if n == 1 else f"{n} months"
        if period_label == "trimestre":
            return "1 quarter" if h == 1 else f"{h} quarters"
        unidad = {"mes": "month", "período": "period", "periodo": "period"}.get(period_label, period_label)
        return f"{h} {unidad}s" if h != 1 else f"1 {unidad}"

    if period_label == "semana":
        meses = h / SEMANAS_POR_MES
        n = int(round(meses))
        return f"{n} mes" if n == 1 else f"{n} meses"
    if period_label == "trimestre":
        return "1 trimestre" if h == 1 else f"{h} trimestres"
    return f"{h} {period_label}s" if h != 1 else f"1 {period_label}"



def etiqueta_benchmark(benchmark, period_label):
    """Cómo se le explica al cliente contra qué se está comparando."""
    idioma = st.session_state.get("idioma", "es")

    if idioma == "pt":
        if benchmark == "zero":
            return "o preço fica igual"
        unidad = {"mes": "mês", "trimestre": "trimestre", "semana": "semana",
                  "período": "período", "periodo": "período"}.get(period_label, period_label)
        return f"repetir o dado do {unidad} atual"

    if idioma == "en":
        if benchmark == "zero":
            return "the price stays the same"
        unidad = {"mes": "month", "trimestre": "quarter", "semana": "week",
                  "período": "period", "periodo": "period"}.get(period_label, period_label)
        return f"repeating the current {unidad}'s figure"

    if benchmark == "zero":
        return "el precio se queda igual"
    return f"repetir el dato del {period_label} actual"

def tabla_extraccion_legible(df):
    """Renombra la tabla de extracción a columnas que se le muestran al cliente."""
    if df is None or df.empty:
        return df
    idioma = st.session_state.get("idioma", "es")
    if idioma == "pt":
        cols = {
            "serie": "Série", "id_ceic": "ID no CEIC", "n_obs": "Observações",
            "desde": "Desde", "hasta": "Até", "frecuencia_real": "Frequência real",
            "ultimo_valor": "Último dado",
        }
    elif idioma == "en":
        cols = {
            "serie": "Series", "id_ceic": "CEIC ID", "n_obs": "Observations",
            "desde": "From", "hasta": "To", "frecuencia_real": "Actual frequency",
            "ultimo_valor": "Latest value",
        }
    else:
        cols = {
            "serie": "Serie", "id_ceic": "ID en CEIC", "n_obs": "Observaciones",
            "desde": "Desde", "hasta": "Hasta", "frecuencia_real": "Frecuencia real",
            "ultimo_valor": "Último dato",
        }
    presentes = [c for c in cols if c in df.columns]
    return df[presentes].rename(columns=cols)


def formatear_p(serie):
    return serie.apply(lambda p: "< 0.001" if pd.notna(p) and p < 0.001 else f"{p:.3f}")


def render_significancia(tabla, horizonte_txt):
    st.markdown(
        f"**Significancia estadística ({horizonte_txt} adelante)** — qué "
        "variables mueven de verdad al indicador y cuáles no:"
    )
    t = tabla.copy()
    t["p_value"] = formatear_p(t["p_value"])
    t["significativo_95%"] = t["significativo_95%"].map({True: "Sí", False: "No"})
    st.dataframe(t, use_container_width=True, hide_index=True)


def render_extraccion(result, period_label):
    """
    Bloque "de dónde salieron los datos". Nicolás lo pidió explícitamente
    y además es el argumento comercial: demuestra que sale de la API en
    vivo, no de un Excel armado a mano.
    """
    tabla = result.get("tabla_extraccion")
    if tabla is None:
        tabla = result.get("auditoria_frecuencia")
    if tabla is None or tabla.empty:
        return

    st.markdown(t("de_donde_salen_datos"))
    st.caption(t("caption_extraccion_serie"))
    st.dataframe(tabla_extraccion_legible(tabla), use_container_width=True, hide_index=True)

    dataset = result["dataset"]
    st.markdown(t("datos_recientes", n=min(8, len(dataset))))
    recientes = dataset.tail(8).iloc[::-1].copy()
    if "date" in recientes.columns:
        recientes["date"] = pd.to_datetime(recientes["date"]).dt.date
    st.dataframe(recientes.round(3), use_container_width=True, hide_index=True)


# ======================================================================
# Login
# ======================================================================
def initialize_session_state():
    for key, value in {"logged_in": False, "result": None, "result_key": None,
                        "idioma": "es"}.items():
        if key not in st.session_state:
            st.session_state[key] = value


def login_page():
    top_left, top_right = st.columns([5, 1])
    with top_right:
        selector_idioma(key_sufijo="login")

    _, col2, _ = st.columns([1, 2, 1])
    with col2:
        # Se embebe como <img> con una clase propia (mismo patrón que el
        # título y el subtítulo de abajo) en vez de usar st.image(): la
        # regla de theme.py que centraba imágenes apuntaba a un contenedor
        # interno de Streamlit que resultó ser flex-direction: column, así
        # que "justify-content: center" ahí centraba vertical, no
        # horizontalmente. Con HTML propio, el centrado depende solo de
        # nuestro CSS, no de cómo Streamlit arme el DOM internamente.
        with open("static/logo2.png", "rb") as f:
            logo_b64 = base64.b64encode(f.read()).decode()
        st.markdown(
            f"<img src='data:image/png;base64,{logo_b64}' class='isi-login-logo'>",
            unsafe_allow_html=True,
        )
        st.markdown(
            f"<h2 class='isi-login-title'>{t('app_title')}</h2>",
            unsafe_allow_html=True,
        )
        st.markdown(
            f"<p class='isi-login-subtitle'>{t('app_subtitle')}</p>",
            unsafe_allow_html=True,
        )

    _, col2, _ = st.columns([1, 2, 1])
    with col2:
        with st.form("login_form"):
            username = st.text_input(t("usuario"))
            password = st.text_input(t("contrasena"), type="password")
            submitted = st.form_submit_button(t("ingresar"), use_container_width=True, type="primary")
            if submitted:
                try:
                    with st.spinner(t("autenticando")):
                        print(f"[Login] Autenticando usuario '{username}' contra la API de CEIC...")
                        Ceic.login(username, password)
                        print("[Login] Sesión iniciada correctamente.")
                        st.session_state.logged_in = True
                        st.rerun()
                except Exception as e:
                    print(f"[Login] Error al autenticar: {e}")
                    st.error(t("error_login", error=e))



# ======================================================================
# Resultados — nowcast del trimestre en curso
# ======================================================================
def render_nowcast_result(result, target_config):
    """
    El caso más fuerte del proyecto, y el que hay que contar con más
    cuidado: la precisión sola no vale nada sin ventaja de calendario.
    Por eso lo primero que se muestra no es el número, es si hoy hay un
    trimestre que se pueda anticipar.
    """
    cal = result["calendario"]
    est = result["estimacion"]
    tabla = result["tabla_precision"]

    if not cal["hay_ventaja"] or est is None:
        st.error(t("sin_ventaja_calendario", mensaje=cal['mensaje']))
    else:
        hero_col, tabla_col = st.columns([1, 2.2])
        with hero_col:
            render_hero_metric(
                label=f"{result['label_objetivo']} — {cal['trimestre_objetivo']}",
                value=f"{est['nowcast']:.1f}%",
                icon="",
                caption=t("estimado_con_meses", n=est['meses_usados']),
            )
            render_metric_card(t("error_tipico_estimacion"),
                                f"±{est['error_tipico']:.2f} pp")
            st.caption(
                t("ultimo_dato_oficial", valor=f"{est['ultimo_pib']:.1f}",
                  trimestre=est['trimestre_ultimo_pib'])
            )
        with tabla_col:
            st.markdown(t("cuanto_sabemos"))
            st.caption(t("caption_error_baja"))
            vista = tabla.copy()
            vista[t("col_meses_publicados")] = vista["meses_de_indicador"].astype(int)
            vista[t("col_error_tipico")] = vista["rmse"].map(lambda v: f"±{v:.2f} pp")
            vista[t("col_error_sin_2020")] = vista["rmse_sin_covid"].map(lambda v: f"±{v:.2f} pp")
            vista[t("col_mejor_que_esperar")] = vista["mejora_%"].map(lambda v: f"{v:.0f}%")
            vista[t("col_trimestres_probados")] = vista["n_trimestres"]
            st.dataframe(
                vista[[t("col_meses_publicados"), t("col_error_tipico"), t("col_error_sin_2020"),
                       t("col_mejor_que_esperar"), t("col_trimestres_probados")]],
                use_container_width=True, hide_index=True,
            )
            st.caption(cal["mensaje"])

    st.markdown("---")

    # ------------------------------------------------------------------
    st.markdown(t("real_vs_estimado"))
    meses_sel = st.selectbox(
        t("con_cuantos_meses"), sorted(result["detalles"].keys()),
        index=len(result["detalles"]) - 1,
        format_func=etiqueta_mes,
        key="nowcast_m",
    )
    detalle = result["detalles"][meses_sel]
    st.plotly_chart(plot_nowcast_historia(detalle), use_container_width=True)

    ultimos = detalle.tail(8).iloc[::-1].copy()
    ultimos["error"] = (ultimos["real"] - ultimos["nowcast"]).round(2)
    st.dataframe(
        ultimos[["trimestre", "real", "nowcast", "error", "ultimo_pib_publicado"]].rename(columns={
            "trimestre": t("col_trimestre"), "real": t("col_dato_oficial_pct"),
            "nowcast": t("col_estimado_pct"), "error": t("col_diferencia_pp"),
            "ultimo_pib_publicado": t("col_lo_que_se_sabia"),
        }).round(2),
        use_container_width=True, hide_index=True,
    )

    st.markdown("---")
    st.markdown(t("de_donde_salen_datos"))
    st.caption(t("caption_dos_series_vivo"))
    st.dataframe(tabla_extraccion_legible(result["tabla_extraccion"]),
                 use_container_width=True, hide_index=True)

    with st.expander(t("ver_detalle_estadistico")):
        st.markdown("**Precisión y significancia por corte:**")
        det = tabla.copy()
        det["p_value"] = formatear_p(det["p_value"])
        st.dataframe(
            det[["meses_de_indicador", "n_trimestres", "r2_ajustado", "p_value",
                 "rmse", "mae", "rmse_ultimo_pib", "rmse_promedio",
                 "rival_mas_duro", "mejora_%"]].rename(columns={
                "meses_de_indicador": "Meses de datos", "n_trimestres": "Trimestres probados",
                "r2_ajustado": "R² ajustado", "p_value": "p-value",
                "rmse": "Error (RMSE)", "mae": "Error medio (MAE)",
                "rmse_ultimo_pib": "Error de esperar al dato anterior",
                "rmse_promedio": "Error del promedio histórico",
                "rival_mas_duro": "Rival más duro", "mejora_%": "Mejora (%)",
            }),
            use_container_width=True, hide_index=True,
        )

        st.info(
            "**Dos advertencias honestas.** (1) El R² ajustado se calcula sobre "
            "todo el período, incluido 2020, así que sale inflado — el número "
            "que vale es el error del backtest. (2) La validación usa la serie "
            "de PIB ya revisada; en el momento real solo existía la primera "
            "estimación. Es la práctica estándar, pero implica que la operación "
            "real sería algo menos precisa que esta tabla."
        )

        st.markdown("**Resultados completos del backtest:**")
        st.dataframe(detalle, use_container_width=True, hide_index=True)
        st.download_button(
            "Descargar backtest (CSV)", detalle.to_csv(index=False).encode("utf-8"),
            "nowcast_backtest.csv", "text/csv",
        )


def plot_nowcast_historia(detalle, color_real="#B33A0F", color_now="#FF5315",
                           color_grid="#eee"):
    """Dato oficial contra estimado. Si se pegan, el mensaje se ve solo."""
    import plotly.graph_objects as go

    x = detalle["trimestre"]
    fig = go.Figure()
    fig.add_trace(go.Scatter(
        x=x, y=detalle["real"], mode="lines+markers", name="Dato oficial del DANE",
        line=dict(color=color_real, width=2.5), marker=dict(size=6),
    ))
    fig.add_trace(go.Scatter(
        x=x, y=detalle["nowcast"], mode="lines+markers", name="Estimado por el modelo",
        line=dict(color=color_now, width=2.5, dash="dot"),
        marker=dict(size=7, symbol="diamond"),
    ))
    fig.update_layout(
        xaxis_title=None, yaxis_title="Crecimiento interanual (%)",
        hovermode="x unified", plot_bgcolor="white", paper_bgcolor="white",
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="left", x=0),
        margin=dict(t=10),
    )
    fig.update_xaxes(showgrid=False)
    fig.update_yaxes(showgrid=True, gridcolor=color_grid)
    return fig


# ======================================================================
# Resultados — caso macro (PIB de Colombia)
# ======================================================================
def render_macro_result(result, target_config):
    target_label = target_config["label"]
    period_label = target_config.get("period_label", "trimestre")
    model, dataset = result["model"], result["dataset"]
    path, bt = result["forecast_path"], result["backtest_summary"]

    primero = path.iloc[0]
    ultimo = path.iloc[-1]

    hero_col, chart_col = st.columns([1, 2.2])
    with hero_col:
        render_hero_metric(
            label=t("crecimiento_esperado", target=target_label),
            value=f"{primero['forecast']:.1f}%",
            icon="",
            caption=t("rango_proximo", lo=f"{primero['ci_95_lower']:.1f}",
                      hi=f"{primero['ci_95_upper']:.1f}", periodo=etiqueta_periodo(period_label)),
        )
        render_metric_card(
            t("a_horizonte", h=etiqueta_horizonte(int(ultimo['horizon']), period_label)),
            f"{ultimo['forecast']:.1f}%",
        )
        st.caption(
            t("basado_en_indicador", indicador=result['chosen_indicator'],
              target=target_label.lower())
        )
    with chart_col:
        st.plotly_chart(model.plot_fan_chart(dataset, history_periods=40),
                        use_container_width=True)

    st.caption(t("caption_banda_ensancha"))

    # Un R² ajustado <= 0 significa que el modelo no le aporta nada al
    # promedio histórico. Mostrar ese horizonte como "pronóstico" sin
    # decirlo sería vender algo que no existe.
    sin_poder = path[path["r_squared_adj"] <= 0.05]
    if not sin_poder.empty:
        etiquetas_sin = ", ".join(
            etiqueta_horizonte(int(h), period_label) for h in sin_poder["horizon"]
        )
        st.warning(t("warning_sin_poder", horizontes=etiquetas_sin))

    st.markdown("---")
    render_extraccion(result, period_label)

    # ------------------------------------------------------------------
    st.markdown("---")
    bench_txt = etiqueta_benchmark(bt["benchmark"].iloc[0], period_label)
    st.markdown(t("que_tan_bien_predice"))
    st.caption(
        t("caption_reentrena_periodo", periodo=etiqueta_periodo(period_label), rival=bench_txt)
    )

    tabla_bt = bt.copy()
    tabla_bt["horizonte"] = tabla_bt["horizon"].apply(
        lambda h: etiqueta_horizonte(int(h), period_label)
    )
    tabla_bt[t("le_gana")] = tabla_bt["le_gana_al_benchmark"].map({True: t("si"), False: t("no")})
    st.dataframe(
        tabla_bt[["horizonte", "n_folds", "rmse_model", "rmse_benchmark",
                  "mejora_vs_benchmark_%", t("le_gana")]].rename(columns={
            "horizonte": t("col_horizonte"),
            "n_folds": t("col_periodos_probados", periodo=etiqueta_periodo(period_label, plural=True, capitalizar=True)),
            "rmse_model": t("col_error_modelo_rmse"),
            "rmse_benchmark": t("col_error_de", rival=bench_txt),
            "mejora_vs_benchmark_%": t("col_mejora_pct"),
        }),
        use_container_width=True, hide_index=True,
    )

    horizontes = sorted(result["backtest_detail"].keys())
    if horizontes:
        h_sel = st.selectbox(
            t("ver_detalle_periodo"), horizontes,
            format_func=lambda h: etiqueta_horizonte(int(h), period_label),
            key="macro_h",
        )
        st.plotly_chart(model.plot_backtest_bars(result["backtest_detail"][h_sel]),
                        use_container_width=True)

    e1, e2, e3 = st.columns(3)
    with e1:
        render_metric_card(t("qué_tanto_explica"), f"{primero['r_squared_adj']:.1%}")
        st.caption(t("caption_comportamiento_proximo", target=target_label.lower(),
                     periodo=etiqueta_periodo(period_label)))
    with e2:
        mejor = bt.sort_values("mejora_vs_benchmark_%", ascending=False).iloc[0]
        render_metric_card(t("mejora_vs_no_usar"), f"{mejor['mejora_vs_benchmark_%']:.0f}%")
        st.caption(t("caption_en_horizonte", h=etiqueta_horizonte(int(mejor['horizon']), period_label)))
    with e3:
        render_metric_card(
            t("periodos_de_historia", periodo=etiqueta_periodo(period_label, plural=True, capitalizar=True)),
            f"{len(dataset)}",
        )
        st.caption(t("caption_desde_anio", anio=f"{pd.to_datetime(dataset['date']).min():%Y}"))

    # ------------------------------------------------------------------
    with st.expander(t("ver_detalle_estadistico")):
        st.markdown(
            f"**Elección del indicador principal.** Se probaron "
            f"{len(result['candidates_tried'])} candidatos y se comparó qué tan "
            f"bien explica cada uno el comportamiento de {target_label.lower()}:"
        )
        cand = pd.DataFrame(result["candidates_tried"])
        cand["r_squared_adj"] = cand["r_squared_adj"].apply(
            lambda r: f"{r:.1%}" if pd.notna(r) else "—"
        )
        st.dataframe(
            cand.rename(columns={"label": "Indicador", "r_squared_adj": "R² ajustado",
                                  "status": "Estado"}),
            use_container_width=True, hide_index=True,
        )

        render_screening(result, period_label)

        render_significancia(
            result["significance"],
            etiqueta_horizonte(result["significance_horizon"], period_label),
        )
        render_colinealidad(result)

        st.markdown("**Capacidad explicativa por horizonte:**")
        p = path.copy()
        p["Horizonte"] = p["horizon"].apply(lambda h: etiqueta_horizonte(int(h), period_label))
        st.dataframe(
            p[["Horizonte", "r_squared_adj", "n_obs", "errores"]].rename(columns={
                "r_squared_adj": "R² ajustado", "n_obs": "Observaciones",
                "errores": "Errores estándar",
            }),
            use_container_width=True, hide_index=True,
        )

        st.markdown("**Dataset completo usado para el modelo:**")
        st.dataframe(dataset, use_container_width=True, hide_index=True)
        st.download_button(
            "Descargar dataset (CSV)", dataset.to_csv(index=False).encode("utf-8"),
            "proyeccion_dataset.csv", "text/csv",
        )


def render_colinealidad(result):
    """
    Explica el patrón "R² decente pero ningún predictor significativo".

    Sin este bloque, la tabla de significancia se lee como "el modelo no
    sirve", cuando lo que realmente dice es que dos predictores contienen
    casi la misma información. El ISE está construido para seguir al PIB,
    así que el modelo no puede repartir el crédito entre ellos aunque
    juntos expliquen bastante.
    """
    vif = result.get("vif")
    conjunto = result.get("ajuste_conjunto") or {}
    if vif is None or vif.empty:
        return

    severa = vif[vif["colinealidad"] == "severa"]
    f_p = conjunto.get("f_pvalue")

    if f_p is not None:
        f_txt = "< 0.001" if f_p < 0.001 else f"{f_p:.3f}"
        st.markdown(
            f"**El modelo en conjunto sí es significativo** (p del test F = {f_txt}), "
            "aunque las variables por separado no lo sean. Eso no es una "
            "contradicción — es lo que pasa cuando dos predictores dicen casi "
            "lo mismo:"
        )

    st.dataframe(
        vif.rename(columns={"variable": "Variable", "vif": "VIF",
                             "colinealidad": "Colinealidad"}),
        use_container_width=True, hide_index=True,
    )

    if not severa.empty:
        nombres = ", ".join(severa["variable"].tolist())
        st.warning(
            f"**Colinealidad severa** en: {nombres} (VIF > 10). Estas variables "
            "se solapan tanto que el modelo no puede distinguir el aporte de "
            "cada una: los coeficientes quedan inestables y los errores "
            "estándar enormes. La proyección en conjunto sigue siendo válida, "
            "pero no se puede afirmar cuál de las dos manda."
        )


def render_screening(result, period_label):
    """
    Tamizaje de las series adicionales — la respuesta visible al pedido de
    Nicolás de "agregar series adicionales para complementar".

    Se muestra completo, incluidas las que NO pasaron. Que una serie no
    aporte también es un resultado, y presentarlo así es lo que hace
    creíble a las que sí quedaron.
    """
    resumen = result.get("screening_resumen")
    if resumen is None or resumen.empty:
        return

    total = len(resumen)
    pasaron = int(resumen["pasa"].sum()) if "pasa" in resumen.columns else 0

    st.markdown(
        f"**Series adicionales evaluadas.** Se probaron {total} combinaciones de "
        f"serie y horizonte, una por una. Para entrar al modelo, una serie tiene "
        f"que pasar DOS filtros: ser estadísticamente significativa **y** reducir "
        f"el error en el backtest. Pasaron {pasaron}."
    )
    if pasaron == 0:
        st.info(
            "Ninguna serie adicional superó los dos filtros, así que el modelo "
            f"se queda con {result['chosen_indicator']} como único predictor. "
            "Esto no es una falla: agregar variables que no aportan empeora la "
            "proyección fuera de muestra."
        )

    tabla = resumen.copy()
    if "horizonte" in tabla.columns:
        tabla["horizonte"] = tabla["horizonte"].apply(
            lambda h: etiqueta_horizonte(int(h), period_label) if pd.notna(h) else "—"
        )
    for col in ("pasa_significancia", "pasa_backtest", "pasa"):
        if col in tabla.columns:
            tabla[col] = tabla[col].map({True: "Sí", False: "No"})
    if "p_value" in tabla.columns:
        tabla["p_value"] = formatear_p(tabla["p_value"])

    st.dataframe(
        tabla.rename(columns={
            "bloque": "Bloque", "candidata": "Serie", "horizonte": "Horizonte",
            "p_value": "p-value", "mejora_rmse_%": "Mejora del error (%)",
            "pasa_significancia": "Significativa", "pasa_backtest": "Mejora el backtest",
            "pasa": "Entra al modelo",
        }),
        use_container_width=True, hide_index=True,
    )

    seleccion = result.get("seleccion_por_horizonte") or {}
    if any(seleccion.values()):
        st.caption(
            "Se limita a 3 series adicionales por horizonte: con ~80 "
            "observaciones trimestrales, más predictores producen un modelo "
            "que memoriza el pasado en vez de anticipar el futuro."
        )


# ======================================================================
# Resultados — caso commodity (precio del acero en China)
# ======================================================================
def render_commodity_result(result, target_config):
    target_label = target_config["label"]
    period_label = target_config.get("period_label", "semana")
    price_path, bt = result["price_path"], result["backtest_summary"]
    last_h = price_path.iloc[-1]
    var_pct = 100 * (last_h["precio"] / result["last_price"] - 1)
    horizonte_txt = etiqueta_horizonte(int(last_h["horizon"]), period_label)

    hero_col, chart_col = st.columns([1, 2.2])
    with hero_col:
        render_hero_metric(
            label=t("precio_esperado_en", horizonte=horizonte_txt),
            value=f"{last_h['precio']:,.0f}",
            icon="",
            caption=t("rango_hoy", lo=f"{last_h['precio_lower']:,.0f}",
                      hi=f"{last_h['precio_upper']:,.0f}", hoy=f"{result['last_price']:,.0f}"),
        )
        render_metric_card(t("variacion_proyectada"), f"{var_pct:+.1f}%")
        st.caption(
            t("caption_ultimo_dato_acero", fecha=f"{result['last_date']:%d-%b-%Y}")
        )
    with chart_col:
        st.plotly_chart(plot_price_fan_chart(result), use_container_width=True)

    st.markdown(t("precio_proyectado_horizonte"))
    pp = price_path.copy()
    pp[t("col_horizonte")] = pp["horizon"].apply(lambda h: etiqueta_horizonte(int(h), period_label))
    st.dataframe(
        pp[[t("col_horizonte"), "precio", "precio_lower", "precio_upper"]].rename(columns={
            "precio": t("col_precio_esperado"), "precio_lower": t("col_minimo_95"),
            "precio_upper": t("col_maximo_95"),
        }).round(0),
        use_container_width=True, hide_index=True,
    )

    st.markdown("---")
    render_extraccion(result, period_label)

    # ------------------------------------------------------------------
    st.markdown("---")
    st.markdown(t("que_tan_bien_predice"))
    st.caption(t("caption_reentrena_semana"))

    if not bt["le_gana_al_benchmark"].any():
        st.warning(t("warning_no_gana_random_walk"))
    elif not bt["le_gana_al_benchmark"].all():
        gana = bt[bt["le_gana_al_benchmark"]]["horizon"].apply(
            lambda h: etiqueta_horizonte(int(h), period_label)
        ).tolist()
        st.info(t("info_gana_solo_en", horizontes=", ".join(gana)))

    bt_display = bt.copy()
    bt_display[t("col_horizonte")] = bt_display["horizon"].apply(
        lambda h: etiqueta_horizonte(int(h), period_label)
    )
    bt_display[t("le_gana")] = bt_display["le_gana_al_benchmark"].map({True: t("si"), False: t("no")})
    st.dataframe(
        bt_display[[t("col_horizonte"), "n_folds", "rmse_model", "rmse_naive_zero",
                    "rmse_naive_persist", "mejora_vs_benchmark_%", t("le_gana")]].rename(columns={
            "n_folds": t("col_semanas_probadas"), "rmse_model": t("col_error_modelo_rmse"),
            "rmse_naive_zero": t("col_error_si_no_cambia"),
            "rmse_naive_persist": t("col_error_si_repite"),
            "mejora_vs_benchmark_%": t("col_mejora_vs_no_cambio"),
        }),
        use_container_width=True, hide_index=True,
    )

    horizontes = sorted(result["backtest_detail"].keys())
    if horizontes:
        h_sel = st.selectbox(
            t("ver_detalle_semana"), horizontes,
            format_func=lambda h: etiqueta_horizonte(int(h), period_label),
            key="acero_h",
        )
        st.plotly_chart(result["model"].plot_backtest_bars(result["backtest_detail"][h_sel]),
                        use_container_width=True)

    e1, e2, e3 = st.columns(3)
    mejor = bt.sort_values("mejora_vs_benchmark_%", ascending=False).iloc[0]
    with e1:
        r2 = result["forecast_path"].iloc[0]["r_squared_adj"]
        render_metric_card(t("qué_tanto_explica"), f"{r2:.1%}")
        st.caption(t("caption_variacion_precio_a",
                     h=etiqueta_horizonte(int(result['forecast_path'].iloc[0]['horizon']), period_label)))
    with e2:
        render_metric_card(t("mejor_mejora_vs_no_cambio"), f"{mejor['mejora_vs_benchmark_%']:.0f}%")
        st.caption(t("caption_en_horizonte", h=etiqueta_horizonte(int(mejor['horizon']), period_label)))
    with e3:
        render_metric_card(t("semanas_de_historia"), f"{len(result['dataset'])}")
        st.caption(t("caption_desde_anio", anio=f"{pd.to_datetime(result['dataset']['date']).min():%Y}"))

    # ------------------------------------------------------------------
    with st.expander(t("ver_detalle_estadistico")):
        render_significancia(
            result["significance"],
            etiqueta_horizonte(result["significance_horizon"], period_label),
        )
        st.caption(
            "A horizontes largos las ventanas de proyección se solapan casi "
            "por completo, así que los errores estándar se calculan con la "
            "corrección de Newey-West. Sin ella los p-values saldrían mucho "
            "más optimistas de lo que corresponde."
        )

        st.markdown("**Capacidad explicativa por horizonte:**")
        p = result["forecast_path"].copy()
        p["Horizonte"] = p["horizon"].apply(lambda h: etiqueta_horizonte(int(h), period_label))
        st.dataframe(
            p[["Horizonte", "r_squared_adj", "n_obs", "errores"]].rename(columns={
                "r_squared_adj": "R² ajustado", "n_obs": "Observaciones",
                "errores": "Errores estándar",
            }),
            use_container_width=True, hide_index=True,
        )

        st.markdown("**Dataset usado para el modelo (variaciones semanales):**")
        st.dataframe(result["dataset"], use_container_width=True, hide_index=True)
        st.download_button(
            "Descargar dataset (CSV)", result["dataset"].to_csv(index=False).encode("utf-8"),
            "acero_china_dataset.csv", "text/csv",
        )


# ======================================================================
def main_app():
    top_left, top_mid, top_right = st.columns([4, 1, 1.5])
    with top_left:
        st.markdown(render_badge("ISI | CEIC API"), unsafe_allow_html=True)
    with top_mid:
        selector_idioma(key_sufijo="main")
    with top_right:
        if st.button(t("cerrar_sesion"), key="logout_btn"):
            st.session_state.logged_in = False
            st.session_state.result = None
            st.rerun()

    st.title(t("main_title"))
    st.markdown(t("main_intro"))
    st.markdown("---")

    st.markdown(f"#### {t('que_proyectar')}")
    target_key = st.selectbox(
        " ", options=list(TARGET_CATALOG.keys()),
        format_func=lambda k: TARGET_CATALOG[k]["label"],
        label_visibility="collapsed",
    )
    target_config = TARGET_CATALOG[target_key]
    target_label = target_config["label"]
    mode = target_config.get("mode", "auto_select")
    period_label = target_config.get("period_label", "período")
    if mode == "nowcast":
        st.caption(
            "Estima el trimestre en curso antes de que se publique el dato "
            "oficial, con los meses de datos que ya salieron."
        )
    else:
        horizonte_max = etiqueta_horizonte(
            max(target_config.get("horizons", [4])), period_label
        )
        st.caption(f"Proyección hasta {horizonte_max} hacia adelante.")

    with st.expander("Configuración avanzada (opcional)"):
        st.caption("Los valores por defecto ya funcionan — normalmente no hace falta tocar esto.")
        start_date = st.date_input("Usar datos desde", value=DEFAULT_START_DATE[mode])
        usar_extras = True
        if mode == "auto_select":  # solo aplica a la proyección a futuro
            usar_extras = st.checkbox(
                "Evaluar las series adicionales para complementar el pronóstico",
                value=True,
                help="Prueba una por una las series que aportó el equipo de producto. "
                     "Agrega tiempo a la corrida porque descarga y evalúa cada serie.",
            )

    verbo = "Estimar" if mode == "nowcast" else "Proyectar"
    col_run, col_cache = st.columns([4, 1])
    with col_run:
        proyectar = st.button(f"{verbo} {target_label}", type="primary",
                               use_container_width=True)
    with col_cache:
        if st.button("Recargar datos", use_container_width=True,
                      help="Vuelve a descargar todo desde CEIC, ignorando el caché."):
            print("[App] Limpiando caché — la próxima corrida vuelve a descargar todo desde CEIC.")
            run_forecast_cacheado.clear()
            st.session_state.result = None
            st.rerun()

    if proyectar:
        try:
            st.session_state.result = run_forecast_cacheado(
                Ceic, target_key, str(start_date), usar_extras
            )
            st.session_state.result_key = target_key
        except Exception as e:
            st.session_state.result = None
            st.error(f"No se pudo generar la proyección: {e}")

    result = st.session_state.result
    if result is not None and st.session_state.result_key == target_key:
        st.markdown("---")
        if mode == "nowcast":
            render_nowcast_result(result, target_config)
        elif mode == "multi_feature":
            render_commodity_result(result, target_config)
        else:
            render_macro_result(result, target_config)
    else:
        st.info(f"Presiona **Proyectar {target_label}** para ver los resultados.")


if __name__ == "__main__":
    initialize_session_state()
    if st.session_state.logged_in:
        main_app()
    else:
        login_page()

# --- END OF FILE app.py ---

"""
translation.py
-----------------
Textos de la interfaz en español, portugués e inglés, más el helper t()
que devuelve el texto en el idioma activo (guardado en st.session_state).

Cómo agregar un texto nuevo:
  1. Agrega la clave en TEXTS con sus tres versiones ("es", "pt", "en").
  2. Donde antes había el string suelto en español, usa t("esa_clave").

Cómo interpolar un valor dinámico (ej. el nombre de un indicador):
  TEXTS["saludo"] = {"es": "Hola {nombre}", "pt": "Olá {nombre}", "en": "Hi {nombre}"}
  t("saludo", nombre="Ana")

Cómo agregar un cuarto idioma más adelante: solo agrega esa clave a cada
entrada de TEXTS y a IDIOMAS_DISPONIBLES — el helper t() y selector_idioma()
no cambian, ya están armados para cualquier cantidad de idiomas.
"""

import streamlit as st

IDIOMA_DEFAULT = "es"
IDIOMAS_DISPONIBLES = {"es": "Español", "pt": "Português", "en": "English"}

TEXTS = {
    # ---------- Login ----------
    "app_title": {
        "es": "Proyección de indicadores económicos",
        "pt": "Projeção de indicadores econômicos",
        "en": "Economic Indicator Projection",
    },
    "app_subtitle": {
        "es": "Anticipa el resultado de indicadores clave antes de que se "
              "publique el dato oficial, con datos que ISI | CEIC "
              "actualiza todos los días",
        "pt": "Antecipe o resultado de indicadores-chave antes da "
              "publicação do dado oficial, com dados que a ISI | CEIC "
              "atualiza todos os dias",
        "en": "Anticipate the outcome of key indicators before the "
              "official figure is published, with data that ISI | CEIC "
              "updates every day",
    },
    "usuario": {"es": "Usuario", "pt": "Usuário", "en": "Username"},
    "contrasena": {"es": "Contraseña", "pt": "Senha", "en": "Password"},
    "ingresar": {"es": "Ingresar", "pt": "Entrar", "en": "Log in"},
    "autenticando": {"es": "Autenticando...", "pt": "Autenticando...", "en": "Authenticating..."},
    "error_login": {
        "es": "Error al iniciar sesión: {error}",
        "pt": "Erro ao iniciar sessão: {error}",
        "en": "Login error: {error}",
    },

    # ---------- Cabecera de la app principal ----------
    "cerrar_sesion": {"es": "Cerrar sesión", "pt": "Sair", "en": "Log out"},
    "main_title": {
        "es": "¿Hacia dónde va la economía?",
        "pt": "Para onde vai a economia?",
        "en": "Where is the economy headed?",
    },
    "main_intro": {
        "es": "Elige qué indicador quieres proyectar. El sistema busca "
              "automáticamente los datos de alta frecuencia más "
              "relacionados con ese indicador y arma la proyección — no "
              "hace falta saber de dónde vienen los datos.",
        "pt": "Escolha qual indicador deseja projetar. O sistema busca "
              "automaticamente os dados de alta frequência mais "
              "relacionados a esse indicador e monta a projeção — não é "
              "preciso saber de onde vêm os dados.",
        "en": "Choose which indicator you want to project. The system "
              "automatically looks for the high-frequency data most "
              "related to that indicator and builds the projection — no "
              "need to know where the data comes from.",
    },
    "que_proyectar": {
        "es": "¿Qué quieres proyectar?",
        "pt": "O que você quer projetar?",
        "en": "What do you want to project?",
    },

    # ---------- Genéricos reutilizados en varias pantallas ----------
    "si": {"es": "Sí", "pt": "Sim", "en": "Yes"},
    "no": {"es": "No", "pt": "Não", "en": "No"},
    "de_donde_salen_datos": {
        "es": "### ¿De dónde salen estos datos?",
        "pt": "### De onde vêm esses dados?",
        "en": "### Where does this data come from?",
    },
    "caption_extraccion_serie": {
        "es": "Cada serie se descarga en vivo desde la API de CEIC al momento de "
              "correr la proyección. La frecuencia es la que se observa en los "
              "datos, no la etiqueta del catálogo — varias series marcadas como "
              "diarias en realidad se publican cada 10 días.",
        "pt": "Cada série é baixada ao vivo da API da CEIC no momento de rodar "
              "a projeção. A frequência é a observada nos dados, não a etiqueta "
              "do catálogo — várias séries marcadas como diárias na prática são "
              "publicadas a cada 10 dias.",
        "en": "Each series is downloaded live from the CEIC API when the "
              "projection runs. The frequency shown is the one observed in "
              "the data, not the catalog label — several series marked as "
              "daily are actually published every 10 days.",
    },
    "datos_recientes": {
        "es": "**Datos más recientes** (últimos {n} períodos del modelo):",
        "pt": "**Dados mais recentes** (últimos {n} períodos do modelo):",
        "en": "**Most recent data** (last {n} periods of the model):",
    },
    "que_tan_bien_predice": {
        "es": "### ¿Qué tan bien predice el modelo?",
        "pt": "### O modelo prevê bem?",
        "en": "### How well does the model predict?",
    },
    "ver_detalle_estadistico": {
        "es": "Ver el detalle estadístico completo",
        "pt": "Ver o detalhe estatístico completo",
        "en": "View full statistical detail",
    },
    "qué_tanto_explica": {
        "es": "Qué tanto explica el modelo",
        "pt": "Quanto o modelo explica",
        "en": "How much the model explains",
    },
    "le_gana": {"es": "¿Le gana?", "pt": "Supera?", "en": "Beats it?"},

    # ---------- Nowcast ----------
    "sin_ventaja_calendario": {
        "es": "**Sin ventaja de calendario en este momento.** {mensaje}",
        "pt": "**Sem vantagem de calendário neste momento.** {mensaje}",
        "en": "**No calendar advantage at this time.** {mensaje}",
    },
    "estimado_con_meses": {
        "es": "Estimado con {n} mes(es) de datos &nbsp;·&nbsp; el dato oficial "
              "aún no se publica",
        "pt": "Estimado com {n} mês(es) de dados &nbsp;·&nbsp; o dado oficial "
              "ainda não foi publicado",
        "en": "Estimated with {n} month(s) of data &nbsp;·&nbsp; the official "
              "figure hasn't been published yet",
    },
    "error_tipico_estimacion": {
        "es": "Error típico de esta estimación", "pt": "Erro típico desta estimativa",
        "en": "Typical error of this estimate",
    },
    "ultimo_dato_oficial": {
        "es": "Último dato oficial publicado: {valor}% ({trimestre}). Este número lo anticipa.",
        "pt": "Último dado oficial publicado: {valor}% ({trimestre}). Este número o antecipa.",
        "en": "Last official figure published: {valor}% ({trimestre}). This number anticipates it.",
    },
    "cuanto_sabemos": {
        "es": "#### Cuánto sabemos, y cuándo", "pt": "#### Quanto sabemos, e quando",
        "en": "#### How much we know, and when",
    },
    "caption_error_baja": {
        "es": "El error baja a medida que salen más meses del trimestre. Todo "
              "medido con validación histórica: en cada trimestre se reentrena "
              "solo con datos anteriores y se compara contra lo que realmente dio.",
        "pt": "O erro cai à medida que mais meses do trimestre são publicados. "
              "Tudo medido com validação histórica: em cada trimestre o modelo "
              "é retreinado só com dados anteriores e comparado contra o que "
              "realmente aconteceu.",
        "en": "The error drops as more months of the quarter come out. "
              "Everything is measured with historical validation: each "
              "quarter the model is retrained using only prior data and "
              "compared against what actually happened.",
    },
    "col_meses_publicados": {"es": "Meses publicados", "pt": "Meses publicados", "en": "Months published"},
    "col_error_tipico": {"es": "Error típico", "pt": "Erro típico", "en": "Typical error"},
    "col_error_sin_2020": {"es": "Error sin 2020", "pt": "Erro sem 2020", "en": "Error excluding 2020"},
    "col_mejor_que_esperar": {"es": "Mejor que esperar", "pt": "Melhor que esperar", "en": "Better than waiting"},
    "col_trimestres_probados": {"es": "Trimestres probados", "pt": "Trimestres testados", "en": "Quarters tested"},
    "real_vs_estimado": {
        "es": "### Real contra estimado, trimestre a trimestre",
        "pt": "### Real vs. estimado, trimestre a trimestre",
        "en": "### Actual vs. estimated, quarter by quarter",
    },
    "con_cuantos_meses": {
        "es": "Con cuántos meses del trimestre:", "pt": "Com quantos meses do trimestre:",
        "en": "With how many months of the quarter:",
    },
    "col_trimestre": {"es": "Trimestre", "pt": "Trimestre", "en": "Quarter"},
    "col_dato_oficial_pct": {"es": "Dato oficial (%)", "pt": "Dado oficial (%)", "en": "Official figure (%)"},
    "col_estimado_pct": {"es": "Estimado (%)", "pt": "Estimado (%)", "en": "Estimated (%)"},
    "col_diferencia_pp": {"es": "Diferencia (pp)", "pt": "Diferença (pp)", "en": "Difference (pp)"},
    "col_lo_que_se_sabia": {
        "es": "Lo que se sabía antes (%)", "pt": "O que já se sabia antes (%)",
        "en": "What was known before (%)",
    },
    "caption_dos_series_vivo": {
        "es": "Las dos series se descargan en vivo desde la API de CEIC. La "
              "frecuencia es la observada en los datos, no la etiqueta del catálogo.",
        "pt": "As duas séries são baixadas ao vivo da API da CEIC. A frequência "
              "é a observada nos dados, não a etiqueta do catálogo.",
        "en": "Both series are downloaded live from the CEIC API. The "
              "frequency shown is the one observed in the data, not the "
              "catalog label.",
    },

    # ---------- Caso macro (PIB) ----------
    "crecimiento_esperado": {
        "es": "Crecimiento esperado — {target}", "pt": "Crescimento esperado — {target}",
        "en": "Expected growth — {target}",
    },
    "rango_proximo": {
        "es": "Rango: {lo}% a {hi}% &nbsp;·&nbsp; próximo {periodo}",
        "pt": "Intervalo: {lo}% a {hi}% &nbsp;·&nbsp; próximo {periodo}",
        "en": "Range: {lo}% to {hi}% &nbsp;·&nbsp; next {periodo}",
    },
    "a_horizonte": {"es": "A {h}", "pt": "Em {h}", "en": "At {h}"},
    "basado_en_indicador": {
        "es": "Basado en **{indicador}**, el indicador de mayor frecuencia con "
              "la relación más fuerte con {target}.",
        "pt": "Baseado em **{indicador}**, o indicador de maior frequência com "
              "a relação mais forte com {target}.",
        "en": "Based on **{indicador}**, the highest-frequency indicator "
              "with the strongest relationship to {target}.",
    },
    "caption_banda_ensancha": {
        "es": "La banda se ensancha con el horizonte porque la certeza baja "
              "mientras más lejos se proyecta — el mismo formato que usan los "
              "bancos centrales.",
        "pt": "A faixa se alarga com o horizonte porque a certeza cai quanto "
              "mais longe se projeta — o mesmo formato usado pelos bancos centrais.",
        "en": "The band widens with the horizon because certainty drops "
              "the further out the projection goes — the same format used "
              "by central banks.",
    },
    "warning_sin_poder": {
        "es": "**A {horizontes} el modelo no aporta información sobre el "
              "promedio histórico** (R² ajustado ≈ 0 o negativo). Esos puntos "
              "sirven para mostrar cómo crece la incertidumbre, pero no deben "
              "presentarse como pronóstico.",
        "pt": "**Em {horizontes} o modelo não agrega informação sobre a média "
              "histórica** (R² ajustado ≈ 0 ou negativo). Esses pontos servem "
              "para mostrar como cresce a incerteza, mas não devem ser "
              "apresentados como previsão.",
        "en": "**At {horizontes} the model adds no information over the "
              "historical average** (adjusted R² ≈ 0 or negative). Those "
              "points show how uncertainty grows, but shouldn't be "
              "presented as a forecast.",
    },
    "caption_reentrena_periodo": {
        "es": "En cada {periodo} histórico se reentrena el modelo usando solo "
              "resultados que ya se conocían en ese momento, y se proyecta "
              "hacia adelante sin ver el dato real. El rival es **{rival}**: "
              "para una tasa de crecimiento, ese es el punto de comparación "
              "honesto — nadie proyecta que la economía crecerá 0%.",
        "pt": "Em cada {periodo} histórico o modelo é retreinado usando só "
              "resultados que já eram conhecidos naquele momento, e projeta "
              "para frente sem ver o dado real. O rival é **{rival}**: para "
              "uma taxa de crescimento, esse é o ponto de comparação honesto "
              "— ninguém projeta que a economia crescerá 0%.",
        "en": "Each historical {periodo} the model is retrained using only "
              "results that were already known at that point, and projects "
              "forward without seeing the actual figure. The rival is "
              "**{rival}**: for a growth rate, that's the honest comparison "
              "point — nobody projects the economy will grow 0%.",
    },
    "col_periodos_probados": {"es": "{periodo} probados", "pt": "{periodo} testados", "en": "{periodo} tested"},
    "col_error_modelo_rmse": {
        "es": "Error del modelo (RMSE)", "pt": "Erro do modelo (RMSE)", "en": "Model error (RMSE)",
    },
    "col_error_de": {"es": "Error de {rival}", "pt": "Erro de {rival}", "en": "Error of {rival}"},
    "col_mejora_pct": {"es": "Mejora (%)", "pt": "Melhoria (%)", "en": "Improvement (%)"},
    "ver_detalle_periodo": {
        "es": "Ver el detalle período a período del horizonte:",
        "pt": "Ver o detalhe período a período do horizonte:",
        "en": "View period-by-period detail for the horizon:",
    },
    "caption_comportamiento_proximo": {
        "es": "Del comportamiento de {target} al próximo {periodo}",
        "pt": "Do comportamento de {target} no próximo {periodo}",
        "en": "Of {target}'s behavior next {periodo}",
    },
    "mejora_vs_no_usar": {
        "es": "Mejora vs. no usar el modelo", "pt": "Melhoria vs. não usar o modelo",
        "en": "Improvement vs. not using the model",
    },
    "caption_en_horizonte": {
        "es": "En el horizonte de {h}", "pt": "No horizonte de {h}", "en": "At the {h} horizon",
    },
    "periodos_de_historia": {
        "es": "{periodo} de historia", "pt": "{periodo} de histórico", "en": "{periodo} of history",
    },
    "caption_desde_anio": {"es": "Desde {anio}", "pt": "Desde {anio}", "en": "Since {anio}"},

    # ---------- Caso commodity (acero) ----------
    "precio_esperado_en": {
        "es": "Precio esperado en {horizonte}", "pt": "Preço esperado em {horizonte}",
        "en": "Expected price in {horizonte}",
    },
    "rango_hoy": {
        "es": "Rango: {lo} a {hi} &nbsp;·&nbsp; hoy: {hoy}",
        "pt": "Intervalo: {lo} a {hi} &nbsp;·&nbsp; hoje: {hoy}",
        "en": "Range: {lo} to {hi} &nbsp;·&nbsp; today: {hoy}",
    },
    "variacion_proyectada": {
        "es": "Variación proyectada", "pt": "Variação projetada", "en": "Projected change",
    },
    "caption_ultimo_dato_acero": {
        "es": "Último dato disponible: {fecha}. Datos diarios y decadales de "
              "China Premium, alineados a semana.",
        "pt": "Último dado disponível: {fecha}. Dados diários e decadais da "
              "China Premium, alinhados por semana.",
        "en": "Last available data: {fecha}. Daily and 10-day China Premium "
              "data, aligned to weekly.",
    },
    "precio_proyectado_horizonte": {
        "es": "**Precio proyectado por horizonte:**", "pt": "**Preço projetado por horizonte:**",
        "en": "**Projected price by horizon:**",
    },
    "col_horizonte": {"es": "Horizonte", "pt": "Horizonte", "en": "Horizon"},
    "col_precio_esperado": {"es": "Precio esperado", "pt": "Preço esperado", "en": "Expected price"},
    "col_minimo_95": {"es": "Mínimo (95%)", "pt": "Mínimo (95%)", "en": "Minimum (95%)"},
    "col_maximo_95": {"es": "Máximo (95%)", "pt": "Máximo (95%)", "en": "Maximum (95%)"},
    "caption_reentrena_semana": {
        "es": "En cada semana histórica se reentrena el modelo usando solo "
              "resultados que ya se conocían en ese momento. El punto de "
              "comparación duro para un precio es suponer que se queda igual: "
              "si el modelo no le gana a eso, no aporta.",
        "pt": "Em cada semana histórica o modelo é retreinado usando só "
              "resultados que já eram conhecidos naquele momento. O ponto de "
              "comparação duro para um preço é supor que ele fica igual: se o "
              "modelo não supera isso, não agrega valor.",
        "en": "Each historical week the model is retrained using only "
              "results that were already known at that point. The hard "
              "comparison point for a price is assuming it stays the same: "
              "if the model doesn't beat that, it isn't adding value.",
    },
    "warning_no_gana_random_walk": {
        "es": "En este momento el modelo **no** le gana al supuesto de "
              "'el precio se queda igual' en ningún horizonte. Conviene "
              "revisar los independientes o acortar el horizonte antes de "
              "mostrarlo a un cliente.",
        "pt": "Neste momento o modelo **não** supera a hipótese de 'o preço "
              "fica igual' em nenhum horizonte. Vale revisar as variáveis "
              "independentes ou encurtar o horizonte antes de mostrar a um cliente.",
        "en": "At this time the model does **not** beat the assumption "
              "that 'the price stays the same' at any horizon. Consider "
              "reviewing the independent variables or shortening the "
              "horizon before showing this to a client.",
    },
    "info_gana_solo_en": {
        "es": "El modelo le gana al supuesto de 'el precio se queda igual' "
              "solo en: {horizontes}. En los demás horizontes conviene "
              "presentar la proyección como escenario, no como pronóstico.",
        "pt": "O modelo supera a hipótese de 'o preço fica igual' apenas em: "
              "{horizontes}. Nos demais horizontes, é melhor apresentar a "
              "projeção como cenário, não como previsão.",
        "en": "The model beats the assumption that 'the price stays the "
              "same' only at: {horizontes}. At the other horizons, it's "
              "better to present the projection as a scenario, not a forecast.",
    },
    "col_semanas_probadas": {"es": "Semanas probadas", "pt": "Semanas testadas", "en": "Weeks tested"},
    "col_error_si_no_cambia": {
        "es": "Error si el precio no cambia", "pt": "Erro se o preço não mudar",
        "en": "Error if the price doesn't change",
    },
    "col_error_si_repite": {
        "es": "Error si repite la variación actual", "pt": "Erro se repetir a variação atual",
        "en": "Error if it repeats the current change",
    },
    "col_mejora_vs_no_cambio": {
        "es": "Mejora vs. no cambio (%)", "pt": "Melhoria vs. não mudar (%)",
        "en": "Improvement vs. no change (%)",
    },
    "ver_detalle_semana": {
        "es": "Ver el detalle semana a semana del horizonte:",
        "pt": "Ver o detalhe semana a semana do horizonte:",
        "en": "View week-by-week detail for the horizon:",
    },
    "caption_variacion_precio_a": {
        "es": "De la variación del precio a {h}", "pt": "Da variação do preço em {h}",
        "en": "Of the price change at {h}",
    },
    "mejor_mejora_vs_no_cambio": {
        "es": "Mejor mejora vs. no cambio", "pt": "Melhor ganho vs. não mudar",
        "en": "Best improvement vs. no change",
    },
    "semanas_de_historia": {"es": "Semanas de historia", "pt": "Semanas de histórico", "en": "Weeks of history"},
}


def t(clave, **kwargs):
    """
    Devuelve el texto de 'clave' en el idioma activo. Si la clave no
    existe todavía, devuelve la clave misma en vez de tumbar la app con
    un KeyError — así un texto que falta se nota en pantalla en vez de
    romper la corrida en medio de una demo.
    """
    idioma = st.session_state.get("idioma", IDIOMA_DEFAULT)
    entrada = TEXTS.get(clave)
    if entrada is None:
        return clave
    texto = entrada.get(idioma, entrada.get(IDIOMA_DEFAULT, clave))
    return texto.format(**kwargs) if kwargs else texto


def selector_idioma(key_sufijo=""):
    """
    Botón que avanza al SIGUIENTE idioma, en el orden de IDIOMAS_DISPONIBLES
    (es -> pt -> en -> es -> ...). Con 2 idiomas esto era lo mismo que
    "el botón muestra el otro idioma"; con 3 o más, "cualquier otro
    idioma" ya no alcanza — hace falta un orden fijo para que el botón
    sea predecible. key_sufijo evita choques de key cuando se llama más
    de una vez en la misma pantalla (ej. login y encabezado principal).
    """
    idiomas = list(IDIOMAS_DISPONIBLES.keys())
    actual = st.session_state.get("idioma", IDIOMA_DEFAULT)
    idx_actual = idiomas.index(actual) if actual in idiomas else 0
    siguiente = idiomas[(idx_actual + 1) % len(idiomas)]
    if st.button(IDIOMAS_DISPONIBLES[siguiente], key=f"idioma_btn_{key_sufijo}"):
        st.session_state.idioma = siguiente
        st.rerun()

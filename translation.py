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
    "warning_backtest_insuficiente": {
        "es": "No hay suficiente historia para validar el modelo contra datos "
              "reales en ningún horizonte (el dataset tiene {n} observaciones). "
              "El número de arriba sigue siendo el ajuste del modelo, pero sin "
              "un backtest detrás — conviene no presentarlo como algo "
              "validado hasta que haya más historia disponible.",
        "pt": "Não há histórico suficiente para validar o modelo contra dados "
              "reais em nenhum horizonte (o dataset tem {n} observações). O "
              "número acima ainda é o ajuste do modelo, mas sem um backtest "
              "por trás — melhor não apresentá-lo como algo validado até "
              "haver mais histórico disponível.",
        "en": "There isn't enough history to validate the model against real "
              "data at any horizon (the dataset has {n} observations). The "
              "number above is still the model's fit, but without a backtest "
              "behind it — better not to present it as validated until more "
              "history is available.",
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


# ======================================================================
# Textos agregados en ago-2026 tras la reunión con Nicolás y Samuel
# ----------------------------------------------------------------------
# Samuel, mirando la app en portugués: "no traduce todo... hace falta
# como los botones, la tabla; y los nombres de las series y ese eje
# también están en español". Nicolás: "sería como revisar eso".
#
# Se agregan acá en un TEXTS.update() en vez de mezclarlos arriba para
# que quede claro qué entró en esta tanda y sea fácil de revisar. Para el
# helper t() no hay ninguna diferencia.
# ======================================================================
TEXTS.update({
    # ---------- Selector y configuración ----------
    "grupo_colombia": {"es": "Colombia", "pt": "Colômbia", "en": "Colombia"},
    "grupo_brasil": {"es": "Brasil", "pt": "Brasil", "en": "Brazil"},
    "grupo_commodities": {"es": "Commodities", "pt": "Commodities", "en": "Commodities"},
    "grupo_otros": {"es": "Otros", "pt": "Outros", "en": "Other"},
    "pais_region": {"es": "País o mercado", "pt": "País ou mercado", "en": "Country or market"},
    "proyeccion_hasta": {
        "es": "Proyección hasta {h} hacia adelante.",
        "pt": "Projeção até {h} à frente.",
        "en": "Projection up to {h} ahead.",
    },
    "caption_nowcast": {
        "es": "Estima el trimestre en curso antes de que se publique el dato "
              "oficial, con los meses de datos que ya salieron.",
        "pt": "Estima o trimestre em curso antes da publicação do dado "
              "oficial, com os meses de dados já divulgados.",
        "en": "Estimates the current quarter before the official figure is "
              "published, using the months of data already out.",
    },
    "config_avanzada": {
        "es": "Configuración avanzada (opcional)",
        "pt": "Configuração avançada (opcional)",
        "en": "Advanced settings (optional)",
    },
    "caption_config_avanzada": {
        "es": "Los valores por defecto ya funcionan — normalmente no hace falta tocar esto.",
        "pt": "Os valores padrão já funcionam — normalmente não é preciso mexer aqui.",
        "en": "The defaults already work — you normally don't need to change this.",
    },
    "usar_datos_desde": {"es": "Usar datos desde", "pt": "Usar dados desde", "en": "Use data from"},
    "evaluar_series_adicionales": {
        "es": "Evaluar las series adicionales para complementar el pronóstico",
        "pt": "Avaliar as séries adicionais para complementar a previsão",
        "en": "Evaluate the additional series to complement the forecast",
    },
    "help_evaluar_series": {
        "es": "Prueba una por una las series de apoyo. Agrega tiempo a la corrida.",
        "pt": "Testa uma a uma as séries de apoio. Aumenta o tempo da execução.",
        "en": "Tests the supporting series one by one. Adds time to the run.",
    },
    "criterio_seleccion": {
        "es": "Criterio para que una serie entre al modelo",
        "pt": "Critério para uma série entrar no modelo",
        "en": "Criterion for a series to enter the model",
    },
    "criterio_estricto": {
        "es": "Estricto: significancia y mejora del backtest",
        "pt": "Estrito: significância e melhoria do backtest",
        "en": "Strict: significance and backtest improvement",
    },
    "criterio_significancia": {
        "es": "Solo significancia estadística",
        "pt": "Só significância estatística",
        "en": "Statistical significance only",
    },
    "help_criterio": {
        "es": "El criterio estricto es más conservador y descarta series que "
              "sí son significativas. El otro las deja entrar.",
        "pt": "O critério estrito é mais conservador e descarta séries que são "
              "significativas. O outro as deixa entrar.",
        "en": "The strict criterion is more conservative and drops series that "
              "are in fact significant. The other one lets them in.",
    },
    "boton_proyectar": {"es": "Proyectar {target}", "pt": "Projetar {target}", "en": "Project {target}"},
    "boton_estimar": {"es": "Estimar {target}", "pt": "Estimar {target}", "en": "Estimate {target}"},
    "recargar_datos": {"es": "Recargar datos", "pt": "Recarregar dados", "en": "Reload data"},
    "help_recargar": {
        "es": "Vuelve a descargar todo desde CEIC, ignorando el caché.",
        "pt": "Baixa tudo novamente da CEIC, ignorando o cache.",
        "en": "Downloads everything from CEIC again, ignoring the cache.",
    },
    "presiona_proyectar": {
        "es": "Presiona **{boton}** para ver los resultados.",
        "pt": "Clique em **{boton}** para ver os resultados.",
        "en": "Click **{boton}** to see the results.",
    },
    "error_proyeccion": {
        "es": "No se pudo generar la proyección: {error}",
        "pt": "Não foi possível gerar a projeção: {error}",
        "en": "The projection could not be generated: {error}",
    },

    "que_es_esto": {
        "es": "¿Qué es esto?",
        "pt": "O que é isto?",
        "en": "What is this?",
    },
    "texto_que_es_esto": {
        "es": "Este tablero es un caso de uso de la API de ISI | CEIC, no un "
              "producto de research. Todas las series se extraen en vivo desde "
              "la API y alimentan modelos de proyección construidos con las "
              "variables que definió el equipo de research.\n\n"
              "Lo que se demuestra es la infraestructura: un cliente puede "
              "montar tableros como este —para su materia prima, su indicador "
              "macro o su variable interna— con datos de CEIC y ver todo el "
              "análisis del modelo. Los modelos que se muestran son un ejemplo "
              "de lo que se puede construir, no la mejor especificación "
              "posible de cada indicador.",
        "pt": "Este painel é um caso de uso da API da ISI | CEIC, não um produto "
              "de research. Todas as séries são extraídas ao vivo da API e "
              "alimentam modelos de projeção construídos com as variáveis "
              "definidas pelo time de research.\n\n"
              "O que se demonstra é a infraestrutura: um cliente pode montar "
              "painéis como este —para sua matéria-prima, seu indicador macro "
              "ou sua variável interna— com dados da CEIC e ver toda a análise "
              "do modelo. Os modelos mostrados são um exemplo do que dá para "
              "construir, não a melhor especificação possível de cada indicador.",
        "en": "This dashboard is a use case for the ISI | CEIC API, not a "
              "research product. Every series is pulled live from the API and "
              "feeds projection models built with the variables defined by the "
              "research team.\n\n"
              "What it demonstrates is the infrastructure: a client can build "
              "dashboards like this one —for their commodity, their macro "
              "indicator or their own internal variable— with CEIC data and see "
              "the full model analysis. The models shown are an example of what "
              "can be built, not the best possible specification for each "
              "indicator.",
    },
    # ---------- Cuadro de pasos ----------
    "pasos_proyeccion": {
        "es": "Pasos de la proyección — {target}",
        "pt": "Etapas da projeção — {target}",
        "en": "Projection steps — {target}",
    },
    "proyeccion_lista": {
        "es": "{target}: proyección lista.", "pt": "{target}: projeção pronta.",
        "en": "{target}: projection ready.",
    },

    # ---------- Detalle estadístico ----------
    "significancia_titulo": {
        "es": "**Significancia estadística ({h} adelante)** — qué variables "
              "mueven de verdad al indicador y cuáles no:",
        "pt": "**Significância estatística ({h} à frente)** — quais variáveis "
              "realmente movem o indicador e quais não:",
        "en": "**Statistical significance ({h} ahead)** — which variables "
              "actually move the indicator and which don't:",
    },
    "eleccion_indicador": {
        "es": "**Elección del indicador principal.** Se probaron {n} candidatos:",
        "pt": "**Escolha do indicador principal.** Foram testados {n} candidatos:",
        "en": "**Choosing the main indicator.** {n} candidates were tested:",
    },
    "col_indicador": {"es": "Indicador", "pt": "Indicador", "en": "Indicator"},
    "col_estado": {"es": "Estado", "pt": "Status", "en": "Status"},
    "col_r2_ajustado": {"es": "R² ajustado", "pt": "R² ajustado", "en": "Adjusted R²"},
    "col_observaciones": {"es": "Observaciones", "pt": "Observações", "en": "Observations"},
    "col_errores_estandar": {"es": "Errores estándar", "pt": "Erros padrão", "en": "Standard errors"},
    "col_variable": {"es": "Variable", "pt": "Variável", "en": "Variable"},
    "col_colinealidad": {"es": "Colinealidad", "pt": "Colinearidade", "en": "Collinearity"},
    "col_serie": {"es": "Serie", "pt": "Série", "en": "Series"},
    "col_bloque": {"es": "Bloque", "pt": "Bloco", "en": "Block"},
    "col_p_value": {"es": "p-value", "pt": "p-valor", "en": "p-value"},
    "col_mejora_error": {
        "es": "Mejora del error (%)", "pt": "Melhoria do erro (%)",
        "en": "Error improvement (%)",
    },
    "col_significativa": {"es": "Significativa", "pt": "Significativa", "en": "Significant"},
    "col_mejora_backtest": {
        "es": "Mejora el backtest", "pt": "Melhora o backtest", "en": "Improves the backtest",
    },
    "col_entra_modelo": {"es": "Entra al modelo", "pt": "Entra no modelo", "en": "Enters the model"},
    "col_significativo_95": {"es": "Significativo (95%)", "pt": "Significativo (95%)",
                              "en": "Significant (95%)"},
    "capacidad_explicativa": {
        "es": "**Capacidad explicativa por horizonte:**",
        "pt": "**Capacidade explicativa por horizonte:**",
        "en": "**Explanatory power by horizon:**",
    },
    "dataset_completo": {
        "es": "**Dataset completo usado para el modelo:**",
        "pt": "**Dataset completo usado no modelo:**",
        "en": "**Full dataset used by the model:**",
    },
    "descargar_dataset": {
        "es": "Descargar dataset (CSV)", "pt": "Baixar dataset (CSV)",
        "en": "Download dataset (CSV)",
    },
    "descargar_series": {
        "es": "Descargar todas las series descargadas (CSV)",
        "pt": "Baixar todas as séries baixadas (CSV)",
        "en": "Download all extracted series (CSV)",
    },
    "descargar_backtest": {
        "es": "Descargar backtest (CSV)", "pt": "Baixar backtest (CSV)",
        "en": "Download backtest (CSV)",
    },
    "caption_hac": {
        "es": "A horizontes largos las ventanas de proyección se solapan, así que "
              "los errores estándar usan la corrección de Newey-West.",
        "pt": "Em horizontes longos as janelas de projeção se sobrepõem, então "
              "os erros padrão usam a correção de Newey-West.",
        "en": "At long horizons the projection windows overlap, so standard "
              "errors use the Newey-West correction.",
    },

    # ---------- Tamizaje / diagnóstico ----------
    "series_adicionales_titulo": {
        "es": "**Series adicionales evaluadas.** {total} combinaciones de serie y "
              "horizonte; entraron al modelo {pasaron}.",
        "pt": "**Séries adicionais avaliadas.** {total} combinações de série e "
              "horizonte; entraram no modelo {pasaron}.",
        "en": "**Additional series evaluated.** {total} series-horizon "
              "combinations; {pasaron} entered the model.",
    },
    "ninguna_paso": {
        "es": "Ninguna serie adicional superó el criterio, así que el modelo se "
              "queda con {indicador} como único predictor.",
        "pt": "Nenhuma série adicional passou no critério, então o modelo fica "
              "com {indicador} como único preditor.",
        "en": "No additional series met the criterion, so the model keeps "
              "{indicador} as its only predictor.",
    },
    "aporte_individual": {
        "es": "**Aporte de cada serie.** Todas las series definidas por el equipo "
              "de research entran al modelo; esta tabla muestra cuánto agrega "
              "cada una por encima de mirar solo el propio indicador.",
        "pt": "**Contribuição de cada série.** Todas as séries definidas pelo time "
              "de research entram no modelo; esta tabela mostra quanto cada uma "
              "acrescenta além de olhar só o próprio indicador.",
        "en": "**Contribution of each series.** Every series defined by the "
              "research team enters the model; this table shows how much each "
              "one adds beyond looking at the indicator alone.",
    },
    "predictores_usados": {
        "es": "**Predictores del modelo:** {lista}",
        "pt": "**Preditores do modelo:** {lista}",
        "en": "**Model predictors:** {lista}",
    },
    "descartadas_colinealidad": {
        "es": "Se retiraron por duplicar la información de otra serie: {lista}.",
        "pt": "Foram retiradas por duplicar a informação de outra série: {lista}.",
        "en": "Removed for duplicating another series' information: {lista}.",
    },
    "series_sin_datos": {
        "es": "Sin datos utilizables en el período: {lista}.",
        "pt": "Sem dados utilizáveis no período: {lista}.",
        "en": "No usable data in the period: {lista}.",
    },

    # ---------- Leyendas de los gráficos ----------
    "leyenda_proyeccion": {"es": "Proyección", "pt": "Projeção", "en": "Projection"},
    "leyenda_rango": {
        "es": "Rango de confianza (95%)", "pt": "Intervalo de confiança (95%)",
        "en": "Confidence range (95%)",
    },
    "leyenda_real": {"es": "Real", "pt": "Real", "en": "Actual"},
    "leyenda_modelo": {
        "es": "Proyección del modelo", "pt": "Projeção do modelo", "en": "Model projection",
    },
    "leyenda_dato_oficial": {
        "es": "Dato oficial", "pt": "Dado oficial", "en": "Official figure",
    },
    "leyenda_estimado": {
        "es": "Estimado por el modelo", "pt": "Estimado pelo modelo",
        "en": "Estimated by the model",
    },

    # ---------- Unidades de los ejes ----------
    "eje_crecimiento_interanual": {
        "es": "Crecimiento interanual (%)", "pt": "Crescimento interanual (%)",
        "en": "Year-over-year growth (%)",
    },
    "eje_variacion_interanual": {
        "es": "Variación interanual (%)", "pt": "Variação interanual (%)",
        "en": "Year-over-year change (%)",
    },
    "eje_variacion_precio": {
        "es": "Variación % del precio", "pt": "Variação % do preço",
        "en": "Price change (%)",
    },

    # ---------- Nowcast: detalle ----------
    "precision_significancia": {
        "es": "**Precisión y significancia por corte:**",
        "pt": "**Precisão e significância por corte:**",
        "en": "**Accuracy and significance by cut-off:**",
    },
    "advertencias_nowcast": {
        "es": "El R² se calcula sobre todo el período, incluido 2020, así que sale "
              "inflado: el número que vale es el error del backtest. Además, la "
              "validación usa la serie de PIB ya revisada, no la primera "
              "estimación — es la práctica estándar, pero la operación real "
              "sería algo menos precisa.",
        "pt": "O R² é calculado sobre todo o período, incluindo 2020, então sai "
              "inflado: o número que vale é o erro do backtest. Além disso, a "
              "validação usa a série de PIB já revisada, não a primeira "
              "estimativa — é a prática padrão, mas a operação real seria um "
              "pouco menos precisa.",
        "en": "The R² is computed over the whole period, 2020 included, so it "
              "comes out inflated: the number that matters is the backtest "
              "error. The validation also uses the already-revised GDP series, "
              "not the first estimate — standard practice, but real-time "
              "operation would be somewhat less accurate.",
    },
    "resultados_backtest": {
        "es": "**Resultados completos del backtest:**",
        "pt": "**Resultados completos do backtest:**",
        "en": "**Full backtest results:**",
    },
    "modelo_conjunto_significativo": {
        "es": "**El modelo en conjunto sí es significativo** (p del test F = {p}), "
              "aunque las variables por separado no lo sean: es lo que pasa "
              "cuando dos predictores dicen casi lo mismo.",
        "pt": "**O modelo em conjunto é significativo** (p do teste F = {p}), "
              "mesmo que as variáveis isoladas não sejam: é o que acontece "
              "quando dois preditores dizem quase a mesma coisa.",
        "en": "**The model as a whole is significant** (F-test p = {p}), even "
              "if the individual variables aren't: that's what happens when "
              "two predictors say almost the same thing.",
    },
    "caption_colinealidad_severa": {
        "es": "Colinealidad severa (VIF > 10) en: {lista}. La proyección en "
              "conjunto sigue siendo válida, pero no se puede afirmar cuál de "
              "esas variables manda.",
        "pt": "Colinearidade severa (VIF > 10) em: {lista}. A projeção em "
              "conjunto continua válida, mas não dá para afirmar qual dessas "
              "variáveis manda.",
        "en": "Severe collinearity (VIF > 10) in: {lista}. The combined "
              "projection is still valid, but it can't be said which of those "
              "variables drives it.",
    },
    "caption_limite_series": {
        "es": "Se limita a 3 series adicionales por horizonte: con ~80 "
              "observaciones, más predictores producen un modelo que memoriza "
              "el pasado en vez de anticipar el futuro.",
        "pt": "Limita-se a 3 séries adicionais por horizonte: com ~80 "
              "observações, mais preditores produzem um modelo que memoriza o "
              "passado em vez de antecipar o futuro.",
        "en": "Capped at 3 additional series per horizon: with ~80 "
              "observations, more predictors produce a model that memorizes "
              "the past instead of anticipating the future.",
    },
})


# ======================================================================
# Nombres de series e indicadores
# ----------------------------------------------------------------------
# El catálogo guarda un solo nombre por serie (en español) porque es la
# clave con la que trabaja el equipo. Traducirlo en el catálogo obligaría
# a escribir tres nombres en cada entrada y a repetirlos en las que se
# comparten (el Brent aparece en tres modelos). Este diccionario traduce
# por NOMBRE, así una serie nueva que reutilice un nombre ya conocido
# queda traducida sin tocar nada.
#
# Una serie que no esté acá se muestra tal cual — se ve, no rompe.
# ======================================================================
SERIES_LABELS = {
    # --- objetivos ---
    "PIB de Colombia": {"pt": "PIB da Colômbia", "en": "Colombia GDP"},
    "PIB de Colombia — trimestre en curso": {
        "pt": "PIB da Colômbia — trimestre em curso",
        "en": "Colombia GDP — current quarter",
    },
    "PIB de Colombia — proyección a futuro": {
        "pt": "PIB da Colômbia — projeção futura",
        "en": "Colombia GDP — forward projection",
    },
    "PIB de Brasil": {"pt": "PIB do Brasil", "en": "Brazil GDP"},
    "PIB de Brasil a/a": {"pt": "PIB do Brasil a/a", "en": "Brazil GDP YoY"},
    "Inflación de Colombia": {"pt": "Inflação da Colômbia", "en": "Colombia inflation"},
    "Inflación de Brasil": {"pt": "Inflação do Brasil", "en": "Brazil inflation"},
    "Ventas de vehículos en Colombia": {
        "pt": "Vendas de veículos na Colômbia", "en": "Colombia vehicle sales",
    },
    "Exportaciones de Colombia": {
        "pt": "Exportações da Colômbia", "en": "Colombia exports",
    },
    "Exportaciones de Brasil": {"pt": "Exportações do Brasil", "en": "Brazil exports"},
    "Precio del acero en China": {
        "pt": "Preço do aço na China", "en": "Steel price in China",
    },

    # --- series ---
    "Índice de Seguimiento a la Economía (ISE)": {
        "pt": "Índice de Acompanhamento da Economia (ISE)",
        "en": "Economic Activity Index (ISE)",
    },
    "Índice de actividad económica": {
        "pt": "Índice de atividade econômica", "en": "Economic activity index",
    },
    "Producción Industrial": {"pt": "Produção industrial", "en": "Industrial production"},
    "Producción industrial": {"pt": "Produção industrial", "en": "Industrial production"},
    "Comercio al por Menor": {"pt": "Comércio varejista", "en": "Retail trade"},
    "Ventas retail": {"pt": "Vendas no varejo", "en": "Retail sales"},
    "Ventas industriales": {"pt": "Vendas industriais", "en": "Industrial sales"},
    "Consumo de electricidad": {
        "pt": "Consumo de eletricidade", "en": "Electricity consumption",
    },
    "Exportaciones": {"pt": "Exportações", "en": "Exports"},
    "Exportaciones totales": {"pt": "Exportações totais", "en": "Total exports"},
    "Inflación a/a": {"pt": "Inflação a/a", "en": "Inflation YoY"},
    "Índice de precios al productor": {
        "pt": "Índice de preços ao produtor", "en": "Producer price index",
    },
    "Tasa de cambio TRM": {"pt": "Taxa de câmbio", "en": "Exchange rate"},
    "Tasa de cambio": {"pt": "Taxa de câmbio", "en": "Exchange rate"},
    "Tasa de cambio real": {"pt": "Taxa de câmbio real", "en": "Real exchange rate"},
    "Precio de la gasolina": {"pt": "Preço da gasolina", "en": "Gasoline price"},
    "Precio de la electricidad": {"pt": "Preço da eletricidade", "en": "Electricity price"},
    "Expectativas de inflación": {
        "pt": "Expectativas de inflação", "en": "Inflation expectations",
    },
    "Índice de confianza del consumidor": {
        "pt": "Índice de confiança do consumidor", "en": "Consumer confidence index",
    },
    "Confianza del consumidor": {
        "pt": "Confiança do consumidor", "en": "Consumer confidence",
    },
    "Confianza del consumidor EEUU": {
        "pt": "Confiança do consumidor EUA", "en": "US consumer confidence",
    },
    "Confianza del consumidor China": {
        "pt": "Confiança do consumidor China", "en": "China consumer confidence",
    },
    "Ventas retail China": {"pt": "Vendas no varejo China", "en": "China retail sales"},
    "Producción industrial EEUU": {
        "pt": "Produção industrial EUA", "en": "US industrial production",
    },
    "Cartera de crédito al consumidor": {
        "pt": "Carteira de crédito ao consumidor", "en": "Consumer credit portfolio",
    },
    "Tasa de interés": {"pt": "Taxa de juros", "en": "Interest rate"},
    "Ventas de vehículos": {"pt": "Vendas de veículos", "en": "Vehicle sales"},
    "Producción de petróleo": {"pt": "Produção de petróleo", "en": "Oil production"},
    "Producción de soya": {"pt": "Produção de soja", "en": "Soybean production"},
    "Precio del Brent": {"pt": "Preço do Brent", "en": "Brent price"},
    "Precio del carbón": {"pt": "Preço do carvão", "en": "Coal price"},
    "Precio del café": {"pt": "Preço do café", "en": "Coffee price"},
    "Precio del acero (rebar, futuro 1er mes, SHFE)": {
        "pt": "Preço do aço (vergalhão, futuro 1º mês, SHFE)",
        "en": "Steel price (rebar, front-month future, SHFE)",
    },
    "Precio del carbón de coque (Tangshan)": {
        "pt": "Preço do carvão de coque (Tangshan)", "en": "Coking coal price (Tangshan)",
    },
    "Inventario de mineral de hierro en puerto": {
        "pt": "Estoque de minério de ferro em porto", "en": "Port iron ore inventory",
    },
    "Inventario de productos de acero (empresas grandes y medianas)": {
        "pt": "Estoque de produtos de aço (empresas grandes e médias)",
        "en": "Steel product inventory (large and medium enterprises)",
    },
    "Tasa de operación de altos hornos": {
        "pt": "Taxa de operação de altos-fornos", "en": "Blast furnace operating rate",
    },
    "Producción diaria de acero crudo (empresas grandes y medianas)": {
        "pt": "Produção diária de aço bruto (empresas grandes e médias)",
        "en": "Daily crude steel output (large and medium enterprises)",
    },

    # --- sufijos y términos que aparecen pegados a un nombre de serie ---
    "objetivo": {"pt": "objetivo", "en": "target"},
    "indicador principal": {"pt": "indicador principal", "en": "main indicator"},
    "Constante": {"pt": "Constante", "en": "Constant"},
}

# Sufijos entre paréntesis que el pipeline le pega al nombre de la serie
# ("Inflación a/a (objetivo)"). Se traducen aparte para no tener que
# duplicar cada nombre con y sin sufijo.
_SUFIJOS = ["objetivo", "indicador principal"]


def tl(label):
    """
    Traduce el NOMBRE de una serie, indicador o entrada del catálogo al
    idioma activo. Si no está en SERIES_LABELS devuelve el original.

    Maneja los sufijos que agrega el pipeline: "Inflación a/a (objetivo)"
    se traduce como nombre + sufijo, sin necesidad de una entrada propia.

    También traduce las frases del tipo "X del período actual", que salen
    de las etiquetas del modelo.
    """
    if not label:
        return label
    idioma = st.session_state.get("idioma", IDIOMA_DEFAULT)
    if idioma == IDIOMA_DEFAULT:
        return label

    texto = str(label).strip()

    for sufijo in _SUFIJOS:
        marca = f" ({sufijo})"
        if texto.endswith(marca):
            base = tl(texto[: -len(marca)])
            traducido = SERIES_LABELS.get(sufijo, {}).get(idioma, sufijo)
            return f"{base} ({traducido})"

    for cola, clave in ((" del período actual", "periodo_actual"),
                        (" del trimestre actual", "periodo_actual")):
        if texto.endswith(cola):
            base = tl(texto[: -len(cola)])
            plantilla = {"pt": "{} do período atual", "en": "{} in the current period"}
            return plantilla.get(idioma, "{} " + cola).format(base)

    if texto.endswith(" (YoY %)"):
        return f"{tl(texto[: -len(' (YoY %)')])} (YoY %)"

    return SERIES_LABELS.get(texto, {}).get(idioma, texto)


def tl_lista(labels, sep=", "):
    """Traduce una lista de nombres de series y la une para mostrarla."""
    return sep.join(tl(x) for x in labels)


def traducir_columna(serie_pandas):
    """Aplica tl() a una columna de pandas con nombres de series."""
    return serie_pandas.map(tl)


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
    Tres botones chicos (ES / PT / EN) para elegir el idioma directo, en
    vez del botón que avanzaba al siguiente en el orden es->pt->en->es
    (con 3 idiomas eso podía pedir hasta 2 clics para llegar al que se
    quería). El botón del idioma activo sale resaltado (type="primary",
    el naranja de marca de theme.py) y deshabilitado -- no hace nada
    clickearlo, así que ni se registra el click.

    Sigue funcionando para cualquier cantidad de idiomas sin tocar el
    código (recorre IDIOMAS_DISPONIBLES), por si se agrega un cuarto más
    adelante -- eso sí, con 4+ botones angostos conviene revisar que la
    columna donde se llama tenga espacio suficiente.

    key_sufijo evita choques de key cuando se llama más de una vez en la
    misma pantalla (ej. login y encabezado principal).
    """
    actual = st.session_state.get("idioma", IDIOMA_DEFAULT)
    cols = st.columns(len(IDIOMAS_DISPONIBLES))
    for col, codigo in zip(cols, IDIOMAS_DISPONIBLES):
        with col:
            es_actual = codigo == actual
            clicked = st.button(
                codigo.upper(),
                key=f"idioma_btn_{codigo}_{key_sufijo}",
                type="primary" if es_actual else "secondary",
                disabled=es_actual,
                use_container_width=True,
            )
            if clicked:
                st.session_state.idioma = codigo
                st.rerun()

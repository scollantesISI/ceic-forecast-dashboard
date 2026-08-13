"""
translation.py
-----------------
Textos de la interfaz en español y portugués, más el helper t() que
devuelve el texto en el idioma activo (guardado en st.session_state).

Cómo agregar un texto nuevo:
  1. Agrega la clave en TEXTS con sus dos versiones ("es" y "pt").
  2. Donde antes había el string suelto en español, usa t("esa_clave").

Cómo interpolar un valor dinámico (ej. el nombre de un indicador):
  TEXTS["saludo"] = {"es": "Hola {nombre}", "pt": "Olá {nombre}"}
  t("saludo", nombre="Ana")

Cómo agregar un tercer idioma más adelante (ej. inglés): solo agrega la
clave "en" a cada entrada de TEXTS — el helper t() no cambia.
"""

import streamlit as st

IDIOMA_DEFAULT = "es"
IDIOMAS_DISPONIBLES = {"es": "Español", "pt": "Português"}

TEXTS = {
    # ---------- Login ----------
    "app_title": {
        "es": "Proyección de indicadores económicos",
        "pt": "Projeção de indicadores econômicos",
    },
    "app_subtitle": {
        "es": "Anticipa el resultado de indicadores clave antes de que se "
              "publique el dato oficial, con datos que ISI | CEIC "
              "actualiza todos los días",
        "pt": "Antecipe o resultado de indicadores-chave antes da "
              "publicação do dado oficial, com dados que a ISI | CEIC "
              "atualiza todos os dias",
    },
    "usuario": {"es": "Usuario", "pt": "Usuário"},
    "contrasena": {"es": "Contraseña", "pt": "Senha"},
    "ingresar": {"es": "Ingresar", "pt": "Entrar"},
    "autenticando": {"es": "Autenticando...", "pt": "Autenticando..."},
    "error_login": {
        "es": "Error al iniciar sesión: {error}",
        "pt": "Erro ao iniciar sessão: {error}",
    },

    # ---------- Cabecera de la app principal ----------
    "cerrar_sesion": {"es": "Cerrar sesión", "pt": "Sair"},
    "main_title": {
        "es": "¿Hacia dónde va la economía?",
        "pt": "Para onde vai a economia?",
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
    },
    "que_proyectar": {
        "es": "¿Qué quieres proyectar?",
        "pt": "O que você quer projetar?",
    },

    # ---------- Genéricos reutilizados en varias pantallas ----------
    "si": {"es": "Sí", "pt": "Sim"},
    "no": {"es": "No", "pt": "Não"},
    "de_donde_salen_datos": {
        "es": "### ¿De dónde salen estos datos?",
        "pt": "### De onde vêm esses dados?",
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
    },
    "datos_recientes": {
        "es": "**Datos más recientes** (últimos {n} períodos del modelo):",
        "pt": "**Dados mais recentes** (últimos {n} períodos do modelo):",
    },
    "que_tan_bien_predice": {
        "es": "### ¿Qué tan bien predice el modelo?",
        "pt": "### O modelo prevê bem?",
    },
    "ver_detalle_estadistico": {
        "es": "Ver el detalle estadístico completo",
        "pt": "Ver o detalhe estatístico completo",
    },
    "qué_tanto_explica": {
        "es": "Qué tanto explica el modelo",
        "pt": "Quanto o modelo explica",
    },
    "le_gana": {"es": "¿Le gana?", "pt": "Supera?"},

    # ---------- Nowcast ----------
    "sin_ventaja_calendario": {
        "es": "**Sin ventaja de calendario en este momento.** {mensaje}",
        "pt": "**Sem vantagem de calendário neste momento.** {mensaje}",
    },
    "estimado_con_meses": {
        "es": "Estimado con {n} mes(es) de datos &nbsp;·&nbsp; el dato oficial "
              "aún no se publica",
        "pt": "Estimado com {n} mês(es) de dados &nbsp;·&nbsp; o dado oficial "
              "ainda não foi publicado",
    },
    "error_tipico_estimacion": {
        "es": "Error típico de esta estimación", "pt": "Erro típico desta estimativa",
    },
    "ultimo_dato_oficial": {
        "es": "Último dato oficial publicado: {valor}% ({trimestre}). Este número lo anticipa.",
        "pt": "Último dado oficial publicado: {valor}% ({trimestre}). Este número o antecipa.",
    },
    "cuanto_sabemos": {"es": "#### Cuánto sabemos, y cuándo", "pt": "#### Quanto sabemos, e quando"},
    "caption_error_baja": {
        "es": "El error baja a medida que salen más meses del trimestre. Todo "
              "medido con validación histórica: en cada trimestre se reentrena "
              "solo con datos anteriores y se compara contra lo que realmente dio.",
        "pt": "O erro cai à medida que mais meses do trimestre são publicados. "
              "Tudo medido com validação histórica: em cada trimestre o modelo "
              "é retreinado só com dados anteriores e comparado contra o que "
              "realmente aconteceu.",
    },
    "col_meses_publicados": {"es": "Meses publicados", "pt": "Meses publicados"},
    "col_error_tipico": {"es": "Error típico", "pt": "Erro típico"},
    "col_error_sin_2020": {"es": "Error sin 2020", "pt": "Erro sem 2020"},
    "col_mejor_que_esperar": {"es": "Mejor que esperar", "pt": "Melhor que esperar"},
    "col_trimestres_probados": {"es": "Trimestres probados", "pt": "Trimestres testados"},
    "real_vs_estimado": {
        "es": "### Real contra estimado, trimestre a trimestre",
        "pt": "### Real contra estimado, trimestre a trimestre",
    },
    "con_cuantos_meses": {
        "es": "Con cuántos meses del trimestre:", "pt": "Com quantos meses do trimestre:",
    },
    "col_trimestre": {"es": "Trimestre", "pt": "Trimestre"},
    "col_dato_oficial_pct": {"es": "Dato oficial (%)", "pt": "Dado oficial (%)"},
    "col_estimado_pct": {"es": "Estimado (%)", "pt": "Estimado (%)"},
    "col_diferencia_pp": {"es": "Diferencia (pp)", "pt": "Diferença (pp)"},
    "col_lo_que_se_sabia": {"es": "Lo que se sabía antes (%)", "pt": "O que já se sabia antes (%)"},
    "caption_dos_series_vivo": {
        "es": "Las dos series se descargan en vivo desde la API de CEIC. La "
              "frecuencia es la observada en los datos, no la etiqueta del catálogo.",
        "pt": "As duas séries são baixadas ao vivo da API da CEIC. A frequência "
              "é a observada nos dados, não a etiqueta do catálogo.",
    },

    # ---------- Caso macro (PIB) ----------
    "crecimiento_esperado": {
        "es": "Crecimiento esperado — {target}", "pt": "Crescimento esperado — {target}",
    },
    "rango_proximo": {
        "es": "Rango: {lo}% a {hi}% &nbsp;·&nbsp; próximo {periodo}",
        "pt": "Intervalo: {lo}% a {hi}% &nbsp;·&nbsp; próximo {periodo}",
    },
    "a_horizonte": {"es": "A {h}", "pt": "Em {h}"},
    "basado_en_indicador": {
        "es": "Basado en **{indicador}**, el indicador de mayor frecuencia con "
              "la relación más fuerte con {target}.",
        "pt": "Baseado em **{indicador}**, o indicador de maior frequência com "
              "a relação mais forte com {target}.",
    },
    "caption_banda_ensancha": {
        "es": "La banda se ensancha con el horizonte porque la certeza baja "
              "mientras más lejos se proyecta — el mismo formato que usan los "
              "bancos centrales.",
        "pt": "A faixa se alarga com o horizonte porque a certeza cai quanto "
              "mais longe se projeta — o mesmo formato usado pelos bancos centrais.",
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
    },
    "col_periodos_probados": {"es": "{periodo} probados", "pt": "{periodo} testados"},
    "col_error_modelo_rmse": {"es": "Error del modelo (RMSE)", "pt": "Erro do modelo (RMSE)"},
    "col_error_de": {"es": "Error de {rival}", "pt": "Erro de {rival}"},
    "col_mejora_pct": {"es": "Mejora (%)", "pt": "Melhoria (%)"},
    "ver_detalle_periodo": {
        "es": "Ver el detalle período a período del horizonte:",
        "pt": "Ver o detalhe período a período do horizonte:",
    },
    "caption_comportamiento_proximo": {
        "es": "Del comportamiento de {target} al próximo {periodo}",
        "pt": "Do comportamento de {target} no próximo {periodo}",
    },
    "mejora_vs_no_usar": {
        "es": "Mejora vs. no usar el modelo", "pt": "Melhoria vs. não usar o modelo",
    },
    "caption_en_horizonte": {"es": "En el horizonte de {h}", "pt": "No horizonte de {h}"},
    "periodos_de_historia": {"es": "{periodo} de historia", "pt": "{periodo} de histórico"},
    "caption_desde_anio": {"es": "Desde {anio}", "pt": "Desde {anio}"},

    # ---------- Caso commodity (acero) ----------
    "precio_esperado_en": {
        "es": "Precio esperado en {horizonte}", "pt": "Preço esperado em {horizonte}",
    },
    "rango_hoy": {
        "es": "Rango: {lo} a {hi} &nbsp;·&nbsp; hoy: {hoy}",
        "pt": "Intervalo: {lo} a {hi} &nbsp;·&nbsp; hoje: {hoy}",
    },
    "variacion_proyectada": {"es": "Variación proyectada", "pt": "Variação projetada"},
    "caption_ultimo_dato_acero": {
        "es": "Último dato disponible: {fecha}. Datos diarios y decadales de "
              "China Premium, alineados a semana.",
        "pt": "Último dado disponível: {fecha}. Dados diários e decadais da "
              "China Premium, alinhados por semana.",
    },
    "precio_proyectado_horizonte": {
        "es": "**Precio proyectado por horizonte:**", "pt": "**Preço projetado por horizonte:**",
    },
    "col_horizonte": {"es": "Horizonte", "pt": "Horizonte"},
    "col_precio_esperado": {"es": "Precio esperado", "pt": "Preço esperado"},
    "col_minimo_95": {"es": "Mínimo (95%)", "pt": "Mínimo (95%)"},
    "col_maximo_95": {"es": "Máximo (95%)", "pt": "Máximo (95%)"},
    "caption_reentrena_semana": {
        "es": "En cada semana histórica se reentrena el modelo usando solo "
              "resultados que ya se conocían en ese momento. El punto de "
              "comparación duro para un precio es suponer que se queda igual: "
              "si el modelo no le gana a eso, no aporta.",
        "pt": "Em cada semana histórica o modelo é retreinado usando só "
              "resultados que já eram conhecidos naquele momento. O ponto de "
              "comparação duro para um preço é supor que ele fica igual: se o "
              "modelo não supera isso, não agrega valor.",
    },
    "warning_no_gana_random_walk": {
        "es": "En este momento el modelo **no** le gana al supuesto de "
              "'el precio se queda igual' en ningún horizonte. Conviene "
              "revisar los independientes o acortar el horizonte antes de "
              "mostrarlo a un cliente.",
        "pt": "Neste momento o modelo **não** supera a hipótese de 'o preço "
              "fica igual' em nenhum horizonte. Vale revisar as variáveis "
              "independentes ou encurtar o horizonte antes de mostrar a um cliente.",
    },
    "info_gana_solo_en": {
        "es": "El modelo le gana al supuesto de 'el precio se queda igual' "
              "solo en: {horizontes}. En los demás horizontes conviene "
              "presentar la proyección como escenario, no como pronóstico.",
        "pt": "O modelo supera a hipótese de 'o preço fica igual' apenas em: "
              "{horizontes}. Nos demais horizontes, é melhor apresentar a "
              "projeção como cenário, não como previsão.",
    },
    "col_semanas_probadas": {"es": "Semanas probadas", "pt": "Semanas testadas"},
    "col_error_si_no_cambia": {
        "es": "Error si el precio no cambia", "pt": "Erro se o preço não mudar",
    },
    "col_error_si_repite": {
        "es": "Error si repite la variación actual", "pt": "Erro se repetir a variação atual",
    },
    "col_mejora_vs_no_cambio": {
        "es": "Mejora vs. no cambio (%)", "pt": "Melhoria vs. não mudar (%)",
    },
    "ver_detalle_semana": {
        "es": "Ver el detalle semana a semana del horizonte:",
        "pt": "Ver o detalhe semana a semana do horizonte:",
    },
    "caption_variacion_precio_a": {
        "es": "De la variación del precio a {h}", "pt": "Da variação do preço em {h}",
    },
    "mejor_mejora_vs_no_cambio": {
        "es": "Mejor mejora vs. no cambio", "pt": "Melhor ganho vs. não mudar",
    },
    "semanas_de_historia": {"es": "Semanas de historia", "pt": "Semanas de histórico"},
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
    Botón que alterna el idioma activo. Muestra el nombre del OTRO
    idioma (si está en español, el botón dice "Português" — al
    apretarlo, cambia a portugués). key_sufijo evita choques de key
    cuando se llama más de una vez en la misma pantalla (ej. login y
    encabezado principal).
    """
    actual = st.session_state.get("idioma", IDIOMA_DEFAULT)
    otro = next(i for i in IDIOMAS_DISPONIBLES if i != actual)
    if st.button(IDIOMAS_DISPONIBLES[otro], key=f"idioma_btn_{otro}_{key_sufijo}"):
        st.session_state.idioma = otro
        st.rerun()

"""
indicator_catalog.py
---------------------
Catálogo de "qué se puede proyectar". Es la capa que permite que el
usuario elija un indicador por nombre ("PIB de Colombia") sin saber qué
es un series_id de CEIC.

MODOS
  auto_select    -> el orquestador elige el indicador principal probando
                    candidatos, y luego evalúa una lista de series
                    adicionales para complementar. Es el caso del PIB.
  multi_feature  -> los independientes ya están definidos y se usan
                    todos juntos en un mismo modelo. Es el caso del
                    acero en China.

TRANSFORMACIONES (campo "transform") — cómo se lleva cada serie a algo
modelable. Elegir mal esto es la forma más fácil de sacar un R² alto que
no significa nada:
  "yoy"          nivel -> variación interanual %. Default para precios,
                 cantidades e índices con tendencia.
  "already_yoy"  la serie YA viene en % interanual desde CEIC. No se le
                 vuelve a aplicar nada (ej. Cartera de crédito a/a).
                 Recalcularla fue un error real que ya nos pasó con el
                 Domestic Credit.
  "level"        se usa el nivel tal cual. Solo para series que ya son
                 tasas o saldos de opinión acotados (confianza, tasa de
                 interés, expectativas de inflación): sacarle variación %
                 a un número que puede cruzar cero produce basura.
  "log_change"   diferencia de logaritmos sobre N períodos base. Precios
                 de alta frecuencia (acero).

LAGS (campo "lag_meses") — el rezago que reportó Samuel: con cuántos
meses de anticipación esa serie mueve al objetivo. No es decorativo:
decide en qué horizontes se prueba cada candidato, lo que reduce el
número de pruebas y baja el riesgo de encontrar "significancia" por puro
azar. None = contemporáneo (se prueba en todos los horizontes).

Para agregar un país/indicador nuevo alcanza con agregar una entrada acá.
"""

TARGET_CATALOG = {
    # ==================================================================
    # 0 — Nowcast del PIB (el caso con mejores resultados reales)
    # ==================================================================
    # Con walk-forward sobre 49 trimestres reales de Colombia, estimar el
    # trimestre EN CURSO con los meses de ISE ya publicados da:
    #     1 mes  -> error típico 1.51 pp  (63% mejor que el último PIB)
    #     2 meses-> error típico 1.01 pp  (76% mejor)
    #     3 meses-> error típico 0.43 pp  (90% mejor)
    # Contra eso, proyectar hacia adelante (entrada "pib_colombia") no le
    # gana de forma relevante ni a repetir el crecimiento actual.
    #
    # El valor no es solo la precisión: es la precisión multiplicada por
    # el tiempo que se gana. El pipeline mide esa ventaja de calendario
    # contra los datos reales en vez de suponerla.
    # ==================================================================
    "nowcast_pib_colombia": {
        "label": "PIB de Colombia — trimestre en curso",
        "mode": "nowcast",
        "country_id": "3070",
        "country_name": "Colombia",
        "base_frequency": "Q",
        "default_start_date": "2005-01-01",
        "unit_label": "Crecimiento interanual (%)",
        "period_label": "trimestre",
        "meses_a_probar": (1, 2, 3),
        "target": {
            "label": "PIB de Colombia",
            "slug": "pib",
            "series_id": "403709667",   # trimestral real, sa
        },
        "indicador_mensual": {
            "label": "Índice de Seguimiento a la Economía (ISE)",
            "slug": "ise",
            "series_id": "403710187",   # mensual, sa
        },
    },

    # ==================================================================
    # 1 — PIB de Colombia (proyección hacia adelante)
    # ==================================================================
    "pib_colombia": {
        "label": "PIB de Colombia — proyección a futuro",
        "mode": "auto_select",
        "country_id": "3070",           # confirmado empíricamente
        "country_name": "Colombia",
        "target_keyword": "GDP real",
        "target_frequency": "Q",
        # ID fijo: si está, no se busca nada. La búsqueda de la serie
        # objetivo + las 4 de candidatos era buena parte de la espera.
        "target_series_id": "403709667",   # PIB trimestral real, sa
        "base_frequency": "Q",
        "default_start_date": "2005-01-01",
        "unit_label": "Crecimiento interanual (%)",
        "period_label": "trimestre",
        "horizons": [1, 2, 3, 4],       # Nicolás pidió mínimo 4 trimestres
        "max_horizon": 4,

        # IDs ya confirmados en corridas reales, por si se quiere saltar
        # la búsqueda: PIB sa = 403709667, PIB nsa = 403709817,
        # ISE sa = 403710187, ISE nsa = 403710177.
        # OJO con early_stop_r2: se calibró en 0.90 cuando el modelo era
        # contemporáneo (PIB(t) ~ ISE(t)) y daba R²≈0.99. En el modelo
        # actual, que proyecta PIB(t+h) desde lo conocido en t, el R²
        # real ronda 0.46 — el umbral NUNCA se alcanza y por eso siempre
        # se probaban los 4 candidatos. Con el ID del ISE fijo el punto
        # queda resuelto: se usa directo y no se prueba nada.
        "candidate_indicators": [
            {"label": "Índice de Seguimiento a la Economía (ISE)",
             "keyword": "Economic Activity Index", "series_id": "403710187"},
            {"label": "Producción Industrial", "keyword": "Industrial Production"},
            {"label": "Comercio al por Menor", "keyword": "Retail Sales"},
            {"label": "Exportaciones", "keyword": "Exports: Total"},
        ],

        # ------------------------------------------------------------------
        # Series adicionales para complementar el pronóstico (lo que pidió
        # Nicolás; los IDs y rezagos los mandó Samuel).
        #
        # Samuel las organizó en tres bloques —inflación, ventas de
        # vehículos y exportaciones— cada uno con su cabeza de bloque y
        # sus propios líderes. Acá TODAS entran como candidatas a
        # predictor del PIB: las cabezas de bloque son indicadores
        # mensuales de actividad y precios por derecho propio, y sus
        # líderes son series de más alta frecuencia que ya vienen
        # rezagadas respecto al ciclo.
        #
        # NO se meten todas juntas al modelo: 18 candidatas contra ~80
        # observaciones trimestrales sería sobreajuste garantizado. Se
        # prueban de a una (ver gdp_feature_screening.py) y solo pasan
        # las que son significativas Y mejoran el backtest walk-forward
        # — el mismo doble filtro que ya reprobó al petróleo.
        #
        # bloque: solo para agrupar en la tabla que se le muestra al
        # cliente; no afecta el modelo.
        # ------------------------------------------------------------------
        "candidate_features": [
            # --- bloque inflación ---
            {"label": "Inflación a/a", "slug": "inflacion", "bloque": "Inflación",
             "series_id": "412380767", "transform": "already_yoy", "lag_meses": None},
            {"label": "Índice de precios al productor", "slug": "ipp", "bloque": "Inflación",
             "series_id": "365745947", "transform": "yoy", "lag_meses": (2, 6)},
            {"label": "Precio de la gasolina", "slug": "gasolina", "bloque": "Inflación",
             "series_id": "507666517", "transform": "yoy", "lag_meses": (1, 1)},
            {"label": "Precio de la electricidad", "slug": "electricidad", "bloque": "Inflación",
             "series_id": "464864977", "transform": "yoy", "lag_meses": (1, 1)},
            {"label": "Expectativas de inflación", "slug": "expectativas", "bloque": "Inflación",
             "series_id": "206940602", "transform": "level", "lag_meses": None},

            # --- bloque ventas de vehículos ---
            {"label": "Ventas de vehículos", "slug": "vehiculos", "bloque": "Vehículos",
             "series_id": "449020167", "transform": "yoy", "lag_meses": None},
            # OJO: 234405303 ya se probó como líder del PIB en
            # test_leading_indicators.py y NO pasó. Se deja porque acá se
            # evalúa con otra especificación y otros horizontes, pero si
            # vuelve a reprobar, no insistir.
            {"label": "Índice de confianza del consumidor", "slug": "confianza", "bloque": "Vehículos",
             "series_id": "234405303", "transform": "level", "lag_meses": (2, 4)},
            {"label": "Cartera de crédito al consumidor", "slug": "cartera_consumo", "bloque": "Vehículos",
             "series_id": "245597403", "transform": "already_yoy", "lag_meses": None},
            {"label": "Tasa de interés", "slug": "tasa_interes", "bloque": "Vehículos",
             "series_id": "114129708", "transform": "level", "lag_meses": (4, 6)},

            # --- bloque exportaciones ---
            {"label": "Exportaciones totales", "slug": "exportaciones", "bloque": "Exportaciones",
             "series_id": "113861408", "transform": "yoy", "lag_meses": None},
            {"label": "Producción de petróleo", "slug": "prod_petroleo", "bloque": "Exportaciones",
             "series_id": "561816207", "transform": "yoy", "lag_meses": None},
            {"label": "Precio del Brent", "slug": "brent", "bloque": "Exportaciones",
             "series_id": "42651501", "transform": "yoy", "lag_meses": (1, 2)},
            {"label": "Precio del carbón", "slug": "carbon", "bloque": "Exportaciones",
             "series_id": "508347897", "transform": "yoy", "lag_meses": (1, 2)},
            {"label": "Precio del café", "slug": "cafe", "bloque": "Exportaciones",
             "series_id": "508345627", "transform": "yoy", "lag_meses": (3, 4)},
            {"label": "Tasa de cambio real", "slug": "tcr", "bloque": "Exportaciones",
             "series_id": "367504067", "transform": "yoy", "lag_meses": (1, 6)},
            {"label": "Producción industrial EEUU", "slug": "prod_ind_eeuu", "bloque": "Exportaciones",
             "series_id": "465764897", "transform": "yoy", "lag_meses": (4, 6)},
            {"label": "Confianza del consumidor EEUU", "slug": "confianza_eeuu", "bloque": "Exportaciones",
             "series_id": "41044301", "transform": "level", "lag_meses": (4, 6)},

            # --- transversal (aparece en dos bloques de Samuel) ---
            {"label": "Tasa de cambio TRM", "slug": "trm", "bloque": "Transversal",
             "series_id": "857382067", "transform": "yoy", "lag_meses": (4, 6)},
        ],
    },

    # ==================================================================
    # 2 — Precio del acero en China (commodity de alta frecuencia)
    # ==================================================================
    # CAMBIO (ago-2026, pedido de Nicolás): el objetivo pasa a ser el
    # precio de liquidación diario del rebar en la Bolsa de Futuros de
    # Shanghái. La serie anterior (36 City Avg) resultó ser MENSUAL, no
    # diaria — sobre una grilla semanal el objetivo solo tenía dato 1 de
    # cada ~4 semanas, así que el modelo venía corriendo con una fracción
    # de las observaciones que aparentaba tener.
    #
    # Grilla SEMANAL con horizonte hasta 26 semanas (~6 meses), que es lo
    # que pidió Nicolás. Consecuencia estadística: los targets acumulados
    # se solapan (la ventana de 26 semanas de una fila comparte 25 con la
    # siguiente), así que los errores estándar OLS clásicos salen
    # demasiado angostos. Por eso el modelo usa errores HAC/Newey-West en
    # los horizontes largos — ver multi_horizon_forecast.py.
    # ==================================================================
    "acero_china": {
        "label": "Precio del acero en China",
        "mode": "multi_feature",
        "country_id": None,             # pendiente confirmar geo ID de China
        "country_name": "China",
        "base_frequency": "W",          # grilla semanal (W-FRI)
        "default_start_date": "2015-01-01",
        "unit_label": "Variación % del precio",
        "period_label": "semana",
        # Se ajustan todos los horizontes 1..26, pero al cliente se le
        # muestran los hitos mensuales: así piensa el negocio.
        "horizons": [4, 9, 13, 17, 22, 26],
        "max_horizon": 26,

        "target": {
            "label": "Precio del acero (rebar, futuro 1er mes, SHFE)",
            "slug": "precio_acero",
            "full_name": "CN: Settlement Price: Shanghai Future Exchange: Steel Rebar: First Month",
            "search_keyword": "Settlement Price Shanghai Future Exchange Steel Rebar",
            "series_id": "251945901",   # diaria, RMB/Ton, SHFE
            "transform": "log_change",
        },

        # Objetivo anterior, dejado como referencia. NO usar como target
        # en grilla semanal: es mensual.
        "target_alternativo_mensual": {
            "label": "Precio del acero (36 ciudades, redondo 16mm Q235)",
            "full_name": "CN: Transaction Price: 36 City Avg: Round Steel: 16mm, Q235",
            "series_id": "252527401",   # MENSUAL, RMB/Ton, NDRC
        },

        "features": [
            {"label": "Precio del carbón de coque (Tangshan)",
             "slug": "carbon_coque",
             "full_name": "CN: Coking Coal Price: Factory Price: Coking Coal: Tangshan",
             "search_keyword": "Coking Coal Price Factory Price Tangshan",
             "series_id": "532020457",  # diaria, RMB/Ton, Custeel
             "transform": "log_change"},

            {"label": "Inventario de mineral de hierro en puerto",
             "slug": "inventario_hierro",
             "full_name": "CN: Iron Ore Inventory: Port",
             "search_keyword": "Iron Ore Inventory Port",
             "series_id": "317697101",  # Ton th, Custeel
             "transform": "log_change"},

            {"label": "Inventario de productos de acero (empresas grandes y medianas)",
             "slug": "inventario_acero",
             "full_name": "CN: Steel: Inventory: Large & Medium Enterprise: Steel Product",
             "search_keyword": "Steel Inventory Large Medium Enterprise Steel Product",
             "series_id": "384035557",  # Ton th, CISA
             # OJO: CEIC la marca "Daily, Everyday" pero NO llega diaria.
             # Los dos últimos datos son 20-jul y 31-jul-2026, y en total
             # tiene 342 observaciones -> publicación decadal (cada ~10
             # días). En la grilla semanal eso significa que ~2 de cada 3
             # semanas arrastran el último dato publicado por ffill, y su
             # variación se mueve a saltos. No invalida el feature (es lo
             # que un analista tendría en pantalla ese día), pero explica
             # por qué puede salir menos significativo que las series
             # realmente diarias. El pipeline verifica el espaciado real
             # de las 6 series y lo reporta.
             "transform": "log_change"},

            {"label": "Tasa de operación de altos hornos",
             "slug": "altos_hornos",
             "full_name": "CN: Operating Rate: Steel Factory Blast Furnace",
             "search_keyword": "Operating Rate Steel Factory Blast Furnace",
             "series_id": "528971047",  # diaria, %, Custeel
             "transform": "level"},     # ya es una tasa en %, acotada 0-100

            {"label": "Producción diaria de acero crudo (empresas grandes y medianas)",
             "slug": "produccion_acero",
             "full_name": "CN: Steel: Production: Daily: Crude Steel: Large & Medium Enterprise",
             "search_keyword": "Steel Production Daily Crude Steel Large Medium Enterprise",
             "series_id": "289907404",  # diaria, Ton th, CISA
             "transform": "log_change"},
        ],
    },
}


# ----------------------------------------------------------------------
# Helpers
# ----------------------------------------------------------------------
def candidatos_para_horizonte(target_config, horizonte, meses_por_periodo=3):
    """
    Candidatos cuyo rezago reportado alcanza a cubrir ese horizonte.

    La regla es de SOLAPAMIENTO de intervalos: el horizonte h cubre la
    ventana ((h-1)*meses, h*meses] y un candidato entra si su rango de
    rezago toca esa ventana. Un candidato sin lag_meses se considera
    contemporáneo y se prueba en todos.

    Ojo con la versión anterior de esta regla, que exigía
    lag_min <= meses <= lag_max: con el PIB trimestral los horizontes
    caen en 3, 6, 9 y 12 meses, así que las series de rezago corto que
    mandó Samuel —gasolina y electricidad (1 mes), Brent y carbón (1-2
    meses)— no calzaban con NINGÚN horizonte y quedaban fuera sin que
    nadie se enterara. Son líderes de rezago corto: su lugar natural es
    el horizonte más cercano, no el descarte. Samuel las eligió pensando
    en objetivos MENSUALES (inflación, vehículos, exportaciones), y al
    reusarlas contra un PIB trimestral hay que traducir la grilla, no
    ignorarlas.

    Restringir por rezago igual importa: probar 18 candidatas en 4
    horizontes son 72 pruebas, y al 5% de significancia unas 3-4 saldrían
    "significativas" por puro azar.
    """
    desde = (horizonte - 1) * meses_por_periodo
    hasta = horizonte * meses_por_periodo
    out = []
    for f in target_config.get("candidate_features", []):
        lag = f.get("lag_meses")
        if lag is None or (lag[0] <= hasta and lag[1] > desde):
            out.append(f)
    return out


def missing_series_ids(target_config):
    """Slugs sin series_id fijo — lo que todavía hay que resolver por búsqueda."""
    specs = []
    if target_config.get("target"):
        specs.append(target_config["target"])
    specs += list(target_config.get("features", []))
    specs += list(target_config.get("candidate_features", []))
    return [s["slug"] for s in specs if not s.get("series_id")]

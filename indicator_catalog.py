"""
indicator_catalog.py
---------------------
Catálogo de "qué se puede proyectar". Es la capa que permite que el
usuario elija un indicador por nombre ("PIB de Colombia") sin saber qué
es un series_id de CEIC.

MODOS
  nowcast        -> estimar el período EN CURSO antes de que salga el
                    dato oficial.
  auto_select    -> el orquestador elige el indicador principal probando
                    candidatos, y luego TAMIZA una lista de series
                    adicionales. Es el caso del PIB de Colombia.
  fixed_features -> los predictores ya están definidos por el equipo de
                    research y entran todos al modelo. El tamizaje se
                    sigue calculando, pero como DIAGNÓSTICO (se muestra
                    qué aporta cada uno), no como filtro que descarta.
  multi_feature  -> predictores fijos sobre grilla de alta frecuencia,
                    con alineación de series de distinta frecuencia. Es
                    el caso del acero en China.

CAMBIO (ago-2026, reunión con Nicolás y Samuel)
------------------------------------------------
Las tablas que mandó Samuel se estaban leyendo mal. Cada tabla NO es una
lista de insumos para el PIB: el título de cada tabla ES la serie a
proyectar, y las series de abajo son los predictores de ESA serie. Sus
palabras: "yo no te mandé esas series para pronosticar PIB, las que te
mandé eran para pronosticar las otras cosas".

Consecuencia: cada tabla se vuelve una entrada propia del catálogo
(inflación, ventas de vehículos, exportaciones — para Colombia y para
Brasil), en modo fixed_features. Meter las 18 al PIB era, además de una
mala lectura, parte de la razón por la que el tamizaje descartaba casi
todo: series elegidas para explicar la inflación mensual no tienen por
qué explicar el PIB trimestral.

Segundo cambio del mismo comentario de Nicolás: "no sé por qué la
descartas si el p-valor es de 0.009". En modo fixed_features el modelo
YA NO descarta por su cuenta — usa las variables que definió research y
muestra el aporte de cada una. El filtro estricto sigue disponible como
opción, pero deja de ser el comportamiento por defecto.

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

Ojo con las series cuyo nombre en la tabla de Samuel ya dice "a/a": van
como "already_yoy". La tabla de extracción del dashboard muestra la
transformación aplicada y el último valor de cada serie justamente para
poder cachar de un vistazo si alguna quedó mal clasificada (una serie
"already_yoy" que en realidad llega en niveles se nota al instante:
último valor de 5.400 en vez de 5,4).

LAGS (campo "lag_meses") — el rezago que reportó Samuel: con cuántos
meses de anticipación esa serie mueve al objetivo. Decide en qué
horizontes se prueba cada candidato en el modo auto_select y ordena la
tabla de diagnóstico en fixed_features. None = contemporáneo.

Para agregar un país/indicador nuevo alcanza con agregar una entrada acá.
"""

# ----------------------------------------------------------------------
# Predictores reutilizados en más de una entrada. Se definen una sola vez
# para que un cambio de ID o de transformación no haya que hacerlo en
# tres lugares y quedarse con dos versiones distintas.
# ----------------------------------------------------------------------
BRENT = {"label": "Precio del Brent", "slug": "brent",
         "series_id": "42651501", "transform": "yoy", "lag_meses": (1, 2)}
CAFE = {"label": "Precio del café", "slug": "cafe",
        "series_id": "508345627", "transform": "yoy", "lag_meses": (3, 4)}
PROD_IND_EEUU = {"label": "Producción industrial EEUU", "slug": "prod_ind_eeuu",
                 "series_id": "465764897", "transform": "yoy", "lag_meses": (4, 6)}
CONFIANZA_EEUU = {"label": "Confianza del consumidor EEUU", "slug": "confianza_eeuu",
                  "series_id": "41044301", "transform": "level", "lag_meses": (4, 6)}


TARGET_CATALOG = {
    # ==================================================================
    # 0 — Nowcast del PIB de Colombia (el caso con mejores resultados)
    # ==================================================================
    # Con walk-forward sobre 49 trimestres reales, estimar el trimestre
    # EN CURSO con los meses de ISE ya publicados da:
    #     1 mes  -> error típico 1.51 pp  (63% mejor que el último PIB)
    #     2 meses-> error típico 1.01 pp  (76% mejor)
    #     3 meses-> error típico 0.43 pp  (90% mejor)
    #
    # Nicolás lo dejó como el caso estándar de la demo: "me gustó mucho
    # más el primero, yo dejaría este como el modelo estándar".
    # ==================================================================
    "nowcast_pib_colombia": {
        "label": "PIB de Colombia — trimestre en curso",
        "grupo": "Colombia",
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
        "grupo": "Colombia",
        "mode": "auto_select",
        "country_id": "3070",           # confirmado empíricamente
        "country_name": "Colombia",
        "target_keyword": "GDP real",
        "target_frequency": "Q",
        "target_series_id": "403709667",   # PIB trimestral real, sa
        "base_frequency": "Q",
        "default_start_date": "2005-01-01",
        "unit_label": "Crecimiento interanual (%)",
        "period_label": "trimestre",
        "horizons": [1, 2, 3, 4],       # Nicolás pidió mínimo 4 trimestres
        "max_horizon": 4,

        # IDs ya confirmados en corridas reales: PIB sa = 403709667,
        # PIB nsa = 403709817, ISE sa = 403710187, ISE nsa = 403710177.
        "candidate_indicators": [
            {"label": "Índice de Seguimiento a la Economía (ISE)",
             "keyword": "Economic Activity Index", "series_id": "403710187"},
            {"label": "Producción Industrial", "keyword": "Industrial Production"},
            {"label": "Comercio al por Menor", "keyword": "Retail Sales"},
            {"label": "Exportaciones", "keyword": "Exports: Total"},
        ],

        # ------------------------------------------------------------------
        # Series adicionales para complementar el pronóstico.
        #
        # OJO (ago-2026): esta lista YA NO son "las tablas de Samuel".
        # Esas eran para otros objetivos y ahora viven en sus propias
        # entradas. Lo que queda acá es un puñado de series de actividad
        # y precios que sí tiene sentido probar como líderes del PIB
        # trimestral, y que se siguen tamizando de a una.
        #
        # No se meten todas juntas al modelo: con ~80 observaciones
        # trimestrales, más de 5-8 predictores es sobreajuste garantizado.
        # ------------------------------------------------------------------
        "candidate_features": [
            {"label": "Inflación a/a", "slug": "inflacion", "bloque": "Precios",
             "series_id": "412380767", "transform": "already_yoy", "lag_meses": None},
            {"label": "Tasa de interés", "slug": "tasa_interes", "bloque": "Precios",
             "series_id": "114129708", "transform": "level", "lag_meses": (4, 6)},
            {"label": "Tasa de cambio TRM", "slug": "trm", "bloque": "Precios",
             "series_id": "857382067", "transform": "yoy", "lag_meses": (4, 6)},
            {"label": "Índice de confianza del consumidor", "slug": "confianza",
             "bloque": "Demanda", "series_id": "234405303", "transform": "level",
             "lag_meses": (2, 4)},
            {"label": "Cartera de crédito al consumidor", "slug": "cartera_consumo",
             "bloque": "Demanda", "series_id": "245597403", "transform": "already_yoy",
             "lag_meses": None},
            {"label": "Ventas de vehículos", "slug": "vehiculos", "bloque": "Demanda",
             "series_id": "449020167", "transform": "yoy", "lag_meses": None},
            {"label": "Exportaciones totales", "slug": "exportaciones",
             "bloque": "Sector externo", "series_id": "113861408", "transform": "yoy",
             "lag_meses": None},
            dict(BRENT, bloque="Sector externo"),
            dict(PROD_IND_EEUU, bloque="Sector externo"),
        ],
    },

    # ==================================================================
    # 2 — Inflación de Colombia  (tabla 1 de Samuel)
    # ==================================================================
    "inflacion_colombia": {
        "label": "Inflación de Colombia",
        "grupo": "Colombia",
        "mode": "fixed_features",
        "country_id": "3070",
        "country_name": "Colombia",
        "base_frequency": "M",
        "default_start_date": "2005-01-01",
        "unit_label": "Variación interanual (%)",
        "period_label": "mes",
        # Cuatro horizontes, hasta 6 meses: es hasta donde llegan los
        # rezagos que reportó Samuel. Más allá de eso el trabajo lo hace
        # el término autorregresivo, no las series líderes.
        "horizons": [1, 2, 3, 6],
        "max_horizon": 6,
        "target": {
            "label": "Inflación a/a", "slug": "inflacion",
            "series_id": "412380767", "transform": "already_yoy",
        },
        "features": [
            {"label": "Índice de precios al productor", "slug": "ipp",
             "series_id": "365745947", "transform": "yoy", "lag_meses": (2, 6)},
            {"label": "Tasa de cambio TRM", "slug": "trm",
             "series_id": "857382067", "transform": "yoy", "lag_meses": (4, 6)},
            {"label": "Precio de la gasolina", "slug": "gasolina",
             "series_id": "507666517", "transform": "yoy", "lag_meses": (1, 1)},
            {"label": "Precio de la electricidad", "slug": "electricidad",
             "series_id": "464864977", "transform": "yoy", "lag_meses": (1, 1)},
            {"label": "Expectativas de inflación", "slug": "expectativas",
             "series_id": "206940602", "transform": "level", "lag_meses": None},
        ],
    },

    # ==================================================================
    # 3 — Ventas de vehículos en Colombia  (tabla 2 de Samuel)
    # ==================================================================
    "vehiculos_colombia": {
        "label": "Ventas de vehículos en Colombia",
        "grupo": "Colombia",
        "mode": "fixed_features",
        "country_id": "3070",
        "country_name": "Colombia",
        "base_frequency": "M",
        "default_start_date": "2005-01-01",
        "unit_label": "Variación interanual (%)",
        "period_label": "mes",
        "horizons": [1, 2, 3, 6],
        "max_horizon": 6,
        "target": {
            "label": "Ventas de vehículos", "slug": "vehiculos",
            "series_id": "449020167", "transform": "yoy",
        },
        "features": [
            {"label": "Índice de confianza del consumidor", "slug": "confianza",
             "series_id": "234405303", "transform": "level", "lag_meses": (2, 4)},
            {"label": "Tasa de cambio TRM", "slug": "trm",
             "series_id": "857382067", "transform": "yoy", "lag_meses": (4, 6)},
            {"label": "Cartera de crédito al consumidor", "slug": "cartera_consumo",
             "series_id": "245597403", "transform": "already_yoy", "lag_meses": None},
            {"label": "Tasa de interés", "slug": "tasa_interes",
             "series_id": "114129708", "transform": "level", "lag_meses": (4, 6)},
        ],
    },

    # ==================================================================
    # 4 — Exportaciones de Colombia  (tabla 3 de Samuel)
    # ==================================================================
    "exportaciones_colombia": {
        "label": "Exportaciones de Colombia",
        "grupo": "Colombia",
        "mode": "fixed_features",
        "country_id": "3070",
        "country_name": "Colombia",
        "base_frequency": "M",
        "default_start_date": "2005-01-01",
        "unit_label": "Variación interanual (%)",
        "period_label": "mes",
        "horizons": [1, 2, 3, 6],
        "max_horizon": 6,
        "target": {
            "label": "Exportaciones totales", "slug": "exportaciones",
            "series_id": "113861408", "transform": "yoy",
        },
        "features": [
            {"label": "Producción de petróleo", "slug": "prod_petroleo",
             "series_id": "561816207", "transform": "yoy", "lag_meses": None},
            dict(BRENT),
            {"label": "Precio del carbón", "slug": "carbon",
             "series_id": "508347897", "transform": "yoy", "lag_meses": (1, 2)},
            dict(CAFE),
            {"label": "Tasa de cambio real", "slug": "tcr",
             "series_id": "367504067", "transform": "yoy", "lag_meses": (1, 6)},
            dict(PROD_IND_EEUU),
            dict(CONFIANZA_EEUU),
        ],
    },

    # ==================================================================
    # 5 — PIB de Brasil  (tabla 1 del correo de Brasil)
    # ==================================================================
    # Nicolás: "así como estamos teniendo uno para Colombia, tener uno
    # para Brasil; con eso ellos, cuando lo tengan en Brasil y lo muestren
    # en portugués, digan: yo estoy creando ese de Brasil".
    #
    # country_id de Brasil: no se resolvió todavía, pero no hace falta —
    # todas las series traen ID fijo, así que no se ejecuta ninguna
    # búsqueda por keyword y el filtro de país nunca se usa.
    # ==================================================================
    "pib_brasil": {
        "label": "PIB de Brasil",
        "grupo": "Brasil",
        "mode": "fixed_features",
        "country_id": None,
        "country_name": "Brazil",
        "base_frequency": "Q",
        "default_start_date": "2005-01-01",
        "unit_label": "Crecimiento interanual (%)",
        "period_label": "trimestre",
        "horizons": [1, 2, 3, 4],
        "max_horizon": 4,
        "target": {
            "label": "PIB de Brasil a/a", "slug": "pib_br",
            "series_id": "366987777", "transform": "already_yoy",
        },
        # Seis predictores mensuales de actividad, todos contemporáneos.
        # Sobre ~80 trimestres eso ya es mucho, y varios se mueven casi
        # igual entre sí: el pipeline aplica un filtro de colinealidad y
        # reporta cuáles quedaron dentro y cuáles salieron por duplicadas.
        "features": [
            {"label": "Índice de actividad económica", "slug": "actividad_br",
             "series_id": "544340267", "transform": "yoy", "lag_meses": None},
            {"label": "Consumo de electricidad", "slug": "electricidad_br",
             "series_id": "1304601", "transform": "yoy", "lag_meses": None},
            {"label": "Producción industrial", "slug": "prod_ind_br",
             "series_id": "505806137", "transform": "yoy", "lag_meses": None},
            {"label": "Ventas industriales", "slug": "ventas_ind_br",
             "series_id": "356295387", "transform": "yoy", "lag_meses": None},
            {"label": "Ventas retail", "slug": "retail_br",
             "series_id": "505767847", "transform": "yoy", "lag_meses": None},
            {"label": "Confianza del consumidor", "slug": "confianza_br",
             "series_id": "373694597", "transform": "level", "lag_meses": None},
        ],
    },

    # ==================================================================
    # 6 — Inflación de Brasil  (tabla 2 del correo de Brasil)
    # ==================================================================
    "inflacion_brasil": {
        "label": "Inflación de Brasil",
        "grupo": "Brasil",
        "mode": "fixed_features",
        "country_id": None,
        "country_name": "Brazil",
        "base_frequency": "M",
        "default_start_date": "2005-01-01",
        "unit_label": "Variación interanual (%)",
        "period_label": "mes",
        "horizons": [1, 2, 3, 6],
        "max_horizon": 6,
        "target": {
            "label": "Inflación a/a", "slug": "inflacion_br",
            "series_id": "273491403", "transform": "already_yoy",
        },
        "features": [
            {"label": "Índice de precios al productor", "slug": "ipp_br",
             "series_id": "414008647", "transform": "yoy", "lag_meses": (2, 6)},
            {"label": "Tasa de cambio", "slug": "fx_br",
             "series_id": "1330801", "transform": "yoy", "lag_meses": (4, 6)},
            # Semanal: to_base_frequency la promedia al mes.
            {"label": "Precio de la gasolina", "slug": "gasolina_br",
             "series_id": "255783202", "transform": "yoy", "lag_meses": (1, 1)},
            {"label": "Precio de la electricidad", "slug": "electricidad_precio_br",
             "series_id": "478098817", "transform": "yoy", "lag_meses": (1, 1)},
        ],
    },

    # ==================================================================
    # 7 — Exportaciones de Brasil  (tabla 3 del correo de Brasil)
    # ==================================================================
    "exportaciones_brasil": {
        "label": "Exportaciones de Brasil",
        "grupo": "Brasil",
        "mode": "fixed_features",
        "country_id": None,
        "country_name": "Brazil",
        "base_frequency": "M",
        "default_start_date": "2005-01-01",
        "unit_label": "Variación interanual (%)",
        "period_label": "mes",
        "horizons": [1, 2, 3, 6],
        "max_horizon": 6,
        "target": {
            "label": "Exportaciones totales", "slug": "exportaciones_br",
            "series_id": "1380001", "transform": "yoy",
        },
        "features": [
            {"label": "Producción de petróleo", "slug": "prod_petroleo_br",
             "series_id": "229192102", "transform": "yoy", "lag_meses": None},
            dict(BRENT),
            {"label": "Producción de soya", "slug": "soya_br",
             "series_id": "228948202", "transform": "yoy", "lag_meses": None},
            dict(CAFE),
            {"label": "Tasa de cambio real", "slug": "tcr_br",
             "series_id": "227507002", "transform": "yoy", "lag_meses": (1, 6)},
            dict(PROD_IND_EEUU),
            dict(CONFIANZA_EEUU),
            {"label": "Confianza del consumidor China", "slug": "confianza_china",
             "series_id": "5198401", "transform": "level", "lag_meses": (4, 6)},
            {"label": "Ventas retail China", "slug": "retail_china",
             "series_id": "5190601", "transform": "yoy", "lag_meses": (2, 4)},
        ],
    },

    # ==================================================================
    # 8 — Precio del acero en China (commodity de alta frecuencia)
    # ==================================================================
    # Grilla SEMANAL con horizonte hasta 26 semanas (~6 meses). Los
    # targets acumulados se solapan (la ventana de 26 semanas de una fila
    # comparte 25 con la siguiente), así que los errores estándar OLS
    # clásicos salen demasiado angostos: el modelo usa HAC/Newey-West en
    # los horizontes largos — ver multi_horizon_forecast.py.
    # ==================================================================
    "acero_china": {
        "label": "Precio del acero en China",
        "grupo": "Commodities",
        "mode": "multi_feature",
        "country_id": None,             # pendiente confirmar geo ID de China
        "country_name": "China",
        "base_frequency": "W",          # grilla semanal (W-FRI)
        "default_start_date": "2015-01-01",
        "unit_label": "Variación % del precio",
        "period_label": "semana",
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
             # Publicación decadal (cada ~10 días): en la grilla semanal
             # ~2 de cada 3 semanas arrastran el último dato por ffill.
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
def meses_por_periodo(target_config):
    """Cuántos meses cubre un período de la frecuencia base del modelo."""
    return {"Q": 3, "M": 1, "W": 0.25}.get(target_config.get("base_frequency", "Q"), 3)


def features_del_modelo(target_config):
    """
    Los predictores de una entrada, sin que el llamador tenga que saber
    si el modo los guarda en "features" (fijos) o en "candidate_features"
    (a tamizar).
    """
    return list(target_config.get("candidate_features")
                or target_config.get("features") or [])


def candidatos_para_horizonte(target_config, horizonte, meses_por_periodo_=None):
    """
    Candidatos cuyo rezago reportado alcanza a cubrir ese horizonte.

    La regla es de SOLAPAMIENTO de intervalos: el horizonte h cubre la
    ventana ((h-1)*meses, h*meses] y un candidato entra si su rango de
    rezago toca esa ventana. Un candidato sin lag_meses se considera
    contemporáneo y se prueba en todos.

    Ojo con la versión anterior de esta regla, que exigía
    lag_min <= meses <= lag_max: con el PIB trimestral los horizontes
    caen en 3, 6, 9 y 12 meses, así que las series de rezago corto
    —gasolina y electricidad (1 mes), Brent y carbón (1-2 meses)— no
    calzaban con NINGÚN horizonte y quedaban fuera sin que nadie se
    enterara. Son líderes de rezago corto: su lugar natural es el
    horizonte más cercano, no el descarte.

    meses_por_periodo_ ahora sale de la frecuencia base de la entrada
    (3 meses en trimestral, 1 en mensual). Con los objetivos mensuales de
    Samuel, dejarlo fijo en 3 habría vuelto a desalinear la grilla.
    """
    mpp = meses_por_periodo_ or meses_por_periodo(target_config)
    desde = (horizonte - 1) * mpp
    hasta = horizonte * mpp
    out = []
    for f in features_del_modelo(target_config):
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


def entradas_por_grupo():
    """
    {grupo: [claves]} para agrupar el selector de la app. Con 9 entradas
    una lista plana ya se lee mal — y con Brasil adentro, el país es lo
    primero que busca un comercial.
    """
    grupos = {}
    for clave, cfg in TARGET_CATALOG.items():
        grupos.setdefault(cfg.get("grupo", "Otros"), []).append(clave)
    return grupos

"""
verificar_instalacion.py
--------------------------
Corre esto DESPUÉS de reemplazar archivos y ANTES de abrir el dashboard.
Tarda segundos y no toca la API de CEIC.

Existe por una razón concreta: los archivos del proyecto se han ido
actualizando por tandas, y basta con que uno quede en una versión
anterior para que la app falle con un mensaje que no dice nada útil
(el clásico "not enough values to unpack (expected 4, got 3)" es
exactamente eso: un archivo esperando otra versión de su vecino).

Qué verifica:
  1. Que todos los módulos importen.
  2. Que las funciones que se llaman entre módulos tengan la forma que
     el llamador espera (número de valores de retorno, parámetros).
  3. Que el catálogo esté completo y sin IDs faltantes.
  4. Que la traducción cubra los tres idiomas y todos los nombres de
     series — el punto que marcó Samuel en la reunión.

Uso:
    python verificar_instalacion.py
"""

import inspect
import sys

OK, FALLA, AVISO = "  [ok]  ", "  [FALLA]", "  [aviso]"

errores, avisos = [], []


def revisar(nombre, condicion, detalle="", arreglo=""):
    if condicion:
        print(f"{OK} {nombre}")
    else:
        print(f"{FALLA} {nombre}")
        if detalle:
            print(f"          {detalle}")
        if arreglo:
            print(f"          -> {arreglo}")
        errores.append(nombre)


def avisar(nombre, detalle):
    print(f"{AVISO} {nombre}")
    print(f"          {detalle}")
    avisos.append(nombre)


print("=" * 78)
print("VERIFICACIÓN DE ARCHIVOS DEL PROYECTO")
print("=" * 78)

# ----------------------------------------------------------------------
print("\n1. Módulos")
modulos = {}
for nombre in ["indicator_catalog", "gdp_data_manager", "multi_horizon_forecast",
               "gdp_feature_screening", "forecast_orchestrator", "steel_pipeline",
               "nowcast_pipeline", "translation", "theme"]:
    try:
        modulos[nombre] = __import__(nombre)
        print(f"{OK} {nombre}.py")
    except Exception as e:
        print(f"{FALLA} {nombre}.py")
        print(f"          {type(e).__name__}: {e}")
        errores.append(nombre)

if errores:
    print("\nHay módulos que no importan. Arregla eso antes de seguir.")
    sys.exit(1)

# ----------------------------------------------------------------------
print("\n2. Contratos entre módulos")

# --- gdp_data_manager: frecuencia genérica (objetivos mensuales) -------
mgr = modulos["gdp_data_manager"].GDPForecastDataManager
revisar(
    "El manager agrega series a cualquier frecuencia (to_base_frequency)",
    hasattr(mgr, "to_base_frequency"),
    "Sin esto, un objetivo mensual se agrega a trimestre y se pierden 2 de cada 3 datos.",
    arreglo="Reemplaza gdp_data_manager.py.",
)
revisar(
    "build_model_dataset acepta 'freq'",
    "freq" in inspect.signature(mgr.build_model_dataset).parameters,
    arreglo="Reemplaza gdp_data_manager.py.",
)
if hasattr(mgr, "to_base_frequency"):
    revisar(
        "La variación interanual usa 12 períodos en mensual y 4 en trimestral",
        mgr.PERIODOS_POR_ANIO.get("M") == 12 and mgr.PERIODOS_POR_ANIO.get("Q") == 4,
        "Con 4 fijo, la inflación mensual salía como 'variación a 4 meses'.",
        arreglo="Reemplaza gdp_data_manager.py.",
    )
revisar(
    "gdp_data_manager expone resumen_extraccion y series_largas",
    hasattr(modulos["gdp_data_manager"], "resumen_extraccion")
    and hasattr(modulos["gdp_data_manager"], "series_largas"),
    "series_largas es lo que alimenta el botón de descargar toda la data.",
    arreglo="Reemplaza gdp_data_manager.py.",
)
revisar(
    "resumen_extraccion acepta 'transformaciones'",
    "transformaciones" in inspect.signature(
        modulos["gdp_data_manager"].resumen_extraccion).parameters,
    "Es la columna que permite cachar una serie mal clasificada como already_yoy.",
    arreglo="Reemplaza gdp_data_manager.py.",
)

# --- tamizaje ----------------------------------------------------------
screening = modulos["gdp_feature_screening"]
fuente = inspect.getsource(screening.tamizar_candidatas)
revisar(
    "tamizar_candidatas devuelve 4 valores (incluye las series crudas)",
    "return df, seleccion, series, crudas" in fuente,
    "La versión anterior devolvía 3 y la tabla de extracción salía incompleta.",
    arreglo="Reemplaza gdp_feature_screening.py.",
)
revisar(
    "tamizar_candidatas acepta 'modo' (estricto / significancia / diagnóstico)",
    "modo" in inspect.signature(screening.tamizar_candidatas).parameters,
    "Sin esto vuelve el descarte de series con p-value bajo que marcó Nicolás.",
    arreglo="Reemplaza gdp_feature_screening.py.",
)
revisar(
    "Existe diagnostico_fijas (aporte por serie en modo fixed_features)",
    hasattr(screening, "diagnostico_fijas"),
    arreglo="Reemplaza gdp_feature_screening.py.",
)

# --- modelo ------------------------------------------------------------
mhf = modulos["multi_horizon_forecast"].MultiHorizonForecaster
firma = inspect.signature(mhf.__init__)
for parametro, para_que in [
    ("horizons", "lista explícita de horizontes"),
    ("hac_lags", "errores estándar HAC en horizontes largos"),
    ("benchmark", "benchmark correcto según el tipo de objetivo"),
]:
    revisar(
        f"MultiHorizonForecaster acepta '{parametro}' ({para_que})",
        parametro in firma.parameters,
        arreglo="Reemplaza multi_horizon_forecast.py.",
    )

for metodo in ("plot_fan_chart", "plot_backtest_bars"):
    revisar(
        f"{metodo} acepta 'labels' (leyendas traducidas)",
        "labels" in inspect.signature(getattr(mhf, metodo)).parameters,
        "Sin esto, la leyenda y el eje se quedan en español con la app en portugués.",
        arreglo="Reemplaza multi_horizon_forecast.py.",
    )

fuente_bt = inspect.getsource(mhf.backtest)
revisar(
    "El backtest corta el entrenamiento en i-h (sin fuga de información)",
    "i - h + 1" in fuente_bt,
    "Sin esto, los resultados a horizontes largos salen inflados.",
    arreglo="Reemplaza multi_horizon_forecast.py.",
)
revisar(
    "El backtest reporta los tres benchmarks (cero, persistencia, promedio)",
    "naive_mean" in fuente_bt,
    arreglo="Reemplaza multi_horizon_forecast.py.",
)

# --- orquestador -------------------------------------------------------
orq = modulos["forecast_orchestrator"]
fuente_orq = inspect.getsource(orq.run_forecast)
for modo in ["nowcast", "fixed_features", "multi_feature"]:
    revisar(
        f"El orquestador enruta el modo '{modo}'",
        f'"{modo}"' in fuente_orq,
        arreglo="Reemplaza forecast_orchestrator.py.",
    )
revisar(
    "Existe run_fixed_forecast (las tablas de Samuel)",
    hasattr(orq, "run_fixed_forecast"),
    arreglo="Reemplaza forecast_orchestrator.py.",
)

# --- acero -------------------------------------------------------------
fuente_steel = inspect.getsource(modulos["steel_pipeline"].build_steel_dataset)
revisar(
    "build_steel_dataset devuelve 5 valores (incluye las series crudas)",
    "return levels, dataset, feature_cols, auditoria, raw" in fuente_steel,
    "Con 4, run_steel_forecast falla con 'not enough values to unpack'.",
    arreglo="Reemplaza steel_pipeline.py (y forecast_orchestrator.py si hace falta).",
)
revisar(
    "plot_price_fan_chart acepta 'labels'",
    "labels" in inspect.signature(modulos["steel_pipeline"].plot_price_fan_chart).parameters,
    arreglo="Reemplaza steel_pipeline.py.",
)

# ----------------------------------------------------------------------
print("\n3. Catálogo")
cat = modulos["indicator_catalog"]
catalogo = cat.TARGET_CATALOG
faltan_ids = cat.missing_series_ids

esperadas = ["nowcast_pib_colombia", "pib_colombia", "inflacion_colombia",
             "vehiculos_colombia", "exportaciones_colombia",
             "pib_brasil", "inflacion_brasil", "exportaciones_brasil",
             "acero_china"]
for clave in esperadas:
    revisar(f"Existe la entrada '{clave}'", clave in catalogo,
            arreglo="Reemplaza indicator_catalog.py.")

revisar("El catálogo expone entradas_por_grupo() y features_del_modelo()",
        hasattr(cat, "entradas_por_grupo") and hasattr(cat, "features_del_modelo"),
        arreglo="Reemplaza indicator_catalog.py.")

for clave, cfg in catalogo.items():
    if cfg.get("mode") == "nowcast":
        continue
    faltantes = faltan_ids(cfg)
    if faltantes:
        avisar(f"'{clave}' tiene series sin ID fijo: {', '.join(faltantes)}",
               "Se resolverán por búsqueda, lo que hace la corrida más lenta.")

# Cada entrada fixed_features necesita objetivo + predictores + frecuencia
for clave, cfg in catalogo.items():
    if cfg.get("mode") != "fixed_features":
        continue
    ok = bool(cfg.get("target", {}).get("series_id")) and bool(cfg.get("features"))
    revisar(f"'{clave}' tiene objetivo y predictores definidos", ok,
            arreglo="Revisa esa entrada en indicator_catalog.py.")
    if cfg.get("base_frequency") not in ("Q", "M"):
        avisar(f"'{clave}' usa base_frequency='{cfg.get('base_frequency')}'",
               "Los modos de proyección macro están probados en 'Q' y 'M'.")

# ----------------------------------------------------------------------
print("\n4. Traducción")
tr = modulos["translation"]
revisar("translation expone tl() para nombres de series",
        hasattr(tr, "tl") and hasattr(tr, "SERIES_LABELS"),
        "Sin tl(), los nombres de las series se quedan en español en pt/en.",
        arreglo="Reemplaza translation.py.")

incompletas = [k for k, v in tr.TEXTS.items()
               if not all(i in v for i in ("es", "pt", "en"))]
revisar("Todos los textos tienen español, portugués e inglés",
        not incompletas,
        f"Sin los tres idiomas: {', '.join(incompletas[:5])}",
        arreglo="Completa esas claves en translation.py.")

if hasattr(tr, "SERIES_LABELS"):
    etiquetas = set()
    for cfg in catalogo.values():
        etiquetas.add(cfg["label"])
        for k in ("target", "indicador_mensual"):
            if cfg.get(k):
                etiquetas.add(cfg[k]["label"])
        for spec in cat.features_del_modelo(cfg):
            etiquetas.add(spec["label"])
        for c in cfg.get("candidate_indicators", []):
            etiquetas.add(c["label"])
    sin_traducir = sorted(e for e in etiquetas if e not in tr.SERIES_LABELS)
    if sin_traducir:
        avisar(f"{len(sin_traducir)} nombre(s) de serie sin traducción",
               "Se muestran en español en pt/en: " + ", ".join(sin_traducir[:4]))
    else:
        print(f"{OK} Las {len(etiquetas)} series del catálogo tienen traducción")

# ----------------------------------------------------------------------
print("\n" + "=" * 78)
if errores:
    print(f"RESULTADO: {len(errores)} problema(s). La app va a fallar hasta arreglarlos.")
    print("Archivos a reemplazar:", ", ".join(sorted(set(errores))))
    sys.exit(1)

print("RESULTADO: todo consistente.")
if avisos:
    print(f"({len(avisos)} aviso(s), no bloquean la corrida)")
print("\nSiguiente paso, para probar la lógica sin gastar llamadas a CEIC:")
print("    python prueba_offline_catalogo.py")

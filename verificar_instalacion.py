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
               "nowcast_pipeline", "theme"]:
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

# gdp_feature_screening.tamizar_candidatas debe devolver 4 valores
fuente = inspect.getsource(modulos["gdp_feature_screening"].tamizar_candidatas)
revisar(
    "tamizar_candidatas devuelve 4 valores (incluye las series crudas)",
    "return df, seleccion, series, crudas" in fuente,
    "La versión anterior devolvía 3 y la tabla de extracción salía incompleta.",
    "Reemplaza gdp_feature_screening.py por la versión más reciente.",
)

# MultiHorizonForecaster: horizontes por lista, HAC y benchmark
firma = inspect.signature(modulos["multi_horizon_forecast"].MultiHorizonForecaster.__init__)
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

fuente_bt = inspect.getsource(modulos["multi_horizon_forecast"].MultiHorizonForecaster.backtest)
revisar(
    "El backtest corta el entrenamiento en i-h (sin fuga de información)",
    "i - h + 1" in fuente_bt,
    "Sin esto, los resultados a horizontes largos salen inflados.",
    "Reemplaza multi_horizon_forecast.py.",
)
revisar(
    "El backtest reporta los tres benchmarks (cero, persistencia, promedio)",
    "naive_mean" in fuente_bt,
    arreglo="Reemplaza multi_horizon_forecast.py.",
)

# gdp_data_manager: helper compartido de extracción
revisar(
    "gdp_data_manager expone resumen_extraccion",
    hasattr(modulos["gdp_data_manager"], "resumen_extraccion"),
    arreglo="Reemplaza gdp_data_manager.py.",
)

# orquestador: los tres modos
fuente_orq = inspect.getsource(modulos["forecast_orchestrator"].run_forecast)
for modo in ["nowcast", "multi_feature"]:
    revisar(
        f"El orquestador enruta el modo '{modo}'",
        f'"{modo}"' in fuente_orq,
        arreglo="Reemplaza forecast_orchestrator.py.",
    )

# ----------------------------------------------------------------------
print("\n3. Catálogo")
catalogo = modulos["indicator_catalog"].TARGET_CATALOG
faltan_ids = modulos["indicator_catalog"].missing_series_ids

for clave in ["nowcast_pib_colombia", "pib_colombia", "acero_china"]:
    revisar(f"Existe la entrada '{clave}'", clave in catalogo,
            arreglo="Reemplaza indicator_catalog.py.")

for clave, cfg in catalogo.items():
    if cfg.get("mode") == "nowcast":
        continue
    faltantes = faltan_ids(cfg)
    if faltantes:
        avisar(f"'{clave}' tiene series sin ID fijo: {', '.join(faltantes)}",
               "Se resolverán por búsqueda, lo que hace la corrida más lenta.")
    else:
        print(f"{OK} '{clave}': todas las series con ID fijo")

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
print("    python prueba_regresion_pib.py")
print("    python prueba_regresion_acero.py")

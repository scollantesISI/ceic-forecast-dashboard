"""
discover_steel_series.py
--------------------------
PRIMER PASO del caso del acero — correr esto ANTES de tocar el dashboard.

Nicolás pasó los nombres tal como se ven en China Premium, pero el
catálogo de CEIC no siempre devuelve el nombre idéntico ni el mismo
código de frecuencia. Este script:

  1. Busca cada una de las 6 series por nombre y muestra los 5 mejores
     candidatos con su ID, nombre real, frecuencia y rango de fechas.
  2. Muestra el geo ID de China que aparece en los resultados (para
     poder fijarlo en indicator_catalog.py y que las búsquedas dejen de
     ir sin filtro de país).
  3. Imprime, listo para copiar y pegar, el bloque de series_id a fijar
     en el catálogo.

Con los IDs fijos, la app arranca en segundos en vez de hacer 6
búsquedas cada vez — el mismo problema de espera que ya tuvimos con los
4 candidatos del PIB.

Uso (sin credenciales en el archivo — ver nota al final):
    set CEIC_USER=...        (Windows: setx para dejarlo permanente)
    set CEIC_PASSWORD=...
    python discover_steel_series.py
"""

import os

import pandas as pd

from gdp_data_manager import GDPForecastDataManager
from indicator_catalog import TARGET_CATALOG

SHOW_COLS = ["id", "name", "frequency", "country", "start_date", "end_date", "match_score"]


def inspect_one(manager, spec, top_n=5):
    print("\n" + "=" * 100)
    print(f"{spec['label']}")
    print(f"  buscado: {spec['full_name']}")
    print(f"  keyword: {spec['search_keyword']}")

    candidates = manager.find_series_by_name(spec["full_name"], spec["search_keyword"])
    if candidates.empty:
        print("  -> SIN RESULTADOS. Prueba acortando el keyword "
              "(ej. solo 'Iron Ore Inventory').")
        return None

    cols = [c for c in SHOW_COLS if c in candidates.columns]
    print(candidates.head(top_n)[cols].to_string(index=False))

    best = candidates.iloc[0]
    if best["match_score"] < 0.6:
        print(f"  -> OJO: el mejor match saca solo {best['match_score']:.2f}. "
              f"Revisa a mano si de verdad es la serie que pidió Nico.")
    return best


def check_data(manager, series_id, label, start_date="2015-01-01"):
    """Confirma que la serie tenga datos y con qué frecuencia real llegan."""
    df = manager.fetch_series(series_id, start_date=start_date)
    if df.empty:
        print(f"  [{label}] sin datos desde {start_date}")
        return
    gaps = df["date"].diff().dt.days.dropna()
    print(f"  [{label}] {len(df)} datos, {df['date'].min().date()} a "
          f"{df['date'].max().date()}, espaciado típico: {gaps.median():.0f} días")


def run(ceic_client, start_date="2015-01-01"):
    cfg = TARGET_CATALOG["acero_china"]
    manager = GDPForecastDataManager(
        ceic_client, country_name=cfg.get("country_name"), country_id=cfg.get("country_id")
    )

    specs = [cfg["target"]] + cfg["features"]
    chosen = {}

    for spec in specs:
        best = inspect_one(manager, spec)
        if best is not None:
            chosen[spec["slug"]] = best

    print("\n" + "=" * 100)
    print("DISPONIBILIDAD DE DATOS")
    for spec in specs:
        best = chosen.get(spec["slug"])
        if best is not None:
            check_data(manager, str(best["id"]), spec["slug"], start_date)

    print("\n" + "=" * 100)
    print("PARA PEGAR EN indicator_catalog.py (reemplazar series_id=None):")
    for spec in specs:
        best = chosen.get(spec["slug"])
        sid = f'"{best["id"]}"' if best is not None else "None"
        print(f'    {spec["slug"]:22} -> "series_id": {sid},')

    countries = {c for c in
                 (best.get("country") for best in chosen.values()) if c}
    print(f"\nPaíses vistos en los resultados: {countries or 'n/d'}")
    print("Si todos dicen China, se puede fijar country_id en el catálogo "
          "y las búsquedas se vuelven más rápidas y precisas.")

    return pd.DataFrame([
        {"slug": slug, "id": row["id"], "name": row["name"],
         "frequency": row.get("frequency"), "match_score": row["match_score"]}
        for slug, row in chosen.items()
    ])


if __name__ == "__main__":
    from ceic_api_client.pyceic import Ceic

    # Credenciales por variable de entorno, no escritas en el archivo.
    # (Los scripts de la fase del PIB quedaron con usuario y contraseña
    # en texto plano dentro del código — conviene sacarlas de ahí antes
    # de compartir la carpeta con alguien más.)
    Ceic.login(os.environ["CEIC_USER"], os.environ["CEIC_PASSWORD"])
    run(Ceic)

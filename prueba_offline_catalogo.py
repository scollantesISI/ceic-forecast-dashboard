"""
prueba_offline_catalogo.py
----------------------------
Corre TODAS las entradas del catálogo contra un CEIC falso, con datos
sintéticos de la frecuencia correcta. No toca la API ni gasta llamadas.

Para qué sirve y para qué NO
-----------------------------
SÍ detecta: errores de frecuencia (un objetivo mensual tratado como
trimestral), columnas que no existen, retornos que cambiaron de forma,
transformaciones mal aplicadas, entradas del catálogo con campos
faltantes — o sea, exactamente los errores que aparecen al agregar
Brasil y los objetivos mensuales de Samuel.

NO dice nada sobre si los modelos son buenos: los datos son inventados.
Los números que salen acá no significan nada. Lo único que se está
probando es que el código corra de punta a punta en los cuatro modos.

Uso:
    python prueba_offline_catalogo.py
"""

import sys
import traceback

import numpy as np
import pandas as pd

from indicator_catalog import TARGET_CATALOG, features_del_modelo
from forecast_orchestrator import run_forecast

RNG = np.random.default_rng(42)

# Frecuencia real de cada serie sintética. La clave es que NO coincida
# siempre con la frecuencia base del modelo: en la vida real la TRM es
# diaria y el objetivo mensual, y ese desajuste es justo donde se rompen
# las cosas.
FREQ_POR_ID = {}


class SeriesFalsa:
    """Imita lo que devuelve Ceic.series_data(), lo justo para el manager."""

    def __init__(self, series_id, fechas, valores, nombre):
        self.metadata = type("M", (), {"id": series_id, "name": nombre})()
        self.time_points = [
            type("TP", (), {"date": str(d.date()), "value": float(v)})()
            for d, v in zip(fechas, valores)
        ]


class ResultadoFalso:
    def __init__(self, series):
        self.data = [series]


class CeicFalso:
    """
    Cliente falso. Genera una serie con tendencia + estacionalidad + ruido
    para cualquier ID que le pidan, con la frecuencia asignada en
    FREQ_POR_ID (mensual por defecto).
    """

    @staticmethod
    def series_data(series_id=None, series_metadata=None, **kwargs):
        sid = str(series_id)
        freq = FREQ_POR_ID.get(sid, "ME")
        fechas = pd.date_range("2004-01-01", "2026-06-30", freq=freq)
        n = len(fechas)
        t = np.arange(n)
        estacional = 3 * np.sin(2 * np.pi * t / (12 if freq in ("ME",) else 4))
        nivel = 100 + 0.05 * t + estacional + RNG.normal(0, 1.5, n)
        return ResultadoFalso(SeriesFalsa(sid, fechas, nivel, f"Serie {sid}"))

    @staticmethod
    def search(**kwargs):
        return []

    @staticmethod
    def geo(**kwargs):
        return []


def frecuencias_del_catalogo():
    """
    Le asigna a cada serie una frecuencia plausible: la del objetivo sale
    de base_frequency, y las series que en el catálogo se describen como
    diarias o semanales se generan así para probar el resample.
    """
    diarias = {"857382067", "507666517", "464864977", "42651501", "1330801",
                "251945901", "532020457", "317697101", "528971047", "289907404"}
    semanales = {"255783202", "384035557"}

    for cfg in TARGET_CATALOG.values():
        base = cfg.get("base_frequency", "Q")
        objetivo = cfg.get("target") or cfg.get("indicador_mensual")
        if objetivo and objetivo.get("series_id"):
            FREQ_POR_ID[str(objetivo["series_id"])] = {
                "Q": "QE", "M": "ME", "W": "W-FRI"
            }.get(base, "ME")
        if cfg.get("indicador_mensual"):
            FREQ_POR_ID[str(cfg["indicador_mensual"]["series_id"])] = "ME"
        if cfg.get("target_series_id"):
            FREQ_POR_ID[str(cfg["target_series_id"])] = "QE"
        for spec in features_del_modelo(cfg):
            sid = str(spec.get("series_id"))
            if sid in diarias:
                FREQ_POR_ID[sid] = "B"
            elif sid in semanales:
                FREQ_POR_ID[sid] = "W-FRI"
            else:
                FREQ_POR_ID.setdefault(sid, "ME")
        for c in cfg.get("candidate_indicators", []):
            if c.get("series_id"):
                FREQ_POR_ID[str(c["series_id"])] = "ME"


def probar(clave, cfg):
    modo = cfg.get("mode", "auto_select")
    kwargs = {"start_date": cfg.get("default_start_date", "2005-01-01")}
    if modo == "auto_select":
        # Sin tamizaje: son 9 candidatas x 4 horizontes con backtest, y
        # con datos falsos no aporta nada. El tamizaje se prueba aparte.
        kwargs["usar_series_adicionales"] = False

    res = run_forecast(CeicFalso, cfg, **kwargs)

    # Comprobaciones que valen para todos los modos
    assert "tabla_extraccion" in res, "falta la tabla de extracción"
    assert not res["tabla_extraccion"].empty, "tabla de extracción vacía"
    assert "dataset" in res and len(res["dataset"]) > 0, "dataset vacío"

    if modo == "nowcast":
        assert not res["tabla_precision"].empty
        return f"{len(res['tabla_precision'])} cortes evaluados"

    n_obs = len(res["dataset"])
    n_h = len(res["model"].horizon_results)
    detalle = f"{n_obs} obs, {n_h} horizontes"

    if modo == "fixed_features":
        usados = res.get("predictores_usados", [])
        assert usados, "el modelo quedó sin predictores"
        detalle += f", {len(usados)} predictores"
        fuera = res.get("descartadas_por_colinealidad") or []
        if fuera:
            detalle += f", {len(fuera)} fuera por colinealidad"
        assert not res["series_crudas"].empty, "no se devolvieron las series crudas"

    return detalle


def main():
    frecuencias_del_catalogo()
    print("=" * 78)
    print("PRUEBA OFFLINE DEL CATÁLOGO (datos sintéticos — los números no significan nada)")
    print("=" * 78)

    fallos = []
    for clave, cfg in TARGET_CATALOG.items():
        modo = cfg.get("mode", "auto_select")
        try:
            detalle = probar(clave, cfg)
            print(f"  [ok]   {clave:24} ({modo:14}) {detalle}")
        except Exception as e:
            print(f"  [FALLA] {clave:24} ({modo:14}) {type(e).__name__}: {e}")
            traceback.print_exc()
            fallos.append(clave)

    print("=" * 78)
    if fallos:
        print(f"RESULTADO: {len(fallos)} entrada(s) con problemas: {', '.join(fallos)}")
        sys.exit(1)
    print("RESULTADO: las 9 entradas corren de punta a punta.")


if __name__ == "__main__":
    main()

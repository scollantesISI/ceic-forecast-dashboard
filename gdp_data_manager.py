"""
gdp_data_manager.py
--------------------
Capa de datos para el modelo de proyección del PIB de Colombia.

Se apoya en PyCEIC (Ceic.search / Ceic.series_data / Ceic.geo) para extraer:
  - Serie objetivo: PIB real de Colombia (trimestral)
  - Series de alta frecuencia (mensuales) usadas como predictores en el
    modelo puente ("bridge equation")

Este manager solo se encarga de descubrir, extraer y transformar datos.
No decide ni ajusta el modelo (eso vive en gdp_bridge_model.py) — mismo
principio de separación que TradeDataManager en el proyecto de trade data.

NOTA IMPORTANTE (v2 — corregido después de probar contra tu sesión real):
.as_pandas() no existe en tu versión instalada de ceic_api_client, ni en
Ceic.geo() ('GeoResult') ni en Ceic.search() ('CeicSearchSeriesResult').
En vez de seguir adivinando dónde SÍ existe, este archivo dejó de usarlo
por completo y ahora parsea los resultados crudos exactamente como lo
hace tu propio TradeDataManager en series.py (que ya funciona en
producción):
  - Ceic.search(...) -> se recorre "for page in results: page.data.items"
    y cada item trae los datos en item.metadata (igual que
    _process_search_results).
  - Ceic.series_data(...) -> se recorre "for series in result.data" y
    cada serie trae metadata en series.metadata y valores en
    series.time_points (igual que _process_history_data).

Si algún atributo puntual no calza con tu versión exacta del SDK (ej.
algún campo viene en camelCase en vez de snake_case), el error va a ser
un AttributeError puntual y fácil de ubicar — mucho más manejable que un
método que no existe en absoluto.
"""

import pandas as pd


class GDPForecastDataManager:
    """
    Orquesta la extracción y preparación de datos para el modelo de
    proyección del PIB de Colombia.
    """

    # Punto de partida sugerido para el caso macro. IMPORTANTE: el
    # catálogo de CEIC está indexado en inglés (confirmado con los
    # resultados reales de find_gdp_series — todos los nombres salieron
    # en inglés), así que estos son los keywords a usar en la búsqueda,
    # no una traducción para mostrar en pantalla. Se validan/ajustan según
    # disponibilidad real en CEIC.
    DEFAULT_INDICATORS = {
        "ise": "Economic Activity Index",   # CEIC: "Economic Activity Index - ISE" para Colombia
        "industrial_production": "Industrial Production",
        "retail_sales": "Retail Sales",
        "exports": "Exports",
        "business_confidence": "Business Confidence",
        "unemployment_rate": "Unemployment Rate",
        "usdcop": "Exchange Rate",
    }

    def __init__(self, ceic_client, country_name="Colombia", country_id=None):
        """
        country_id: si ya conoces el ID de geo de CEIC para el país (ej.
        el que ya tienes cacheado en filters/geo_data.json del proyecto
        de trade data), pásalo aquí directamente y te saltas por completo
        la llamada a Ceic.geo().
        """
        self.ceic_client = ceic_client
        self.country_name = country_name
        self._country_id = country_id

    # ------------------------------------------------------------------
    # Helpers internos de parseo (mismo patrón que TradeDataManager)
    # ------------------------------------------------------------------
    @staticmethod
    def _iter_search_items(results):
        """
        Recorre un resultado de Ceic.search() o Ceic.geo() sin depender de
        .as_pandas(): itera "páginas" y, dentro de cada una, los items en
        .data.items — igual que TradeDataManager._process_search_results.

        FIX (ago-2026): Ceic.search() devuelve algo iterable (páginas),
        pero Ceic.geo() devuelve un GeoResult que NO lo es — iterarlo
        directo tumbaba la búsqueda con "'GeoResult' object is not
        iterable". Ahora se normaliza: si el resultado no es iterable se
        trata como una sola página, y si .data ya es una lista de items
        (sin .items adentro) también se recorre.
        """
        try:
            pages = iter(results)
        except TypeError:
            pages = iter([results])

        for page in pages:
            data = getattr(page, "data", page)
            items = getattr(data, "items", None)
            if items is None:
                # Algunas respuestas traen .data como lista de items
                # directamente (es el caso de GeoResult).
                if isinstance(data, (list, tuple)):
                    items = data
                else:
                    continue
            if callable(items):   # dict.items u otro método, no datos
                continue
            for item in items:
                yield item

    @staticmethod
    def _get(obj, *names, default=None):
        """
        Intenta varios nombres de atributo en orden (snake_case y
        camelCase conviven en distintas versiones del SDK — el propio
        TradeDataManager ya hace este mismo tipo de fallback para
        trade_code/tradeCode).
        """
        for name in names:
            if hasattr(obj, name):
                return getattr(obj, name)
        return default

    # ------------------------------------------------------------------
    # Descubrimiento de país (Ceic.geo)
    # ------------------------------------------------------------------
    def resolve_country_id(self, strict=True):
        """
        Resuelve el ID de geo de CEIC para el país objetivo (Colombia).
        Se cachea para no repetir la llamada en cada búsqueda. Si ya se
        pasó country_id al constructor, no llama a la API en absoluto.

        strict=False -> si no logra resolverlo devuelve None en vez de
        lanzar excepción. Se usa para el caso del acero en China, donde
        todavía no tenemos el geo ID confirmado: la búsqueda corre sin
        filtro de país y después se filtra por el nombre de la serie
        (todas empiezan con "CN:"). Cuando discover_steel_series.py
        confirme el ID, se pega en indicator_catalog.py y esta ruta deja
        de usarse.
        """
        if self._country_id is not None:
            return self._country_id

        if self.country_name is None:
            return None

        try:
            self._country_id = self._lookup_country_id()
        except Exception:
            if strict:
                raise
            return None   # sin filtro de país: la búsqueda igual funciona

        if self._country_id is not None:
            return self._country_id

        if not strict:
            return None

        raise ValueError(
            f"No se encontró geo ID para '{self.country_name}' vía Ceic.geo(). "
            f"Vía rápida: GDPForecastDataManager(Ceic, country_id=<ID>) "
            f"usando el ID que ya tienes en filters/geo_data.json."
        )

    def _lookup_country_id(self):
        """Busca el ID del país en Ceic.geo(). Devuelve None si no aparece."""
        geo_result = self.ceic_client.geo()
        target = self.country_name.strip().lower()

        for item in self._iter_search_items(geo_result):
            meta = self._get(item, "metadata", default=item)
            item_type = self._get(meta, "type")
            if item_type and str(item_type).upper() != "COUNTRY":
                continue

            title = self._get(meta, "title", "name")
            if title and str(title).strip().lower() == target:
                return str(self._get(meta, "id"))

        return None

    # ------------------------------------------------------------------
    # Descubrimiento de series (Ceic.search)
    # ------------------------------------------------------------------
    def _search_to_dataframe(self, keyword, frequency=None, limit=20):
        """
        frequency=None -> no se filtra por frecuencia. Necesario para las
        series de China Premium del caso del acero: son una mezcla de
        diaria, semanal y decadal (cada 10 días), y filtrar por "D" deja
        por fuera justo los inventarios y la tasa de operación.

        Si no hay geo ID resoluble, la búsqueda va sin filtro de país
        (ver resolve_country_id(strict=False)).
        """
        country_id = self.resolve_country_id(strict=False)

        kwargs = {
            "keyword": keyword,
            "status": ["T"],
            "limit": limit,  # acota resultados — keywords genéricos (ej.
                             # "Exports") pueden matchear miles de series
                             # desagregadas y volver la búsqueda muy lenta.
        }
        if frequency:
            kwargs["frequency"] = [frequency] if isinstance(frequency, str) else list(frequency)
        if country_id is not None:
            # OJO: el kwarg real de la API es 'geo', no 'region' (así lo
            # usa TradeDataManager y el ejemplo de la guía).
            kwargs["geo"] = [country_id]

        results = self.ceic_client.search(**kwargs)

        records = []
        for item in self._iter_search_items(results):
            meta = self._get(item, "metadata", default=item)
            item_id = self._get(meta, "id")
            if item_id is None:
                # Item sin metadata utilizable (le pasó a Santi con 2 de
                # 46 resultados del ISE) — se descarta en vez de meter
                # una fila en blanco que además fuerza la columna "id"
                # a float64 por los NaN.
                continue

            frequency_obj = self._get(meta, "frequency")
            country_obj = self._get(meta, "country")
            status_obj = self._get(meta, "status")

            records.append({
                "id": item_id,
                "name": self._get(meta, "name"),
                "frequency": self._get(frequency_obj, "name", "id"),
                "country": self._get(country_obj, "name"),
                "status": self._get(status_obj, "name"),
                "start_date": self._get(meta, "start_date", "startDate"),
                "end_date": self._get(meta, "end_date", "endDate"),
                "key_series": self._get(meta, "key_series", "keySeries"),
                "headline_series": self._get(meta, "headline_series", "headlineSeries"),
            })

        return pd.DataFrame(records)

    def find_gdp_series(self, keyword="GDP real", frequency="Q"):
        """
        Busca series candidatas de PIB real trimestral para el país.
        Devuelve un DataFrame para que el usuario elija manualmente la
        serie correcta (headline_series / key_series ayudan a identificar
        la oficial vs. sub-componentes).
        """
        return self._search_to_dataframe(keyword, frequency)

    def find_indicator_candidates(self, keyword, frequency="M"):
        """
        Busca series candidatas para un indicador de alta frecuencia dado
        (ej. 'ISE', 'Industrial Production', 'Retail Sales').
        """
        return self._search_to_dataframe(keyword, frequency)

    # ------------------------------------------------------------------
    # Resolución automática — para que el usuario nunca vea un series_id
    # ------------------------------------------------------------------
    @staticmethod
    def _pick_best_row(candidates, prefer_headline=False):
        """
        De una lista de candidatos, prioriza: headline_series=True (si se
        pide) -> versión ajustada estacionalmente ('sa' en el nombre) ->
        primer resultado. Mismo criterio que usamos a mano con el PIB y
        el ISE de Colombia (headline + sa), ahora automatizado.
        """
        pool = candidates
        if prefer_headline and "headline_series" in candidates.columns:
            headline = candidates[candidates["headline_series"] == True]  # noqa: E712
            if not headline.empty:
                pool = headline

        if "name" in pool.columns:
            sa = pool[pool["name"].astype(str).str.contains(r":\s*sa\b", case=False, na=False, regex=True)]
            if not sa.empty:
                return sa.iloc[0]

        return pool.iloc[0]

    def auto_resolve_target(self, target_keyword, target_frequency="Q"):
        """
        Resuelve automáticamente la serie oficial del indicador objetivo
        (ej. PIB) SIN mostrarle al usuario la lista de candidatos —
        aplica el mismo criterio (headline + sa) que se usó manualmente
        para elegir el PIB real de Colombia.
        """
        candidates = self._search_to_dataframe(target_keyword, target_frequency)
        if candidates.empty:
            raise ValueError(f"No se encontraron series para '{target_keyword}'.")
        return self._pick_best_row(candidates, prefer_headline=True)

    def try_candidate_indicator(self, keyword, frequency="M"):
        """
        Busca un indicador candidato y devuelve la mejor serie encontrada
        (o None si no hay resultados) — para que el orquestador pruebe
        varios candidatos y compare cuál explica mejor el objetivo, sin
        que el usuario tenga que elegir ni saber que esto está pasando.
        """
        candidates = self._search_to_dataframe(keyword, frequency)
        if candidates.empty:
            return None
        return self._pick_best_row(candidates, prefer_headline=False)

    # ------------------------------------------------------------------
    # Extracción de series ya identificadas (por series_id)
    # ------------------------------------------------------------------
    def fetch_series(self, series_id, start_date=None):
        """
        Trae timepoints (niveles) para una serie ya identificada.
        Parsea igual que TradeDataManager._process_history_data:
        result.data -> lista de series, cada una con .metadata y
        .time_points.

        series_id se normaliza a str (o lista de str) antes de llamar al
        SDK: si viene de un DataFrame de pandas (ej. candidatos.iloc[0]["id"])
        llega como numpy.int64, y el SDK de CEIC lo rechaza internamente
        con "Unsupported parameter value format" — solo acepta tipos
        nativos de Python, tal como se ve en los ejemplos de la guía
        (Ceic.series('210438802'), siempre como string).
        """
        if isinstance(series_id, (list, tuple, set)):
            series_id = [str(s) for s in series_id]
        else:
            series_id = str(series_id)

        kwargs = {}
        if start_date:
            kwargs["start_date"] = start_date

        result = self.ceic_client.series_data(series_id, **kwargs)

        records = []
        for series in result.data:
            meta = self._get(series, "metadata", default=series)
            series_name = self._get(meta, "name")
            series_id_value = self._get(meta, "id")

            time_points = self._get(series, "time_points", "timePoints", default=[])
            for tp in time_points:
                records.append({
                    "date": self._get(tp, "date"),
                    "value": self._get(tp, "value"),
                    "id": series_id_value,
                    "name": series_name,
                })

        df = pd.DataFrame(records)
        if not df.empty:
            df["date"] = pd.to_datetime(df["date"])
            df = df.sort_values("date").reset_index(drop=True)
        return df

    # ------------------------------------------------------------------
    # Transformaciones
    # ------------------------------------------------------------------
    @staticmethod
    def monthly_to_quarterly(df, value_col="value", date_col="date", how="mean"):
        """
        Agrega una serie MENSUAL en niveles a frecuencia trimestral.

        how="mean" -> promedio de los 3 meses del trimestre (default,
                       estándar para bridge equations)
        how="last" -> último mes disponible del trimestre (útil para
                       nowcasting cuando el trimestre aún está incompleto)
        """
        df = df.set_index(date_col)
        quarterly = df[value_col].resample("QE").agg(how)
        return quarterly.reset_index()

    @staticmethod
    def to_growth_rate(df, value_col="value", date_col="date",
                        frequency="Q", method="yoy"):
        """
        Convierte niveles (ya en frecuencia trimestral) en tasas de
        crecimiento.
          method="yoy" -> variación interanual (periods=4 en trimestral)
          method="qoq" -> variación intertrimestral (periods=1)

        Se aplica DESPUÉS de monthly_to_quarterly para los indicadores
        mensuales, y directamente sobre la serie de PIB (que ya viene
        trimestral desde CEIC).
        """
        df = df.sort_values(date_col).copy()
        periods = 4 if (method == "yoy" and frequency == "Q") else 1
        df["growth"] = df[value_col].pct_change(periods=periods) * 100
        return df.dropna(subset=["growth"])

    def build_model_dataset(self, gdp_growth_df, indicator_growth_dfs):
        """
        Combina el crecimiento del PIB (trimestral) con el crecimiento de
        cada indicador (ya agregado a trimestral vía monthly_to_quarterly
        + to_growth_rate) en un único DataFrame alineado por fecha, listo
        para el modelo.

        gdp_growth_df: DataFrame con columnas ["date", "growth"]
        indicator_growth_dfs: dict {nombre_indicador: DataFrame con
                                     columnas ["date", "growth"]}

        IMPORTANTE: el merge se hace por TRIMESTRE (pd.Period), no por
        fecha exacta. CEIC reporta el PIB con fecha de inicio de
        trimestre (ej. 2005-01-01), mientras que monthly_to_quarterly()
        genera fecha de FIN de trimestre para los indicadores mensuales
        (ej. 2005-03-31, por el resample("QE")). Si se juntara por fecha
        exacta, nunca haría match y el dataset saldría vacío — esto pasó
        con los datos reales de Colombia.
        """
        def with_quarter_key(df):
            df = df.copy()
            df["_quarter"] = pd.to_datetime(df["date"]).dt.to_period("Q")
            return df

        gdp = with_quarter_key(gdp_growth_df[["date", "growth"]])
        merged = gdp.rename(columns={"growth": "gdp_growth"})[
            ["_quarter", "date", "gdp_growth"]
        ]

        for name, df in indicator_growth_dfs.items():
            ind = with_quarter_key(df[["date", "growth"]])
            ind = ind.rename(columns={"growth": f"{name}_growth"})[
                ["_quarter", f"{name}_growth"]
            ]
            merged = merged.merge(ind, on="_quarter", how="left")

        return merged.drop(columns="_quarter").dropna().reset_index(drop=True)

    # ==================================================================
    # ALTA FRECUENCIA (diaria / semanal / decadal) — caso acero China
    # ------------------------------------------------------------------
    # El caso macro (PIB) resuelve series por keyword genérico y elige
    # "la mejor". Acá es al revés: Nicolás ya dio el NOMBRE EXACTO de las
    # 6 series de China Premium, así que lo que hace falta es encontrar
    # esa serie puntual entre los resultados de búsqueda — de ahí el
    # match por similitud de nombre en vez de "headline + sa".
    # ==================================================================
    @staticmethod
    def _normalize_name(name):
        """Nombre en minúsculas y sin puntuación, para comparar nombres
        de series de CEIC ('CN: Steel: Inventory: ...' vs lo que devuelve
        la búsqueda, que a veces cambia separadores o abreviaciones)."""
        import re
        return re.sub(r"[^a-z0-9 ]+", " ", str(name).lower()).split()

    @classmethod
    def _name_similarity(cls, candidate_name, full_name):
        """
        Puntaje 0-1 entre el nombre de un candidato y el nombre exacto
        que buscamos. Combina similitud de secuencia (difflib) con qué
        proporción de las palabras del nombre buscado aparecen en el
        candidato — esta segunda parte es la que evita elegir una serie
        parecida pero de otro producto (ej. "Round Steel 20mm" en vez de
        "16mm").
        """
        from difflib import SequenceMatcher

        cand_tokens = cls._normalize_name(candidate_name)
        want_tokens = cls._normalize_name(full_name)
        if not cand_tokens or not want_tokens:
            return 0.0

        seq = SequenceMatcher(None, " ".join(cand_tokens), " ".join(want_tokens)).ratio()
        covered = sum(1 for t in want_tokens if t in cand_tokens) / len(want_tokens)
        return round(0.4 * seq + 0.6 * covered, 4)

    def find_series_by_name(self, full_name, search_keyword=None, frequency=None, limit=40):
        """
        Busca por keyword corto y devuelve los candidatos ORDENADOS por
        qué tan parecido es su nombre al nombre exacto (full_name), con
        la columna match_score. Útil para inspeccionar a mano antes de
        fijar el series_id en el catálogo.
        """
        candidates = self._search_to_dataframe(
            search_keyword or full_name, frequency=frequency, limit=limit
        )
        if candidates.empty:
            return candidates
        candidates = candidates.copy()
        candidates["match_score"] = candidates["name"].apply(
            lambda n: self._name_similarity(n, full_name)
        )
        return candidates.sort_values("match_score", ascending=False).reset_index(drop=True)

    def resolve_series_by_name(self, full_name, search_keyword=None, frequency=None,
                                min_score=0.6):
        """
        Devuelve la fila de la serie que mejor calza con full_name, o
        None si ni el mejor candidato llega a min_score (mejor devolver
        nada que modelar en silencio con la serie equivocada).
        """
        candidates = self.find_series_by_name(full_name, search_keyword, frequency)
        if candidates.empty:
            return None
        best = candidates.iloc[0]
        return best if best["match_score"] >= min_score else None

    @staticmethod
    def resample_series(df, freq="W-FRI", how="mean", value_col="value", date_col="date"):
        """
        Lleva CUALQUIER serie (diaria, semanal, decadal) a una frecuencia
        común. Generaliza monthly_to_quarterly, que quedó atado al caso
        mensual->trimestral.

        how="mean" -> promedio del período (default; suaviza el ruido
                       diario del precio del acero)
        how="last" -> último dato del período (más cercano a "lo que se
                       sabía al cierre de la semana")
        """
        out = df[[date_col, value_col]].copy()
        out[date_col] = pd.to_datetime(out[date_col])
        out = out.set_index(date_col).sort_index()
        resampled = out[value_col].resample(freq).agg(how)
        return resampled.reset_index().rename(columns={date_col: "date", value_col: "value"})

    @staticmethod
    def period_change(df, periods=4, value_col="value", date_col="date", method="pct"):
        """
        Variación de una serie en niveles sobre 'periods' períodos de la
        frecuencia base (ej. con base semanal, periods=4 ≈ variación
        mensual).

        method="pct" -> variación porcentual
        method="log" -> diferencia de logaritmos * 100 (simétrica; útil
                        para precios, que se mueven en escala
                        multiplicativa)

        Por qué modelar variaciones y no niveles: el precio del acero es
        una serie no estacionaria. Una regresión en niveles saca R²
        altísimos que no significan nada (todas las series suben o bajan
        juntas en el tiempo) y no sobrevive un backtest. Todo el modelo
        del acero trabaja sobre variaciones.
        """
        import numpy as np

        out = df.sort_values(date_col).copy()
        if method == "log":
            out["growth"] = (np.log(out[value_col]) - np.log(out[value_col].shift(periods))) * 100
        else:
            out["growth"] = out[value_col].pct_change(periods=periods) * 100
        return out.dropna(subset=["growth"])[[date_col, "growth"]].rename(columns={date_col: "date"})

    def build_aligned_levels(self, series_map, freq="W-FRI", how="mean",
                              ffill_limit=8, no_ffill=()):
        """
        Alinea varias series de frecuencias distintas en una sola grilla
        de frecuencia 'freq', en NIVELES.

        series_map: {nombre: DataFrame crudo con [date, value]}
        no_ffill:   nombres que NO se rellenan hacia adelante (típicamente
                    la serie objetivo — rellenarla inventaría
                    observaciones que en realidad no se publicaron).

        El relleno es SOLO hacia adelante (último dato conocido), nunca
        hacia atrás: rellenar hacia atrás metería información del futuro
        en el pasado y el backtest quedaría inflado. Series como el
        inventario de puerto o la tasa de altos hornos se publican cada
        semana o cada 10 días, así que en la grilla semanal arrastran su
        último valor publicado — que es exactamente lo que un analista
        tendría en pantalla ese día.
        """
        aligned = None
        for name, df in series_map.items():
            s = self.resample_series(df, freq=freq, how=how).rename(columns={"value": name})
            aligned = s if aligned is None else aligned.merge(s, on="date", how="outer")

        aligned = aligned.sort_values("date").reset_index(drop=True)
        fill_cols = [c for c in aligned.columns if c != "date" and c not in no_ffill]
        aligned[fill_cols] = aligned[fill_cols].ffill(limit=ffill_limit)
        return aligned.dropna().reset_index(drop=True)

    @classmethod
    def build_change_dataset(cls, levels, target, features, periods=4, method="log"):
        """
        Convierte el DataFrame de niveles alineados (build_aligned_levels)
        en el dataset de variaciones que consume el modelo:
        columnas [date, target_change, <feature>_change...].
        """
        out = pd.DataFrame({"date": pd.to_datetime(levels["date"])})
        for col in [target] + list(features):
            change = cls.period_change(
                levels[["date", col]].rename(columns={col: "value"}),
                periods=periods, method=method,
            ).rename(columns={"growth": f"{col}_change"})
            out = out.merge(change, on="date", how="left")
        return out.dropna().reset_index(drop=True)


# ----------------------------------------------------------------------
# Ejemplo de uso (referencia, no ejecutar sin sesión CEIC activa)
# ----------------------------------------------------------------------
"""
from ceic_api_client.pyceic import Ceic
Ceic.login("user", "pass")

# Recomendado mientras seguimos validando el shape exacto de Ceic.geo():
# si ya tienes el ID de Colombia cacheado en filters/geo_data.json (del
# proyecto de trade data), pásalo directo y evita depender de geo():
manager = GDPForecastDataManager(Ceic, country_id="3070")

# 1. Descubrir la serie oficial de PIB real trimestral
candidatos_pib = manager.find_gdp_series()
print(candidatos_pib[["id", "name", "frequency", "headline_series"]])
# En la corrida real de Santi salieron dos con headline_series=True:
#   403709817  Gross Domestic Product (GDP): 2015p        (no ajustada)
#   403709667  Gross Domestic Product (GDP): 2015p: sa    (ajustada estacionalmente)
# Para el modelo puente conviene la versión "sa" (ajustada) — es la
# práctica estándar en nowcasting, aunque con crecimiento YoY el efecto
# estacional ya se cancela bastante igual. Confirmar cuál usar.
gdp_series_id = candidatos_pib.iloc[0]["id"]  # confirmar manualmente cuál es

# 2. Descubrir el ISE como indicador de alta frecuencia
# OJO: el catálogo de CEIC está en inglés — usar "Economic Activity Index"
# (o "ISE"), no la traducción al español.
candidatos_ise = manager.find_indicator_candidates("Economic Activity Index")
if candidatos_ise.empty:
    raise ValueError("Sin resultados — prueba con otro keyword, ej. 'ISE'")
print(candidatos_ise[["id", "name", "frequency"]])
ise_series_id = candidatos_ise.iloc[0]["id"]

# 3. Extraer y transformar
gdp_raw = manager.fetch_series(gdp_series_id, start_date="2005-01-01")
gdp_growth = manager.to_growth_rate(gdp_raw, frequency="Q", method="yoy")

ise_raw = manager.fetch_series(ise_series_id, start_date="2005-01-01")
ise_quarterly = manager.monthly_to_quarterly(ise_raw)
ise_growth = manager.to_growth_rate(ise_quarterly, frequency="Q", method="yoy")

# 4. Dataset final para el modelo
dataset = manager.build_model_dataset(gdp_growth, {"ise": ise_growth})
"""


# ----------------------------------------------------------------------
# Resumen de extracción — lo que Nicolás pidió mostrar explícitamente
# ----------------------------------------------------------------------
def resumen_extraccion(raw, etiquetas=None, ids=None):
    """
    Una fila por serie descargada: de dónde salió, cuántos datos trajo,
    qué período cubre, cada cuánto se publica de verdad y cuál es el dato
    más reciente.

    Nicolás pidió "mostrar con un poco más de detalle el proceso de
    extracción". Esta tabla es esa respuesta: hace visible que los datos
    salen de la API en vivo y no de un Excel, que es justamente lo que
    hay que demostrarle a un cliente.

    El espaciado se calcula de los datos, no de la etiqueta de CEIC:
    varias series dicen "Daily, Everyday" y llegan cada 10 días.

    raw:       {slug: DataFrame con [date, value]}
    etiquetas: {slug: nombre legible}
    ids:       {slug: series_id de CEIC}
    """
    etiquetas, ids = etiquetas or {}, ids or {}
    filas = []
    for slug, df in raw.items():
        if df is None or df.empty:
            filas.append({"serie": etiquetas.get(slug, slug), "slug": slug,
                          "id_ceic": ids.get(slug), "n_obs": 0,
                          "frecuencia_real": "sin datos"})
            continue

        d = df.sort_values("date")
        dias = d["date"].diff().dt.days.dropna()
        mediana = float(dias.median()) if len(dias) else float("nan")
        filas.append({
            "serie": etiquetas.get(slug, slug),
            "slug": slug,
            "id_ceic": ids.get(slug),
            "n_obs": len(d),
            "desde": d["date"].min().date(),
            "hasta": d["date"].max().date(),
            "espaciado_mediano_dias": round(mediana, 1) if mediana == mediana else None,
            "frecuencia_real": etiqueta_frecuencia(mediana),
            "ultimo_valor": round(float(d["value"].iloc[-1]), 2),
        })
    return pd.DataFrame(filas)


def etiqueta_frecuencia(dias_mediana):
    """Traduce el espaciado mediano observado a una etiqueta legible."""
    if dias_mediana != dias_mediana:   # NaN
        return "sin datos"
    if dias_mediana <= 1.5:
        return "diaria"
    if dias_mediana <= 4:
        return "días hábiles"
    if dias_mediana <= 8:
        return "semanal"
    if dias_mediana <= 15:
        return "decadal (~10 días)"
    if dias_mediana <= 40:
        return "mensual"
    if dias_mediana <= 110:
        return "trimestral"
    return "más lenta que trimestral"

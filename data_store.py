from __future__ import annotations

import os
from functools import lru_cache
from pathlib import Path
from typing import Iterable

import pandas as pd
import pyarrow.dataset as ds


BASE_DIR = Path(__file__).resolve().parent
OPTIMIZED_DIR = BASE_DIR / "assets" / "optimized"
WQX_PARQUET = OPTIMIZED_DIR / "wqx_measurements.parquet"
WQX_SITE_CATALOG = OPTIMIZED_DIR / "wqx_site_catalog.parquet"
WQX_METADATA = OPTIMIZED_DIR / "wqx_metadata.parquet"
USGS_PARQUET = OPTIMIZED_DIR / "usgs_daily.parquet"
USGS_SITE_CATALOG = OPTIMIZED_DIR / "usgs_site_catalog.parquet"


REBUILD_MESSAGE = (
    "Optimized Parquet assets are missing. Run: python scripts/build_optimized_assets.py"
)


def optimized_assets_available() -> bool:
    return WQX_PARQUET.exists() and WQX_SITE_CATALOG.exists() and WQX_METADATA.exists()


def require_optimized_assets() -> None:
    missing = [p for p in [WQX_PARQUET, WQX_SITE_CATALOG, WQX_METADATA] if not p.exists()]
    if missing:
        missing_names = ", ".join(str(p.relative_to(BASE_DIR)) for p in missing)
        raise RuntimeError(f"{REBUILD_MESSAGE}. Missing: {missing_names}")


def _as_list(value) -> list:
    if value is None or value == "All" or value == ["All"]:
        return []
    if isinstance(value, (list, tuple, set)):
        return [v for v in value if v and v != "All"]
    return [value]


def _and_filter(parts):
    parts = [part for part in parts if part is not None]
    if not parts:
        return None
    filt = parts[0]
    for part in parts[1:]:
        filt = filt & part
    return filt


@lru_cache(maxsize=1)
def get_site_catalog() -> pd.DataFrame:
    require_optimized_assets()
    return pd.read_parquet(WQX_SITE_CATALOG)


@lru_cache(maxsize=1)
def get_metadata() -> pd.DataFrame:
    require_optimized_assets()
    return pd.read_parquet(WQX_METADATA)


@lru_cache(maxsize=1)
def get_usgs_site_catalog() -> pd.DataFrame:
    if not USGS_SITE_CATALOG.exists():
        return pd.DataFrame()
    return pd.read_parquet(USGS_SITE_CATALOG)


def get_date_bounds() -> tuple[int, int]:
    metadata = get_metadata()
    values = dict(zip(metadata["key"], metadata["value"]))
    return int(values["min_year"]), int(values["max_year"])


def get_all_characteristics() -> list[str]:
    return sorted(get_metadata().loc[get_metadata()["key"] == "characteristic", "value"].dropna().tolist())


def get_fractions(characteristic=None, basin=None, sites=None) -> list[str]:
    columns = ["Result_SampleFraction"]
    if characteristic:
        filters = {"characteristic": characteristic, "basin": basin, "sites": sites}
        df = query_wqx(columns=columns, **filters)
        return sorted(df["Result_SampleFraction"].dropna().unique().tolist())
    return sorted(get_metadata().loc[get_metadata()["key"] == "fraction", "value"].dropna().tolist())


def get_sites(basin=None) -> list[str]:
    catalog = get_site_catalog()
    if basin and basin != "All" and "Basin" in catalog.columns:
        catalog = catalog[catalog["Basin"] == basin]
    return sorted(catalog["Location_Name"].dropna().unique().tolist())


def get_characteristics(basin=None, sites=None) -> list[str]:
    df = query_wqx(basin=basin, sites=sites, columns=["Result_Characteristic"])
    return sorted(df["Result_Characteristic"].dropna().unique().tolist())


def query_wqx(
    characteristic=None,
    fraction=None,
    basin=None,
    sites=None,
    sample_type=None,
    start_year=None,
    end_year=None,
    columns=None,
) -> pd.DataFrame:
    require_optimized_assets()
    wanted_columns = list(columns) if columns else None
    required_for_filters = ["Activity_Year"]
    if characteristic and characteristic != "All":
        required_for_filters.append("Result_Characteristic")
    if fraction and fraction != "All":
        required_for_filters.append("Result_SampleFraction")
    if basin and basin != "All":
        required_for_filters.append("Basin")
    if _as_list(sites):
        required_for_filters.append("Location_Name")
    if sample_type and sample_type != "All":
        required_for_filters.append("Activity_MediaSubdivision")
    if wanted_columns is not None:
        wanted_columns = sorted(set(wanted_columns) | set(required_for_filters))

    filters = []
    if characteristic and characteristic != "All":
        filters.append(ds.field("Result_Characteristic") == characteristic)
    if fraction and fraction != "All":
        filters.append(ds.field("Result_SampleFraction") == fraction)
    if basin and basin != "All":
        filters.append(ds.field("Basin") == basin)
    site_values = _as_list(sites)
    if site_values:
        filters.append(ds.field("Location_Name").isin(site_values))
    if sample_type and sample_type != "All":
        filters.append(ds.field("Activity_MediaSubdivision") == sample_type)
    if start_year is not None:
        filters.append(ds.field("Activity_Year") >= int(start_year))
    if end_year is not None:
        filters.append(ds.field("Activity_Year") <= int(end_year))

    table = ds.dataset(WQX_PARQUET, format="parquet").to_table(
        columns=wanted_columns,
        filter=_and_filter(filters),
    )
    df = table.to_pandas()
    if columns:
        keep = [col for col in columns if col in df.columns]
        df = df[keep]
    return df


def query_usgs(sites=None, parameter=None, start_year=None, end_year=None, columns=None) -> pd.DataFrame:
    if not USGS_PARQUET.exists():
        return pd.DataFrame()
    wanted_columns = list(columns) if columns else None
    required_for_filters = ["Year"]
    if _as_list(sites):
        required_for_filters.append("Site_Name")
    if parameter:
        required_for_filters.append(parameter)
    if wanted_columns is not None:
        wanted_columns = sorted(set(wanted_columns) | set(required_for_filters))

    filters = []
    site_values = _as_list(sites)
    if site_values:
        filters.append(ds.field("Site_Name").isin(site_values))
    if start_year is not None:
        filters.append(ds.field("Year") >= int(start_year))
    if end_year is not None:
        filters.append(ds.field("Year") <= int(end_year))
    if parameter:
        filters.append(ds.field(parameter).is_valid())

    table = ds.dataset(USGS_PARQUET, format="parquet").to_table(
        columns=wanted_columns,
        filter=_and_filter(filters),
    )
    df = table.to_pandas()
    if columns:
        keep = [col for col in columns if col in df.columns]
        df = df[keep]
    return df


def get_map_aggregates(**filters) -> pd.DataFrame:
    columns = [
        "Location_Name",
        "Location_LatitudeStandardized",
        "Location_LongitudeStandardized",
        "Result_Measure",
        "Result_Characteristic",
    ]
    df = query_wqx(columns=columns, **filters)
    if df.empty:
        return df
    return df.groupby("Location_Name", as_index=False, observed=True).agg(
        Location_LatitudeStandardized=("Location_LatitudeStandardized", "mean"),
        Location_LongitudeStandardized=("Location_LongitudeStandardized", "mean"),
        Result_Measure=("Result_Measure", "mean"),
        Result_Characteristic=("Result_Characteristic", "first"),
    )


def get_timeseries(**filters) -> pd.DataFrame:
    columns = [
        "Location_Name",
        "Activity_StartDate",
        "Result_Measure",
        "Result_MeasureUnit",
        "Result_Characteristic",
        "Result_SampleFraction",
    ]
    return query_wqx(columns=columns, **filters)


def get_export_data(**filters) -> pd.DataFrame:
    columns = [
        "Location_Name",
        "Activity_StartDate",
        "Result_Characteristic",
        "Result_SampleFraction",
        "Result_Measure",
        "Result_MeasureUnit",
        "Activity_MediaSubdivision",
        "Location_LatitudeStandardized",
        "Location_LongitudeStandardized",
        "Org_Identifier",
    ]
    return query_wqx(columns=columns, **filters)

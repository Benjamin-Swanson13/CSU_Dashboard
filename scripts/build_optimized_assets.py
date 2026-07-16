from __future__ import annotations

import re
from datetime import datetime
from pathlib import Path

import geopandas as gpd
import pandas as pd


BASE_DIR = Path(__file__).resolve().parents[1]
ASSET_DIR = BASE_DIR / "assets"
OUT_DIR = ASSET_DIR / "optimized"

WQX_COLUMNS = [
    "Org_Identifier",
    "Org_FormalName",
    "Location_Name",
    "Location_HUCEightDigitCode",
    "Location_LatitudeStandardized",
    "Location_LongitudeStandardized",
    "Activity_MediaSubdivision",
    "Activity_StartDate",
    "Result_Characteristic",
    "Result_SampleFraction",
    "Result_Measure",
    "Result_MeasureUnit",
    "Acute",
    "Chronic",
]

STRING_COLUMNS = [
    "Org_Identifier",
    "Org_FormalName",
    "Location_Name",
    "Location_HUCEightDigitCode",
    "Activity_MediaSubdivision",
    "Result_Characteristic",
    "Result_SampleFraction",
    "Result_MeasureUnit",
]


def newest_file(pattern: str, regex: str) -> Path:
    files = [p for p in ASSET_DIR.glob(pattern) if re.match(regex, p.name)]
    if not files:
        raise FileNotFoundError(f"No files match {pattern} in {ASSET_DIR}")
    return max(files, key=lambda p: datetime.strptime(re.match(regex, p.name).group(1), "%Y%m%d"))


def normalize_huc(value) -> str | None:
    if pd.isna(value):
        return None
    text = str(value).strip()
    if not text:
        return None
    if text.endswith(".0"):
        text = text[:-2]
    digits = re.sub(r"\D", "", text)
    return digits.zfill(8) if digits else text


def compact_frame(df: pd.DataFrame) -> pd.DataFrame:
    for col in WQX_COLUMNS:
        if col not in df.columns:
            df[col] = pd.NA
    df = df[WQX_COLUMNS].copy()
    df["Activity_StartDate"] = pd.to_datetime(df["Activity_StartDate"], errors="coerce")
    df["Activity_Year"] = df["Activity_StartDate"].dt.year.astype("Int16")
    for col in ["Result_Measure", "Location_LatitudeStandardized", "Location_LongitudeStandardized", "Acute", "Chronic"]:
        df[col] = pd.to_numeric(df[col], errors="coerce", downcast="float")
    df["Location_HUCEightDigitCode"] = df["Location_HUCEightDigitCode"].map(normalize_huc)
    for col in STRING_COLUMNS:
        df[col] = df[col].astype("string")
    return df


def standardize_sample_fractions(df: pd.DataFrame) -> pd.DataFrame:
    mapping = {
        "Filtered, field": "Dissolved",
        "Filtered, lab": "Dissolved",
        "Filtered": "Dissolved",
        "filtered, field": "Dissolved",
        "filtered, lab": "Dissolved",
        "filtered": "Dissolved",
        "Unfiltered": "Total",
        "unfiltered": "Total",
        "Unfiltered, field": "Total",
        "unfiltered, field": "Total",
        "total": "Total",
        "TOTAL": "Total",
        "dissolved": "Dissolved",
        "DISSOLVED": "Dissolved",
    }
    df["Result_SampleFraction"] = df["Result_SampleFraction"].replace(mapping)
    return df


def standardize_units(df: pd.DataFrame) -> pd.DataFrame:
    def unit_in(units):
        return df["Result_MeasureUnit"].str.lower().isin([u.lower() for u in units])

    trace_metals = ["Selenium", "Aluminum", "Arsenic", "Cadmium", "Copper", "Iron", "Lead", "Manganese", "Zinc", "Silver", "Cobalt", "Uranium"]
    major_ions = ["Calcium", "Magnesium", "Potassium", "Sodium", "Sulfate", "Phosphorus", "Total Phosphorus", "Orthophosphate", "Phosphate-phosphorus"]
    nitrogen = ["Nitrogen", "Nitrate", "Nitrite", "Nitrate + Nitrite", "Nitrite + Nitrate", "Ammonia", "Ammonia-nitrogen", "Ammonia and ammonium", "Ammonium", "Total Kjeldahl Nitrogen"]
    solids = ["Total Suspended Solids", "Total suspended solids", "Total dissolved solids"]
    hardness = ["Hardness, Ca, Mg", "Hardness, non-carbonate", "Hardness, carbonate", "Total hardness"]

    mask = df["Result_Characteristic"].isin(trace_metals) & unit_in(["mg/L", "mg/l"])
    df.loc[mask, "Result_Measure"] = df.loc[mask, "Result_Measure"] * 1000
    df.loc[mask, "Result_MeasureUnit"] = "ug/L"
    mask = df["Result_Characteristic"].isin(major_ions + nitrogen + solids + hardness) & unit_in(["ug/L", "ug/l", "µg/L"])
    df.loc[mask, "Result_Measure"] = df.loc[mask, "Result_Measure"] * 0.001
    df.loc[mask, "Result_MeasureUnit"] = "mg/L"
    df.loc[df["Result_Characteristic"] == "pH", "Result_MeasureUnit"] = "std units"
    for unit, factor in {"ms/cm": 1000, "s/cm": 1000000}.items():
        mask = df["Result_Characteristic"].isin(["Conductivity", "Specific conductance"]) & unit_in([unit])
        df.loc[mask, "Result_Measure"] = df.loc[mask, "Result_Measure"] * factor
        df.loc[mask, "Result_MeasureUnit"] = "uS/cm"
    flow_chars = ["Flow", "Stream flow, instantaneous", "Flow rate, instantaneous", "Stream flow"]
    mask = df["Result_Characteristic"].isin(flow_chars) & unit_in(["ft3/s", "ft3/sec", "ft³/s", "ft³/sec"])
    df.loc[mask, "Result_MeasureUnit"] = "cfs"
    mask = df["Result_Characteristic"].isin(flow_chars) & unit_in(["m3/sec", "m³/sec", "m3/s", "m³/s"])
    df.loc[mask, "Result_Measure"] = df.loc[mask, "Result_Measure"] * 35.3147
    df.loc[mask, "Result_MeasureUnit"] = "cfs"
    mask = df["Result_Characteristic"].isin(flow_chars) & unit_in(["mgd", "mgal/d"])
    df.loc[mask, "Result_Measure"] = df.loc[mask, "Result_Measure"] * 1.547
    df.loc[mask, "Result_MeasureUnit"] = "cfs"
    mask = df["Result_Characteristic"].isin(flow_chars) & unit_in(["gal/min", "gpm", "gallons/min"])
    df.loc[mask, "Result_Measure"] = df.loc[mask, "Result_Measure"] * 0.002228
    df.loc[mask, "Result_MeasureUnit"] = "cfs"
    df.loc[df["Result_Characteristic"] == "Hardness as CaCO3", "Result_Characteristic"] = "Hardness, Ca, Mg"
    mask = df["Result_Characteristic"].isin(["Total Suspended Solids", "Total suspended solids"]) & (
        df["Result_SampleFraction"].isna() | (df["Result_SampleFraction"] == "")
    )
    df.loc[mask, "Result_SampleFraction"] = "Total"
    mask = (df["Result_Characteristic"] == "Temperature, water") & unit_in(["deg F", "F", "°F"])
    df.loc[mask, "Result_Measure"] = (df.loc[mask, "Result_Measure"] - 32) * 5 / 9
    df.loc[mask, "Result_MeasureUnit"] = "deg C"
    mask = df["Result_Characteristic"].isin(["Dissolved oxygen", "Dissolved Oxygen (DO)", "Oxygen"]) & unit_in(["ug/L", "ug/l", "µg/L"])
    df.loc[mask, "Result_Measure"] = df.loc[mask, "Result_Measure"] * 0.001
    df.loc[mask, "Result_MeasureUnit"] = "mg/L"
    return df


def add_basin(df: pd.DataFrame) -> pd.DataFrame:
    centroids = pd.read_csv(ASSET_DIR / "HUC8_Centroids.csv", dtype={"huc8": "string"})
    huc_to_name = dict(zip(centroids["huc8"].astype(str).str.zfill(8), centroids["name"]))
    df["Basin"] = df["Location_HUCEightDigitCode"].map(huc_to_name).astype("string")
    return df


def read_wqx_source() -> pd.DataFrame:
    source = newest_file("CSU_EPAWQData_Beta_19901001-*_parsed.csv", r"CSU_EPAWQData_Beta_19901001-(\d{8})_parsed.csv")
    header = pd.read_csv(source, nrows=0).columns
    usecols = [col for col in WQX_COLUMNS if col in header]
    print(f"Input WQX: {source.name}")
    print(f"Retained WQX columns: {usecols}")
    print(f"Dropped WQX columns: {len(header) - len(usecols)}")
    chunks = []
    for chunk in pd.read_csv(source, usecols=usecols, dtype="string", chunksize=25000, low_memory=True):
        chunk = add_basin(standardize_units(standardize_sample_fractions(compact_frame(chunk))))
        chunks.append(chunk)
    return pd.concat(chunks, ignore_index=True, copy=False)


def read_fountain_creek() -> pd.DataFrame:
    path = ASSET_DIR / "USGSFountainCreek_Ecoli.csv"
    if not path.exists():
        return pd.DataFrame()
    header = pd.read_csv(path, nrows=0).columns
    usecols = [col for col in WQX_COLUMNS if col in header]
    df = pd.read_csv(path, usecols=usecols, dtype="string", low_memory=True)
    return add_basin(standardize_units(standardize_sample_fractions(compact_frame(df))))


def add_moffat_site(df: pd.DataFrame) -> pd.DataFrame:
    name = "ARKANSAS RIVER AT MOFFAT STREET AT PUEBLO, CO"
    if name in set(df["Location_Name"].dropna().astype(str)):
        return df
    row = {col: pd.NA for col in df.columns}
    row.update(
        {
            "Org_Identifier": "USGS",
            "Org_FormalName": "USGS",
            "Location_Name": name,
            "Location_LatitudeStandardized": 38.2536139630922,
            "Location_LongitudeStandardized": -104.606085372154,
        }
    )
    return pd.concat([df, pd.DataFrame([row])], ignore_index=True)


def build_site_catalog(df: pd.DataFrame) -> pd.DataFrame:
    cols = ["Location_Name", "Location_LatitudeStandardized", "Location_LongitudeStandardized", "Location_HUCEightDigitCode", "Basin", "Org_Identifier"]
    catalog = df[cols].dropna(subset=["Location_Name", "Location_LatitudeStandardized", "Location_LongitudeStandardized"])
    return catalog.drop_duplicates(subset=["Location_Name"], keep="first").reset_index(drop=True)


def build_metadata(df: pd.DataFrame) -> pd.DataFrame:
    year_values = df["Activity_Year"].dropna()
    rows = [
        {"key": "row_count", "value": str(len(df))},
        {"key": "min_year", "value": str(int(year_values.min()))},
        {"key": "max_year", "value": str(int(year_values.max()))},
    ]
    for key, col in [("characteristic", "Result_Characteristic"), ("fraction", "Result_SampleFraction"), ("sample_type", "Activity_MediaSubdivision"), ("basin", "Basin")]:
        for value in sorted(df[col].dropna().astype(str).unique()):
            rows.append({"key": key, "value": value})
    return pd.DataFrame(rows)


def build_usgs() -> None:
    source = newest_file("USGS_DailyData_Arkansas_*.csv", r"USGS_DailyData_Arkansas_19901001-(\d{8}).csv")
    df = pd.read_csv(source, dtype={"Site_Number": "string", "Site_Name": "string"}, parse_dates=["Date"])
    df["Year"] = df["Date"].dt.year.astype("Int16")
    for col in ["Flow_cfs", "SpCond_uScm"]:
        df[col] = pd.to_numeric(df[col], errors="coerce", downcast="float")
    df.to_parquet(OUT_DIR / "usgs_daily.parquet", index=False, compression="zstd")
    mapping_path = source.with_name(source.stem + "_SiteMapping.csv")
    if mapping_path.exists():
        mapping = pd.read_csv(mapping_path, dtype={"Site_Number": "string", "WQX_Site_Name": "string"})
        mapping.to_parquet(OUT_DIR / "usgs_site_catalog.parquet", index=False, compression="zstd")
    print(f"Input USGS rows: {len(df):,}")


def build_geospatial_assets() -> None:
    layers = [
        ("huc8_boundaries.geojson", "huc8_boundaries_simplified.geojson", 0.001),
        ("Final_GIS_Canal_Layer.shp", "canals_simplified.geojson", 0.0005),
        ("StreamsRivers.shp", "streams_simplified.geojson", 0.0005),
        ("21CW3XXX_Pts.shp", "exchange_points.geojson", 0),
    ]
    for source_name, output_name, tolerance in layers:
        source = ASSET_DIR / source_name
        if not source.exists():
            continue
        try:
            gdf = gpd.read_file(source).to_crs("EPSG:4326")
            keep = [col for col in ["name", "huc8", "PNAME", "POSS_NAME", "Label", "Color", "geometry"] if col in gdf.columns]
            gdf = gdf[keep]
            if tolerance:
                gdf["geometry"] = gdf.geometry.simplify(tolerance, preserve_topology=True)
            gdf = gdf[gdf.geometry.notna() & ~gdf.geometry.is_empty]
            gdf.to_file(OUT_DIR / output_name, driver="GeoJSON")
            print(f"Geo asset {output_name}: {len(gdf):,} features")
        except Exception as exc:
            print(f"Warning: failed to optimize {source_name}: {exc}")


def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    wqx = read_wqx_source()
    fountain = read_fountain_creek()
    if not fountain.empty:
        print(f"Input Fountain Creek rows: {len(fountain):,}")
        wqx = pd.concat([wqx, fountain[wqx.columns]], ignore_index=True, copy=False)
    wqx = add_moffat_site(wqx).reset_index(drop=True)
    site_catalog = build_site_catalog(wqx)
    metadata = build_metadata(wqx)
    wqx.to_parquet(OUT_DIR / "wqx_measurements.parquet", index=False, compression="zstd")
    site_catalog.to_parquet(OUT_DIR / "wqx_site_catalog.parquet", index=False, compression="zstd")
    metadata.to_parquet(OUT_DIR / "wqx_metadata.parquet", index=False, compression="zstd")
    build_usgs()
    build_geospatial_assets()
    print(f"Output WQX rows: {len(wqx):,}")
    print(f"Output site rows: {len(site_catalog):,}")
    for path in sorted(OUT_DIR.glob("*")):
        if path.is_file():
            print(f"{path.relative_to(BASE_DIR)}: {path.stat().st_size / 1024 / 1024:.2f} MB")
    print("Final WQX Parquet schema:")
    print(pd.read_parquet(OUT_DIR / "wqx_measurements.parquet").dtypes)
    subset = pd.read_parquet(OUT_DIR / "wqx_measurements.parquet", columns=["Location_Name", "Activity_StartDate", "Result_Measure"]).head(10000)
    print(f"Representative 10,000-row subset memory: {subset.memory_usage(deep=True).sum() / 1024 / 1024:.2f} MB")


if __name__ == "__main__":
    main()

# CSU Water Quality Dashboard

This repository serves the Plotly Dash dashboard through `app.py`, which imports
the optimized implementation in `app2.py` and exposes `server = app.server` for
Gunicorn/Render.

## Production Install

```bash
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
```

## Preprocessing Install

```bash
python -m pip install -r requirements-preprocess.txt
```

## Build Optimized Assets

Run this locally before deployment and commit the generated files under
`assets/optimized/`.

```bash
python scripts/build_optimized_assets.py
```

The production app prefers:

- `assets/optimized/wqx_measurements.parquet`
- `assets/optimized/wqx_site_catalog.parquet`
- `assets/optimized/wqx_metadata.parquet`
- `assets/optimized/usgs_daily.parquet`
- `assets/optimized/usgs_site_catalog.parquet`

If optimized assets are missing, `app2.py` falls back to constrained CSV loading
for local development and prints the preprocessing command.

## Render

Build command:

```bash
python -m pip install --upgrade pip && python -m pip install -r requirements.txt
```

Start command:

```bash
gunicorn app:server --bind 0.0.0.0:$PORT --workers 1 --worker-class gthread --threads 2 --timeout 300
```

Required environment variable:

```text
MAPBOX_ACCESS_TOKEN
```

Recommended environment defaults are defined in `render.yaml`.

## Memory Profiling

```bash
python scripts/profile_memory.py
```

Latest local Windows measurement with optimized assets:

- Startup/import peak: 227.9 MB
- Root request RSS: 228.4 MB
- Representative map query peak: 247.7 MB
- Representative time-series query peak: 268.3 MB
- Representative export query peak: 291.9 MB

The profiler exits nonzero if startup peak exceeds 400 MB or representative
operations exceed 450 MB.

## Notes

Raw source CSVs are preprocessing inputs. The production entry point uses the
optimized Parquet assets when they are present and does not run WQX or USGS
network imports during app startup.

# Create CSV & geojson from HUC2 Watershed Boundaries (WBD)
# WBD data downloaded from https://apps.nationalmap.gov/downloader/#/

import pandas as pd
import geopandas as gpd

# Read the shapefile
gdf = gpd.read_file('WBDHU8.shp')

# Your HUC8 IDs
my_huc8s = ['11020006', '11020009', '11020010', '11020003', '11020002', 
            '11020005', '11020007', '11020008']

# Filter to your HUC8s
filtered = gdf[gdf['huc8'].isin(my_huc8s)]

# === CREATE CENTROIDS CSV ===
# Reproject to a projected CRS to get accurate centroids
filtered_projected = filtered.to_crs('EPSG:5070')  # Albers Equal Area for US

# Calculate centroids
filtered_projected['centroid'] = filtered_projected.geometry.centroid
filtered_projected['lon'] = filtered_projected['centroid'].to_crs('EPSG:4326').x
filtered_projected['lat'] = filtered_projected['centroid'].to_crs('EPSG:4326').y

# Export centroids to CSV
filtered_projected[['huc8', 'name', 'areasqkm', 'lat', 'lon']].to_csv('HUC8_Centroids.csv', index=False)
print(f"✓ Created HUC8_Centroids.csv with {len(filtered_projected)} watersheds")

# === CREATE GEOJSON ===
# Make sure it's in WGS84 (standard for GeoJSON)
filtered_geojson = filtered.to_crs('EPSG:4326')

# Rename column to match what your dashboard expects
filtered_geojson = filtered_geojson.rename(columns={'huc8': 'ID'})

# Save as GeoJSON
filtered_geojson.to_file('huc8_boundaries.geojson', driver='GeoJSON')
print(f"✓ Created huc8_boundaries.geojson with {len(filtered_geojson)} HUC8 watersheds")
print(f"  Columns: {filtered_geojson.columns.tolist()}")
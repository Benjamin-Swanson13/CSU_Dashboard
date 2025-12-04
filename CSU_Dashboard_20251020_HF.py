# Colorado Springs Utilities Water Quality Dashboard
# This dashboard pulls data from EPA beta WQX, processes it, and provides interactive visualizations.
# It also includes canal/ditch and exchange locations that may be relevant to the project goals.
# Created by Haley Farwell & Eidan Willis; SGM, Inc. 2025


import os
import pathlib
import re
import site
import dash
from dash import Dash, html, dcc, callback, Output, Input, dash_table, State
import pandas as pd
import geopandas as gpd
from dash.dependencies import Input, Output, State
from shapefile_functions import add_shapefile_data
from WQXDataImport_CSU_251006_HF import WQXDataImport
import json
import plotly.express as px
from datetime import datetime
import numpy as np
import plotly.graph_objects as go
import numpy as np
import plotly.express as px
import dash_bootstrap_components as dbc
import pandas as pd
import numpy as np
import glob
import fiona

# Try to find USGS files
usgs_files = glob.glob("USGS_DailyData_Arkansas_*.csv")
print(f"Found USGS files: {usgs_files}")

if usgs_files:
    print("✓ Files found in current directory")
else:
    print("✗ No files found - checking if path issue...")
    # Try with full path
    script_dir = os.path.dirname(os.path.abspath(__file__))
    usgs_files_fullpath = glob.glob(os.path.join(script_dir, "USGS_DailyData_Arkansas_*.csv"))
    print(f"Checking in script dir: {usgs_files_fullpath}")

print("="*80 + "\n")

script_dir = os.path.dirname(os.path.abspath(__file__))
print("WD identified as: " + script_dir)

#call data import function
user_input = input("Do you want to initiate a new data pull from WQX? (y/n): ").strip().lower()

if user_input in ['y', 'yes']:

    print("Initiating new data pull from WQX...")
    try:
        parsed_csv = WQXDataImport()
        print("WQX Import/Data Processing Complete, exported to " + parsed_csv  + ".")
    except Exception as e:
        print("function raised an error:", e)

elif user_input not in ['n', 'no']:
    print("Invalid input, exiting script...")
    exit()

print("Initializing, processing large amounts of data - this may take a minute...")

filename_pattern = r"CSU_EPAWQData_Beta_19901001-(\d{8})_parsed.csv"

existing_files = [f for f in os.listdir(script_dir) if re.match(filename_pattern, f)]

if existing_files:
    #extract dates and find most recent file
    dates = [datetime.strptime(re.match(filename_pattern, f).group(1), "%Y%m%d") for f in existing_files]
    most_recent_date = max(dates)
    parsed_csv = f"CSU_EPAWQData_Beta_19901001-{most_recent_date.strftime('%Y%m%d')}_parsed.csv"

#parsed_csv_path = script_dir + "\\" + parsed_csv


def filter_data(df, characteristic, fraction, basin, site, sample_type, start_year, end_year):
    DEBUG_MODE = True  # Set to True for debugging
    
    if DEBUG_MODE:
        print(f"\n=== DETAILED FILTER DEBUG ===")
        print(f"Input: {len(df)} records")
        print(f"Filtering for: {characteristic}, {fraction}, {basin}, {site}, {sample_type}, {start_year}-{end_year}")
    
    # Fix: Handle case where inputs might be lists
    if isinstance(characteristic, (list, tuple)):
        characteristic = characteristic[0] if characteristic else None
    if isinstance(fraction, (list, tuple)):
        fraction = fraction[0] if fraction else None
    if isinstance(sample_type, (list, tuple)):
        sample_type = sample_type[0] if sample_type else None
    if isinstance(basin, (list, tuple)):
        basin = basin[0] if basin else None
    #if isinstance(site, (list, tuple)): 
    #    site = site[0] if site else None
    
    # Convert "All" to None for easier handling
    if characteristic == "All":
        characteristic = None
    if basin == "All":
        basin = None
    if sample_type == "All":
        sample_type = None
    if site == "All":
        site = None

    if DEBUG_MODE:
        print(f"After type fixing - Characteristic: {characteristic}, Fraction: {fraction}, Basin: {basin}, Sample Type: {sample_type}")
    
    # Start with all data
    data_out = df.copy()

    # Step 1: Filter by characteristic (if specified)
    if characteristic is not None:
        char_mask = data_out['Result_Characteristic'] == characteristic
        if DEBUG_MODE:
            print(f"Step 1 - Characteristic '{characteristic}': {char_mask.sum()} records")
        
        if char_mask.sum() == 0:
            if DEBUG_MODE:
                print("ERROR: No records found for this characteristic!")
            return pd.DataFrame()
        
        data_out = data_out[char_mask]
    else:
        if DEBUG_MODE:
            print("Step 1 - No characteristic filter (showing all)")
    
    # Step 2: Filter by fraction (if specified and characteristic is specified)
    if fraction is not None and characteristic is not None:
        if characteristic == "Flow":
            frac_mask = (
                (data_out['Result_SampleFraction'] == fraction) | 
                (data_out['Result_SampleFraction'].isna()) |
                (data_out['Result_SampleFraction'] == '')
            )
        else:
            frac_mask = data_out['Result_SampleFraction'] == fraction
        
        if DEBUG_MODE:
            print(f"Step 2 - Fraction '{fraction}': {frac_mask.sum()} records")
        
        data_out = data_out[frac_mask]
        
        if DEBUG_MODE:
            print(f"Step 2b - After fraction filter: {len(data_out)} records")
    else:
        if DEBUG_MODE:
            print("Step 2 - No fraction filter applied")
    
    # Step 3: Filter by sample type (if specified)
    if sample_type is not None:
        sample_type_mask = data_out['Activity_MediaSubdivision'] == sample_type
        if DEBUG_MODE:
            print(f"Step 3 - Sample Type '{sample_type}': {sample_type_mask.sum()} records")
        
        data_out = data_out[sample_type_mask]
        
        if DEBUG_MODE:
            print(f"Step 3b - After sample type filter: {len(data_out)} records")
    else:
        if DEBUG_MODE:
            print("Step 3 - No sample type filter (showing all)")
    
    # Step 3.5: Filter by site/monitoring location (if specified)
    if site is not None:
        # Handle both single site (string) and multiple sites (list)
        if isinstance(site, (list, tuple)):
            # Filter out 'All' from list
            site_list = [s for s in site if s != 'All']
            
            # If list is empty or only contained 'All', show all sites
            if not site_list:
                if DEBUG_MODE:
                    print(f"Step 3.5 - 'All' selected or empty list, showing all sites")
                # Don't filter - show all sites
            else:
                site_mask = data_out['Location_Name'].isin(site_list)
                if DEBUG_MODE:
                    print(f"Step 3.5 - Sites {site_list}: {site_mask.sum()} records")
                
                data_out = data_out[site_mask]
                
                if DEBUG_MODE:
                    print(f"Step 3.5b - After site filter: {len(data_out)} records")
        else:
            # Single site
            site_mask = data_out['Location_Name'] == site
            if DEBUG_MODE:
                print(f"Step 3.5 - Site '{site}': {site_mask.sum()} records")
            
            data_out = data_out[site_mask]
            
            if DEBUG_MODE:
                print(f"Step 3.5b - After site filter: {len(data_out)} records")
    else:
        if DEBUG_MODE:
            print("Step 3.5 - No site filter (showing all sites)")

    # Step 4: Check coordinate validity
    coord_valid = (
        data_out['Location_LongitudeStandardized'].notna() & 
        data_out['Location_LatitudeStandardized'].notna()
    )
    
    if DEBUG_MODE:
        print(f"Step 4 - Valid coordinates: {coord_valid.sum()} records")
    
    data_out = data_out[coord_valid]
    
    if DEBUG_MODE:
        print(f"Step 4b - After coordinate filter: {len(data_out)} records")
    
    if len(data_out) == 0:
        if DEBUG_MODE:
            print("ERROR: No records with valid coordinates!")
        return pd.DataFrame()
    
    # Step 5: Spatial filtering (only if basin is specified)
    if basin is not None:
        try:
            points = gpd.GeoSeries(gpd.points_from_xy(
                data_out['Location_LongitudeStandardized'], 
                data_out['Location_LatitudeStandardized']
            )).set_crs('EPSG:4326')
            
            if DEBUG_MODE:
                print(f"Step 5 - Created {len(points)} spatial points")
            
            # Find the correct basin column name
            basin_col = None
            for col in ['name', 'NAME', 'BASINS', 'BASIN_NAM', 'NAMELSAD']:
                if col in BASINS_GDF.columns:
                    basin_col = col
                    break

            if basin_col is None:
                print("ERROR: No basin column found in GeoJSON")
                return pd.DataFrame()
            
            if DEBUG_MODE:
                print(f"Step 5 - Using basin column: {basin_col}")
            
            # Check if basin exists in the GeoDataFrame
            basin_match = BASINS_GDF[BASINS_GDF[basin_col] == basin]
            if basin_match.empty:
                print(f"ERROR: Basin '{basin}' not found in column '{basin_col}'")
                print(f"Available basins: {BASINS_GDF[basin_col].unique()}")
                return pd.DataFrame()
            
            basin_geom = basin_match['geometry'].iloc[0]
            
            if DEBUG_MODE:
                print(f"Step 5 - Basin geometry type: {basin_geom.geom_type}")
                print(f"Step 5 - Basin bounds: {basin_geom.bounds}")
            
            data_in_basin = points.within(basin_geom, align=False)
            data_in_basin.index = data_out.index
            
            if DEBUG_MODE:
                print(f"Step 5 - Points in basin: {data_in_basin.sum()}")
            
            data_out = data_out[data_in_basin].copy()
            
            if DEBUG_MODE:
                print(f"Step 5b - After spatial filter: {len(data_out)} records")
            
        except Exception as e:
            print(f"ERROR in spatial filtering: {e}")
            import traceback
            traceback.print_exc()
            return pd.DataFrame()
    else:
        if DEBUG_MODE:
            print("Step 5 - No basin filter (showing all basins)")
    
    # Step 6: Date filtering
    if len(data_out) > 0:
        try:
            date_mask = (
                (data_out['Activity_StartDate'] > datetime(year=start_year, month=1, day=1)) & 
                (data_out['Activity_StartDate'] <= datetime(year=end_year, month=12, day=31))
            )
            data_out = data_out[date_mask].copy()
            
            if DEBUG_MODE:
                print(f"Step 6 - After date filter: {len(data_out)} records")
        except Exception as e:
            print(f"ERROR in date filtering: {e}")
            import traceback
            traceback.print_exc()
            return pd.DataFrame()
    
    # Step 7: Convert result values and apply flow conversion if needed
    if len(data_out) > 0:
        data_out['Result_Measure'] = pd.to_numeric(data_out['Result_Measure'], errors='coerce')
        
        if DEBUG_MODE:
            valid_values = data_out['Result_Measure'].notna().sum()
            print(f"Step 7 - Valid numeric values: {valid_values}")
    
    print(f"Filter complete: {len(data_out)} records")
    return data_out

# Aggregation function
def first(arr):
        return arr[0]
    
# Function to create heatmap color scale based on characteristic threshold values 
# pass max value because scale must be normalized
def assign_continuous_color_scale(df):  
    """
    Create a continuous color scale using plotly's color mapping
    """
    if df.empty:
        return ['grey'] * len(df), 0, 1
    
    values = pd.to_numeric(df['Result_Measure'], errors='coerce')
    valid_values = values.dropna()
    
    print(f"Color assignment debug:")
    print(f"  Total rows: {len(df)}")
    print(f"  Valid values: {len(valid_values)}")
    if len(valid_values) > 0:
        print(f"  Value range: {valid_values.min():.3f} to {valid_values.max():.3f}")
    
    if len(valid_values) == 0:
        return ['grey'] * len(df), 0, 1
    
    min_val = float(valid_values.min())
    max_val = float(valid_values.max())
    
    if min_val == max_val:
        print(f"  All values are the same ({min_val}), using blue")
        return ['blue'] * len(df), min_val, max_val
    
    if len(valid_values) == 0:
        return ['grey'] * len(df), 0, 1
    
    min_val = float(valid_values.min())
    max_val = float(valid_values.max())
    
    if min_val == max_val:
        return ['blue'] * len(df), min_val, max_val
    
    # Simple color mapping
    colors = []
    for value in values:
        if pd.isna(value):
            colors.append('grey')
        else:
            norm_val = (value - min_val) / (max_val - min_val)
            if norm_val <= 0.33:
                colors.append('blue')
            elif norm_val <= 0.66:
                colors.append('yellow')
            else:
                colors.append('red')
    
    return colors, min_val, max_val

def create_data_driven_color_scale(values):
    """Create color scale based on actual data distribution"""
    if len(values) == 0:
        return 'Viridis'
    
    # Calculate percentiles from the actual data
    p25 = np.percentile(values, 25)
    p50 = np.percentile(values, 50)  
    p75 = np.percentile(values, 75)
    p90 = np.percentile(values, 90)
    max_val = np.max(values)
    
    if max_val == 0:
        return 'Viridis'
    
    # Create color scale based on data distribution
    scale = [
        (0.0, 'darkblue'),           # Minimum values
        (p25/max_val, 'blue'),       # Lower quartile
        (p50/max_val, 'lightgreen'), # Median
        (p75/max_val, 'yellow'),     # Upper quartile
        (p90/max_val, 'orange'),     # 90th percentile
        (1.0, 'red')                 # Maximum values
    ]
    
    return scale

# Initialize app
app = dash.Dash(
    __name__,
    external_stylesheets=[dbc.themes.DARKLY],
    meta_tags=[
        {"name": "viewport", "content": "width=device-width, initial-scale=1.0"}
    ],
)
app.title = "Colorado Springs Utilities Water Quality Data Dashboard"
server = app.server

app.index_string = '''
<!DOCTYPE html>
<html>
    <head>
        {%metas%}
        <title>{%title%}</title>
        {%favicon%}
        {%css%}
        <style>
            * {
                font-family: "Arial", "Helvetica", sans-serif !important;
            }
            
            body {
                background-color: #1e1e1e !important;
                color: #ffffff !important;
                margin: 0;
                padding: 0;
            }
            
            #root {
                background-color: #1e1e1e !important;
                color: #ffffff !important;
            }
            
            /* Enhanced dropdown styling */
            .Select-control {
                background-color: #404040 !important;
                border: 2px solid #555 !important;
                border-radius: 6px !important;
                color: #ffffff !important;
                min-height: auto !important;
            }
            
            .Select-control:hover {
                border-color: #777 !important;
            }
            
        /* Allow multi-select values to wrap within the dropdown */
            .Select-multi-value-wrapper {
                display: flex !important;
                flex-wrap: wrap !important;
            }

            .Select-menu-outer {
                background-color: #404040 !important;
                border: 1px solid #555 !important;
                border-radius: 6px !important;
                box-shadow: 0 4px 8px rgba(0,0,0,0.3) !important;
                z-index: 99999 !important;  /* Ensure dropdown appears above everything */
                position: absolute !important;
            }
            
            .Select-menu {
                background-color: #404040 !important;
                max-height: 200px !important;
            }
            
            .Select-option {
                background-color: #404040 !important;
                color: #ffffff !important;
                padding: 12px 16px !important;
            }
            
            .Select-option:hover, 
            .Select-option.is-focused {
                background-color: #555 !important;
                color: #ffffff !important;
            }
            
            .Select-value-label {
                color: #ffffff !important;
                padding: 8px 12px !important;
                white-space: normal !important;
            }
            
        /* Make sure dropdown container has proper positioning */
            .Select {
                position: relative !important;
                z-index: 100 !important;
            }

        /* When dropdown is open, increase z-index significantly */
            .Select.is-open {
                z-index: 10000 !important;
            }
            
        /* Give higher z-index to focused dropdown */
            .Select.is-focused {
                z-index: 10000 !important;
            }
            
        /* Stacking context for each dropdown wrapper */
            #left-controls-column > div > div {
                position: relative !important;
            }

        /* Ensure the plot doesn't overlap dropdowns */
            #right-analysis-column {
                z-index: 1 !important;
                position: relative !important;
            }
            
            #left-controls-column {
                z-index: 100 !important;
                position: relative !important;
            }

            /* Range slider styling */
            .rc-slider {
                background-color: #555 !important;
                height: 6px !important;
            }
            
            .rc-slider-track {
                background-color: #2196F3 !important;
                height: 6px !important;
            }
            
            .rc-slider-handle {
                border: 2px solid #2196F3 !important;
                background-color: #2196F3 !important;
                height: 18px !important;
                width: 18px !important;
                margin-top: -6px !important;
                box-shadow: 0 2px 4px rgba(0,0,0,0.3) !important;
            }
            
            .rc-slider-handle:hover {
                border-color: #1976D2 !important;
            }
            
            .rc-slider-mark-text {
                color: #ffffff !important;
                font-size: 12px !important;
            }
            
            /* Table improvements */
            .dash-table-container {
                background-color: #2d2d2d !important;
                border-radius: 8px !important;
                overflow: hidden !important;
            }
            
            /* Scrollbar styling */
            ::-webkit-scrollbar {
                width: 8px;
                height: 8px;
            }
            
            ::-webkit-scrollbar-track {
                background: #2d2d2d;
            }
            
            ::-webkit-scrollbar-thumb {
                background: #555;
                border-radius: 4px;
            }
            
            ::-webkit-scrollbar-thumb:hover {
                background: #777;
            }
            
            /* Hide Dash undo-redo */
            ._dash-undo-redo {
                display: none !important;
            }
            
            /* Responsive improvements */
            @media (max-width: 768px) {
                #left-column, #right-column {
                    width: 100% !important;
                    margin-left: 0 !important;
                    margin-bottom: 20px;
                }
            }
        </style>
    </head>
    <body>
        {%app_entry%}
        <footer>
            {%config%}
            {%scripts%}
            {%renderer%}
        </footer>
    </body>
</html>
'''

# Load WQX water quality data
CSU_df = pd.read_csv(parsed_csv, dtype=str)
CSU_df['Activity_StartDate'] = pd.to_datetime(CSU_df['Activity_StartDate'], errors='coerce')
CSU_df['Result_Measure'] = pd.to_numeric(CSU_df['Result_Measure'], errors='coerce')

# ADD MANUAL COORDINATE FOR "AT MOFFAT" SITE
# This site has USGS data but no WQX data, so we add a dummy entry to give it coordinates
if 'ARKANSAS RIVER AT MOFFAT STREET AT PUEBLO, CO' not in CSU_df['Location_Name'].values:
    # Create a dictionary with all columns at once
    dummy_data = {
        'Location_Name': 'ARKANSAS RIVER AT MOFFAT STREET AT PUEBLO, CO',
        'Location_LatitudeStandardized': 38.2536139630922,
        'Location_LongitudeStandardized': -104.606085372154,
        'Activity_StartDate': pd.NaT,
        'Result_Measure': np.nan,
        'Result_Characteristic': '',
        'Result_SampleFraction': '',
        'Result_MeasureUnit': '',
        'Org_Identifier': 'USGS'
    }
    
    # Add all other columns with default values in one go
    for col in CSU_df.columns:
        if col not in dummy_data:
            dummy_data[col] = ''
    
    # Create DataFrame from complete dictionary (no fragmentation!)
    dummy_row = pd.DataFrame([dummy_data])
    
    # Append to CSU_df
    CSU_df = pd.concat([CSU_df, dummy_row], ignore_index=True)

# Load USGS daily data (flow + specific conductance)
print("Loading USGS daily data...")
try:
    # Find most recent USGS file
    import glob
    usgs_files = glob.glob("USGS_DailyData_Arkansas_*.csv")
    usgs_files = [f for f in usgs_files if 'SiteMapping' not in f]

    print(f"  Found {len(usgs_files)} USGS data file(s): {usgs_files}")

    if usgs_files:
        latest_usgs = max(usgs_files)
        USGS_df = pd.read_csv(latest_usgs)
        USGS_df['Date'] = pd.to_datetime(USGS_df['Date'])
        HAS_USGS_DATA = True
        print(f"✓ Loaded {len(USGS_df):,} USGS daily records from {latest_usgs}")
        
        # Load site mapping
        mapping_file = latest_usgs.replace('.csv', '_SiteMapping.csv')
        try:
            USGS_MAPPING = pd.read_csv(mapping_file)
            print(f"✓ Loaded site mapping with {len(USGS_MAPPING)} sites")

            #Add coordinates to USGS_MAPPING if not already present ***
            if 'Latitude' not in USGS_MAPPING.columns or 'Longitude' not in USGS_MAPPING.columns:
                print("Adding coordinates to USGS site mapping...")
                
                # Merge coordinates from CSU_df where WQX site names match
                coord_mapping = CSU_df[['Location_Name', 'Location_LatitudeStandardized', 'Location_LongitudeStandardized']].drop_duplicates()
                coord_mapping = coord_mapping.rename(columns={'Location_Name': 'WQX_Site_Name'})
                
                USGS_MAPPING = USGS_MAPPING.merge(
                    coord_mapping, 
                    on='WQX_Site_Name', 
                    how='left'
                )
                USGS_MAPPING = USGS_MAPPING.rename(columns={
                    'Location_LatitudeStandardized': 'Latitude',
                    'Location_LongitudeStandardized': 'Longitude'
                })
                
                print(f"  Sites with coordinates: {USGS_MAPPING['Latitude'].notna().sum()}/{len(USGS_MAPPING)}")
            
            # Merge coordinates back into USGS_df ***
            USGS_df = USGS_df.merge(
                USGS_MAPPING[['Site_Number', 'Latitude', 'Longitude']],
                on='Site_Number',
                how='left'
            )
            
            print(f"  USGS_df now has coordinates for {USGS_df['Latitude'].notna().sum()} records")
            
        except FileNotFoundError:
            USGS_MAPPING = None
            print("⚠ No site mapping file found")
    else:
        HAS_USGS_DATA = False
        USGS_df = pd.DataFrame()
        USGS_MAPPING = None
        print("⚠ No USGS data found - run USGS_Flow_Import.py first")
except Exception as e:
    HAS_USGS_DATA = False
    USGS_df = pd.DataFrame()
    USGS_MAPPING = None
    print(f"⚠ Error loading USGS data: {e}")

# Create unified site list from both WQX and USGS data
print("\nCreating unified site list...")
wqx_sites = set(CSU_df['Location_Name'].dropna().unique())
usgs_sites = set(USGS_df['Site_Name'].dropna().unique()) if HAS_USGS_DATA else set()

ALL_SITES = sorted(list(wqx_sites | usgs_sites))  # Union of both sets

print(f"  WQX sites: {len(wqx_sites)}")
print(f"  USGS sites: {len(usgs_sites)}")
print(f"  Shared sites: {len(wqx_sites & usgs_sites)}")
print(f"  USGS-only sites: {len(usgs_sites - wqx_sites)}")
print(f"  Total unique sites: {len(ALL_SITES)}")

# Show USGS-only sites (like the Moffat site)
usgs_only = usgs_sites - wqx_sites
if usgs_only:
    print(f"\n  USGS-only sites that will now appear:")
    for site in sorted(usgs_only):
        print(f"    - {site}")

# Load Stream Miles mapping
try:
    stream_miles_df = pd.read_csv('StreamMiles.csv')
    print(f"✓ Loaded {len(stream_miles_df)} stream mile records")
    print(f"  Columns: {stream_miles_df.columns.tolist()}")
    
    # Create a dictionary for quick lookups - direct mapping, no translation
    stream_miles_dict = dict(zip(stream_miles_df['Name'], stream_miles_df['Stream Mile']))
    
    print(f"  Created lookup for {len(stream_miles_dict)} sites")
    print(f"  Sample mappings:")
    for name, mile in list(stream_miles_dict.items())[:5]:
        print(f"    '{name}' → {mile}")
    
except FileNotFoundError:
    stream_miles_df = None
    stream_miles_dict = {}
    print("⚠ StreamMiles.csv not found")
except Exception as e:
    stream_miles_df = None
    stream_miles_dict = {}
    print(f"⚠ Error loading StreamMiles.csv: {e}")

# Load CDHPE stream segmentation 
try:
    print("\n" + "="*80)
    print("LOADING STREAM SEGMENTATION FROM GDB")
    print("="*80)
    
    import fiona
    gdb_path = 'segmentation_2024.gdb'
    
    print(f"Looking for GDB at: {gdb_path}")
    
    # List available layers
    layers = fiona.listlayers(gdb_path)
    print(f"✓ Found {len(layers)} layers in GDB:")
    for layer in layers:
        print(f"  - {layer}")
    
    # Load the StreamsHammer2024 layer
    layer_name = 'StreamsHammer2024'
    print(f"\nLoading layer: {layer_name}")
    
    stream_segments_gdf = gpd.read_file(gdb_path, layer=layer_name)
    
    print(f"✓ Loaded {len(stream_segments_gdf)} stream segments")
    print(f"  Original CRS: {stream_segments_gdf.crs}")
    print(f"  Geometry types: {stream_segments_gdf.geometry.geom_type.unique()}")
    
    # Reproject to WGS84
    stream_segments_gdf = stream_segments_gdf.to_crs('EPSG:4326')
    print(f"  Reprojected to: {stream_segments_gdf.crs}")
    
    # Check the Cat (Category) column
    if 'Cat' in stream_segments_gdf.columns:
        print(f"\n  Water Quality Categories found:")
        cat_counts = stream_segments_gdf['Cat'].value_counts()
        for cat, count in cat_counts.items():
            print(f"    Category {cat}: {count} segments")
    
    print("="*80 + "\n")
    
except FileNotFoundError as e:
    stream_segments_gdf = None
    print("="*80)
    print(f"❌ ERROR: File not found - {e}")
    print("="*80 + "\n")
except Exception as e:
    stream_segments_gdf = None
    print("="*80)
    print(f"❌ ERROR loading stream segments: {e}")
    import traceback
    traceback.print_exc()
    print("="*80 + "\n")

# Load lakes from CDPHE stream segmentation
try:
    print("\n" + "="*80)
    print("LOADING LAKES FROM GDB")
    print("="*80)
    
    gdb_path = 'segmentation_2024.gdb'
    layer_name = 'Lakes2024Hammer'
    
    print(f"Loading layer: {layer_name}")
    
    lakes_gdf = gpd.read_file(gdb_path, layer=layer_name)
    
    print(f"✓ Loaded {len(lakes_gdf)} lake features")
    print(f"  Original CRS: {lakes_gdf.crs}")
    print(f"  Geometry types: {lakes_gdf.geometry.geom_type.unique()}")
    
    # Reproject to WGS84
    lakes_gdf = lakes_gdf.to_crs('EPSG:4326')
    print(f"  Reprojected to: {lakes_gdf.crs}")
    
    print("="*80 + "\n")
    
except Exception as e:
    lakes_gdf = None
    print("="*80)
    print(f"❌ ERROR loading lakes: {e}")
    import traceback
    traceback.print_exc()
    print("="*80 + "\n")

# 303(d) Assessment Category Mapping
#ASSESSMENT_CATEGORIES = {
#    '1': {'name': 'Attaining (no TMDL needed)', 'color': '#2E7D32'},  # Dark Green
#    '1a': {'name': 'Attaining - All Uses', 'color': '#43A047'},  # Green
#    '1b': {'name': 'Attaining - TMDL Approved', 'color': '#66BB6A'},  # Light Green
#    '2': {'name': 'Attaining - All Assessed', 'color': '#81C784'},  # Lighter Green
#    '3': {'name': 'Insufficient Data', 'color': '#9E9E9E'},  # Gray
#    '3a': {'name': 'No Data Available', 'color': '#BDBDBD'},  # Light Gray
#    '3b': {'name': 'M&E List', 'color': '#757575'},  # Medium Gray
#    '4': {'name': 'TMDL Required', 'color': '#F57C00'},  # Orange
#    '4a': {'name': 'TMDL Approved', 'color': '#FB8C00'},  # Light Orange
#    '4b': {'name': 'TMDL in Progress', 'color': '#FF9800'},  # Lighter Orange
#    '4c': {'name': 'TMDL Not Required', 'color': '#FFB74D'},  # Pale Orange
#   '5': {'name': '303(d) Listed - Impaired', 'color': '#D32F2F'},  # Red
#    '5a': {'name': '303(d) - High Priority', 'color': '#C62828'},  # Dark Red
#    'NA': {'name': 'Not Assessed', 'color': '#EEEEEE'},  # Very Light Gray
#    'Other': {'name': 'Other Status', 'color': '#9C27B0'}  # Purple
#}

ASSESSMENT_CATEGORIES = {
    # Attaining Categories (Green shades)
    '1': {'name': 'Attaining (no TMDL needed)', 'color': '#2E7D32'},  # Dark Green
    '1a': {'name': 'All attaining', 'color': '#43A047'},  # Green - LAKES
    '1b': {'name': 'Attaining - TMDL Approved', 'color': '#66BB6A'},  # Light Green - STREAMS
    '2': {'name': 'Everything assessed was attaining', 'color': '#81C784'},  # Lighter Green - LAKES
    
    # Insufficient Data Categories (Gray shades)
    '3': {'name': 'Insufficient Data', 'color': '#9E9E9E'},  # Gray
    '3a': {'name': 'Not enough information to assess', 'color': '#BDBDBD'},  # Light Gray - LAKES
    '3b': {'name': 'M&E List', 'color': '#757575'},  # Medium Gray - LAKES
    
    # TMDL Categories (Orange shades)
    '4': {'name': 'TMDL Required', 'color': '#F57C00'},  # Orange
    '4a': {'name': 'TMDL', 'color': '#FB8C00'},  # Light Orange - LAKES
    '4b': {'name': 'TMDL in Progress', 'color': '#FF9800'},  # Lighter Orange - STREAMS
    '4c': {'name': 'TMDL Not Required', 'color': '#FFB74D'},  # Pale Orange - STREAMS
    
    # Impaired Categories (Red shades)
    '5': {'name': '303(d)', 'color': '#D32F2F'},  # Red - LAKES
    '5a': {'name': '303(d) - High Priority', 'color': '#C62828'},  # Dark Red - STREAMS
    
    # Other/Unknown
    'NA': {'name': 'Not Assessed', 'color': '#EEEEEE'},  # Very Light Gray
    'Other': {'name': 'Other Status', 'color': '#9C27B0'}  # Purple
}

# Date range slider limits
min_year = CSU_df['Activity_StartDate'].min().year
max_year = CSU_df['Activity_StartDate'].max().year

# Load Canals shp
canals_gdf = gpd.read_file('Final_GIS_Canal_Layer.shp')
canals_gdf = canals_gdf.to_crs('EPSG:4326')  # Reproject from NAD83 UTM Zone 13N to WGS84
print(f"Loaded {len(canals_gdf)} canal features and reprojected to EPSG:4326")

# Load exchange pts shp
exchange_gdf = gpd.read_file('21CW3XXX_Pts.shp')
exchange_gdf = exchange_gdf.to_crs('EPSG:4326')  # Reproject from NAD83 UTM Zone 13N to WGS84
print(f"Loaded {len(exchange_gdf)} exchange features and reprojected to EPSG:4326")

# Load streams/rivers
try:
    print("\n" + "="*80)
    print("LOADING STREAMS SHAPEFILE")
    print("="*80)
    streams_gdf = gpd.read_file('StreamsRivers.shp')
    print(f"✓ Loaded {len(streams_gdf)} stream/river features")
    print(f"  Original CRS: {streams_gdf.crs}")
    
    streams_gdf = streams_gdf.to_crs('EPSG:4326')
    print(f"  Reprojected to: {streams_gdf.crs}")
    
    # Debug: Check what columns are available
    print(f"  Columns: {streams_gdf.columns.tolist()}")
    print(f"  First 3 records:")
    for idx, row in streams_gdf.head(3).iterrows():
        for col in streams_gdf.columns:
            if 'name' in col.lower() or col == 'PNAME':
                print(f"    [{col}]: {row[col]}")
    print("="*80 + "\n")
    
except FileNotFoundError:
    streams_gdf = None
    print("="*80)
    print("⚠ StreamsRivers.shp not found in current directory")
    print(f"Current directory: {os.getcwd()}")
    print("="*80 + "\n")
except Exception as e:
    streams_gdf = None
    print("="*80)
    print(f"⚠ Error loading StreamsRivers.shp: {e}")
    import traceback
    traceback.print_exc()
    print("="*80 + "\n")

# Convert Color to integer since it's stored as string
exchange_gdf['Color'] = pd.to_numeric(exchange_gdf['Color'], errors='coerce').astype('Int64')
print(f"Converted Color column to numeric. Values: {exchange_gdf['Color'].unique()}")

# Filter to only Color 2 and 3
exchange_gdf = exchange_gdf[exchange_gdf['Color'].isin([2, 3])]
print(f"Filtered to {len(exchange_gdf)} exchange features (Color 2 and 3 only)")

# Global units mapping - used throughout the dashboard
UNITS_MAP = {
    'Selenium': 'μg/L',
    'Iron': 'μg/L', 
    'Arsenic': 'μg/L',
    'Lead': 'μg/L',
    'Aluminum': 'μg/L',
    'Manganese': 'μg/L',
    'Cadmium': 'μg/L',
    'Copper': 'μg/L',
    'Zinc': 'μg/L',
    'Calcium': 'μg/L',
    'Cobalt': 'μg/L',
    'Silver': 'μg/L',
    'Uranium': 'μg/L',
    'Magnesium': 'mg/L',
    'Potassium': 'mg/L',
    'Sodium': 'mg/L',
    'pH': 'standard units',
    'Temperature, water': '°C',
    'Conductivity': 'μS/cm',
    'Specific conductance': 'μS/cm',
    'Flow': 'cfs',
    'Hardness, Ca, Mg': 'mg/L',
    'Hardness, non-carbonate': 'mg/L',
    'Hardness, carbonate': 'mg/L',
    'Total hardness': 'mg/L',
    'Total suspended solids': 'mg/L',
    'Total Suspended Solids': 'mg/L',
    'Total dissolved solids': 'mg/L',
    'Turbidity': 'NTU',
    'Escherichia coli': 'CFU/100mL',
    'Escherichia Coli': 'CFU/100mL',
    'Nitrogen': 'mg/L',
    'Nitrate': 'mg/L',
    'Nitrite': 'mg/L',
    'Nitrate + Nitrite': 'mg/L',
    'Nitrite + Nitrate': 'mg/L',
    'Ammonia': 'mg/L',
    'Ammonia-nitrogen': 'mg/L',
    'Ammonia and ammonium': 'mg/L',
    'Phosphorus': 'mg/L',
    'Total Phosphorus': 'mg/L',
    'Ammonium': 'mg/L',
    'Orthophosphate': 'mg/L',
    'Phosphate-phosphorus': 'mg/L',
    'Sulfate': 'mg/L',
    'Salinity': 'ppt',
    'Dissolved oxygen': 'mg/L',
    'Dissolved Oxygen (DO)': 'mg/L',
    'Oxygen': 'mg/L'
}

# Convert units in CSU_df to standard units
def standardize_water_quality_units(df):
    """
    Standardize units for water quality parameters in CSU_df
    Only converts units that are mathematically equivalent, preserving analytical method distinctions
    """
    print("\n=== STARTING UNIT STANDARDIZATION ===\n")
    
    # Create a copy to avoid modifying original
    df_standardized = df.copy()
    
    # Track conversions
    conversions_made = []
    
    # Helper function to convert values
    def convert_and_log(mask, characteristic, old_unit, new_unit, factor, description):
        if mask.any():
            count = mask.sum()
            df_standardized.loc[mask, 'Result_Measure'] = df_standardized.loc[mask, 'Result_Measure'] * factor
            df_standardized.loc[mask, 'Result_MeasureUnit'] = new_unit
            conversions_made.append(f"{characteristic}: {count} records converted from {old_unit} to {new_unit}")
            print(f"Converted {count} {characteristic} records: {old_unit} → {new_unit} (factor: {factor})")
    
    # Helper function for case-insensitive unit matching
    def create_case_insensitive_mask(characteristic, units_list):
        char_mask = df_standardized['Result_Characteristic'] == characteristic
        unit_mask = df_standardized['Result_MeasureUnit'].str.lower().isin([u.lower() for u in units_list])
        return char_mask & unit_mask
    
    # TRACE METALS: mg/L to μg/L (these should be in μg/L)
    trace_metals = ['Selenium', 'Aluminum', 'Arsenic', 'Cadmium', 'Copper', 'Iron', 
                    'Lead', 'Manganese', 'Zinc', 'Silver', 'Cobalt', 'Uranium']
    
    for metal in trace_metals:
        metal_mg = create_case_insensitive_mask(metal, ['mg/L', 'mg/l', 'MG/L', 'Mg/L'])
        convert_and_log(metal_mg, metal, 'mg/L', 'ug/L', 1000, 'mg/L to μg/L')
    
    # MAJOR IONS: Keep in mg/L, but convert ug/L to mg/L if needed
    major_ions = ['Calcium', 'Magnesium', 'Potassium', 'Sodium', 'Sulfate', 
                  'Phosphorus', 'Total Phosphorus', 'Orthophosphate', 'Phosphate-phosphorus']
    
    for ion in major_ions:
        ion_ug = create_case_insensitive_mask(ion, ['ug/L', 'μg/L', 'UG/L', 'Ug/L', 'ug/l'])
        convert_and_log(ion_ug, ion, 'ug/L', 'mg/L', 0.001, 'μg/L to mg/L')
    
    # NITROGEN COMPOUNDS: Keep in mg/L, convert ug/L to mg/L if needed
    nitrogen_compounds = ['Nitrogen', 'Nitrate', 'Nitrite', 'Nitrate + Nitrite', 
                         'Nitrite + Nitrate', 'Ammonia', 'Ammonia-nitrogen', 
                         'Ammonia and ammonium', 'Ammonium', 'Total Kjeldahl Nitrogen']
    
    for compound in nitrogen_compounds:
        compound_ug = create_case_insensitive_mask(compound, ['ug/L', 'μg/L', 'UG/L', 'Ug/L', 'ug/l'])
        convert_and_log(compound_ug, compound, 'ug/L', 'mg/L', 0.001, 'μg/L to mg/L')
    
    # SOLIDS: Keep in mg/L
    solids = ['Total Suspended Solids', 'Total suspended solids', 'Total dissolved solids']
    
    for solid in solids:
        solid_ug = create_case_insensitive_mask(solid, ['ug/L', 'μg/L', 'UG/L', 'Ug/L', 'ug/l'])
        convert_and_log(solid_ug, solid, 'ug/L', 'mg/L', 0.001, 'μg/L to mg/L')
    
    # HARDNESS compounds: Keep in mg/L
    hardness_types = ['Hardness, Ca, Mg', 'Hardness, non-carbonate', 
                     'Hardness, carbonate', 'Total hardness']
    
    for hardness in hardness_types:
        hardness_ug = create_case_insensitive_mask(hardness, ['ug/L', 'μg/L', 'UG/L', 'Ug/L', 'ug/l'])
        convert_and_log(hardness_ug, hardness, 'ug/L', 'mg/L', 0.001, 'μg/L to mg/L')
    
    # PH: Standardize to "std units"
    ph_various = df_standardized['Result_Characteristic'] == 'pH'
    if ph_various.any():
        df_standardized.loc[ph_various, 'Result_MeasureUnit'] = 'std units'
        count = ph_various.sum()
        conversions_made.append(f"pH: {count} records standardized to 'std units'")
        print(f"Standardized {count} pH records to 'std units'")
    
    # CONDUCTIVITY: Standardize to μS/cm
    conductivity_chars = ['Conductivity', 'Specific conductance']
    conductivity_units = {
        'ms/cm': 1000,      # millisiemens to microsiemens
        'mS/cm': 1000,
        'us/cm': 1,         # already correct
        'μS/cm': 1,
        'uS/cm': 1,
        's/cm': 1000000,    # siemens to microsiemens
        'S/cm': 1000000
    }
    
    for cond_char in conductivity_chars:
        for unit, factor in conductivity_units.items():
            if factor != 1:
                cond_mask = (df_standardized['Result_Characteristic'] == cond_char) & \
                           (df_standardized['Result_MeasureUnit'].str.lower() == unit.lower())
                convert_and_log(cond_mask, cond_char, unit, 'uS/cm', factor, f'{unit} to μS/cm')
    
    # FLOW UNITS: Standardize to cfs
    flow_chars = ['Flow', 'Stream flow, instantaneous', 'Flow rate, instantaneous', 'Stream flow']
    
    for flow_char in flow_chars:
        # ft3/s, ft3/sec → cfs (just rename, same unit)
        flow_ft3s = (df_standardized['Result_Characteristic'] == flow_char) & \
                    (df_standardized['Result_MeasureUnit'].str.lower().isin(['ft3/s', 'ft3/sec', 'ft³/s', 'ft³/sec']))
        if flow_ft3s.any():
            df_standardized.loc[flow_ft3s, 'Result_MeasureUnit'] = 'cfs'
            count = flow_ft3s.sum()
            conversions_made.append(f"{flow_char}: {count} records renamed ft3/s → cfs")
            print(f"Renamed {count} {flow_char} records: ft3/s → cfs")
        
        # m3/sec → cfs
        flow_m3s = (df_standardized['Result_Characteristic'] == flow_char) & \
                   (df_standardized['Result_MeasureUnit'].str.lower().isin(['m3/sec', 'm³/sec', 'm3/s', 'm³/s']))
        convert_and_log(flow_m3s, flow_char, 'm3/sec', 'cfs', 35.3147, 'm³/s to cfs')
        
        # Mgd → cfs
        flow_mgd = (df_standardized['Result_Characteristic'] == flow_char) & \
                   (df_standardized['Result_MeasureUnit'].str.lower().isin(['mgd', 'mgal/d']))
        convert_and_log(flow_mgd, flow_char, 'Mgd', 'cfs', 1.547, 'MGD to cfs')
        
        # gal/min → cfs
        flow_gpm = (df_standardized['Result_Characteristic'] == flow_char) & \
                   (df_standardized['Result_MeasureUnit'].str.lower().isin(['gal/min', 'gpm', 'gallons/min']))
        convert_and_log(flow_gpm, flow_char, 'gal/min', 'cfs', 0.002228, 'gal/min to cfs')
    
    # HARDNESS: Rename "Hardness as CaCO3" for consistency
    hardness_caco3 = df_standardized['Result_Characteristic'] == 'Hardness as CaCO3'
    if hardness_caco3.any():
        df_standardized.loc[hardness_caco3, 'Result_Characteristic'] = 'Hardness, Ca, Mg'
        count = hardness_caco3.sum()
        conversions_made.append(f"Hardness: {count} records renamed 'Hardness as CaCO3' → 'Hardness, Ca, Mg'")
        print(f"Renamed {count} hardness records for consistency")
    
    # TOTAL SUSPENDED SOLIDS: Assign 'Total' fraction if blank
    tss_blank_fraction = (df_standardized['Result_Characteristic'].isin(['Total Suspended Solids', 'Total suspended solids'])) & \
                         (df_standardized['Result_SampleFraction'].isna() | 
                          (df_standardized['Result_SampleFraction'] == ''))
    if tss_blank_fraction.any():
        df_standardized.loc[tss_blank_fraction, 'Result_SampleFraction'] = 'Total'
        count = tss_blank_fraction.sum()
        conversions_made.append(f"Total Suspended Solids: {count} records assigned 'Total' fraction")
        print(f"Assigned 'Total' fraction to {count} TSS records")

    # TEMPERATURE: deg F to deg C
    temp_f = create_case_insensitive_mask('Temperature, water', ['deg F', 'F', 'deg f', 'Deg F', '°F'])
    if temp_f.any():
        df_standardized.loc[temp_f, 'Result_Measure'] = (df_standardized.loc[temp_f, 'Result_Measure'] - 32) * 5/9
        df_standardized.loc[temp_f, 'Result_MeasureUnit'] = 'deg C'
        count = temp_f.sum()
        conversions_made.append(f"Temperature, water: {count} records converted °F to °C")
        print(f"Converted {count} temperature records: °F to °C")
    
    # DISSOLVED OXYGEN: Standardize to mg/L
    do_chars = ['Dissolved oxygen', 'Dissolved Oxygen (DO)', 'Oxygen']
    for do_char in do_chars:
        do_ug = create_case_insensitive_mask(do_char, ['ug/L', 'μg/L', 'UG/L', 'Ug/L', 'ug/l'])
        convert_and_log(do_ug, do_char, 'ug/L', 'mg/L', 0.001, 'μg/L to mg/L')
    
    # Print summary
    print(f"\n=== UNIT STANDARDIZATION COMPLETE ===")
    print(f"Total conversions made: {len(conversions_made)}")
    
    print("\nNOTE: The following units were preserved to maintain analytical method distinctions:")
    print("  - E. coli: MPN/100mL, CFU/100mL, #/100mL (different counting methods)")
    print("  - Turbidity: NTU, FNU, NTRU (different optical measurement principles)")
    
    return df_standardized, conversions_made

# Apply unit standardization
CSU_df_standardized, conversion_log = standardize_water_quality_units(CSU_df)

# Usage: Apply to CSU_df
print("\nOriginal data shape:", CSU_df.shape)
print("Standardized data shape:", CSU_df_standardized.shape)

# Defragment the DataFrame after all the unit conversions
CSU_df_standardized = CSU_df_standardized.copy()
print("✓ DataFrame defragmented")

# Replace original dataframe
CSU_df = CSU_df_standardized

# Save conversion log for reference
with open('unit_conversion_log.txt', 'w', encoding='utf-8') as f:
    f.write("Water Quality Unit Conversion Log\n")
    f.write("=" * 40 + "\n\n")
    for conversion in conversion_log:
        # Replace Unicode arrow with ASCII equivalent for file compatibility
        safe_conversion = conversion.replace('→', '->')
        f.write(f"{safe_conversion}\n")
    f.write("\n\nPreserved Units (Different Analytical Methods):\n")
    f.write("- E. coli: MPN/100mL, CFU/100mL, #/100mL\n")
    f.write("- Turbidity: NTU, FNU, NTRU\n")

print("\nUnit conversion log saved to 'unit_conversion_log.txt'")


# Read HUC8 centroids for basin dropdown
huc_centroids = pd.read_csv('HUC8_Centroids.csv')

huc_to_name = dict(zip(huc_centroids['huc8'], huc_centroids['name']))  
name_to_huc = dict(zip(huc_centroids['name'], huc_centroids['huc8']))

# Get base characteristics from WQX data
base_characteristics = sorted(CSU_df['Result_Characteristic'].unique().tolist())

# Add USGS daily specific conductance if USGS data is available
if HAS_USGS_DATA:
    base_characteristics.append('Specific conductance (USGS-daily)')
    base_characteristics = sorted(base_characteristics)

CHARACTERISTICS = ['All'] + base_characteristics

BASINS = ['All'] + sorted(huc_centroids['name'].unique().tolist())
FRACTIONS = sorted(CSU_df['Result_SampleFraction'].dropna().unique())
SAMPLE_TYPES = ['All'] + sorted(CSU_df['Activity_MediaSubdivision'].dropna().unique().tolist())
SITES = ['All'] + sorted(CSU_df['Location_Name'].dropna().unique().tolist())

print(f"Available sample types: {SAMPLE_TYPES}")
BASINS_GDF = gpd.read_file('huc8_boundaries.geojson')

# Basin Centroids
data_initial = [
    dict(
    lat = CSU_df['Location_LatitudeStandardized'],
    lon = CSU_df['Location_LongitudeStandardized'],
    type = 'scattermapbox',
    hovertext=CSU_df['Location_Name'],
    marker = dict(size = 5, color = 'blue', opacity = 1),
    name='Site Location',
    showlegend=False
    ),
    dict(
    lat = huc_centroids['lat'],
    lon = huc_centroids['lon'],
    type = 'scattermapbox',
    hovertext=huc_centroids['name'],
    hovermode='closest',
    marker = dict(size = 100, color = 'white', opacity = 0),
    showlegend=False
    )
]

# Code to convert .shp files into .geojson that can be added as mapbox layer
with open('huc8_boundaries.geojson') as f:
    temp_file = json.load(f)

layer = dict(
    sourcetype='geojson',
    source=temp_file,
    type='fill',
    fill='lightblue',
    color='lightblue',
    opacity=0.3,
    name='Basin Boundaries',
    below='traces'
)

mapbox_access_token = 'pk.eyJ1IjoiY29vcGVyLXAiLCJhIjoiY2x3a3Y4c2k5MDh5bjJqcGIycXV6Znl3biJ9.4J3P3HOVVTiVaY_lW5Ew2Q'
mapbox_style = 'satellite-streets'

# App Layout 
app.layout = html.Div(
    id='root',
    children=[
        # Header section
        html.Div(
            id='header',
            children=[
                html.H1('Colorado Springs Utilities Water Quality Data Dashboard', 
                       style={'text-align': 'center', 'color': '#ffffff', 'margin-bottom': '30px',
                              'font-size': '28px', 'font-weight': '300'})
            ],
            style={'padding': '20px 0', 'background-color': '#2d2d2d', 'margin-bottom': '20px'}
        ),
        
        # Modal for pop up plot
        dbc.Modal(
            [
                dbc.ModalHeader(
                    dbc.ModalTitle(id="site-modal-title"),
                    close_button=True,
                    style={'background-color': '#2d2d2d', 'color': '#ffffff'}
                ),
                dbc.ModalBody(
                    [
                        html.Div(id="site-modal-info", style={'margin-bottom': '20px', 'color': '#ffffff'}),
                        dash_table.DataTable(
                            id='site-stats-table',
                            columns=[
                                {'name': 'Characteristic', 'id': 'Characteristic'},
                                {'name': 'Organization', 'id': 'Organization'},
                                {'name': 'Min', 'id': 'Min'},
                                {'name': 'Max', 'id': 'Max'},
                                {'name': 'Mean', 'id': 'Mean'},
                                {'name': 'Median', 'id': 'Median'},
                                {'name': 'Count', 'id': 'Count'}
                            ],
                            data=[],
                            style_cell={
                                'backgroundColor': '#2d2d2d',
                                'color': 'white',
                                'border': '1px solid #555',
                                'textAlign': 'left',
                                'padding': '12px',
                                'font-family': 'Arial, sans-serif',
                                'fontSize': '13px'
                            },
                            style_header={
                                'backgroundColor': '#404040',
                                'color': 'white',
                                'fontWeight': 'bold',
                                'border': '1px solid #555',
                                'textAlign': 'center'
                            },
                            style_data_conditional=[
                                {
                                    'if': {'row_index': 'odd'},
                                    'backgroundColor': '#333333'
                                }
                            ],
                            style_table={
                                'maxHeight': '400px',
                                'overflowY': 'auto'
                            }
                        )
                    ],
                    style={'background-color': '#1e1e1e'}
                ),
                dbc.ModalFooter(
                    dbc.Button("Close", id="close-site-modal", className="ms-auto", n_clicks=0),
                    style={'background-color': '#2d2d2d'}
                ),
            ],
            id="site-modal",
            size="xl",
            is_open=False,
            style={'color': '#ffffff'}
        ),

        # Large map section at the top
        html.Div(
            id='top-map-section',
            children=[
                html.Div([
                    html.H3('Monitoring Locations', 
                           style={'color': '#ffffff', 'margin-bottom': '15px', 'font-size': '18px'}),
                    
                    # Rivers & Streams Dropdown (above the map)
                    html.Div([
                        html.Label('Rivers & Streams:', 
                                style={'color': '#ffffff', 'font-weight': 'bold', 'margin-right': '10px', 'display': 'inline-block'}),
                        dcc.Dropdown(
                            id='rivers-toggle',  
                            options=[],  
                            value=[],
                            multi=True,
                            placeholder='Select rivers/streams to display...',
                            style={
                                'width': '500px', 
                                'display': 'inline-block',
                                'verticalAlign': 'middle'
                            }
                        )
                    ], style={'margin-bottom': '15px', 'display': 'flex', 'alignItems': 'center'}),

                    # CDPHE Stream Segmentation
                    html.Div([
                        html.Label('Additional Layers:', 
                                style={'color': '#ffffff', 'font-weight': 'bold', 'margin-bottom': '8px', 'display': 'block'}),
                        dcc.Checklist(
                            id='additional-layers-toggle',
                            options=[
                                {'label': ' Stream Segmentation (by category)', 'value': 'segments'},
                                {'label': ' Lakes & Reservoirs', 'value': 'lakes'}
                            ],
                            value=[],
                            style={'color': '#ffffff'},
                            labelStyle={'display': 'block', 'margin-bottom': '5px'}
                        )
                    ], style={'margin-bottom': '15px'}),
                    dcc.Graph(
                        id="basin-map",
                        figure=dict(
                            data=data_initial,
                            layout=dict(
                                mapbox=dict(
                                    layers=[layer],
                                    accesstoken=mapbox_access_token,
                                    style=mapbox_style,
                                    center=dict(lat=38.2, lon=-103.6),
                                    pitch=0,
                                    zoom=7,
                                ),
                                margin=dict(t=0, l=0, r=0, b=0),
                                paper_bgcolor='#1e1e1e',
                                showlegend=False
                            ),
                        ),
                        config=dict(scrollZoom=True, displayModeBar='hover'),
                        style={'height': '600px'}
                    ),
                ], style={
                    'background-color': '#2d2d2d',
                    'padding': '20px',
                    'border-radius': '8px',
                    'box-shadow': '0 4px 6px rgba(0, 0, 0, 0.3)'
                })
            ],
            style={'margin-bottom': '20px'}
        ),
        
        # Date Range Slider 
        html.Div(
            id='date-range-section',
            children=[
                html.Div([
                    html.Label('Date Range:', 
                             style={'color': '#ffffff', 'font-weight': 'bold', 'margin-bottom': '15px', 'display': 'block', 'font-size': '16px'}),
                    dcc.RangeSlider(
                        id='date-slider',
                        min=min(CSU_df['Activity_StartDate'].apply(pd.to_datetime)).year,
                        max=max(CSU_df['Activity_StartDate'].apply(pd.to_datetime)).year,
                        step=1,
                        marks={
                            year: {'label': str(year), 'style': {'color': '#ffffff', 'font-size': '12px'}}
                            for year in range(
                                min(CSU_df['Activity_StartDate'].apply(pd.to_datetime)).year,
                                max(CSU_df['Activity_StartDate'].apply(pd.to_datetime)).year + 1, 2
                            )
                        },
                        value=[1986, 2025],
                        tooltip={'placement': 'bottom', 'always_visible': True}
                    )
                ], style={'margin-bottom': '20px'})
            ],
            style={
                'background-color': '#2d2d2d',
                'padding': '20px',
                'border-radius': '10px',
                'box-shadow': '0 4px 6px rgba(0, 0, 0, 0.3)',
                'margin-bottom': '20px'
            }
        ),
        
        # Controls and Time Series side by side
        html.Div(
            id='controls-and-analysis-row',
            children=[
                # Left column - Controls (1/3 width)
                html.Div(
                    id='left-controls-column',
                    children=[
                        html.Div(
                            id='dropdown-filters',
                            children=[
                                html.Div([
                                    html.Label('Basin:', 
                                             style={'color': '#ffffff', 'font-weight': 'bold', 'margin-bottom': '8px', 'display': 'block'}),
                                    dcc.Dropdown(
                                        BASINS,
                                        id='basin-select',
                                        value='All',
                                        style={'margin-bottom': '20px'}
                                    )
                                ], style={'margin-bottom': '15px'}),
                                html.Div([
                                    html.Label('Monitoring Location:', 
                                            style={'color': '#ffffff', 'font-weight': 'bold', 'margin-bottom': '8px', 'display': 'block'}),
                                    dcc.Dropdown(
                                        SITES,
                                        id='site-select',
                                        value='All',
                                        multi=True,
                                        style={'margin-bottom': '20px'}
                                    )
                                ], style={'margin-bottom': '15px'}),
                                # CANALS
                                html.Div([
                                    html.Label('Canals/Ditches:', 
                                            style={'color': '#ffffff', 'font-weight': 'bold', 'margin-bottom': '8px', 'display': 'block'}),
                                    dcc.Dropdown(
                                        id='canal-select',
                                        options=[],
                                        value=[],
                                        multi=True,
                                        placeholder='Select canals to display (or leave empty for none)...',
                                        style={'margin-bottom': '20px'}
                                    )
                                ], style={'margin-bottom': '15px'}),
                                # STRUCTURES (Exchange Points)
                                html.Div([
                                    html.Label('Exchange Points:', 
                                            style={'color': '#ffffff', 'font-weight': 'bold', 'margin-bottom': '8px', 'display': 'block'}),
                                    dcc.Dropdown(
                                        id='exchange-select',
                                        options=[],
                                        value=[],
                                        multi=True,
                                        placeholder='Select exchange points to display (or leave empty for none)...',
                                        style={'margin-bottom': '20px'}
                                    )
                                ], style={'margin-bottom': '15px'}),
                                html.Div([
                                    html.Label('Sample Type:', 
                                            style={'color': '#ffffff', 'font-weight': 'bold', 'margin-bottom': '8px', 'display': 'block'}),
                                    dcc.Dropdown(
                                        SAMPLE_TYPES,
                                        id='sample-type-select',
                                        value='All',
                                        style={'margin-bottom': '20px'}
                                    )
                                ], style={'margin-bottom': '15px'}),
                                html.Div([
                                    html.Label('Characteristic:', 
                                             style={'color': '#ffffff', 'font-weight': 'bold', 'margin-bottom': '8px', 'display': 'block'}),
                                    dcc.Dropdown(
                                        CHARACTERISTICS,
                                        id='characteristic-select',
                                        value='All',
                                        style={'margin-bottom': '20px'}
                                    )
                                ], style={'margin-bottom': '15px'}),
                                
                                html.Div([
                                    html.Label('Sample Fraction:', 
                                             style={'color': '#ffffff', 'font-weight': 'bold', 'margin-bottom': '8px', 'display': 'block'}),
                                    dcc.Dropdown(
                                        [],
                                        id='fraction-select',
                                        value='All',
                                        style={'margin-bottom': '20px'}
                                    )
                                ], style={'margin-bottom': '15px'}),
                                
                                html.Div([
                                    html.Label('Additional Data:', 
                                            style={'color': '#ffffff', 'font-weight': 'bold', 'margin-bottom': '8px', 'display': 'block'}),
                                    dcc.Checklist(
                                        id='additional-data-toggle',
                                        options=[
                                            {'label': ' WQX Flow (spot measurements)', 'value': 'wqx_flow'},
                                            {'label': ' USGS Daily Flow', 'value': 'usgs_flow'}
                                        ],
                                        value=[],
                                        style={'color': '#ffffff'},
                                        labelStyle={'display': 'block', 'margin-bottom': '5px'}
                                    )
                                ], style={'margin-bottom': '15px'})
                            ],
                            style={
                                'background-color': '#2d2d2d',
                                'padding': '25px',
                                'border-radius': '10px',
                                'box-shadow': '0 4px 6px rgba(0, 0, 0, 0.3)',
                                'height': 'fit-content'
                            }
                        )
                    ],
                    style={
                        'width': '32%',
                        'display': 'inline-block',
                        'vertical-align': 'top',
                        'margin-right': '1%'
                    }
                ),
                
                # Right column - Time series (2/3 width)
                html.Div(
                    id='right-analysis-column',
                    children=[
                        html.Div([
                            html.Div([
                                html.H3('Time Series Analysis', 
                                    style={'color': '#ffffff', 'margin-bottom': '15px', 'font-size': '18px', 'display': 'inline-block'}),
                                html.Button(
                                    '⬇ Export Data',
                                    id='export-timeseries-btn',
                                    n_clicks=0,
                                    style={
                                        'float': 'right',
                                        'background-color': '#4fc3f7',
                                        'color': '#1e1e1e',
                                        'border': 'none',
                                        'padding': '10px 20px',
                                        'border-radius': '5px',
                                        'cursor': 'pointer',
                                        'font-weight': 'bold',
                                        'font-size': '14px'
                                    }
                                ),
                                dcc.Download(id='download-timeseries-csv')
                            ], style={'margin-bottom': '15px'}),
                            dcc.Graph(
                                id='analysis',
                                figure=dict(data=None, layout=dict([])),
                                style={'height': '700px'}
                            )
                        ], style={
                            'background-color': '#2d2d2d',
                            'padding': '20px',
                            'border-radius': '10px',
                            'box-shadow': '0 4px 6px rgba(0, 0, 0, 0.3)'
                        })
                    ],
                    style={
                        'width': '67%',
                        'display': 'inline-block',
                        'vertical-align': 'top'
                    }
                ),
            ],
             style={'margin-bottom': '30px', 'white-space': 'nowrap'}
        ), 
        
        # Bottom section - Analysis Period, Summary and heatmap
        html.Div(
            id='summary-section',
            children=[
                # Analysis Period Display 
                html.Div([
                    html.Div(
                        id='date-range-display',
                        children=[]
                    )
                ], style={
                    'background-color': '#2d2d2d',
                    'padding': '20px',
                    'border-radius': '10px',
                    'box-shadow': '0 4px 6px rgba(0, 0, 0, 0.3)',
                    'margin-bottom': '20px'
                }),
                
                # Summary table
                html.Div([
                    html.H3('Summary Statistics', 
                           style={'color': '#ffffff', 'margin-bottom': '15px', 'font-size': '18px'}),
                    dash_table.DataTable(
                        data=None,
                        id='summary-table',
                        columns=[
                            {'name': 'Statistic', 'id': 'Statistic'},
                            {'name': 'Value', 'id': 'Value'},
                            {'name': 'Units', 'id': 'Units'}
                        ],
                        style_cell={
                            'backgroundColor': '#2d2d2d',
                            'color': 'white',
                            'border': '1px solid #555',
                            'textAlign': 'left',
                            'padding': '12px',
                            'font-family': 'Arial, sans-serif',
                            'fontSize': '13px'
                        },
                        style_header={
                            'backgroundColor': '#404040',
                            'color': 'white',
                            'fontWeight': 'bold',
                            'border': '1px solid #555',
                            'textAlign': 'center'
                        },
                        style_data_conditional=[
                            {
                                'if': {'row_index': 'odd'},
                                'backgroundColor': '#333333'
                            },
                            {
                                'if': {
                                    'filter_query': '{Statistic} contains "Threshold"',
                                },
                                'backgroundColor': '#2a4d3a',
                            },
                            {
                                'if': {
                                    'filter_query': '{Statistic} contains "Above"',
                                },
                                'backgroundColor': '#4d2a2a',
                            }
                        ],
                        style_table={
                            'maxHeight': '400px',
                            'overflowY': 'auto'
                        }
                    )
                ], style={
                    'background-color': '#2d2d2d',
                    'padding': '20px',
                    'border-radius': '10px',
                    'box-shadow': '0 4px 6px rgba(0, 0, 0, 0.3)',
                    'margin-bottom': '20px'
                }),
                
                # Heatmap
                html.Div([
                    html.H3('Spatial and Temporal Heatmap', 
                           style={'color': '#ffffff', 'margin-bottom': '15px', 'font-size': '18px'}),
                    dcc.Graph(
                        id='heatmap',
                        figure={},
                        style={'height': '400px'}
                    )
                ], style={
                    'background-color': '#2d2d2d',
                    'padding': '20px',
                    'border-radius': '10px',
                    'box-shadow': '0 4px 6px rgba(0, 0, 0, 0.3)'
                })
            ]
        )  
    ],  
    style={
        'background-color': '#1e1e1e',
        'min-height': '100vh',
        'padding': '0 20px 20px 20px',
        'font-family': 'Arial, sans-serif'
    }
)

@app.callback(
    [Output('fraction-select', 'options'),
     Output('fraction-select', 'value')],
    [Input('characteristic-select', 'value')]
)
def update_fraction_options(characteristic):
    if characteristic is None:
        return [], None
    
    # Get available fractions for this characteristic
    char_data = CSU_df[CSU_df['Result_Characteristic'] == characteristic]
    available_fractions = sorted(char_data['Result_SampleFraction'].dropna().unique())
    
    # Create options list
    options = [{'label': fraction, 'value': fraction} for fraction in available_fractions]
    
    # Set default value (first available fraction)
    default_value = available_fractions[0] if available_fractions else None
    
    print(f"Available fractions for {characteristic}: {available_fractions}")
    
    return options, default_value

# Update site options based on selected basin
@app.callback(
    [Output('site-select', 'options'),
     Output('site-select', 'value')],
    [Input('basin-select', 'value')]
)
def update_site_options(basin):
    """Update monitoring location dropdown based on selected basin"""
    
    # If "All" basins selected, show all sites
    if basin is None or basin == "All":
        # Get sites from both WQX and USGS data
        wqx_sites = set(CSU_df['Location_Name'].dropna().unique())
        usgs_sites = set(USGS_df['Site_Name'].dropna().unique()) if HAS_USGS_DATA else set()
        
        # Combine both sets
        available_sites = sorted(list(wqx_sites | usgs_sites))
        
        options = [{'label': 'All', 'value': 'All'}] + [{'label': site, 'value': site} for site in available_sites]
        return options, ['']  # Return list for multi-select
    
    # Filter sites by basin using spatial join
    try:
        # Get all unique sites with coordinates from WQX
        wqx_sites_df = CSU_df[['Location_Name', 'Location_LatitudeStandardized', 'Location_LongitudeStandardized']].drop_duplicates()
        wqx_sites_df = wqx_sites_df.dropna()
        
        # Convert to numeric
        wqx_sites_df['Location_LatitudeStandardized'] = pd.to_numeric(wqx_sites_df['Location_LatitudeStandardized'], errors='coerce')
        wqx_sites_df['Location_LongitudeStandardized'] = pd.to_numeric(wqx_sites_df['Location_LongitudeStandardized'], errors='coerce')
        wqx_sites_df = wqx_sites_df.dropna(subset=['Location_LatitudeStandardized', 'Location_LongitudeStandardized'])
        
        # Create GeoSeries of points
        points = gpd.GeoSeries(gpd.points_from_xy(
            wqx_sites_df['Location_LongitudeStandardized'], 
            wqx_sites_df['Location_LatitudeStandardized']
        )).set_crs('EPSG:4326')
        
        # Find the correct basin column name
        basin_col = None
        for col in ['name', 'NAME', 'BASINS', 'BASIN_NAM', 'NAMELSAD']:
            if col in BASINS_GDF.columns:
                basin_col = col
                break
        
        if basin_col is None:
            print("ERROR: No basin column found")
            # Fallback to all sites
            wqx_sites = set(CSU_df['Location_Name'].dropna().unique())
            usgs_sites = set(USGS_df['Site_Name'].dropna().unique()) if HAS_USGS_DATA else set()
            available_sites = sorted(list(wqx_sites | usgs_sites))
            options = [{'label': 'All', 'value': 'All'}] + [{'label': site, 'value': site} for site in available_sites]
            return options, ['']
        
        # Get basin geometry
        basin_match = BASINS_GDF[BASINS_GDF[basin_col] == basin]
        if basin_match.empty:
            print(f"ERROR: Basin '{basin}' not found")
            # Fallback to all sites
            wqx_sites = set(CSU_df['Location_Name'].dropna().unique())
            usgs_sites = set(USGS_df['Site_Name'].dropna().unique()) if HAS_USGS_DATA else set()
            available_sites = sorted(list(wqx_sites | usgs_sites))
            options = [{'label': 'All', 'value': 'All'}] + [{'label': site, 'value': site} for site in available_sites]
            return options, ['']
        
        basin_geom = basin_match['geometry'].iloc[0]
        
        # Find WQX sites within basin
        wqx_in_basin = points.within(basin_geom, align=False)
        wqx_in_basin.index = wqx_sites_df.index
        filtered_wqx_sites = set(wqx_sites_df[wqx_in_basin]['Location_Name'].unique())
        
        # Get USGS-only sites (sites that don't have WQX equivalents)
        usgs_only_sites = set()
        if HAS_USGS_DATA and USGS_MAPPING is not None:
            usgs_only_sites = set(USGS_MAPPING[~USGS_MAPPING['WQX_Site_Name'].isin(CSU_df['Location_Name'])]['WQX_Site_Name'].unique())
        
        # Combine WQX sites in basin + USGS-only sites (which appear in all basins)
        basin_sites = sorted(list(filtered_wqx_sites | usgs_only_sites))
        
        options = [{'label': 'All', 'value': 'All'}] + [{'label': site, 'value': site} for site in basin_sites]
        return options, ['']
        
    except Exception as e:
        print(f"Error in basin filtering: {e}")
        import traceback
        traceback.print_exc()
        # Fallback to all sites
        wqx_sites = set(CSU_df['Location_Name'].dropna().unique())
        usgs_sites = set(USGS_df['Site_Name'].dropna().unique()) if HAS_USGS_DATA else set()
        available_sites = sorted(list(wqx_sites | usgs_sites))
        options = [{'label': 'All', 'value': 'All'}] + [{'label': site, 'value': site} for site in available_sites]
        return options, ['']

@app.callback(
    Output('rivers-toggle', 'options'),
    [Input('basin-select', 'value')]
)
def update_rivers_dropdown(basin):
    """Populate rivers dropdown with Arkansas River and tributaries"""
    
    if streams_gdf is None:
        return [{'label': 'No streams data available', 'value': 'none', 'disabled': True}]
    
    try:
        print(f"\n=== UPDATE RIVERS DROPDOWN ===")
        print(f"Basin selected: {basin}")
        
        # Show ALL streams matching Arkansas River system
        arkansas_keywords = [
            'ARKANSAS',
            'FOUNTAIN',
            'ST. CHARLES', 
            'ST CHARLES',
            'HUERFANO',
            'APISHAPA',
            'PURGATOIRE',
            'HORSE',
            'TIMPAS',
            'CROOKED',
            'SALT'
        ]
        
        # Filter streams - look in PNAME column
        filtered_streams = streams_gdf[
            streams_gdf['PNAME'].str.contains('|'.join(arkansas_keywords), case=False, na=False)
        ]
        
        print(f"Found {len(filtered_streams)} stream segments matching Arkansas system")
        
        # Get unique river names
        river_names = sorted(filtered_streams['PNAME'].dropna().unique())
        
        print(f"Unique river names: {river_names}")
        
        if len(river_names) == 0:
            return [{'label': 'No Arkansas River system streams found', 'value': 'none', 'disabled': True}]
        
        # Create options with "All" at top
        options = [{'label': 'All Rivers & Streams', 'value': 'All'}]
        
        # Separate Arkansas River from tributaries
        arkansas_rivers = [name for name in river_names if 'ARKANSAS' in name.upper()]
        tributaries = [name for name in river_names if 'ARKANSAS' not in name.upper()]
        
        # Add Arkansas River section
        if arkansas_rivers:
            options.append({'label': '--- Arkansas River ---', 'value': 'header_ark', 'disabled': True})
            for name in sorted(arkansas_rivers):
                display_name = name.title() 
                options.append({'label': f"  {name}", 'value': name})
        
        # Add Tributaries section
        if tributaries:
            options.append({'label': '--- Tributaries ---', 'value': 'header_trib', 'disabled': True})
            for name in sorted(tributaries):
                display_name = name.title()
                options.append({'label': f"  {name}", 'value': name})
        
        print(f"Returning {len(options)} dropdown options")
        print("=== END RIVERS DROPDOWN ===\n")
        
        return options
        
    except Exception as e:
        print(f"❌ Error populating rivers dropdown: {e}")
        import traceback
        traceback.print_exc()
        return [{'label': 'Error loading rivers', 'value': 'error', 'disabled': True}]

# Callback to open modal and populate site statistics
@app.callback(
    [Output('site-modal', 'is_open'),
     Output('site-modal-title', 'children'),
     Output('site-modal-info', 'children'),
     Output('site-stats-table', 'data')],
    [Input('basin-map', 'clickData'),
     Input('close-site-modal', 'n_clicks'),
     Input('date-slider', 'value')],  
    [State('site-modal', 'is_open')],
    prevent_initial_call=True
)
def toggle_site_modal(clickData, close_clicks, date_range, is_open):
    """Open modal when clicking on a monitoring location and display site statistics"""
    
    ctx = dash.callback_context
    
    if not ctx.triggered:
        return False, "", "", []
    
    trigger_id = ctx.triggered[0]['prop_id'].split('.')[0]
    
    # If close button clicked, close the modal
    if trigger_id == 'close-site-modal':
        return False, "", "", []
    
    # If date slider changed and modal is open, update the data
    # If map clicked, process the click
    if (trigger_id == 'basin-map' and clickData) or (trigger_id == 'date-slider' and is_open):
        try:
            # Extract the clicked site name (or use existing site if date changed)
            if trigger_id == 'basin-map':
                clicked_text = clickData['points'][0].get('hovertext', '')
                
                # Handle the hovertext format (it might have <br> tags)
                if '<br>' in clicked_text:
                    site_name = clicked_text.split('<br>')[0]
                else:
                    site_name = clicked_text
                
                # Skip if clicked on basin centroids or other non-site points
                if not site_name or site_name in ['Other Stations', 'No Data Available', ''] or 'Basin' in site_name:
                    return False, "", "", []
            else:
                # Date slider changed - need to get the site name from current modal
                # This won't work perfectly, so let's just keep modal closed on date change for now
                return is_open, dash.no_update, dash.no_update, dash.no_update
            
            print(f"Clicked on site: {site_name}")
            print(f"Date range: {date_range[0]} - {date_range[1]}")
            
            # Filter data for this specific site
            site_data = CSU_df[CSU_df['Location_Name'] == site_name].copy()
            
            if site_data.empty:
                return False, "", "", []
            
            # Apply date filter
            site_data['Activity_StartDate'] = pd.to_datetime(site_data['Activity_StartDate'], errors='coerce')
            date_mask = (
                (site_data['Activity_StartDate'] >= datetime(year=date_range[0], month=1, day=1)) & 
                (site_data['Activity_StartDate'] <= datetime(year=date_range[1], month=12, day=31))
            )
            site_data = site_data[date_mask]
            
            if site_data.empty:
                # No data in this date range
                modal_title = f"📍 {site_name}"
                modal_info = html.Div([
                    html.P([
                        html.Strong("No data available for the selected date range: "),
                        f"{date_range[0]} - {date_range[1]}"
                    ], style={'margin': '5px 0', 'font-size': '14px', 'color': '#ff6b6b'})
                ])
                return True, modal_title, modal_info, []
            
            # Get site coordinates
            site_lat = site_data['Location_LatitudeStandardized'].iloc[0]
            site_lon = site_data['Location_LongitudeStandardized'].iloc[0]
            
            # Get organizations using Org_Identifier column
            if 'Org_Identifier' in site_data.columns:
                organizations = site_data['Org_Identifier'].dropna().unique()
                org_text = ", ".join(organizations) if len(organizations) > 0 else "Unknown"
            else:
                org_text = "Not available"
            
            # Get date range from filtered data
            earliest_date = site_data['Activity_StartDate'].min()
            latest_date = site_data['Activity_StartDate'].max()
            
            # Create modal title
            modal_title = f"📍 {site_name}"
            
            # Create info section
            modal_info = html.Div([
                html.P([
                    html.Strong("Coordinates: "),
                    f"{site_lat}, {site_lon}"
                ], style={'margin': '5px 0', 'font-size': '14px'}),
                html.P([
                    html.Strong("Selected Date Range: "),
                    f"{date_range[0]} - {date_range[1]}"
                ], style={'margin': '5px 0', 'font-size': '14px', 'color': '#4fc3f7'}),
                html.P([
                    html.Strong("Data Range: "),
                    f"{earliest_date.strftime('%B %d, %Y') if pd.notna(earliest_date) else 'N/A'} to {latest_date.strftime('%B %d, %Y') if pd.notna(latest_date) else 'N/A'}"
                ], style={'margin': '5px 0', 'font-size': '14px'}),
                html.P([
                    html.Strong("Total Measurements: "),
                    f"{len(site_data):,}"
                ], style={'margin': '5px 0', 'font-size': '14px'})
            ])
            
            # Calculate statistics by characteristic
            stats_data = []
            
            # Group by characteristic
            for characteristic in sorted(site_data['Result_Characteristic'].dropna().unique()):
                char_data = site_data[site_data['Result_Characteristic'] == characteristic].copy()
                
                # Convert to numeric
                char_data['Result_Measure'] = pd.to_numeric(char_data['Result_Measure'], errors='coerce')
                numeric_values = char_data['Result_Measure'].dropna()
                
                if len(numeric_values) > 0:
                    # Get organization(s) for this characteristic
                    if 'Org_Identifier' in char_data.columns:
                        char_orgs = char_data['Org_Identifier'].dropna().unique()
                        org_display = ", ".join(char_orgs[:2])  # Show first 2 orgs
                        if len(char_orgs) > 2:
                            org_display += f" (+{len(char_orgs)-2} more)"
                    else:
                        org_display = "N/A"
                    
                    # Get unit for this characteristic
                    unit = UNITS_MAP.get(characteristic, 'units')
                    
                    stats_data.append({
                        'Characteristic': f"{characteristic} ({unit})",
                        'Organization': org_display,
                        'Min': f"{numeric_values.min():.3f}",
                        'Max': f"{numeric_values.max():.3f}",
                        'Mean': f"{numeric_values.mean():.3f}",
                        'Median': f"{numeric_values.median():.3f}",
                        'Count': f"{len(numeric_values):,}"
                    })
            
            return True, modal_title, modal_info, stats_data
            
        except Exception as e:
            print(f"Error processing site click: {e}")
            import traceback
            traceback.print_exc()
            return False, "", "", []
    
    return is_open, "", "", []

# Update characteristic dropdown based on basin and site selection
@app.callback(
    [Output('characteristic-select', 'options'),
     Output('characteristic-select', 'value')],
    [Input('basin-select', 'value'),
     Input('site-select', 'value')]
)
def update_characteristic_options(basin, site):
    """Update characteristic dropdown based on selected basin and monitoring location"""

    # Handle site being a list (multi-select)
    site_list = []
    if site:
        if isinstance(site, list):
            site_list = [s for s in site if s != 'All']
        elif site != 'All':
            site_list = [site]
    
    # PRIORITY 1: If specific site(s) selected, show only characteristics at those sites
    if len(site_list) > 0:
        print(f">>> PRIORITY: Filtering by {len(site_list)} selected site(s)")
        
        if len(site_list) == 1:
            # Single site - show all its characteristics
            site_data = CSU_df[CSU_df['Location_Name'] == site_list[0]]
            available_characteristics = sorted(site_data['Result_Characteristic'].dropna().unique())
            print(f"Single site '{site_list[0]}': {len(available_characteristics)} characteristics")
        else:
            # Multiple sites - find intersection of characteristics (present at ALL sites)
            characteristic_sets = []
            for site_name in site_list:
                site_data = CSU_df[CSU_df['Location_Name'] == site_name]
                site_chars = set(site_data['Result_Characteristic'].dropna().unique())
                characteristic_sets.append(site_chars)
                print(f"Site '{site_name}': {len(site_chars)} characteristics")
            
            # Get intersection (characteristics present in ALL sites)
            common_characteristics = set.intersection(*characteristic_sets) if characteristic_sets else set()
            available_characteristics = sorted(list(common_characteristics))
            print(f"Found {len(available_characteristics)} COMMON characteristics across {len(site_list)} sites")
        
        # ADD USGS OPTION if data is available
        if HAS_USGS_DATA:
            available_characteristics = list(available_characteristics)
            available_characteristics.append('Specific conductance (USGS-daily)')
            available_characteristics = sorted(available_characteristics)

        if len(available_characteristics) == 0:
            if len(site_list) > 1:
                options = [{'label': 'No common characteristics at selected sites', 'value': 'All'}]
            else:
                options = [{'label': 'No data at selected site', 'value': 'All'}]
            return options, 'All'
        else:
            options = [{'label': 'All', 'value': 'All'}] + [{'label': char, 'value': char} for char in available_characteristics]
            return options, 'All'
    
    # PRIORITY 2: If basin selected (but no specific sites), filter by basin
    if basin is not None and basin != "All":
        print(f">>> Filtering by basin: {basin}")
        try:
            # Get all data with coordinates
            data_with_coords = CSU_df[
                CSU_df['Location_LatitudeStandardized'].notna() & 
                CSU_df['Location_LongitudeStandardized'].notna()
            ].copy()
            
            # Convert to numeric
            data_with_coords['Location_LatitudeStandardized'] = pd.to_numeric(data_with_coords['Location_LatitudeStandardized'], errors='coerce')
            data_with_coords['Location_LongitudeStandardized'] = pd.to_numeric(data_with_coords['Location_LongitudeStandardized'], errors='coerce')
            data_with_coords = data_with_coords.dropna(subset=['Location_LatitudeStandardized', 'Location_LongitudeStandardized'])
            
            # Create GeoSeries of points
            points = gpd.GeoSeries(gpd.points_from_xy(
                data_with_coords['Location_LongitudeStandardized'], 
                data_with_coords['Location_LatitudeStandardized']
            )).set_crs('EPSG:4326')
            
            # Find the correct basin column name
            basin_col = None
            for col in ['name', 'NAME', 'BASINS', 'BASIN_NAM', 'NAMELSAD']:
                if col in BASINS_GDF.columns:
                    basin_col = col
                    break
            
            if basin_col is None:
                print("ERROR: No basin column found")
                available_characteristics = sorted(CSU_df['Result_Characteristic'].dropna().unique())
                options = [{'label': 'All', 'value': 'All'}] + [{'label': char, 'value': char} for char in available_characteristics]
                return options, 'All'
            
            # Get basin geometry
            basin_match = BASINS_GDF[BASINS_GDF[basin_col] == basin]
            if basin_match.empty:
                print(f"ERROR: Basin '{basin}' not found")
                available_characteristics = sorted(CSU_df['Result_Characteristic'].dropna().unique())
                options = [{'label': 'All', 'value': 'All'}] + [{'label': char, 'value': char} for char in available_characteristics]
                return options, 'All'
            
            basin_geom = basin_match['geometry'].iloc[0]
            
            # Find data points within basin
            data_in_basin = points.within(basin_geom, align=False)
            data_in_basin.index = data_with_coords.index
            
            # Get data in basin
            basin_data = data_with_coords[data_in_basin]
            available_characteristics = sorted(basin_data['Result_Characteristic'].dropna().unique())
            
            print(f"Found {len(available_characteristics)} characteristics in basin")
            
            # ADD USGS OPTION
            if HAS_USGS_DATA:
                available_characteristics = list(available_characteristics)
                available_characteristics.append('Specific conductance (USGS-daily)')
                available_characteristics = sorted(available_characteristics)

            # Create options
            if len(available_characteristics) == 0:
                options = [{'label': 'No data in selected basin', 'value': 'All'}]
                return options, 'All'
            else:
                options = [{'label': 'All', 'value': 'All'}] + [{'label': char, 'value': char} for char in available_characteristics]
                return options, 'All'
        
        except Exception as e:
            print(f"ERROR in characteristic filtering: {e}")
            import traceback
            traceback.print_exc()
            
            # Fallback to all characteristics on error
            available_characteristics = sorted(CSU_df['Result_Characteristic'].dropna().unique())
            options = [{'label': 'All', 'value': 'All'}] + [{'label': char, 'value': char} for char in available_characteristics]
            return options, 'All'
    
    # PRIORITY 3: No filters - show all characteristics
    print(f">>> No filters - showing all characteristics")
    available_characteristics = sorted(CSU_df['Result_Characteristic'].dropna().unique())

    # ADD USGS OPTION
    if HAS_USGS_DATA:
        available_characteristics = list(available_characteristics)
        available_characteristics.append('Specific conductance (USGS-daily)')
        available_characteristics = sorted(available_characteristics)

    options = [{'label': 'All', 'value': 'All'}] + [{'label': char, 'value': char} for char in available_characteristics]
    return options, 'All'

# Callback to populate canal dropdown based on selected basin
@app.callback(
    Output('canal-select', 'options'),
    [Input('basin-select', 'value')]
)
def update_canal_dropdown(basin):
    print(f"\n=== UPDATE CANAL DROPDOWN CALLED ===")
    print(f"Basin selected: '{basin}' (type: {type(basin)})")
    
    try:
        # If a specific basin is selected, filter canals to that basin
        if basin and basin != 'All':
            print(f">>> BRANCH: Filtering canals for specific basin: {basin}")
            
            # Find the basin column
            basin_col = None
            for col in ['name', 'NAME', 'BASINS', 'BASIN_NAM', 'NAMELSAD']:
                if col in BASINS_GDF.columns:
                    basin_col = col
                    break
            
            print(f"Using basin column: {basin_col}")
            
            if basin_col:
                # Get the selected basin geometry
                basin_geom_gdf = BASINS_GDF[BASINS_GDF[basin_col] == basin]
                print(f"Basin geometry found: {not basin_geom_gdf.empty}")
                
                if not basin_geom_gdf.empty:
                    print(f"Original canals_gdf CRS: {canals_gdf.crs}")
                    print(f"Original BASINS_GDF CRS: {BASINS_GDF.crs}")
                    print(f"Total canals before filtering: {len(canals_gdf)}")
                    
                    # Reproject both to UTM Zone 13N for proper distance operations
                    basin_projected = basin_geom_gdf.to_crs('EPSG:26913')
                    canals_projected = canals_gdf.to_crs('EPSG:26913')
                    
                    basin_union = basin_projected.geometry.iloc[0]
                    print(f"Basin bounds (projected): {basin_union.bounds}")
                    
                    # Buffer by 100 meters to catch canals near boundaries
                    basin_buffered = basin_union.buffer(100)
                    print(f"Buffered basin area: {basin_buffered.area}")
                    
                    canals_filtered = canals_projected[canals_projected.geometry.intersects(basin_buffered)]
                    print(f"✓ Found {len(canals_filtered)} canals in basin '{basin}'")
                else:
                    canals_filtered = canals_gdf
                    print(f"Basin geometry empty, showing all {len(canals_filtered)} canals")
            else:
                canals_filtered = canals_gdf
                print(f"No basin column found, showing all {len(canals_filtered)} canals")
        else:
            # No basin selected or "All" selected - show all canals within HUC8 boundaries
            print(f">>> BRANCH: Showing all canals in HUC8 boundaries (basin was '{basin}')")
            print(f"Original canals_gdf CRS: {canals_gdf.crs}")
            print(f"Original BASINS_GDF CRS: {BASINS_GDF.crs}")
            print(f"Total canals before filtering: {len(canals_gdf)}")
            
            basins_projected = BASINS_GDF.to_crs('EPSG:26913')
            canals_projected = canals_gdf.to_crs('EPSG:26913')
            
            huc8_union = basins_projected.geometry.union_all()
            print(f"HUC8 union bounds: {huc8_union.bounds}")
            huc8_buffered = huc8_union.buffer(100)
            print(f"Buffered HUC8 area: {huc8_buffered.area}")
            
            canals_filtered = canals_projected[canals_projected.geometry.intersects(huc8_buffered)]
            print(f"✓ Found {len(canals_filtered)} canals in all HUC8 basins")
        
        # Check if any canals were found
        if len(canals_filtered) == 0:
            print("❌ No canals found - returning 'No canals' message")
            return [{'label': 'No canals in selected basin', 'value': 'none', 'disabled': True}]
        
        # Get canal names
        name_col = None
        for col in canals_filtered.columns:
            if col.lower() in ['poss_name', 'name', 'canal_name', 'canalname']:
                name_col = col
                break
        
        print(f"Using name column: {name_col}")
        
        if name_col:
            canal_names = sorted(canals_filtered[name_col].dropna().unique())
            print(f"Unique canal names: {len(canal_names)}")
            
            if len(canal_names) == 0:
                print("❌ No named canals found")
                return [{'label': 'No canals in selected basin', 'value': 'none', 'disabled': True}]
            
            # Add "All" option at the beginning
            options = [{'label': 'All Canals', 'value': 'All'}] + [{'label': name, 'value': name} for name in canal_names]
            print(f"✓ Returning {len(options)-1} canal options for dropdown")
            print("=== CANAL DROPDOWN UPDATE COMPLETE ===\n")
            return options
        else:
            print("⚠ No name column found for canals")
            return [{'label': 'No canals available', 'value': 'none', 'disabled': True}]
        
    except Exception as e:
        print(f"❌ ERROR populating canal dropdown: {e}")
        import traceback
        traceback.print_exc()
        print("=== CANAL DROPDOWN UPDATE FAILED ===\n")
        return [{'label': 'Error loading canals', 'value': 'error', 'disabled': True}]

# Callback to populate exchange points dropdown based on selected basin
@app.callback(
    Output('exchange-select', 'options'),
    [Input('basin-select', 'value')]
)
def update_exchange_dropdown(basin):
    print(f"\n=== UPDATE EXCHANGE DROPDOWN CALLED ===")
    print(f"Basin selected: {basin}")
    
    try:
        # If a specific basin is selected, filter exchange points to that basin
        if basin and basin != 'All':
            print(f"Filtering exchange points for basin: {basin}")

            # Find the basin column
            basin_col = None
            for col in ['name', 'NAME', 'BASINS', 'BASIN_NAM', 'NAMELSAD']:
                if col in BASINS_GDF.columns:
                    basin_col = col
                    break
            
            if basin_col:
                basin_geom_gdf = BASINS_GDF[BASINS_GDF[basin_col] == basin]
                
                if not basin_geom_gdf.empty:
                    # Reproject to UTM for proper distance operations
                    basin_projected = basin_geom_gdf.to_crs('EPSG:26913')
                    exchange_projected = exchange_gdf.to_crs('EPSG:26913')  
                    
                    basin_union = basin_projected.geometry.iloc[0]
                    basin_buffered = basin_union.buffer(100)

                    exchange_filtered = exchange_projected[exchange_projected.geometry.intersects(basin_buffered)]  
                    print(f"✓ Found {len(exchange_filtered)} exchange points in basin '{basin}'")
                else:
                    exchange_filtered = exchange_gdf
                    print(f"Basin geometry empty, using all exchange points")
            else:
                exchange_filtered = exchange_gdf
                print(f"No basin column found, using all exchange points")
        else:
            # No basin selected - show all structures within HUC8 boundaries
            print("No specific basin selected, showing all exchange points in HUC8 boundaries")
            basins_projected = BASINS_GDF.to_crs('EPSG:26913')
            exchange_projected = exchange_gdf.to_crs('EPSG:26913')
            
            huc8_union = basins_projected.geometry.union_all()
            huc8_buffered = huc8_union.buffer(500)
            exchange_filtered = exchange_projected[exchange_projected.geometry.intersects(huc8_buffered)]
            print(f"✓ Found {len(exchange_filtered)} exchange points in all basins")
        
        # Check if any exchange points were found
        if len(exchange_filtered) == 0:
            print("❌ No exchange points found in selected basin")
            return [{'label': 'No exchange points in selected basin', 'value': 'none', 'disabled': True}]
        
        # Create options grouped by Color (type)
        options = [{'label': 'All Exchange Points', 'value': 'All'}]

        # Add Color 2 
        color2 = exchange_filtered[exchange_filtered['Color'] == 2]
        print(f"Color 2 count: {len(color2)}")
        if len(color2) > 0:
            options.append({'label': '--- Substitute Supply Release ---', 'value': 'header_color2', 'disabled': True})
            for _, row in color2.iterrows():
                label = row['Label'] if 'Label' in row and pd.notna(row['Label']) else f"Exchange Point {row.name}"
                options.append({'label': f"  {label}", 'value': f"color2_{row.name}"})
        
        # Add Color 3 
        color3 = exchange_filtered[exchange_filtered['Color'] == 3]
        print(f"Color 3 count: {len(color3)}")
        if len(color3) > 0:
            options.append({'label': '--- Exchange-from-Location ---', 'value': 'header_color3', 'disabled': True})
            for _, row in color3.iterrows():
                label = row['Label'] if 'Label' in row and pd.notna(row['Label']) else f"Exchange Point {row.name}"
                options.append({'label': f"  {label}", 'value': f"color3_{row.name}"})

        print(f"✓ Returning {len(options)-1} exchange point options")
        print("=== EXCHANGE POINT DROPDOWN UPDATE COMPLETE ===\n")

        return options
        
    except Exception as e:
        print(f"❌ ERROR populating exchange point dropdown: {e}")
        import traceback
        traceback.print_exc()
        return [{'label': 'All Exchange Points', 'value': 'All'}]

# BASIN DROPDOWN AND MAP HIGHLIGHTING
@app.callback(
    Output('basin-map', 'figure'),
    [Input('characteristic-select', 'value'),
     Input('fraction-select', 'value'),
     Input('basin-select', 'value'),
     Input('site-select', 'value'),
     Input('canal-select', 'value'),
     Input('exchange-select', 'value'),
     Input('rivers-toggle', 'value'),
     Input('additional-layers-toggle', 'value'),
     Input('sample-type-select', 'value'),
     Input('date-slider', 'value')
    ]
)

def highlight_basin(characteristic, fraction, basin, site, selected_canals, selected_exchange, rivers_toggle, additional_layers, sample_type, date_range):
    print(f"Debug: Selected basin = {basin}")
    print(f"Debug: Selected canals = {selected_canals}")
    print(f"Debug: Selected characteristic = {characteristic}")

    # Load basin data
    basin_df = gpd.read_file('huc8_boundaries.geojson')
    
    # Find the correct basin column name in the GeoJSON
    basin_col = None
    for col in ['name', 'NAME', 'BASINS', 'BASIN_NAM', 'NAMELSAD']:
        if col in basin_df.columns:
            basin_col = col
            break
    
    if basin_col is None:
        print("Error: No basin name column found in GeoJSON")
        basin_col = 'ID'
    
    print(f"Debug: Using basin column = {basin_col}")
    print(f"Debug: Available basins = {basin_df[basin_col].unique()}")
    
    # Get the specific basin geometry
    selected_basin_row = basin_df[basin_df[basin_col] == basin]
    
    if selected_basin_row.empty:
        print(f"Debug: Basin '{basin}' not found!")
        layers_to_use = [layer]
        basin_geom = None
    else:
        # Get the geometry
        basin_geometry = selected_basin_row.geometry.iloc[0]
        print(f"Debug: Geometry type = {basin_geometry.geom_type}")
        
        # Create proper GeoJSON structure for highlighting
        try:
            from shapely.geometry import mapping
            geom_dict = mapping(basin_geometry)
            
            basin_geojson = {
                "type": "FeatureCollection",
                "features": [
                    {
                        "type": "Feature",
                        "properties": {basin_col: basin},
                        "geometry": geom_dict
                    }
                ]
            }
            print("Debug: Using shapely mapping method")
            
        except Exception as e:
            print(f"Debug: Shapely method failed: {e}")
            
            # Fallback method
            try:
                coords_array = list(basin_geometry.get_coordinates())
                coords_list = [[float(coord[0]), float(coord[1])] for coord in coords_array]
                
                basin_geojson = {
                    "type": "FeatureCollection",
                    "features": [
                        {
                            "type": "Feature",
                            "geometry": {
                                "type": "Polygon",
                                "coordinates": [coords_list]
                            }
                        }
                    ]
                }
                print("Debug: Using fallback coordinate method")
                    
            except Exception as e2:
                print(f"Debug: Fallback method also failed: {e2}")
                basin_geojson = None
        
        # Create the highlighted basin layer
        if basin_geojson:
            basin_layer = dict(
                sourcetype='geojson',
                source=basin_geojson,
                type='fill',
                fill='rgb(0, 191, 255)',
                color='rgb(0, 191, 255)',
                opacity=0.3,
                line=dict(width=8),
                name='Selected Basin'
            )
            layers_to_use = [layer, basin_layer]
            basin_geom = basin_geometry
            print("Debug: Basin layer created successfully")
        else:
            layers_to_use = [layer]
            basin_geom = None
            print("Debug: Using original layers (no highlight)")

    # ===================================================================
    # VARIABLE DEFINITIONS - AVAILABLE EVERYWHERE
    # ===================================================================
    is_usgs_spc = (characteristic == 'Specific conductance (USGS-daily)')
    
    selected_sites = []
    if site and site != 'All':
        if isinstance(site, str):
            selected_sites = [site]
        elif isinstance(site, list):
            selected_sites = [s for s in site if s != 'All']
    
    has_usgs_sites = False
    usgs_site_names = set()
    if HAS_USGS_DATA and USGS_MAPPING is not None:
        usgs_site_names = set(USGS_MAPPING['WQX_Site_Name'].tolist())
        if selected_sites:
            has_usgs_sites = any(s in usgs_site_names for s in selected_sites)

    # ===================================================================
    # MAIN MAP DATA LOGIC
    # ===================================================================
    data = []
    
    if characteristic and basin:
        # BRANCH 1: USGS SpC characteristic selected
        if is_usgs_spc and HAS_USGS_DATA:
            print("Debug: USGS SpC selected - showing USGS sites on map")
            
            usgs_sc_data = get_usgs_data_for_sites(
                USGS_df,
                selected_sites if selected_sites else [],
                USGS_MAPPING,
                date_range,
                parameter='SpCond_uScm'
            )
            
            if not usgs_sc_data.empty:
                print(f"Debug: Found {len(usgs_sc_data)} USGS SpC records")
                
                # Get coordinates
                if 'Latitude' in usgs_sc_data.columns and 'Longitude' in usgs_sc_data.columns:
                    usgs_with_coords = usgs_sc_data.copy()
                    usgs_with_coords = usgs_with_coords.rename(columns={
                        'Latitude': 'Location_LatitudeStandardized',
                        'Longitude': 'Location_LongitudeStandardized'
                    })
                else:
                    if USGS_MAPPING is not None and 'Latitude' in USGS_MAPPING.columns:
                        usgs_with_coords = usgs_sc_data.merge(
                            USGS_MAPPING[['Site_Number', 'Latitude', 'Longitude']],
                            on='Site_Number',
                            how='left'
                        )
                        usgs_with_coords = usgs_with_coords.rename(columns={
                            'Latitude': 'Location_LatitudeStandardized',
                            'Longitude': 'Location_LongitudeStandardized'
                        })
                    else:
                        usgs_with_coords = usgs_sc_data.merge(
                            CSU_df[['Location_Name', 'Location_LatitudeStandardized', 'Location_LongitudeStandardized']].drop_duplicates(),
                            left_on='Site_Name',
                            right_on='Location_Name',
                            how='left'
                        )
                
                # Convert to numeric and remove invalid
                usgs_with_coords['Location_LatitudeStandardized'] = pd.to_numeric(
                    usgs_with_coords['Location_LatitudeStandardized'], errors='coerce'
                )
                usgs_with_coords['Location_LongitudeStandardized'] = pd.to_numeric(
                    usgs_with_coords['Location_LongitudeStandardized'], errors='coerce'
                )
                usgs_with_coords = usgs_with_coords.dropna(
                    subset=['Location_LatitudeStandardized', 'Location_LongitudeStandardized']
                )
                
                # Aggregate by site
                usgs_agg = usgs_with_coords.groupby('Site_Name', as_index=False).agg({
                    'Location_LatitudeStandardized': 'mean',
                    'Location_LongitudeStandardized': 'mean',
                    'SpCond_uScm': 'mean'
                })
                
                # Get all WQX sites for grey background
                all_wqx_sites = CSU_df[['Location_Name', 'Location_LatitudeStandardized', 'Location_LongitudeStandardized']].drop_duplicates()
                all_wqx_sites['Location_LatitudeStandardized'] = pd.to_numeric(all_wqx_sites['Location_LatitudeStandardized'], errors='coerce')
                all_wqx_sites['Location_LongitudeStandardized'] = pd.to_numeric(all_wqx_sites['Location_LongitudeStandardized'], errors='coerce')
                all_wqx_sites = all_wqx_sites.dropna(subset=['Location_LatitudeStandardized', 'Location_LongitudeStandardized'])
                
                non_selected = all_wqx_sites[~all_wqx_sites['Location_Name'].isin(usgs_agg['Site_Name'].unique())]
                
                # Create map data
                data = [
                    dict(
                        lat=non_selected['Location_LatitudeStandardized'].tolist(),
                        lon=non_selected['Location_LongitudeStandardized'].tolist(),
                        type='scattermapbox',
                        hovertext=non_selected['Location_Name'].tolist(),
                        marker=dict(size=5, color='grey', opacity=0.5),
                        name='Other Stations',
                        showlegend=False
                    ),
                    dict(
                        lat=usgs_agg['Location_LatitudeStandardized'].tolist(),
                        lon=usgs_agg['Location_LongitudeStandardized'].tolist(),
                        type='scattermapbox',
                        hovertext=[f"{name}<br>USGS SpC: {val:.0f} µS/cm" for name, val in
                                zip(usgs_agg['Site_Name'], usgs_agg['SpCond_uScm'])],
                        marker=dict(size=15, color='#00CED1', opacity=1),
                        name='USGS Specific Conductance',
                        showlegend=True
                    ),
                    dict(
                        lat=huc_centroids['lat'].tolist(),
                        lon=huc_centroids['lon'].tolist(),
                        type='scattermapbox',
                        hovertext=huc_centroids['name'].tolist(),
                        hovermode='closest',
                        marker=dict(size=100, color='white', opacity=0),
                        showlegend=False
                    )
                ]
            else:
                print("Debug: No USGS SpC data found")
                data = [
                    dict(
                        lat=CSU_df['Location_LatitudeStandardized'],
                        lon=CSU_df['Location_LongitudeStandardized'],
                        type='scattermapbox',
                        hovertext=CSU_df['Location_Name'],
                        marker=dict(size=5, color='grey', opacity=0.5),
                        name='No Data Available',
                        showlegend=False
                    ),
                    dict(
                        lat=huc_centroids['lat'],
                        lon=huc_centroids['lon'],
                        type='scattermapbox',
                        hovertext=huc_centroids['name'],
                        hovermode='closest',
                        marker=dict(size=100, color='white', opacity=0),
                        showlegend=False
                    )
                ]
        
        # BRANCH 2: WQX characteristic selected
        else:
            df = filter_data(CSU_df, characteristic, fraction, basin, site, sample_type, date_range[0], date_range[1])
            
            if not df.empty:
                print(f"Debug: Found {len(df)} filtered records")
                
                df['Result_Measure'] = pd.to_numeric(df['Result_Measure'], errors='coerce')
                df['Location_LatitudeStandardized'] = pd.to_numeric(df['Location_LatitudeStandardized'], errors='coerce')
                df['Location_LongitudeStandardized'] = pd.to_numeric(df['Location_LongitudeStandardized'], errors='coerce')
                df = df.dropna(subset=['Location_LatitudeStandardized', 'Location_LongitudeStandardized', 'Result_Measure'])

                agg_dict = {
                    'Location_LatitudeStandardized': 'mean',
                    'Location_LongitudeStandardized': 'mean',
                    'Result_Measure': 'mean'
                }
                df_mean = df.groupby('Location_Name', as_index=False).agg(agg_dict)
                df_mean['Result_Characteristic'] = characteristic
                
                non_selected = CSU_df[~CSU_df['Location_Name'].isin(df_mean['Location_Name'].unique())]

                data = [
                    dict(
                        lat=non_selected['Location_LatitudeStandardized'],
                        lon=non_selected['Location_LongitudeStandardized'],
                        type='scattermapbox',
                        hovertext=non_selected['Location_Name'],
                        marker=dict(size=5, color='grey', opacity=0.5),
                        name='Other Stations',
                        showlegend=False
                    ),
                    dict(
                        lat=df_mean['Location_LatitudeStandardized'],
                        lon=df_mean['Location_LongitudeStandardized'],
                        type='scattermapbox',
                        hovertext=[f"{name}<br>{char}: {val:.2f}" for name, char, val in
                                zip(df_mean['Location_Name'],
                                    df_mean['Result_Characteristic'],
                                    df_mean['Result_Measure'])],
                        marker=dict(size=10, color='blue', opacity=1),
                        name='Selected Data',
                        showlegend=False
                    ),
                    dict(
                        lat=huc_centroids['lat'],
                        lon=huc_centroids['lon'],
                        type='scattermapbox',
                        hovertext=huc_centroids['name'],
                        hovermode='closest',
                        marker=dict(size=100, color='white', opacity=0),
                        showlegend=False
                    )
                ]

                # Add USGS sites if selected
                if has_usgs_sites and HAS_USGS_DATA:
                    usgs_selected = [s for s in selected_sites if s in usgs_site_names]
                    usgs_display = USGS_MAPPING[USGS_MAPPING['WQX_Site_Name'].isin(usgs_selected)].copy()
                    
                    if not usgs_display.empty and 'Latitude' in usgs_display.columns:
                        usgs_display['Latitude'] = pd.to_numeric(usgs_display['Latitude'], errors='coerce')
                        usgs_display['Longitude'] = pd.to_numeric(usgs_display['Longitude'], errors='coerce')
                        usgs_display = usgs_display.dropna(subset=['Latitude', 'Longitude'])
                        
                        if not usgs_display.empty:
                            data.append(dict(
                                lat=usgs_display['Latitude'].tolist(),
                                lon=usgs_display['Longitude'].tolist(),
                                type='scattermapbox',
                                hovertext=[f"{name}<br>(USGS Site)" for name in usgs_display['WQX_Site_Name']],
                                marker=dict(size=15, color='#00CED1', opacity=1),
                                name='USGS Sites',
                                showlegend=True
                            ))
                            print(f"Debug: Added {len(usgs_display)} USGS sites to WQX map")
                            
                # If NO sites selected, also show all USGS sites by default
                elif not selected_sites and HAS_USGS_DATA and USGS_MAPPING is not None:
                    if 'Latitude' in USGS_MAPPING.columns and 'Longitude' in USGS_MAPPING.columns:
                        all_usgs = USGS_MAPPING[['WQX_Site_Name', 'Latitude', 'Longitude']].copy()
                        all_usgs['Latitude'] = pd.to_numeric(all_usgs['Latitude'], errors='coerce')
                        all_usgs['Longitude'] = pd.to_numeric(all_usgs['Longitude'], errors='coerce')
                        all_usgs = all_usgs.dropna(subset=['Latitude', 'Longitude'])
                        
                        if not all_usgs.empty:
                            data.append(dict(
                                lat=all_usgs['Latitude'].tolist(),
                                lon=all_usgs['Longitude'].tolist(),
                                type='scattermapbox',
                                hovertext=[f"{name}<br>(USGS Site)" for name in all_usgs['WQX_Site_Name']],
                                marker=dict(size=7, color='#00CED1', opacity=0.8),
                                name='USGS Sites',
                                showlegend=True
                            ))
                            print(f"Debug: Added {len(all_usgs)} USGS sites to default WQX view")
            else:
                data = [
                    dict(
                        lat=CSU_df['Location_LatitudeStandardized'],
                        lon=CSU_df['Location_LongitudeStandardized'],
                        type='scattermapbox',
                        hovertext=CSU_df['Location_Name'],
                        marker=dict(size=5, color='grey', opacity=0.5),
                        name='No Data Available',
                        showlegend=False
                    ),
                    dict(
                        lat=huc_centroids['lat'],
                        lon=huc_centroids['lon'],
                        type='scattermapbox',
                        hovertext=huc_centroids['name'],
                        hovermode='closest',
                        marker=dict(size=100, color='white', opacity=0),
                        showlegend=False
                    )
                ]

                # Add USGS sites if selected
                if has_usgs_sites and HAS_USGS_DATA:
                    usgs_selected = [s for s in selected_sites if s in usgs_site_names]
                    usgs_display = USGS_MAPPING[USGS_MAPPING['WQX_Site_Name'].isin(usgs_selected)].copy()
                    
                    if not usgs_display.empty and 'Latitude' in usgs_display.columns:
                        usgs_display['Latitude'] = pd.to_numeric(usgs_display['Latitude'], errors='coerce')
                        usgs_display['Longitude'] = pd.to_numeric(usgs_display['Longitude'], errors='coerce')
                        usgs_display = usgs_display.dropna(subset=['Latitude', 'Longitude'])
                        
                        if not usgs_display.empty:
                            data.append(dict(
                                lat=usgs_display['Latitude'].tolist(),
                                lon=usgs_display['Longitude'].tolist(),
                                type='scattermapbox',
                                hovertext=[f"{name}<br>(USGS Site)" for name in usgs_display['WQX_Site_Name']],
                                marker=dict(size=15, color='#00CED1', opacity=1),
                                name='USGS Sites',
                                showlegend=True
                            ))
                            print(f"Debug: Added {len(usgs_display)} USGS sites to map")
    
    # BRANCH 3: No characteristic/basin selected - show all sites
    else:
        print("Debug: No characteristic or basin selected")
        
        # Get all WQX sites
        all_wqx_sites = CSU_df[['Location_Name', 'Location_LatitudeStandardized', 'Location_LongitudeStandardized']].drop_duplicates()
        all_wqx_sites['Location_LatitudeStandardized'] = pd.to_numeric(all_wqx_sites['Location_LatitudeStandardized'], errors='coerce')
        all_wqx_sites['Location_LongitudeStandardized'] = pd.to_numeric(all_wqx_sites['Location_LongitudeStandardized'], errors='coerce')
        all_wqx_sites = all_wqx_sites.dropna(subset=['Location_LatitudeStandardized', 'Location_LongitudeStandardized'])
        
        # Get all USGS sites
        all_usgs_sites = pd.DataFrame()
        if HAS_USGS_DATA and USGS_MAPPING is not None and 'Latitude' in USGS_MAPPING.columns:
            all_usgs_sites = USGS_MAPPING[['WQX_Site_Name', 'Latitude', 'Longitude']].copy()
            all_usgs_sites = all_usgs_sites.rename(columns={
                'WQX_Site_Name': 'Location_Name',
                'Latitude': 'Location_LatitudeStandardized',
                'Longitude': 'Location_LongitudeStandardized'
            })
            all_usgs_sites['Location_LatitudeStandardized'] = pd.to_numeric(all_usgs_sites['Location_LatitudeStandardized'], errors='coerce')
            all_usgs_sites['Location_LongitudeStandardized'] = pd.to_numeric(all_usgs_sites['Location_LongitudeStandardized'], errors='coerce')
            all_usgs_sites = all_usgs_sites.dropna(subset=['Location_LatitudeStandardized', 'Location_LongitudeStandardized'])
            all_usgs_sites['is_usgs'] = True
        
        all_wqx_sites['is_usgs'] = False
        all_sites = pd.concat([all_wqx_sites, all_usgs_sites], ignore_index=True)
        
        # If sites are selected, highlight them
        if selected_sites:
            print(f"Debug: Highlighting {len(selected_sites)} selected site(s)")
            selected_df = all_sites[all_sites['Location_Name'].isin(selected_sites)]
            non_selected_df = all_sites[~all_sites['Location_Name'].isin(selected_sites)]
            
            data = [
                dict(
                    lat=non_selected_df['Location_LatitudeStandardized'].tolist(),
                    lon=non_selected_df['Location_LongitudeStandardized'].tolist(),
                    type='scattermapbox',
                    hovertext=non_selected_df['Location_Name'].tolist(),
                    marker=dict(size=5, color='grey', opacity=0.5),
                    name='Other Stations',
                    showlegend=False
                ),
                dict(
                    lat=selected_df['Location_LatitudeStandardized'].tolist(),
                    lon=selected_df['Location_LongitudeStandardized'].tolist(),
                    type='scattermapbox',
                    hovertext=[f"{name}<br>{'(USGS Site)' if is_usgs else '(WQX Site)'}" 
                              for name, is_usgs in zip(selected_df['Location_Name'], selected_df['is_usgs'])],
                    marker=dict(size=15, color='#00CED1', opacity=1),
                    name='Selected Sites',
                    showlegend=True
                ),
                dict(
                    lat=huc_centroids['lat'].tolist(),
                    lon=huc_centroids['lon'].tolist(),
                    type='scattermapbox',
                    hovertext=huc_centroids['name'].tolist(),
                    hovermode='closest',
                    marker=dict(size=100, color='white', opacity=0),
                    showlegend=False
                )
            ]
        else:
            # No sites selected - show all
            print(f"Debug: Showing all sites (WQX: {len(all_wqx_sites)}, USGS: {len(all_usgs_sites)})")
            
            data = [
                dict(
                    lat=all_wqx_sites['Location_LatitudeStandardized'].tolist(),
                    lon=all_wqx_sites['Location_LongitudeStandardized'].tolist(),
                    type='scattermapbox',
                    hovertext=all_wqx_sites['Location_Name'].tolist(),
                    marker=dict(size=5, color='blue', opacity=0.7),
                    name='WQX Sites',
                    showlegend=True
                ),
                dict(
                    lat=huc_centroids['lat'].tolist(),
                    lon=huc_centroids['lon'].tolist(),
                    type='scattermapbox',
                    hovertext=huc_centroids['name'].tolist(),
                    hovermode='closest',
                    marker=dict(size=100, color='white', opacity=0),
                    showlegend=False
                )
            ]
            
            if not all_usgs_sites.empty:
                data.append(dict(
                    lat=all_usgs_sites['Location_LatitudeStandardized'].tolist(),
                    lon=all_usgs_sites['Location_LongitudeStandardized'].tolist(),
                    type='scattermapbox',
                    hovertext=[f"{name}<br>(USGS Site)" for name in all_usgs_sites['Location_Name']],
                    marker=dict(size=7, color='#00CED1', opacity=0.8),
                    name='USGS Sites',
                    showlegend=True
                ))
                print(f"Debug: Added {len(all_usgs_sites)} USGS sites to default map")

    # Add canals/ditches if any are selected
    if selected_canals:
        try:
            # Check if "All" is selected
            show_all_canals = 'All' in selected_canals
            
            if show_all_canals:
                print(f"Debug: ADDING ALL CANALS")
            else:
                print(f"Debug: ADDING SELECTED CANALS - {len(selected_canals)} selected")
                print(f"Debug: Selected canal names: {selected_canals}")
            
            # Make sure both are in the same CRS
            if canals_gdf.crs != BASINS_GDF.crs:
                canals_temp = canals_gdf.to_crs(BASINS_GDF.crs)
            else:
                canals_temp = canals_gdf
            
            # Filter by basin if one is selected
            if basin and basin != 'All':
                basin_col = None
                for col in ['name', 'NAME', 'BASINS', 'BASIN_NAM', 'NAMELSAD']:
                    if col in BASINS_GDF.columns:
                        basin_col = col
                        break
                
                if basin_col:
                    basin_geom = BASINS_GDF[BASINS_GDF[basin_col] == basin].geometry
                    if not basin_geom.empty:
                        # Reproject to UTM before buffering
                        basin_projected = BASINS_GDF[BASINS_GDF[basin_col] == basin].to_crs('EPSG:26913')
                        canals_projected = canals_temp.to_crs('EPSG:26913')
                        
                        basin_union = basin_projected.geometry.iloc[0]
                        basin_buffered = basin_union.buffer(100)
                        canals_in_basin = canals_projected[canals_projected.geometry.intersects(basin_buffered)]
                        
                        # Convert back to original CRS
                        canals_in_basin = canals_in_basin.to_crs(canals_temp.crs)
                        print(f"Debug: Found {len(canals_in_basin)} canals in basin '{basin}'")
                    else:
                        canals_in_basin = canals_temp
                else:
                    canals_in_basin = canals_temp
            else:
                # Show canals in all HUC8 boundaries
                basins_projected = BASINS_GDF.to_crs('EPSG:26913')
                canals_projected = canals_temp.to_crs('EPSG:26913')
                
                huc8_union = basins_projected.geometry.union_all()
                huc8_buffered = huc8_union.buffer(100)
                canals_in_basin = canals_projected.clip(huc8_buffered)
                
                # Convert back
                canals_in_basin = canals_in_basin.to_crs(canals_temp.crs)
                print(f"Debug: Clipped to {len(canals_in_basin)} canal segments in all HUC8 basins")
            
            # Convert back to lat/lon for display
            canals_to_show = canals_in_basin.to_crs('EPSG:4326')
            
            # Find the correct name column
            name_col = None
            for col in canals_to_show.columns:
                if col.lower() in ['poss_name', 'name', 'canal_name', 'canalname']:
                    name_col = col
                    break
            
            # Filter to selected canals if not "All"
            if name_col and not show_all_canals:
                selected_canal_names = [c for c in selected_canals if c != 'All']
                print(f"Debug: Filtering to these specific canals: {selected_canal_names}")
                canals_to_show = canals_to_show[canals_to_show[name_col].isin(selected_canal_names)]
                print(f"Debug: After name filtering: {len(canals_to_show)} canals")
            
            print(f"Debug: Displaying {len(canals_to_show)} canals")
            
            # Add each canal as a line trace
            canal_count = 0
            for idx, row in canals_to_show.iterrows():
                geom = row.geometry
                canal_name = row[name_col] if name_col else f"Canal {idx}"
                
                # Extract coordinates from the line geometry
                if geom.geom_type == 'LineString':
                    lons, lats = geom.xy
                    lons = list(lons)
                    lats = list(lats)
                elif geom.geom_type == 'MultiLineString':
                    lons = []
                    lats = []
                    for line in geom.geoms:
                        line_lons, line_lats = line.xy
                        lons.extend(list(line_lons))
                        lats.extend(list(line_lats))
                        lons.append(None)
                        lats.append(None)
                else:
                    continue
                
                canal_trace = dict(
                    lat=lats,
                    lon=lons,
                    type='scattermapbox',
                    mode='lines',
                    line=dict(width=4, color='#FF6B00'),
                    hovertemplate=f'<b>🌊 {canal_name}</b><extra></extra>',
                    name=canal_name,
                    showlegend=(not show_all_canals),
                    legendgroup='canals'
                )
                data.append(canal_trace)
                canal_count += 1
            
            # If showing all canals, add a single legend entry
            if show_all_canals:
                data.append(dict(
                    lat=[None],
                    lon=[None],
                    type='scattermapbox',
                    mode='lines',
                    line=dict(width=4, color='#FF6B00'),
                    name='All Canals/Ditches',
                    showlegend=True,
                    legendgroup='canals'
                ))
            
            print(f"Debug: Added {canal_count} canal line traces to map")
            
        except Exception as e:
            print(f"ERROR adding canals: {e}")
            import traceback
            traceback.print_exc()
    else:
        print("Debug: No canals selected")

    # Add exchange points if any are selected
    if selected_exchange:
        try:
            print(f"\n=== EXCHANGE POINTS DISPLAY DEBUG ===")
            print(f"selected_exchange value: {selected_exchange}")
            
            show_all_exchange = 'All' in selected_exchange
            print(f"show_all_exchange: {show_all_exchange}")

            if show_all_exchange:
                print(f"Debug: ADDING ALL EXCHANGE POINTS")
            else:
                print(f"Debug: ADDING SELECTED EXCHANGE POINTS - {len(selected_exchange)} selected")

            # Filter by basin if one is selected
            if basin and basin != 'All':
                print(f"Debug: Filtering exchange points for basin: {basin}")
                basin_col = None
                for col in ['name', 'NAME', 'BASINS', 'BASIN_NAM', 'NAMELSAD']:
                    if col in BASINS_GDF.columns:
                        basin_col = col
                        break
                
                if basin_col:
                    basin_geom = BASINS_GDF[BASINS_GDF[basin_col] == basin].geometry
                    if not basin_geom.empty:
                        # Reproject to UTM for proper buffering
                        exchange_projected = exchange_gdf.to_crs('EPSG:26913')
                        basin_projected = BASINS_GDF[BASINS_GDF[basin_col] == basin].to_crs('EPSG:26913')
                        basin_union = basin_projected.geometry.iloc[0]
                        basin_buffered = basin_union.buffer(500)
                        exchange_in_basin = exchange_projected[exchange_projected.geometry.intersects(basin_buffered)]
                        print(f"Debug: Found {len(exchange_in_basin)} exchange points in basin '{basin}'")
                    else:
                        exchange_in_basin = exchange_gdf
                        print(f"Debug: Basin geometry empty, showing all {len(exchange_in_basin)} points")
                else:
                    exchange_in_basin = exchange_gdf
                    print(f"Debug: No basin column, showing all {len(exchange_in_basin)} points")
            else:
                # Show structures in all HUC8 boundaries
                print(f"Debug: Filtering for all basins")
                exchange_projected = exchange_gdf.to_crs('EPSG:26913')
                basins_projected = BASINS_GDF.to_crs('EPSG:26913')
                huc8_union = basins_projected.geometry.union_all()
                huc8_buffered = huc8_union.buffer(500)
                exchange_in_basin = exchange_projected[exchange_projected.geometry.intersects(huc8_buffered)]
                print(f"Debug: Found {len(exchange_in_basin)} exchange points in all HUC8 basins")
            
            # Convert back to lat/lon for display
            exchange_to_show = exchange_in_basin.to_crs('EPSG:4326')
            print(f"Debug: exchange_to_show length after CRS conversion: {len(exchange_to_show)}")
            print(f"Debug: exchange_to_show Color values: {exchange_to_show['Color'].unique()}")

            # Filter to selected structures if not "All"
            if not show_all_exchange:
                # Extract row indices from selected values
                selected_indices = []
                for sel in selected_exchange:
                    if sel.startswith('color2_') or sel.startswith('color3_'):
                        idx = int(sel.split('_')[1])
                        selected_indices.append(idx)

                exchange_to_show = exchange_to_show.loc[exchange_to_show.index.isin(selected_indices)]
                print(f"Debug: Displaying {len(exchange_to_show)} selected exchange points")
            else:
                print(f"Debug: Displaying all {len(exchange_to_show)} exchange points")

            # Combine all exchange points into lists by color
            color2_structures = exchange_to_show[exchange_to_show['Color'] == 2]
            color3_structures = exchange_to_show[exchange_to_show['Color'] == 3]
            
            print(f"Debug: Color 2 count: {len(color2_structures)}, Color 3 count: {len(color3_structures)}")

            # Add Color 2 (Substitute Supply Release)
            if len(color2_structures) > 0:
                color2_trace = dict(
                    lat=[geom.y for geom in color2_structures.geometry],
                    lon=[geom.x for geom in color2_structures.geometry],
                    type='scattermapbox',
                    mode='markers',
                    marker=dict(
                        size=16,
                        color="#470953",
                        symbol='circle',
                    ),
                    text=color2_structures['Label'].tolist(),
                    hovertemplate='<b>▲ %{text}</b><br>Substitute Supply Release<extra></extra>',
                    name='▲ Substitute Supply Release',
                    showlegend=True
                )
                data.append(color2_trace)
                print(f"Debug: Added {len(color2_structures)} Color 2 (triangle) structures")

            # Add Color 3 (Exchange-from-Location) 
            if len(color3_structures) > 0:
                color3_trace = dict(
                    lat=[geom.y for geom in color3_structures.geometry],
                    lon=[geom.x for geom in color3_structures.geometry],
                    type='scattermapbox',
                    mode='markers',
                    marker=dict(
                        size=16,
                        color='#D946EF',  
                        symbol='circle'  
                    ),
                    text=color3_structures['Label'].tolist(),
                    hovertemplate='<b>● %{text}</b><br>Exchange-from-Location<extra></extra>',
                    name='● Exchange-from-Location',
                    showlegend=True
                )
                data.append(color3_trace)
                print(f"Debug: Added {len(color3_structures)} Color 3 (circle) structures")
            
            print("=== EXCHANGE POINTS DISPLAY COMPLETE ===\n")
            
        except Exception as e:
            print(f"ERROR adding structures: {e}")
            import traceback
            traceback.print_exc()
    else:
        print("Debug: No exchange points selected")

    # Add rivers/streams if toggle is checked
    if rivers_toggle and len(rivers_toggle) > 0 and streams_gdf is not None:
        try:
            print(f"\n=== ADDING RIVERS TO MAP ===")
            print(f"Rivers toggle value: {rivers_toggle}")
            print(f"Current data traces before adding rivers: {len(data)}")
            
            # Convert to WGS84 for display
            rivers_to_show = streams_gdf.to_crs('EPSG:4326')
            
            # Determine which rivers to show
            show_all = 'All' in rivers_toggle
            selected_rivers = [r for r in rivers_toggle if r != 'All']
            
            # Filter to selected rivers if not "All"
            if not show_all and len(selected_rivers) > 0:
                rivers_to_show = rivers_to_show[rivers_to_show['PNAME'].isin(selected_rivers)]
                print(f"Filtered to {len(selected_rivers)} selected rivers: {selected_rivers}")
                print(f"River segments after filter: {len(rivers_to_show)}")
            else:
                print(f"Showing all {len(rivers_to_show)} river segments")
            
            # Color scheme
            river_colors = {
                'arkansas': '#1E90FF',
                'fountain': '#4169E1',
                'st. charles': '#6495ED',
                'st charles': '#6495ED',     
                'huerfano': '#00CED1',
                'apishapa': '#20B2AA',
                'purgatoire': '#48D1CC',
                'horse': '#40E0D0',
                'timpas': '#5F9EA0',
                'crooked': '#87CEEB',
                'salt': '#87CEFA'
            }
            
            # Group by river name
            unique_rivers = rivers_to_show['PNAME'].dropna().unique()
            print(f"Processing {len(unique_rivers)} unique rivers")
            
            traces_added = 0
            for river_name in unique_rivers:
                river_segments = rivers_to_show[rivers_to_show['PNAME'] == river_name]
                print(f"\nProcessing river: {river_name}")
                print(f"  Number of segments: {len(river_segments)}")
                
                # Determine color and width
                color = '#4682B4'
                line_width = 2
                
                river_name_lower = str(river_name).lower()
                for keyword, keyword_color in river_colors.items():
                    if keyword in river_name_lower:
                        color = keyword_color
                        if keyword == 'arkansas':
                            line_width = 4
                        break
                
                # Extract coordinates
                lons = []
                lats = []
                segments_processed = 0
                for idx, row in river_segments.iterrows():
                    geom = row.geometry
                    if geom is None:
                        continue
                    
                    segments_processed += 1
                    
                    try:
                        if geom.geom_type == 'LineString':
                            line_lons, line_lats = geom.xy
                            lons.extend(list(line_lons))
                            lats.extend(list(line_lats))
                            lons.append(None)
                            lats.append(None)
                        elif geom.geom_type == 'MultiLineString':
                            for line in geom.geoms:
                                line_lons, line_lats = line.xy
                                lons.extend(list(line_lons))
                                lats.extend(list(line_lats))
                                lons.append(None)
                                lats.append(None)
                    except Exception as e:
                        print(f"  ⚠ Error processing geometry: {e}")
                        continue
                
                if lons and lats:
                        valid_lons = [x for x in lons if x is not None]
                        valid_lats = [y for y in lats if y is not None]
                    
                        if valid_lons and valid_lats:
                            river_name_display = river_name.title()
                            
                            river_trace = dict(
                                lat=lats,
                                lon=lons,
                                type='scattermapbox',
                                mode='lines',
                                line=dict(width=line_width, color=color),
                                hovertemplate=f'<b>🌊 {river_name_display}</b><extra></extra>',
                                name=river_name_display,
                                showlegend=True,
                                legendgroup='rivers'
                            )
                            data.append(river_trace)
                            traces_added += 1
            
        except Exception as e:
            print(f"❌ ERROR adding rivers: {e}")
            import traceback
            traceback.print_exc()
    else:
        if streams_gdf is None:
            print("Debug: streams_gdf is None - shapefile not loaded")
        elif not rivers_toggle or len(rivers_toggle) == 0:
            print(f"Debug: Rivers toggle is empty (value: {rivers_toggle})")

    # Add stream segments if selected
    if additional_layers and 'segments' in additional_layers and stream_segments_gdf is not None:
        try:
            print(f"\n=== ADDING STREAM SEGMENTS TO MAP ===")
            
            # Filter to HUC8 basins
            segments_projected = stream_segments_gdf.to_crs('EPSG:26913')
            basins_projected = BASINS_GDF.to_crs('EPSG:26913')
            
            huc8_union = basins_projected.geometry.union_all()
            huc8_buffered = huc8_union.buffer(1000)
            
            segments_in_huc8 = segments_projected[segments_projected.geometry.intersects(huc8_buffered)]
            print(f"Filtered to {len(segments_in_huc8)} segments in study area")
            
            # Convert back to WGS84
            segments_to_show = segments_in_huc8.to_crs('EPSG:4326')
            
            # Group by category
            segments_to_show['Cat'] = segments_to_show['Cat'].fillna('NA').astype(str)
            categories = sorted(segments_to_show['Cat'].unique())
            print(f"Found categories: {categories}")
            
            category_order = ['5', '5a', '4', '4a', '4b', '4c', '3', '3a', '3b', '2', '1', '1a', '1b', 'NA', 'Other']
            
            def get_priority(cat):
                try:
                    return category_order.index(str(cat))
                except ValueError:
                    return len(category_order)
            
            categories_sorted = sorted(categories, key=get_priority)
            
            for cat in categories_sorted:
                cat_segments = segments_to_show[segments_to_show['Cat'] == cat]
                
                if len(cat_segments) == 0:
                    continue
                
                cat_info = ASSESSMENT_CATEGORIES.get(cat, ASSESSMENT_CATEGORIES['Other'])
                color = cat_info['color']
                cat_name = cat_info['name']
                
                all_lons = []
                all_lats = []
                
                for idx, row in cat_segments.iterrows():
                    geom = row.geometry
                    
                    if geom is None:
                        continue
                    
                    try:
                        if geom.geom_type == 'LineString':
                            lons, lats = geom.xy
                            all_lons.extend(list(lons))
                            all_lats.extend(list(lats))
                            all_lons.append(None)
                            all_lats.append(None)
                        elif geom.geom_type == 'MultiLineString':
                            for line in geom.geoms:
                                lons, lats = line.xy
                                all_lons.extend(list(lons))
                                all_lats.extend(list(lats))
                                all_lons.append(None)
                                all_lats.append(None)
                    except Exception as e:
                        print(f"  Warning: Error processing segment geometry: {e}")
                        continue
                
                if not all_lons or not all_lats:
                    continue
                
                segment_trace = dict(
                    lat=all_lats,
                    lon=all_lons,
                    type='scattermapbox',
                    mode='lines',
                    line=dict(width=4, color=color),
                    opacity=0.85,
                    hovertemplate=f'<b>303(d) Category {cat}</b><br>{cat_name}<br>({len(cat_segments)} segments)<extra></extra>',
                    name=f'Cat {cat}: {cat_name}',
                    showlegend=True,
                    legendgroup='stream_segments',
                    legendgrouptitle=dict(text='303(d) Stream Assessments', font=dict(size=12, color='white', family='Arial'))
                )
                data.append(segment_trace)
            
        except Exception as e:
            import traceback
            traceback.print_exc()

    # Add lakes if selected
    if additional_layers and 'lakes' in additional_layers and lakes_gdf is not None:
        try:
            lakes_projected = lakes_gdf.to_crs('EPSG:26913')
            basins_projected = BASINS_GDF.to_crs('EPSG:26913')
            
            huc8_union = basins_projected.geometry.union_all()
            huc8_buffered = huc8_union.buffer(1000)
            
            lakes_in_huc8 = lakes_projected[lakes_projected.geometry.intersects(huc8_buffered)]            
            lakes_to_show = lakes_in_huc8.to_crs('EPSG:4326')
            
            lakes_to_show['Cat'] = lakes_to_show['Cat'].fillna('Other').astype(str)
            categories = sorted(lakes_to_show['Cat'].unique())
            category_order = ['5', '4a', '3b', '3a', '2', '1a', 'Other']
            
            def get_priority(cat):
                try:
                    return category_order.index(str(cat))
                except ValueError:
                    return len(category_order)
            
            categories_sorted = sorted(categories, key=get_priority)
            
            for cat in categories_sorted:
                cat_lakes = lakes_to_show[lakes_to_show['Cat'] == cat]
                
                if len(cat_lakes) == 0:
                    continue
                
                cat_info = ASSESSMENT_CATEGORIES.get(cat, ASSESSMENT_CATEGORIES['Other'])
                color = cat_info['color']
                cat_name = cat_info['name']
                
                all_lons = []
                all_lats = []
                
                for idx, row in cat_lakes.iterrows():
                    geom = row.geometry
                    
                    if geom is None:
                        continue
                    
                    try:
                        if geom.geom_type == 'Polygon':
                            lons, lats = geom.exterior.xy
                            all_lons.extend(list(lons))
                            all_lats.extend(list(lats))
                            all_lons.append(None)
                            all_lats.append(None)
                        elif geom.geom_type == 'MultiPolygon':
                            for poly in geom.geoms:
                                lons, lats = poly.exterior.xy
                                all_lons.extend(list(lons))
                                all_lats.extend(list(lats))
                                all_lons.append(None)
                                all_lats.append(None)
                    except Exception as e:
                        continue
                
                if not all_lons or not all_lats:
                    continue
                
                hex_color = color.lstrip('#')
                r, g, b = tuple(int(hex_color[i:i+2], 16) for i in (0, 2, 4))
                fill_color = f'rgba({r}, {g}, {b}, 0.4)'
                
                lake_trace = dict(
                    lat=all_lats,
                    lon=all_lons,
                    type='scattermapbox',
                    mode='lines',
                    fill='toself',
                    fillcolor=fill_color,
                    line=dict(width=2, color=color),
                    hovertemplate=f'<b>Lake/Reservoir - Cat {cat}</b><br>{cat_name}<br>({len(cat_lakes)} waterbodies)<extra></extra>',
                    name=f'Cat {cat}: {cat_name}',
                    showlegend=True,
                    legendgroup='lakes',
                    legendgrouptitle=dict(text='Lakes/Reservoirs [2026 Provisional]', font=dict(size=12, color='white', family='Arial'))
                )
                data.append(lake_trace)
            
        except Exception as e:
            print(f"❌ ERROR adding lakes: {e}")
            import traceback
            traceback.print_exc()

    # Update layout with the highlighted basin 
    layout = dict(
        mapbox=dict(
            layers=layers_to_use,
            accesstoken=mapbox_access_token,
            style=mapbox_style,
            center=dict(lat=38.019914, lon=-103.574052),
            pitch=0,
            zoom=7,
        ),
        margin=dict(t=25, l=25, r=25, b=25),
        paper_bgcolor='#1e1e1e',
        showlegend=True,
        legend=dict(
            bgcolor='rgba(45, 45, 45, 0.8)',
            bordercolor='white',
            font=dict(color='white')
        ),
        uirevision='constant'
    )

    fig = dict(data=data, layout=layout)
    return fig

# Add helper function for usgs data
def get_usgs_data_for_sites(usgs_df, wqx_sites, mapping_df, date_range, parameter='Flow_cfs'):
    """
    Helper function to get USGS data for selected WQX sites
    """
    if usgs_df.empty:
        return pd.DataFrame()
    
    # Filter by date range
    start_date = datetime(year=date_range[0], month=1, day=1)
    end_date = datetime(year=date_range[1], month=12, day=31)
    
    date_mask = (usgs_df['Date'] >= start_date) & (usgs_df['Date'] <= end_date)
    filtered_df = usgs_df[date_mask].copy()
    
    # If specific sites selected, filter to those
    if wqx_sites and wqx_sites != ['All'] and mapping_df is not None:
        usgs_site_numbers = []
        for wqx_site in wqx_sites:
            if wqx_site and wqx_site != 'All':
                matches = mapping_df[mapping_df['WQX_Site_Name'] == wqx_site]
                if not matches.empty:
                    usgs_site_numbers.append(matches.iloc[0]['Site_Number'])
        
        if usgs_site_numbers:
            filtered_df = filtered_df[filtered_df['Site_Number'].isin(usgs_site_numbers)]
    
    # Only return rows with valid data for the requested parameter
    if parameter in filtered_df.columns:
        filtered_df = filtered_df[filtered_df[parameter].notna()]
    
    return filtered_df

# TIME SERIES ANALYSIS
@app.callback(
    Output('analysis', 'figure'),
    [Input('characteristic-select', 'value'),
     Input('fraction-select', 'value'),
     Input('basin-select', 'value'),
     Input('site-select', 'value'),
     Input('sample-type-select', 'value'),
     Input('date-slider', 'value'),
     Input('additional-data-toggle', 'value'),
     Input('basin-map', 'clickData')
    ],
    prevent_initial_call=True
)

def plot_data(characteristic, fraction, basin, site, sample_type, date_range, additional_data, clickData):  
    
    # Handle click data
    clicked_site = None
    if clickData:
        try:
            clicked_text = clickData['points'][0].get('hovertext', '')
            if '<br>' in clicked_text:
                clicked_site = clicked_text.split('<br>')[0]
            else:
                clicked_site = clicked_text
            
            if clicked_site and clicked_site not in ['Other Stations', 'No Data Available', '']:
                site = clicked_site
                print(f"Debug: Map clicked - using site: {clicked_site}")
        except Exception as e:
            print(f"Debug: Error processing click data: {e}")
            pass
    
    # Check if USGS daily SpC was selected
    is_usgs_spc = (characteristic == 'Specific conductance (USGS-daily)')

    # Check if any USGS sites are selected
    selected_sites = []
    if site and site != 'All':
        if isinstance(site, str):
            selected_sites = [site]
        elif isinstance(site, list):
            selected_sites = [s for s in site if s != 'All']

    # Check if selected sites include USGS sites
    has_usgs_sites = False
    if HAS_USGS_DATA and USGS_MAPPING is not None and selected_sites:
        usgs_site_names = set(USGS_MAPPING['WQX_Site_Name'].tolist())
        has_usgs_sites = any(s in usgs_site_names for s in selected_sites)

    # ========================================
    # BRANCH 1: USGS Specific Conductance
    # ========================================
    if is_usgs_spc and HAS_USGS_DATA:
        usgs_sc_data = get_usgs_data_for_sites(
            USGS_df,
            selected_sites if selected_sites else [],
            USGS_MAPPING,
            date_range,
            parameter='SpCond_uScm'
        )

        if usgs_sc_data.empty:
            fig = go.Figure()
            fig.add_annotation(
                text="No USGS Specific Conductance data available for selected filters",
                xref="paper", yref="paper",
                x=0.5, y=0.5, xanchor='center', yanchor='middle',
                showarrow=False,
                font=dict(size=16, color="white")
            )
            fig.update_layout(
                plot_bgcolor='#2d2d2d',
                paper_bgcolor='#1e1e1e',
                font=dict(color='white'),
                xaxis=dict(visible=False),
                yaxis=dict(visible=False),
                title="Time Series Analysis - No USGS Data",
                title_font=dict(color='white')
            )
            return fig
        
        # Create figure with USGS SpC data
        fig = go.Figure()
        
        primary_colors = ['#1f77b4', '#ff7f0e', '#2ca02c', '#d62728', '#9467bd']
        
        for idx, usgs_site_name in enumerate(usgs_sc_data['Site_Name'].unique()):
            site_sc = usgs_sc_data[usgs_sc_data['Site_Name'] == usgs_site_name]
            
            fig.add_trace(go.Scatter(
                x=site_sc['Date'],
                y=site_sc['SpCond_uScm'],
                mode='lines',
                name=f'{usgs_site_name}',
                yaxis='y1',
                showlegend=True,
                line=dict(width=2, color=primary_colors[idx % len(primary_colors)]),
                opacity=0.8,
                hovertemplate='<b>%{fullData.name}</b><br>' +
                            'Date: %{x|%Y-%m-%d}<br>' +
                            'SpCond: %{y:.0f} µS/cm<br>' +
                            '<extra></extra>'
            ))
        
        # Check if additional flow data requested
        has_secondary_axis = False
        
        # Add WQX Flow if requested
        if additional_data and 'wqx_flow' in additional_data:
            try:
                flow_data = filter_data(CSU_df, 'Flow', None, basin, site, sample_type, date_range[0], date_range[1])
                
                if flow_data is not None and not flow_data.empty:
                    has_secondary_axis = True
                    
                    for idx, location in enumerate(flow_data['Location_Name'].unique()):
                        location_flow = flow_data[flow_data['Location_Name'] == location].copy()
                        
                        fig.add_trace(go.Scatter(
                            x=location_flow['Activity_StartDate'],
                            y=location_flow['Result_Measure'],
                            mode='markers',
                            name=f'{location} (WQX Flow)',
                            yaxis='y2',
                            showlegend=True,
                            marker=dict(size=10, symbol='diamond', opacity=0.8, 
                                        color=primary_colors[idx % len(primary_colors)]),
                            hovertemplate='<b>%{fullData.name}</b><br>' +
                                            'Date: %{x|%Y-%m-%d}<br>' +
                                            'Flow: %{y:.2f} cfs<br>' +
                                            '<extra></extra>'
                        ))
            except Exception as e:
                print(f"Error adding WQX flow data: {e}")
        
        # Add USGS Daily Flow if requested
        if additional_data and 'usgs_flow' in additional_data and HAS_USGS_DATA:
            try:
                usgs_flow_data = get_usgs_data_for_sites(
                    USGS_df, 
                    selected_sites, 
                    USGS_MAPPING,
                    date_range,
                    parameter='Flow_cfs'
                )
                
                if not usgs_flow_data.empty:
                    has_secondary_axis = True
                    
                    primary_locations = list(usgs_sc_data['Site_Name'].unique())
                    
                    for idx, usgs_site_name in enumerate(usgs_flow_data['Site_Name'].unique()):
                        site_flow = usgs_flow_data[usgs_flow_data['Site_Name'] == usgs_site_name]
                        
                        wqx_site_name = None
                        if USGS_MAPPING is not None:
                            usgs_site_num = site_flow['Site_Number'].iloc[0]
                            mapping_match = USGS_MAPPING[USGS_MAPPING['Site_Number'] == usgs_site_num]
                            if not mapping_match.empty:
                                wqx_site_name = mapping_match.iloc[0]['WQX_Site_Name']
                        
                        if wqx_site_name and wqx_site_name in primary_locations:
                            color_idx = primary_locations.index(wqx_site_name)
                            line_color = primary_colors[color_idx % len(primary_colors)]
                        elif usgs_site_name in primary_locations:
                            color_idx = primary_locations.index(usgs_site_name)
                            line_color = primary_colors[color_idx % len(primary_colors)]
                        else:
                            line_color = '#00CED1'
                        
                        fig.add_trace(go.Scatter(
                            x=site_flow['Date'],
                            y=site_flow['Flow_cfs'],
                            mode='lines',
                            name=f'{usgs_site_name} (USGS Flow)',
                            yaxis='y2',
                            showlegend=True,
                            line=dict(width=2, color=line_color, dash='dash'),
                            opacity=0.7,
                            legendgroup=f'{usgs_site_name}_usgs_flow',
                            hovertemplate='<b>%{fullData.name}</b><br>' +
                                        'Date: %{x|%Y-%m-%d}<br>' +
                                        'Flow: %{y:.2f} cfs<br>' +
                                        '<extra></extra>'
                        ))
            except Exception as e:
                print(f"Error adding USGS flow data: {e}")
        
        # Build title
        title = 'Specific Conductance (USGS Daily) Over Time'
        if has_secondary_axis:
            title += ' + Flow'
        
        # Layout configuration
        layout_config = dict(
            title=title,
            xaxis_title='Date',
            hovermode='closest',
            legend_title_text='Data Source',
            plot_bgcolor='#2d2d2d',
            paper_bgcolor='#1e1e1e',
            font=dict(family="Arial, sans-serif", size=12, color="white"),
            title_font=dict(family="Arial, sans-serif", size=16, color="white"),
            xaxis=dict(gridcolor='#404040', zerolinecolor='#404040', color='white', showgrid=True),
            legend=dict(
                orientation="h",
                yanchor="top",
                y=-0.15,
                xanchor="center",
                x=0.5,
                bgcolor='rgba(45, 45, 45, 0.8)',
                bordercolor='#555',
                borderwidth=1,
                font=dict(color='white', size=10)
            ),
            margin=dict(t=50, r=80, b=120, l=80)
        )
        
        # Add y-axis configurations
        if has_secondary_axis:
            layout_config['yaxis'] = dict(
                title=dict(text='Specific Conductance (µS/cm)', font=dict(color='white', size=14)),
                gridcolor='#404040',
                zerolinecolor='#404040',
                color='white',
                showgrid=True,
                side='left'
            )
            layout_config['yaxis2'] = dict(
                title=dict(text='Flow (cfs)', font=dict(color='#00CED1', size=14)),
                overlaying='y',
                side='right',
                color='#00CED1',
                showgrid=False
            )
        else:
            layout_config['yaxis'] = dict(
                title=dict(text='Specific Conductance (µS/cm)', font=dict(color='white', size=14)),
                gridcolor='#404040',
                color='white',
                showgrid=True
            )
        
        fig.update_layout(**layout_config)
        return fig
    
    # ========================================
    # BRANCH 2: WQX Characteristics
    # ========================================
    
    # Convert "All" to None
    if characteristic == "All":
        characteristic = None
    if basin == "All":
        basin = None
    if site == "All":
        site = None
    if sample_type == "All":
        sample_type = None

    # Get WQX Data
    data = filter_data(CSU_df, characteristic, fraction, basin, site, sample_type, date_range[0], date_range[1])

    # Check if data is empty
    if data is None or data.empty:
        fig = go.Figure()
        fig.add_annotation(
            text="No data available for selected filters",
            xref="paper", yref="paper",
            x=0.5, y=0.5, xanchor='center', yanchor='middle',
            showarrow=False,
            font=dict(size=16, color="white")
        )
        fig.update_layout(
            plot_bgcolor='#2d2d2d',
            paper_bgcolor='#1e1e1e',
            font=dict(color='white'),
            xaxis=dict(visible=False),
            yaxis=dict(visible=False),
            title="Time Series Analysis - No Data",
            title_font=dict(color='white')
        )
        return fig
        
    # If "All" characteristics selected, can't make a meaningful time series
    if characteristic is None:
        fig = go.Figure()
        fig.add_annotation(
            text="Please select a specific characteristic to view time series.<br>Multiple characteristics cannot be displayed on the same plot.",
            xref="paper", yref="paper",
            x=0.5, y=0.5, xanchor='center', yanchor='middle',
            showarrow=False,
            font=dict(size=16, color="white")
        )
        fig.update_layout(
            plot_bgcolor='#2d2d2d',
            paper_bgcolor='#1e1e1e',
            font=dict(color='white'),
            xaxis=dict(visible=False),
            yaxis=dict(visible=False),
            title="Time Series Analysis - Select a Characteristic",
            title_font=dict(color='white')
        )
        return fig
    
    # Get the appropriate unit for this characteristic
    unit = UNITS_MAP.get(characteristic, 'units')

    # Create figure
    fig = go.Figure()
    
    # Define color palette for primary data
    primary_colors = ['#1f77b4', '#ff7f0e', '#2ca02c', '#d62728', '#9467bd', 
                    '#8c564b', '#e377c2', '#7f7f7f', '#bcbd22', '#17becf']
    
    # Track if we need secondary y-axis
    has_secondary_axis = False

    # Add traces for the selected characteristic (WQX Data) - MARKERS ONLY
    for idx, location in enumerate(data['Location_Name'].unique()):
        location_data = data[data['Location_Name'] == location]
        fig.add_trace(go.Scatter(
            x=location_data['Activity_StartDate'],
            y=location_data['Result_Measure'],
            mode='markers',  # ONLY markers, no lines
            name=location,
            yaxis='y1',
            legendgroup=location,
            showlegend=True,  # Explicitly show legend
            marker=dict(size=8, opacity=0.8, color=primary_colors[idx % len(primary_colors)]),
            hovertemplate='<b>%{fullData.name}</b><br>' +
                        'Date: %{x|%Y-%m-%d}<br>' +
                        f'{characteristic}: %{{y:.2f}} {unit}<br>' +
                        '<extra></extra>'
        ))
    
    # Check what additional data to add
    if additional_data:
        
        # WQX Flow Data (spot measurements)
        if 'wqx_flow' in additional_data:
            try:
                flow_data = filter_data(CSU_df, 'Flow', None, basin, site, sample_type, date_range[0], date_range[1])
                
                if flow_data is not None and not flow_data.empty:
                    has_secondary_axis = True
                    print(f"Adding WQX flow data: {len(flow_data)} records")
                    
                    for idx, location in enumerate(flow_data['Location_Name'].unique()):
                        location_flow = flow_data[flow_data['Location_Name'] == location].copy()
                        location_flow = location_flow.sort_values('Activity_StartDate')
                        
                        # Match color to primary data if same site
                        location_list = list(data['Location_Name'].unique())
                        color_idx = location_list.index(location) if location in location_list else idx
                        
                        fig.add_trace(go.Scatter(
                            x=location_flow['Activity_StartDate'],
                            y=location_flow['Result_Measure'],
                            mode='markers',
                            name=f'{location} (WQX Flow)',
                            yaxis='y2',
                            showlegend=True,
                            marker=dict(size=10, symbol='diamond', opacity=0.8, 
                                    color=primary_colors[color_idx % len(primary_colors)]),
                            legendgroup=f'{location}_wqx_flow',
                            hovertemplate='<b>%{fullData.name}</b><br>' +
                                        'Date: %{x|%Y-%m-%d}<br>' +
                                        'Flow: %{y:.2f} cfs<br>' +
                                        '<extra></extra>'
                        ))
            except Exception as e:
                print(f"Error adding WQX flow data: {e}")
        
        # USGS Daily Flow Data
        if 'usgs_flow' in additional_data and HAS_USGS_DATA:
            try:
                # Get selected sites (convert to list if needed)
                selected_sites = [site] if isinstance(site, str) and site else (site if isinstance(site, list) else [])
                
                # Filter USGS data
                usgs_flow_data = get_usgs_data_for_sites(
                    USGS_df, 
                    selected_sites, 
                    USGS_MAPPING,
                    date_range,
                    parameter='Flow_cfs'
                )
                
                if not usgs_flow_data.empty:
                    has_secondary_axis = True
                    print(f"Adding USGS daily flow: {len(usgs_flow_data)} records")
                    
                    # Get list of primary data locations to match colors
                    primary_locations = list(data['Location_Name'].unique())
                    
                    for idx, usgs_site_name in enumerate(usgs_flow_data['Site_Name'].unique()):
                        site_flow = usgs_flow_data[usgs_flow_data['Site_Name'] == usgs_site_name]
                        
                        # Get the WQX site name for this USGS site
                        wqx_site_name = None
                        if USGS_MAPPING is not None:
                            usgs_site_num = site_flow['Site_Number'].iloc[0]
                            mapping_match = USGS_MAPPING[USGS_MAPPING['Site_Number'] == usgs_site_num]
                            if not mapping_match.empty:
                                wqx_site_name = mapping_match.iloc[0]['WQX_Site_Name']
                        
                        # Match color to the WQX site if it exists in primary data
                        if wqx_site_name and wqx_site_name in primary_locations:
                            color_idx = primary_locations.index(wqx_site_name)
                            line_color = primary_colors[color_idx % len(primary_colors)]
                            print(f"  Matched USGS site '{usgs_site_name}' to WQX site '{wqx_site_name}' - using color {line_color}")
                        else:
                            # Fallback color if no match
                            line_color = '#00CED1'
                            print(f"  No WQX match for USGS site '{usgs_site_name}' - using default color")
                        
                        fig.add_trace(go.Scatter(
                            x=site_flow['Date'],
                            y=site_flow['Flow_cfs'],
                            mode='lines',
                            name=f'{usgs_site_name} (USGS Flow)',
                            yaxis='y2',
                            showlegend=True,
                            line=dict(width=2, color=line_color, dash='dash'),  # ← Using matched color
                            opacity=0.7,
                            legendgroup=f'{usgs_site_name}_usgs_flow',
                            hovertemplate='<b>%{fullData.name}</b><br>' +
                                        'Date: %{x|%Y-%m-%d}<br>' +
                                        'Flow: %{y:.2f} cfs<br>' +
                                        '<extra></extra>'
                        ))
            except Exception as e:
                print(f"Error adding USGS flow data: {e}")
                import traceback
                traceback.print_exc()
        
        # USGS Daily Specific Conductance
        if 'usgs_sc' in additional_data and HAS_USGS_DATA:
            try:
                selected_sites = [site] if isinstance(site, str) and site else (site if isinstance(site, list) else [])
                
                usgs_sc_data = get_usgs_data_for_sites(
                    USGS_df,
                    selected_sites,
                    USGS_MAPPING,
                    date_range,
                    parameter='SpCond_uScm'
                )
                
                if not usgs_sc_data.empty:
                    print(f"Adding USGS daily specific conductance: {len(usgs_sc_data)} records")
                    
                    # If primary characteristic is conductivity-related, use primary axis
                    if characteristic in ['Conductivity', 'Specific conductance']:
                        yaxis_ref = 'y1'
                    else:
                        yaxis_ref = 'y2'
                        has_secondary_axis = True
                    
                    # Get list of primary data locations to match colors
                    primary_locations = list(data['Location_Name'].unique())
                    
                    for idx, usgs_site_name in enumerate(usgs_sc_data['Site_Name'].unique()):
                        site_sc = usgs_sc_data[usgs_sc_data['Site_Name'] == usgs_site_name]
                        
                        # Get the WQX site name for this USGS site
                        wqx_site_name = None
                        if USGS_MAPPING is not None:
                            usgs_site_num = site_sc['Site_Number'].iloc[0]
                            mapping_match = USGS_MAPPING[USGS_MAPPING['Site_Number'] == usgs_site_num]
                            if not mapping_match.empty:
                                wqx_site_name = mapping_match.iloc[0]['WQX_Site_Name']
                        
                        # Match color to the WQX site if it exists in primary data
                        if wqx_site_name and wqx_site_name in primary_locations:
                            color_idx = primary_locations.index(wqx_site_name)
                            line_color = primary_colors[color_idx % len(primary_colors)]
                        else:
                            line_color = '#FFA500'  # Orange fallback
                        
                        fig.add_trace(go.Scatter(
                            x=site_sc['Date'],
                            y=site_sc['SpCond_uScm'],
                            mode='lines',
                            name=f'{usgs_site_name} (USGS SpCond)',
                            yaxis=yaxis_ref,
                            showlegend=True,
                            line=dict(width=2, color=line_color, dash='dot'),  # ← Using matched color
                            opacity=0.7,
                            legendgroup=f'{usgs_site_name}_usgs_sc',
                            hovertemplate='<b>%{fullData.name}</b><br>' +
                                        'Date: %{x|%Y-%m-%d}<br>' +
                                        'SpCond: %{y:.0f} µS/cm<br>' +
                                        '<extra></extra>'
                        ))
            except Exception as e:
                print(f"Error adding USGS specific conductance data: {e}")
            
    # Update figure layout with dynamic title
    title_parts = [f'{characteristic} Over Time']
    if additional_data:
        if 'wqx_flow' in additional_data:
            title_parts.append('WQX Flow')
        if 'usgs_flow' in additional_data:
            title_parts.append('USGS Flow')
        if 'usgs_sc' in additional_data:
            title_parts.append('USGS SpCond')
    
    title = ' + '.join(title_parts) if len(title_parts) > 1 else title_parts[0]

    # Determine secondary axis label based on what's selected
    secondary_y_label = []
    if additional_data:
        if 'wqx_flow' in additional_data or 'usgs_flow' in additional_data:
            secondary_y_label.append('Flow (cfs)')
        if 'usgs_sc' in additional_data:
            # Only add SpCond to secondary if primary characteristic is NOT conductivity
            if characteristic not in ['Conductivity', 'Specific conductance']:
                secondary_y_label.append('SpCond (µS/cm)')

    secondary_y_title = ' / '.join(secondary_y_label) if secondary_y_label else 'Additional Data'

    # Base layout
    layout_config = dict(
        title=title,
        xaxis_title='Date',
        hovermode='closest',
        legend_title_text='Data Source',
        plot_bgcolor='#2d2d2d',
        paper_bgcolor='#1e1e1e',
        font=dict(
            family="Arial, sans-serif",
            size=12,
            color="white"
        ),
        title_font=dict(
            family="Arial, sans-serif",
            size=16,
            color="white"
        ),
        xaxis=dict(
            gridcolor='#404040',
            zerolinecolor='#404040',
            color='white',
            showgrid=True
        ),
        legend=dict(
            orientation="h",  # ← HORIZONTAL
            yanchor="top",
            y=-0.15,  # ← BELOW PLOT
            xanchor="center",
            x=0.5,  # ← CENTERED
            bgcolor='rgba(45, 45, 45, 0.8)',
            bordercolor='#555',
            borderwidth=1,
            font=dict(color='white', size=10),
            itemclick='toggle',
            itemdoubleclick='toggleothers',
            tracegroupgap=5  # Space between legend groups
        ),
        margin=dict(t=50, r=80, b=120, l=80)  
    )

    # Add y-axis configurations
    if has_secondary_axis:
        # Primary y-axis (left)
        layout_config['yaxis'] = dict(
            title=dict(
                text=f'{characteristic} ({unit})',
                font=dict(color='white', size=14)
            ),
            gridcolor='#404040',
            zerolinecolor='#404040',
            color='white',
            showgrid=True,
            showticklabels=True,
            tickfont=dict(color='white', size=12),
            side='left'
        )
        # Secondary y-axis (right) with dynamic label
        layout_config['yaxis2'] = dict(
            title=dict(
                text=secondary_y_title,  # ← DYNAMIC LABEL
                font=dict(color='#00CED1', size=14)
            ),
            overlaying='y',
            side='right',
            color='#00CED1',
            showticklabels=True,
            tickfont=dict(color='#00CED1', size=12),
            showgrid=False,
            zeroline=False
        )
    else:
        # Just primary y-axis
        layout_config['yaxis'] = dict(
            title=dict(
                text=f'{characteristic} ({unit})',
                font=dict(color='white', size=14)
            ),
            gridcolor='#404040',
            zerolinecolor='#404040',
            color='white',
            showgrid=True,
            showticklabels=True,
            tickfont=dict(color='white', size=12)
        )

    # Get acute and chronic values for the selected characteristic
    acute_values = data[(data['Acute'] != '') & (data['Acute'].notna())]['Acute'].dropna()
    chronic_values = data[(data['Chronic'] != '') & (data['Chronic'].notna())]['Chronic'].dropna()

    # Add horizontal lines for acute and chronic levels if they exist
    if not acute_values.empty:
        try:
            acute_level = float(acute_values.iloc[0])
            fig.add_hline(
                y=acute_level, 
                line_dash="dash", 
                line_color="red",
                annotation_text=f"Acute: {acute_level:.2f}",
                annotation_position="right"
            )
            # Add invisible scatter point to create legend entry
            fig.add_scatter(
                x=[None], y=[None],
                mode='lines',
                line=dict(color='red', dash='dash'),
                name=f'CDPHE Acute Standard ({acute_level:.2f})',
                showlegend=True
            )
        except (ValueError, TypeError):
            print(f"Warning: Could not convert acute value to float")

    if not chronic_values.empty:
        try:
            chronic_level = float(chronic_values.iloc[0])
            fig.add_hline(
                y=chronic_level, 
                line_dash="dash", 
                line_color="orange",
                annotation_text=f"Chronic: {chronic_level:.2f}",
                annotation_position="right"
            )
            # Add invisible scatter point to create legend entry
            fig.add_scatter(
                x=[None], y=[None],
                mode='lines',
                line=dict(color='orange', dash='dash'),
                name=f'CDPHE Chronic Standard ({chronic_level:.2f})',
                showlegend=True
            )
        except (ValueError, TypeError):
            print(f"Warning: Could not convert chronic value to float")

    # Apply layout
    fig.update_layout(**layout_config)
    
    return fig


def get_usgs_data_for_sites(usgs_df, wqx_sites, mapping_df, date_range, parameter='Flow_cfs'):
    """
    Helper function to get USGS data for selected WQX sites
    """
    print(f"\n=== GET_USGS_DATA DEBUG ===")
    print(f"USGS df size: {len(usgs_df)}")
    print(f"WQX sites: {wqx_sites}")
    print(f"Has mapping: {mapping_df is not None}")
    print(f"Date range: {date_range}")
    print(f"Parameter: {parameter}")
    
    if usgs_df.empty:
        print("ERROR: USGS dataframe is empty!")
        return pd.DataFrame()
    
    # Filter by date range
    start_date = datetime(year=date_range[0], month=1, day=1)
    end_date = datetime(year=date_range[1], month=12, day=31)
    
    date_mask = (usgs_df['Date'] >= start_date) & (usgs_df['Date'] <= end_date)
    filtered_df = usgs_df[date_mask].copy()
    print(f"After date filter: {len(filtered_df)} records")
    
    # If specific sites selected, filter to those
    if wqx_sites and wqx_sites != ['All'] and mapping_df is not None:
        print(f"Filtering for specific WQX sites...")
        print(f"Available mappings:\n{mapping_df[['WQX_Site_Name', 'Site_Number']]}")
        
        # Convert WQX site names to USGS site numbers
        usgs_site_numbers = []
        for wqx_site in wqx_sites:
            if wqx_site and wqx_site != 'All':
                matches = mapping_df[mapping_df['WQX_Site_Name'] == wqx_site]
                if not matches.empty:
                    site_num = matches.iloc[0]['Site_Number']
                    usgs_site_numbers.append(site_num)
                    print(f"  Matched '{wqx_site}' → USGS {site_num}")
                else:
                    print(f"  ⚠ No mapping found for '{wqx_site}'")
        
        if usgs_site_numbers:
            print(f"Looking for USGS sites: {usgs_site_numbers}")
            filtered_df = filtered_df[filtered_df['Site_Number'].isin(usgs_site_numbers)]
            print(f"After site filter: {len(filtered_df)} records")
        else:
            print("⚠ No USGS site numbers found - returning empty")
            return pd.DataFrame()
    else:
        print(f"No site filtering (showing all sites)")
    
    # Only return rows with valid data for the requested parameter
    if parameter in filtered_df.columns:
        before = len(filtered_df)
        filtered_df = filtered_df[filtered_df[parameter].notna()]
        print(f"After removing null {parameter}: {len(filtered_df)} records (removed {before - len(filtered_df)})")
    else:
        print(f"⚠ Parameter '{parameter}' not found in USGS data!")
        print(f"Available columns: {filtered_df.columns.tolist()}")
        return pd.DataFrame()
    
    print(f"=== RETURNING {len(filtered_df)} USGS RECORDS ===\n")
    return filtered_df

# Callback to export time series data as CSV
@app.callback(
    Output('download-timeseries-csv', 'data'),
    [Input('export-timeseries-btn', 'n_clicks')],
    [State('characteristic-select', 'value'),
     State('fraction-select', 'value'),
     State('basin-select', 'value'),
     State('site-select', 'value'),
     State('sample-type-select', 'value'),
     State('date-slider', 'value'),
     State('additional-data-toggle', 'value'),
     State('analysis', 'figure')],
    prevent_initial_call=True
)
def export_timeseries_data(n_clicks, characteristic, fraction, basin, site, sample_type, date_range, additional_data, figure):
    """Export the currently displayed time series data to CSV including USGS data"""

    if n_clicks == 0:
        return None
    
    # Check if USGS daily SpC was selected as the characteristic
    is_usgs_spc = (characteristic == 'Specific conductance (USGS-daily)')
    
    # Ensure site is always a list or None
    if site == "All" or site == ["All"]:
        site = None
    elif isinstance(site, str):
        site = [site]
    
    # Convert other "All" values to None
    if not is_usgs_spc and characteristic == "All":
        characteristic = None
    if basin == "All":
        basin = None
    if sample_type == "All":
        sample_type = None
    
    all_export_data = []
    
    # Extract visible trace names from figure
    visible_trace_names = set()
    if figure and 'data' in figure:
        for trace in figure['data']:
            # Check if trace is visible (visible property can be True, None, or missing)
            is_visible = trace.get('visible', True)
            if is_visible is not False and is_visible != 'legendonly':
                trace_name = trace.get('name', '')
                if trace_name:
                    visible_trace_names.add(trace_name)
    
    # HANDLE USGS SPECIFIC CONDUCTANCE AS PRIMARY CHARACTERISTIC
    if is_usgs_spc and HAS_USGS_DATA:
        try:
            selected_sites = site if site else []
            usgs_sc = get_usgs_data_for_sites(
                USGS_df,
                selected_sites,
                USGS_MAPPING,
                date_range,
                parameter='SpCond_uScm'
            )
            
            if not usgs_sc.empty:
                # Filter by visible traces using trace names
                if visible_trace_names:
                    # Match site names to visible traces
                    visible_sites = [s for s in usgs_sc['Site_Name'].unique() if s in visible_trace_names]
                    if visible_sites:
                        usgs_sc = usgs_sc[usgs_sc['Site_Name'].isin(visible_sites)]
                
                # ADD STREAM MILE
                usgs_sc['Stream_Mile'] = usgs_sc['Site_Name'].map(stream_miles_dict)
                
                usgs_sc_export = pd.DataFrame({
                    'Location_Name': usgs_sc['Site_Name'],
                    'Stream_Mile': usgs_sc['Stream_Mile'],  
                    'Date': usgs_sc['Date'],
                    'Result_Characteristic': 'Specific conductance',
                    'Result_SampleFraction': '',
                    'Result_Measure': usgs_sc['SpCond_uScm'],
                    'Result_MeasureUnit': 'uS/cm',
                    'Data_Source': 'USGS_Daily'
                })
                all_export_data.append(usgs_sc_export)
                print(f"Added {len(usgs_sc_export)} USGS SpC records")
        except Exception as e:
            print(f"Error exporting USGS SpC: {e}")
    
    # HANDLE REGULAR WQX DATA
    else:
        wqx_data = filter_data(CSU_df, characteristic, fraction, basin, site, sample_type, date_range[0], date_range[1])
        
        if wqx_data is not None and not wqx_data.empty:
            export_columns = [
                'Location_Name',
                'Activity_StartDate',
                'Result_Characteristic',
                'Result_SampleFraction',
                'Result_Measure',
                'Result_MeasureUnit',
                'Activity_MediaSubdivision',
                'Location_LatitudeStandardized',
                'Location_LongitudeStandardized',
                'Org_Identifier'
            ]
            export_columns = [col for col in export_columns if col in wqx_data.columns]
            
            wqx_export = wqx_data[export_columns].copy()
            wqx_export['Stream_Mile'] = wqx_export['Location_Name'].map(stream_miles_dict)
            wqx_export['Data_Source'] = 'WQX'
            wqx_export = wqx_export.rename(columns={'Activity_StartDate': 'Date'})
            
            # Reorder columns to put Stream_Mile after Location_Name
            cols = wqx_export.columns.tolist()
            if 'Stream_Mile' in cols:
                cols.remove('Stream_Mile')
                loc_idx = cols.index('Location_Name')
                cols.insert(loc_idx + 1, 'Stream_Mile')
                wqx_export = wqx_export[cols]

            # Filter by visible traces using location names
            if visible_trace_names:
                visible_locations = [loc for loc in wqx_export['Location_Name'].unique() if loc in visible_trace_names]
                if visible_locations:
                    wqx_export = wqx_export[wqx_export['Location_Name'].isin(visible_locations)]
            
            all_export_data.append(wqx_export)
    
    # ADD WQX FLOW if toggled (regardless of primary characteristic)
    if additional_data and 'wqx_flow' in additional_data:
        try:
            flow_data = filter_data(CSU_df, 'Flow', None, basin, site, sample_type, date_range[0], date_range[1])
            
            if flow_data is not None and not flow_data.empty:
                flow_data['Stream_Mile'] = flow_data['Location_Name'].map(stream_miles_dict)
                
                wqx_flow_export = pd.DataFrame({
                    'Location_Name': flow_data['Location_Name'],
                    'Stream_Mile': flow_data['Stream_Mile'],
                    'Date': flow_data['Activity_StartDate'],
                    'Result_Characteristic': 'Flow',
                    'Result_SampleFraction': flow_data['Result_SampleFraction'] if 'Result_SampleFraction' in flow_data.columns else '',
                    'Result_Measure': flow_data['Result_Measure'],
                    'Result_MeasureUnit': 'cfs',
                    'Data_Source': 'WQX_Flow'
                })
                
                # Filter by visible traces - match "Location (WQX Flow)" pattern
                if visible_trace_names:
                    visible_locations = []
                    for loc in wqx_flow_export['Location_Name'].unique():
                        # Check if either the plain name or the "name (WQX Flow)" is visible
                        if loc in visible_trace_names or f"{loc} (WQX Flow)" in visible_trace_names:
                            visible_locations.append(loc)
                    
                    if visible_locations:
                        wqx_flow_export = wqx_flow_export[wqx_flow_export['Location_Name'].isin(visible_locations)]
                        print(f"Filtered WQX Flow to visible locations: {visible_locations}")
                
                all_export_data.append(wqx_flow_export)
                print(f"Added {len(wqx_flow_export)} WQX Flow records")
        except Exception as e:
            print(f"Error exporting WQX flow: {e}")
            import traceback
            traceback.print_exc()
    
    # ADD USGS FLOW if toggled
    if additional_data and 'usgs_flow' in additional_data and HAS_USGS_DATA:
        try:
            selected_sites = site if site else []
            usgs_flow = get_usgs_data_for_sites(
                USGS_df, 
                selected_sites, 
                USGS_MAPPING,
                date_range,
                parameter='Flow_cfs'
            )
            
            if not usgs_flow.empty:
                # Filter by visible traces - match "Site Name (USGS Flow)" pattern
                if visible_trace_names:
                    visible_sites = []
                    for site_name in usgs_flow['Site_Name'].unique():
                        # Check if "name (USGS Flow)" is visible
                        if f"{site_name} (USGS Flow)" in visible_trace_names:
                            visible_sites.append(site_name)
                    
                    if visible_sites:
                        usgs_flow = usgs_flow[usgs_flow['Site_Name'].isin(visible_sites)]
                        print(f"Filtered USGS Flow to visible sites: {visible_sites}")
                
                usgs_flow['Stream_Mile'] = usgs_flow['Site_Name'].map(stream_miles_dict)
                
                usgs_flow_export = pd.DataFrame({
                    'Location_Name': usgs_flow['Site_Name'],
                    'Stream_Mile': usgs_flow['Stream_Mile'],
                    'Date': usgs_flow['Date'],
                    'Result_Characteristic': 'Flow',
                    'Result_SampleFraction': '',
                    'Result_Measure': usgs_flow['Flow_cfs'],
                    'Result_MeasureUnit': 'cfs',
                    'Data_Source': 'USGS_Daily'
                })
                all_export_data.append(usgs_flow_export)
                print(f"Added {len(usgs_flow_export)} USGS Flow records")
        except Exception as e:
            print(f"Error exporting USGS flow: {e}")
            import traceback
            traceback.print_exc()
    
    # Combine all data
    if len(all_export_data) == 0:
        print("No data to export")
        return None
    
    export_data = pd.concat(all_export_data, ignore_index=True)
    export_data = export_data.sort_values(['Location_Name', 'Date'])
    
    print(f"\n=== EXPORT SUMMARY ===")
    print(f"Total records: {len(export_data)}")
    print(f"Unique locations/sites: {export_data['Location_Name'].nunique()}")
    print(f"Data sources: {export_data['Data_Source'].unique()}")
    
    # Create filename
    filename_parts = []
    if is_usgs_spc:
        filename_parts.append('USGS_SpC')
    elif characteristic:
        filename_parts.append(characteristic.replace(' ', '_').replace(',', ''))
    if basin:
        filename_parts.append(basin.replace(' ', '_').replace(',', ''))
    if site and len(site) <= 3:
        for s in site:
            filename_parts.append(s.replace(' ', '_').replace(',', '')[:20])
    filename_parts.append(f"{date_range[0]}-{date_range[1]}")
    
    if additional_data:
        filename_parts.append('WithUSGS')
    
    filename = f"CSU_WaterQuality_{'_'.join(filename_parts)}.csv"
    
    print(f"Exporting to: {filename}")
    print("=== END EXPORT ===\n")
    
    return dcc.send_data_frame(export_data.to_csv, filename, index=False)   

# SUMMARY TABLE AND DATE RANGE DISPLAY 
# Date Range Display
@app.callback(
        Output('date-range-display', 'children'),
        [Input('date-slider', 'value'),
        Input('characteristic-select', 'value'),
        Input('fraction-select', 'value'),
        Input('basin-select', 'value'),
        Input('site-select', 'value'),
        Input('sample-type-select', 'value')
        ],
        prevent_initial_call=True
    )
def update_date_range_display(date_range, characteristic, fraction, basin, site, sample_type):
        # Get the actual data to find the real date range within the selection
        data = filter_data(CSU_df, characteristic, fraction, basin, site, sample_type, date_range[0], date_range[1])

        if data is None or data.empty:
            return html.Div([
                html.P(f"Selected Date Range: {date_range[0]} - {date_range[1]}", 
                    style={'margin': '0', 'font-size': '16px', 'color': '#ffffff'}),
                html.P("No data available for this selection", 
                    style={'margin': '5px 0 0 0', 'font-size': '14px', 'color': '#ff6b6b'})
            ])
        
        # Convert dates and find actual range in the filtered data
        data_dates = data['Activity_StartDate']  
        actual_start = data_dates.min().strftime('%B %Y')
        actual_end = data_dates.max().strftime('%B %Y')
                
        # Get total number of records and date count
        total_records = len(data)
        date_span_years = date_range[1] - date_range[0] + 1
        
        return html.Div([
            html.H4("Analysis Period", 
                    style={'margin': '0 0 10px 0', 'color': '#ffffff', 'font-size': '18px'}),
            html.P([
                html.Span("Selected Range: ", style={'font-weight': 'bold'}),
                f"{date_range[0]} - {date_range[1]} ({date_span_years} years)"
            ], style={'margin': '0', 'font-size': '14px', 'color': '#ffffff'}),
            html.P([
                html.Span("Data Available: ", style={'font-weight': 'bold'}),
                f"{actual_start} to {actual_end}"
            ], style={'margin': '5px 0 0 0', 'font-size': '14px', 'color': '#a0d468'}),
            html.P([
                html.Span("Total Records: ", style={'font-weight': 'bold'}),
                f"{total_records:,} measurements"
            ], style={'margin': '5px 0 0 0', 'font-size': '14px', 'color': '#4fc3f7'}),
         ])
  
# Summary Table
@app.callback(
    Output('summary-table', 'data'),
    [Input('characteristic-select', 'value'),
     Input('fraction-select', 'value'),
     Input('basin-select', 'value'),
     Input('site-select', 'value'),
     Input('sample-type-select', 'value'),
     Input('date-slider', 'value')
    ],
    prevent_initial_call=True
)

def update_table(characteristic, fraction, basin, site, sample_type, date_range):
    # Store original characteristic before converting to None
    original_characteristic = characteristic
    
    # Check if USGS daily SpC was selected
    is_usgs_spc = (characteristic == 'Specific conductance (USGS-daily)')

    # Convert "All" to None
    if not is_usgs_spc and characteristic == "All":
        characteristic = None
    if basin == "All":
        basin = None
    if site == "All":
        site = None
    if sample_type == "All":
        sample_type = None

    # Handle USGS SpC specially
    if is_usgs_spc and HAS_USGS_DATA:
        selected_sites = [site] if isinstance(site, str) and site else (site if isinstance(site, list) else [])
        
        usgs_sc_data = get_usgs_data_for_sites(
            USGS_df,
            selected_sites,
            USGS_MAPPING,
            date_range,
            parameter='SpCond_uScm'
        )
        
        if usgs_sc_data.empty:
            return [{'Statistic': 'No USGS Specific Conductance data available', 'Value': '', 'Units': ''}]
        
        # Convert to format similar to WQX data
        numeric_values = pd.to_numeric(usgs_sc_data['SpCond_uScm'], errors='coerce').dropna()
        data_dates = pd.to_datetime(usgs_sc_data['Date'])
        total_records = len(usgs_sc_data)
        num_valid = len(numeric_values)
        num_empty = total_records - num_valid
        
        earliest_date = data_dates.min().strftime('%m/%d/%Y')
        latest_date = data_dates.max().strftime('%m/%d/%Y')
        
        # Calculate statistics
        stats = {
            'Analysis Period': f"{date_range[0]} - {date_range[1]}",
            'Actual Data Range': f"{earliest_date} to {latest_date}",
            'Total Records': total_records,
            'Valid Records': num_valid,
            'Empty/Invalid Records': num_empty,
            'Mean': np.mean(numeric_values),
            'Std Deviation': np.std(numeric_values, ddof=1) if num_valid > 1 else 0,
            'Minimum': np.min(numeric_values),
            'Maximum': np.max(numeric_values),
            '25th Percentile': np.percentile(numeric_values, 25),
            '50th Percentile (Median)': np.percentile(numeric_values, 50),
            '75th Percentile': np.percentile(numeric_values, 75),
            '85th Percentile': np.percentile(numeric_values, 85),
            '95th Percentile': np.percentile(numeric_values, 95)
        }
        
        unit = 'µS/cm'
        
        # Format the data for the table
        summary_data = []
        for stat_name, value in stats.items():
            if stat_name in ['Total Records', 'Valid Records', 'Empty/Invalid Records']:
                formatted_value = f"{int(value)}"
                unit_display = "records (USGS Daily)"
            elif stat_name in ['Analysis Period', 'Actual Data Range']:
                formatted_value = str(value)
                unit_display = ""
            else:
                formatted_value = f"{value:.3f}"
                unit_display = unit
            
            summary_data.append({
                'Statistic': stat_name,
                'Value': formatted_value,
                'Units': unit_display
            })
        
        return summary_data
    
    # Otherwise, get WQX data (rest of function remains the same)
    data = filter_data(CSU_df, characteristic, fraction, basin, site, sample_type, date_range[0], date_range[1])
    
    if data is None or data.empty:
        # Return empty table if no data
        return []
    
    # Convert Result_Measure to numeric, handling any conversion errors
    numeric_values = pd.to_numeric(data['Result_Measure'], errors='coerce')
    
    # Count total records and valid numeric records
    total_records = len(data)
    valid_records = numeric_values.dropna()
    num_valid = len(valid_records)
    num_empty = total_records - num_valid
    
    if num_valid == 0:
        # If no valid numeric data, return a row showing this
        summary_data = [{
            'Statistic': 'No valid numeric data available',
            'Value': '',
            'Units': f'Selected: {date_range[0]}-{date_range[1]}'
        }]
        return summary_data
    
    # Get date information
    data_dates = pd.to_datetime(data['Activity_StartDate'])
    earliest_date = data_dates.min().strftime('%m/%d/%Y')
    latest_date = data_dates.max().strftime('%m/%d/%Y')
    
    # Calculate statistics
    try:
        stats = {
            'Analysis Period': f"{date_range[0]} - {date_range[1]}",
            'Actual Data Range': f"{earliest_date} to {latest_date}",
            'Total Records': total_records,
            'Valid Records': num_valid,
            'Empty/Invalid Records': num_empty,
            'Mean': np.mean(valid_records),
            'Std Deviation': np.std(valid_records, ddof=1) if num_valid > 1 else 0,
            'Minimum': np.min(valid_records),
            'Maximum': np.max(valid_records),
            '25th Percentile': np.percentile(valid_records, 25),
            '50th Percentile (Median)': np.percentile(valid_records, 50),
            '75th Percentile': np.percentile(valid_records, 75),
            '85th Percentile': np.percentile(valid_records, 85),
            '95th Percentile': np.percentile(valid_records, 95)
        }  
        
        # Get the appropriate unit 
        if original_characteristic and original_characteristic != "All":
            unit = UNITS_MAP.get(original_characteristic, 'units')
        else:
            # If "All" is selected, try to get the unit from the actual data
            if not data.empty and 'Result_Characteristic' in data.columns:
                # Get the most common characteristic in the filtered data
                most_common_char = data['Result_Characteristic'].mode()
                if len(most_common_char) > 0:
                    unit = UNITS_MAP.get(most_common_char.iloc[0], 'units')
                else:
                    unit = 'various'
            else:
                unit = 'various'
        
        # Format the data for the table
        summary_data = []
        for stat_name, value in stats.items():
            if stat_name in ['Total Records', 'Valid Records', 'Empty/Invalid Records']:
                # These are counts, keep as integers
                formatted_value = f"{int(value)}"
                unit_display = "records"
            elif stat_name in ['Analysis Period', 'Actual Data Range']:
                # These are date ranges, keep as strings
                formatted_value = str(value)
                unit_display = ""
            else:
                # These are measurements, format to 3 decimal places
                formatted_value = f"{value:.3f}"
                unit_display = unit
            
            summary_data.append({
                'Statistic': stat_name,
                'Value': formatted_value,
                'Units': unit_display
            })
        
        return summary_data
        
    except Exception as e:
        print(f"Error calculating statistics: {e}")
        return [{'Statistic': 'Error calculating statistics', 'Value': str(e), 'Units': ''}]

# HEATMAP
@app.callback(
    Output('heatmap', 'figure'),
    [Input('characteristic-select', 'value'),
     Input('fraction-select', 'value'),
     Input('basin-select', 'value'),
     Input('site-select', 'value'),
     Input('sample-type-select', 'value'),
     Input('date-slider', 'value')
    ],
    prevent_initial_call=True
)
def plot_heatmap(characteristic, fraction, basin, site, sample_type, date_range):
    # Store original characteristic before converting to None
    original_characteristic = characteristic
    
    # Check if USGS daily SpC was selected
    is_usgs_spc = (characteristic == 'Specific conductance (USGS-daily)')
    
    # Handle USGS SpC specially
    if is_usgs_spc and HAS_USGS_DATA:
        selected_sites = [site] if isinstance(site, str) and site else (site if isinstance(site, list) else [])
        
        usgs_sc_data = get_usgs_data_for_sites(
            USGS_df,
            selected_sites,
            USGS_MAPPING,
            date_range,
            parameter='SpCond_uScm'
        )
        
        if usgs_sc_data.empty:
            fig = go.Figure()
            fig.add_annotation(
                text="No USGS Specific Conductance data available",
                xref="paper", yref="paper",
                x=0.5, y=0.5, xanchor='center', yanchor='middle',
                showarrow=False,
                font=dict(size=16, color="white")
            )
            fig.update_layout(
                plot_bgcolor='#2d2d2d',
                paper_bgcolor='#1e1e1e',
                font=dict(color='white'),
                xaxis=dict(visible=False),
                yaxis=dict(visible=False),
                title='USGS Specific Conductance Heatmap - No Data',
                title_font=dict(color='white')
            )
            return fig
        
        # Convert to numeric
        numeric_values = pd.to_numeric(usgs_sc_data['SpCond_uScm'], errors='coerce').dropna()
        
        if len(numeric_values) == 0:
            fig = go.Figure()
            fig.add_annotation(
                text="No valid USGS data available",
                xref="paper", yref="paper",
                x=0.5, y=0.5, xanchor='center', yanchor='middle',
                showarrow=False,
                font=dict(size=16, color="white")
            )
            fig.update_layout(
                plot_bgcolor='#2d2d2d',
                paper_bgcolor='#1e1e1e',
                font=dict(color='white'),
                xaxis=dict(visible=False),
                yaxis=dict(visible=False),
                title='USGS Specific Conductance Heatmap - No Valid Data',
                title_font=dict(color='white')
            )
            return fig
        
        unit = 'µS/cm'
        
        # Calculate statistics for the colorbar annotation
        min_val = np.min(numeric_values)
        max_val = np.max(numeric_values)
        median_val = np.median(numeric_values)
        p75_val = np.percentile(numeric_values, 75)
        p90_val = np.percentile(numeric_values, 90)
        
        # Create the heatmap
        figure = go.Figure(data = go.Heatmap(
            z = usgs_sc_data.loc[numeric_values.index, 'SpCond_uScm'],
            x = usgs_sc_data.loc[numeric_values.index, 'Date'],
            y = usgs_sc_data.loc[numeric_values.index, 'Site_Name'], 
            colorscale = create_data_driven_color_scale(numeric_values),
            colorbar=dict(
                title=dict(
                    text=f"Specific Conductance<br>(USGS Daily)<br>({unit})",
                    font=dict(color='white', size=12)
                ),
                tickfont=dict(color='white'),
                tickmode='linear',
                tick0=min_val,
                dtick=(max_val - min_val) / 5,
                bgcolor='rgba(45, 45, 45, 0.8)',
                bordercolor='white',
                borderwidth=1
            ),
            hovertemplate='<b>%{y}</b><br>' +
                        'Date: %{x}<br>' +
                        f'SpCond: %{{z:.1f}} {unit}<br>' +
                        '<extra></extra>'
        ))

        # Add color legend annotation
        color_legend = (
            f"<b>Color Scale (from data):</b><br>" +
            f"🔵 Dark Blue: {min_val:.1f} {unit} (minimum)<br>" +
            f"🔵 Blue: {np.percentile(numeric_values, 25):.1f} {unit} (25th percentile)<br>" +
            f"🟢 Green: {median_val:.1f} {unit} (median)<br>" +
            f"🟡 Yellow: {p75_val:.1f} {unit} (75th percentile)<br>" +
            f"🟠 Orange: {p90_val:.1f} {unit} (90th percentile)<br>" +
            f"🔴 Red: {max_val:.1f} {unit} (maximum)"
        )

        figure.update_layout(
            plot_bgcolor='#2d2d2d',
            paper_bgcolor='#1e1e1e',
            font=dict(color='white'),
            xaxis=dict(
                color='white',
                title=dict(text='Date', font=dict(color='white'))
            ),
            yaxis=dict(
                color='white',
                title=dict(text='Monitoring Location', font=dict(color='white'))
            ),
            title=dict(
                text=f'USGS Specific Conductance Heatmap ({unit})<br><sub>Range: {min_val:.2f}-{max_val:.2f} {unit} | Median: {median_val:.2f} {unit}</sub>',
                font=dict(color='white', size=16),
                x=0.5
            ),
            annotations=[
                dict(
                    text=color_legend,
                    xref="paper", yref="paper",
                    x=-0.3, y=1.25,
                    xanchor='left', yanchor='top',
                    showarrow=False,
                    font=dict(size=10, color="white"),
                    bgcolor="rgba(45, 45, 45, 0.8)",
                    bordercolor="white",
                    borderwidth=1
                )
            ],
            margin=dict(t=80, r=50, b=50, l=50)
        )

        return figure
    
    # Otherwise, handle WQX data (rest of function remains the same)
    # Convert "All" to None
    if characteristic == "All":
        characteristic = None
    if basin == "All":
        basin = None
    if site == "All":
        site = None
    if sample_type == "All":
        sample_type = None
    
    data = filter_data(CSU_df, characteristic, fraction, basin, site, sample_type, date_range[0], date_range[1])
    
    if data is None or data.empty or 'Result_Measure' not in data.columns:
        # Return empty figure with message
        fig = go.Figure()
        fig.add_annotation(
            text="No data available for selected filters",
            xref="paper", yref="paper",
            x=0.5, y=0.5, xanchor='center', yanchor='middle',
            showarrow=False,
            font=dict(size=16, color="white")
        )
        fig.update_layout(
            plot_bgcolor='#2d2d2d',
            paper_bgcolor='#1e1e1e',
            font=dict(color='white'),
            xaxis=dict(visible=False),
            yaxis=dict(visible=False),
            title='Heatmap - No Data',
            title_font=dict(color='white')
        )
        return fig
    
    # If "All" characteristics selected, can't make a meaningful heatmap
    if characteristic is None:
        fig = go.Figure()
        fig.add_annotation(
            text="Please select a specific characteristic to view heatmap.<br>Multiple characteristics cannot be displayed together.",
            xref="paper", yref="paper",
            x=0.5, y=0.5, xanchor='center', yanchor='middle',
            showarrow=False,
            font=dict(size=16, color="white")
        )
        fig.update_layout(
            plot_bgcolor='#2d2d2d',
            paper_bgcolor='#1e1e1e',
            font=dict(color='white'),
            xaxis=dict(visible=False),
            yaxis=dict(visible=False),
            title='Heatmap - Select a Characteristic',
            title_font=dict(color='white')
        )
        return fig
          
    # Check if we have valid numeric data
    numeric_values = pd.to_numeric(data['Result_Measure'], errors='coerce').dropna()
    if len(numeric_values) == 0:
        # Return empty figure with message
        fig = go.Figure()
        fig.add_annotation(
            text="No valid numeric data available",
            xref="paper", yref="paper",
            x=0.5, y=0.5, xanchor='center', yanchor='middle',
            showarrow=False,
            font=dict(size=16, color="white")
        )
        fig.update_layout(
            plot_bgcolor='#2d2d2d',
            paper_bgcolor='#1e1e1e',
            font=dict(color='white'),
            xaxis=dict(visible=False),
            yaxis=dict(visible=False),
            title=f'{original_characteristic} Heatmap - No Valid Data',
            title_font=dict(color='white')
        )
        return fig
    
    # Get the appropriate unit for this characteristic
    unit = UNITS_MAP.get(original_characteristic, 'units')
    
    # Calculate statistics for the colorbar annotation
    min_val = np.min(numeric_values)
    max_val = np.max(numeric_values)
    median_val = np.median(numeric_values)
    p75_val = np.percentile(numeric_values, 75)
    p90_val = np.percentile(numeric_values, 90)
    
    # Create the heatmap using data-driven color scale
    figure = go.Figure(data = go.Heatmap(
        z = numeric_values,
        x = data.loc[numeric_values.index, 'Activity_StartDate'],
        y = data.loc[numeric_values.index, 'Location_Name'], 
        colorscale = create_data_driven_color_scale(numeric_values),
        colorbar=dict(
           title=dict(
                text=f"{original_characteristic}<br>({unit})",
                font=dict(color='white', size=12)
            ),
            tickfont=dict(color='white'),
            tickmode='linear',
            tick0=min_val,
            dtick=(max_val - min_val) / 5,
            bgcolor='rgba(45, 45, 45, 0.8)',
            bordercolor='white',
            borderwidth=1
        ),
        hovertemplate='<b>%{y}</b><br>' +
                      'Date: %{x}<br>' +
                      f'{original_characteristic}: %{{z:.1f}} {unit}<br>' +
                      '<extra></extra>'
    ))

    # Add annotations to show what the colors represent
    color_legend = (
        f"<b>Color Scale (from data):</b><br>" +
        f"🔵 Dark Blue: {min_val:.1f} {unit} (minimum)<br>" +
        f"🔵 Blue: {np.percentile(numeric_values, 25):.1f} {unit} (25th percentile)<br>" +
        f"🟢 Green: {median_val:.1f} {unit} (median)<br>" +
        f"🟡 Yellow: {p75_val:.1f} {unit} (75th percentile)<br>" +
        f"🟠 Orange: {p90_val:.1f} {unit} (90th percentile)<br>" +
        f"🔴 Red: {max_val:.1f} {unit} (maximum)"
    )

    figure.update_layout(
        plot_bgcolor='#2d2d2d',
        paper_bgcolor='#1e1e1e',
        font=dict(color='white'),
        xaxis=dict(
            color='white',
            title=dict(text='Date', font=dict(color='white'))
        ),
        yaxis=dict(
            color='white',
            title=dict(text='Monitoring Location', font=dict(color='white'))
        ),
        title=dict(
            text=f'{original_characteristic} Concentration Heatmap ({unit})<br><sub>Range: {min_val:.2f}-{max_val:.2f} {unit} | Median: {median_val:.2f} {unit}</sub>',
            font=dict(color='white', size=16),
            x=0.5
        ),

        # Add annotation explaining the color scale
        annotations=[
            dict(
                text=color_legend,
                xref="paper", yref="paper",
                x=-0.3, y=1.25,
                xanchor='left', yanchor='top',
                showarrow=False,
                font=dict(size=10, color="white"),
                bgcolor="rgba(45, 45, 45, 0.8)",
                bordercolor="white",
                borderwidth=1
            )
        ],
        margin=dict(t=80, r=50, b=50, l=50)
    )

    return figure

if __name__ == "__main__":
    app.run(debug=True)
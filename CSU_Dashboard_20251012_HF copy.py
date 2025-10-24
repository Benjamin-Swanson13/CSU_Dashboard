# Colorado Springs Utilities Water Quality Dashboard
# This dashboard pulls data from EPA beta WQX, processes it, and provides interactive visualizations.
# It also includes canal/ditch locations that may be relevant to the project goals.
# Created by Haley Farwell & Eidan Willis; SGM, Inc. 2025


import os
import pathlib
import re
import dash
from dash import Dash, html, dcc, callback, Output, Input, dash_table
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

import pandas as pd
import numpy as np


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


def filter_data(df, characteristic, fraction, basin, site, canal_toggle, sample_type, start_year, end_year):
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
    if isinstance(site, (list, tuple)): 
        site = site[0] if site else None
    
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
    
    # Step 3.5: Filter by site/monitoring location (if specified) - ADD THIS ENTIRE SECTION
    if site is not None:
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
                min-height: 40px !important;
            }
            
            .Select-control:hover {
                border-color: #777 !important;
            }
            
            .Select-menu-outer {
                background-color: #404040 !important;
                border: 1px solid #555 !important;
                border-radius: 6px !important;
                box-shadow: 0 4px 8px rgba(0,0,0,0.3) !important;
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

# Load data
CSU_df = pd.read_csv(parsed_csv, dtype=str)
canals_df = pd.read_csv('Canal_locs.csv')

# Convert dates safely
CSU_df['Activity_StartDate'] = pd.to_datetime(CSU_df['Activity_StartDate'], errors='coerce')

# Convert numeric values safely, handling text values
CSU_df['Result_Measure'] = pd.to_numeric(CSU_df['Result_Measure'], errors='coerce')

# Only add this if parse_dates fails:
#CSU_df['Activity_StartDate'] = pd.to_datetime(CSU_df['Activity_StartDate'], errors='coerce')

# Date range slider limits
min_year = CSU_df['Activity_StartDate'].min().year
max_year = CSU_df['Activity_StartDate'].max().year

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

CHARACTERISTICS = ['All'] + sorted(CSU_df['Result_Characteristic'].unique().tolist())
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
    name='Basin Boundaries'
)

mapbox_access_token = 'pk.eyJ1IjoiY29vcGVyLXAiLCJhIjoiY2x3a3Y4c2k5MDh5bjJqcGIycXV6Znl3biJ9.4J3P3HOVVTiVaY_lW5Ew2Q'
mapbox_style = 'satellite-streets'

# App Layout
app.layout = html.Div(
    id='root',
    children=[
        # Header section (unchanged)
        html.Div(
            id='header',
            children=[
                html.H1('Colorado Springs Utilities Water Quality Data Dashboard', 
                       style={'text-align': 'center', 'color': '#ffffff', 'margin-bottom': '30px',
                              'font-size': '28px', 'font-weight': '300'})
            ],
            style={'padding': '20px 0', 'background-color': '#2d2d2d', 'margin-bottom': '20px'}
        ),
        
        # Large map section at the top
        html.Div(
            id='top-map-section',
            children=[
                html.Div([
                    html.H3('Monitoring Locations', 
                           style={'color': '#ffffff', 'margin-bottom': '15px', 'font-size': '18px'}),
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
                        style={'height': '600px'}  # Bigger height
                    ),
                    dcc.Checklist(
                        id='canal-toggle',
                        options=[{'label': ' Show Canals/Ditches', 'value': 'show'}],
                        value=[],  # Empty by default (canals hidden)
                        style={'margin': '10px', 'color': '#ffffff'}  # Added white text color
                    )
                ], style={
                    'background-color': '#2d2d2d',
                    'padding': '20px',
                    'border-radius': '8px',
                    'box-shadow': '0 4px 6px rgba(0, 0, 0, 0.3)'
                })
            ],
            style={'margin-bottom': '20px'}
        ),
        
        # Controls and analysis section (side by side)
        html.Div(
            id='controls-and-analysis',
            children=[
                # Left column - Controls 
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
                                    html.Label('Date Range:', 
                                             style={'color': '#ffffff', 'font-weight': 'bold', 'margin-bottom': '15px', 'display': 'block'}),
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
                                'padding': '25px',
                                'border-radius': '10px',
                                'box-shadow': '0 4px 6px rgba(0, 0, 0, 0.3)',
                                'height': 'fit-content'  # Adjust to content
                            }
                        )
                    ],
                    style={'width': '100%', 'margin-bottom': '20px'}
                ),
                
                # Right column - Time series 
                html.Div(
                    id='right-analysis-column',
                    children=[
                        html.Div([
                            html.H3('Time Series Analysis', 
                                   style={'color': '#ffffff', 'margin-bottom': '15px', 'font-size': '18px'}),
                            dcc.Graph(
                                id='analysis',
                                figure=dict(data=None, layout=dict([])),
                                style={'height': '500px'}
                            )
                        ], style={
                            'background-color': '#2d2d2d',
                            'padding': '20px',
                            'border-radius': '10px',
                            'box-shadow': '0 4px 6px rgba(0, 0, 0, 0.3)'
                        })
                    ],
                    style={'width': '100%'}
                )
            ],
            style={'margin-bottom': '30px'}
        ),
        
        # Bottom section - Date range display, summary and heatmap 
        html.Div(
            id='summary-section',
            children=[
                # Date Range Display
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
        available_sites = sorted(CSU_df['Location_Name'].dropna().unique())
        options = [{'label': 'All', 'value': 'All'}] + [{'label': site, 'value': site} for site in available_sites]
        return options, 'All'
    
    # Filter sites by basin using spatial join
    try:
        # Get all unique sites with coordinates
        sites_df = CSU_df[['Location_Name', 'Location_LatitudeStandardized', 'Location_LongitudeStandardized']].drop_duplicates()
        sites_df = sites_df.dropna()
        
        # Convert to numeric
        sites_df['Location_LatitudeStandardized'] = pd.to_numeric(sites_df['Location_LatitudeStandardized'], errors='coerce')
        sites_df['Location_LongitudeStandardized'] = pd.to_numeric(sites_df['Location_LongitudeStandardized'], errors='coerce')
        sites_df = sites_df.dropna()
        
        # Create GeoSeries of points
        points = gpd.GeoSeries(gpd.points_from_xy(
            sites_df['Location_LongitudeStandardized'], 
            sites_df['Location_LatitudeStandardized']
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
            available_sites = sorted(CSU_df['Location_Name'].dropna().unique())
            options = [{'label': 'All', 'value': 'All'}] + [{'label': site, 'value': site} for site in available_sites]
            return options, 'All'
        
        # Get basin geometry
        basin_match = BASINS_GDF[BASINS_GDF[basin_col] == basin]
        if basin_match.empty:
            print(f"ERROR: Basin '{basin}' not found")
            # Fallback to all sites
            available_sites = sorted(CSU_df['Location_Name'].dropna().unique())
            options = [{'label': 'All', 'value': 'All'}] + [{'label': site, 'value': site} for site in available_sites]
            return options, 'All'
        
        basin_geom = basin_match['geometry'].iloc[0]
        
        # Find sites within basin
        sites_in_basin = points.within(basin_geom, align=False)
        sites_in_basin.index = sites_df.index
        
        # Get list of site names in basin
        sites_in_basin_df = sites_df[sites_in_basin]
        available_sites = sorted(sites_in_basin_df['Location_Name'].unique())
        
        print(f"Found {len(available_sites)} sites in basin '{basin}'")
        
        # Create options
        if len(available_sites) == 0:
            # No sites in basin
            options = [{'label': 'No sites in selected basin', 'value': 'All'}]
            return options, 'All'
        else:
            options = [{'label': 'All', 'value': 'All'}] + [{'label': site, 'value': site} for site in available_sites]
            return options, 'All'
    
    except Exception as e:
        print(f"ERROR in site filtering: {e}")
        import traceback
        traceback.print_exc()
        
        # Fallback to all sites on error
        available_sites = sorted(CSU_df['Location_Name'].dropna().unique())
        options = [{'label': 'All', 'value': 'All'}] + [{'label': site, 'value': site} for site in available_sites]
        return options, 'All'

# Update characteristic dropdown based on basin and site selection
@app.callback(
    [Output('characteristic-select', 'options'),
     Output('characteristic-select', 'value')],
    [Input('basin-select', 'value'),
     Input('site-select', 'value')]
)
def update_characteristic_options(basin, site):
    """Update characteristic dropdown based on selected basin and monitoring location"""
    
    # If both "All" selected, show all characteristics
    if (basin is None or basin == "All") and (site is None or site == "All"):
        available_characteristics = sorted(CSU_df['Result_Characteristic'].dropna().unique())
        options = [{'label': 'All', 'value': 'All'}] + [{'label': char, 'value': char} for char in available_characteristics]
        return options, 'All'
    
    # If only site is selected (basin is "All")
    if (basin is None or basin == "All") and site and site != "All":
        site_data = CSU_df[CSU_df['Location_Name'] == site]
        available_characteristics = sorted(site_data['Result_Characteristic'].dropna().unique())
        
        print(f"Found {len(available_characteristics)} characteristics at site '{site}'")
        
        if len(available_characteristics) == 0:
            options = [{'label': 'No data at selected site', 'value': 'All'}]
            return options, 'All'
        else:
            options = [{'label': 'All', 'value': 'All'}] + [{'label': char, 'value': char} for char in available_characteristics]
            return options, 'All'
    
    # If basin is selected (with or without site)
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
            # Fallback to all characteristics
            available_characteristics = sorted(CSU_df['Result_Characteristic'].dropna().unique())
            options = [{'label': 'All', 'value': 'All'}] + [{'label': char, 'value': char} for char in available_characteristics]
            return options, 'All'
        
        # Get basin geometry
        basin_match = BASINS_GDF[BASINS_GDF[basin_col] == basin]
        if basin_match.empty:
            print(f"ERROR: Basin '{basin}' not found")
            # Fallback to all characteristics
            available_characteristics = sorted(CSU_df['Result_Characteristic'].dropna().unique())
            options = [{'label': 'All', 'value': 'All'}] + [{'label': char, 'value': char} for char in available_characteristics]
            return options, 'All'
        
        basin_geom = basin_match['geometry'].iloc[0]
        
        # Find data points within basin
        data_in_basin = points.within(basin_geom, align=False)
        data_in_basin.index = data_with_coords.index
        
        # Get data in basin
        basin_data = data_with_coords[data_in_basin]
        
        # Further filter by site if a specific site is selected
        if site and site != "All":
            basin_data = basin_data[basin_data['Location_Name'] == site]
            print(f"Filtering for basin '{basin}' AND site '{site}'")
        else:
            print(f"Filtering for basin '{basin}' (all sites)")
        
        # Get unique characteristics in this filtered data
        available_characteristics = sorted(basin_data['Result_Characteristic'].dropna().unique())
        
        print(f"Found {len(available_characteristics)} characteristics")
        
        # Create options
        if len(available_characteristics) == 0:
            # No characteristics found
            if site and site != "All":
                options = [{'label': 'No data for selected basin and site', 'value': 'All'}]
            else:
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

# BASIN DROPDOWN AND MAP HIGHLIGHTING
@app.callback(
    Output('basin-map', 'figure'),
    [Input('characteristic-select', 'value'),
     Input('fraction-select', 'value'),
     Input('basin-select', 'value'),
     Input('site-select', 'value'),
     Input('canal-toggle', 'value'),
     Input('sample-type-select', 'value'),
     Input('date-slider', 'value')
    ]
)
def highlight_basin(characteristic, fraction, basin, site, canal_toggle, sample_type, date_range):
    print(f"Debug: Selected basin = {basin}")
    print(f"Debug: Canal toggle = {canal_toggle}")

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
        basin_col = 'ID'  # Fallback to ID if no name column found
    
    print(f"Debug: Using basin column = {basin_col}")
    print(f"Debug: Available basins = {basin_df[basin_col].unique()}")
    
    # Get the specific basin geometry using the name
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
        showlegend=False
    )
    
    # Filter and process the data
    data = []
    if characteristic and basin:
        df = filter_data(CSU_df, characteristic, fraction, basin, site, canal_toggle, sample_type, date_range[0], date_range[1])
        
        if not df.empty:
            print(f"Debug: Found {len(df)} filtered records")
            
            # Convert to numeric
            df['Result_Measure'] = pd.to_numeric(df['Result_Measure'], errors='coerce')
            df['Location_LatitudeStandardized'] = pd.to_numeric(df['Location_LatitudeStandardized'], errors='coerce')
            df['Location_LongitudeStandardized'] = pd.to_numeric(df['Location_LongitudeStandardized'], errors='coerce')
            
            # Remove any rows where conversion failed
            df = df.dropna(subset=['Location_LatitudeStandardized', 'Location_LongitudeStandardized', 'Result_Measure'])

            # Aggregate data by monitoring location
            agg_dict = {
                'Location_LatitudeStandardized': 'mean',
                'Location_LongitudeStandardized': 'mean',
                'Result_Measure': 'mean'
            }

            df_mean = df.groupby('Location_Name', as_index=False).agg(agg_dict)
            df_mean['Result_Characteristic'] = characteristic
            
            # Assign colors
            colors, min_val, max_val = assign_continuous_color_scale(df_mean)
            df_mean['color'] = colors

            # Get non-selected stations (outside the basin or different characteristics)
            non_selected = CSU_df[~CSU_df['Location_Name'].isin(df_mean['Location_Name'].unique())]

            # Create the map data
            data = [
                dict(  # Grey points for non-selected stations
                    lat=non_selected['Location_LatitudeStandardized'],
                    lon=non_selected['Location_LongitudeStandardized'],
                    type='scattermapbox',
                    hovertext=non_selected['Location_Name'],
                    marker=dict(size=5, color='grey', opacity=0.5),
                    name='Other Stations',
                    showlegend=False
                ),
                dict(  # Color-coded points for selected basin/characteristic
                    lat=df_mean['Location_LatitudeStandardized'],
                    lon=df_mean['Location_LongitudeStandardized'],
                    type='scattermapbox',
                    hovertext=[f"{name}<br>{char}: {val:.2f}" for name, char, val in
                              zip(df_mean['Location_Name'],
                                  df_mean['Result_Characteristic'],
                                  df_mean['Result_Measure'])],
                    marker=dict(size=10, color=df_mean['color'], opacity=1),
                    name='Selected Data',
                    showlegend=False
                ),
                dict(  # Basin centroids for hover text
                    lat=huc_centroids['lat'],
                    lon=huc_centroids['lon'],
                    type='scattermapbox',
                    hovertext=huc_centroids['name'],  # Changed from 'ID' to 'name'
                    hovermode='closest',
                    marker=dict(size=100, color='white', opacity=0),
                    showlegend=False
                )
            ]
        else:
            print("Debug: No filtered data found")
            # If no filtered data, show all stations as grey
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
                dict(  # Basin centroids
                    lat=huc_centroids['lat'],
                    lon=huc_centroids['lon'],
                    type='scattermapbox',
                    hovertext=huc_centroids['name'],  # Changed from 'ID' to 'name'
                    hovermode='closest',
                    marker=dict(size=100, color='white', opacity=0),
                    showlegend=False
                )
            ]
    else:
        print("Debug: No characteristic or basin selected")
        # If no characteristic or basin selected, use initial data
        data = data_initial

    fig = dict(data=data, layout=layout)
    
    # Add canals/ditches if toggle is checked
    if canal_toggle and 'show' in canal_toggle:
        try:
            print(f"Debug: ADDING CANALS - Found {len(canals_df)} canal locations")
            
            # Convert to lists explicitly
            print("Debug: Converting to lists...")
            canal_lats = canals_df['Latitude'].tolist()
            print(f"Debug: Got {len(canal_lats)} latitudes")
            
            canal_lons = canals_df['Longitude'].tolist()
            print(f"Debug: Got {len(canal_lons)} longitudes")
            
            canal_names = canals_df['Name'].tolist()
            print(f"Debug: Got {len(canal_names)} names")
            
            print(f"Debug: Sample canal - {canal_names[0]}: ({canal_lats[0]}, {canal_lons[0]})")
            
            canal_trace = dict(
                lat=canal_lats,
                lon=canal_lons,
                type='scattermapbox',
                mode='markers',
                marker=dict(
                    size=15,
                    color="orange",
                    opacity=1,
                    symbol='triangle',
                    line=dict(width=2, color='white')
                ),
                text=canal_names,
                hovertemplate='<b>🌊 CANAL: %{text}</b><br>Lat: %{lat:.4f}<br>Lon: %{lon:.4f}<extra></extra>',
                name='Canals/Ditches',
                showlegend=True
            )
            print("Debug: Canal trace dict created")
            
            data.append(canal_trace)
            print(f"Debug: Canal trace appended. Total traces now: {len(data)}")
            
        except Exception as e:
            print(f"ERROR adding canals: {e}")
            import traceback
            traceback.print_exc()
    else:
        print("Debug: Canal toggle NOT activated")
    

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
        showlegend=True,  # Changed to True so canal legend shows
        legend=dict(
            bgcolor='rgba(45, 45, 45, 0.8)',
            bordercolor='white',
            font=dict(color='white')
        )
    )

    fig = dict(data=data, layout=layout)
    return fig


# TIME SERIES ANALYSIS
@app.callback(
    Output('analysis', 'figure'),
    [Input('characteristic-select', 'value'),
     Input('fraction-select', 'value'),
     Input('basin-select', 'value'),
     Input('site-select', 'value'),
     Input('canal-toggle', 'value'),
     Input('sample-type-select', 'value'),
     Input('date-slider', 'value')
    ],
    prevent_initial_call=True
)
def plot_data(characteristic, fraction, basin, site, canal_toggle, sample_type, date_range):
     # Convert "All" to None
    if characteristic == "All":
        characteristic = None
    if basin == "All":
        basin = None
    if site == "All":
        site = None
    if sample_type == "All":
        sample_type = None

    data = filter_data(CSU_df, characteristic, fraction, basin, site, canal_toggle, sample_type, date_range[0], date_range[1])
    
     # Check if data is empty
    if data is None or data.empty:
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

    # Create the base scatter plot
    figure = px.scatter(data, x='Activity_StartDate', y='Result_Measure', color='Location_Name')
    
    # Create figure with secondary y-axis
    fig = go.Figure()
    
    # Add traces for the selected characteristic
    for location in data['Location_Name'].unique():
        location_data = data[data['Location_Name'] == location]
        fig.add_trace(go.Scatter(
            x=location_data['Activity_StartDate'],
            y=location_data['Result_Measure'],
            mode='markers',
            name=location,
            yaxis='y1'
        ))
    
    # Try to add flow data on secondary axis
    try:
        # Get flow data for the same filters (but force characteristic to be Flow)
        flow_data = filter_data(CSU_df, 'Flow', None, basin, site, canal_toggle, sample_type, date_range[0], date_range[1])
        
        if flow_data is not None and not flow_data.empty:
            # Add flow traces on secondary y-axis
            for location in flow_data['Location_Name'].unique():
                location_flow = flow_data[flow_data['Location_Name'] == location]
                fig.add_trace(go.Scatter(
                    x=location_flow['Activity_StartDate'],
                    y=location_flow['Result_Measure'],
                    mode='lines',
                    name=f'{location} (Flow)',
                    yaxis='y2',
                    line=dict(dash='dash'),
                    opacity=0.6
                ))
            
            # Update layout with secondary y-axis
            has_flow = True
        else:
            has_flow = False
    except:
        has_flow = False

    # Get acute and chronic values for the selected characteristic
    # Filter data to get non-empty acute/chronic values for this characteristic
    #acute_values = data[data['Acute'] != '']['Acute'].dropna()
    #chronic_values = data[data['Chronic'] != '']['Chronic'].dropna()
    
    # Add horizontal lines for acute and chronic levels if they exist
    #if not acute_values.empty:
    #   acute_level = float(acute_values.iloc[0])  # Get the first non-empty value
    #    figure.add_hline(
    #        y=acute_level, 
    #        line_dash="dash", 
    #        line_color="red"
    #    )
    #    # Add invisible scatter point to create legend entry
    #    figure.add_scatter(
    #        x=[None], y=[None],
    #        mode='lines',
    #        line=dict(color='red', dash='dash'),
    #        name=f'CDPHE Acute Standard ({acute_level})',
    #        showlegend=True
    #    )
    
    #if not chronic_values.empty:
    #    chronic_level = float(chronic_values.iloc[0])  # Get the first non-empty value
    #    figure.add_hline(
    #        y=chronic_level, 
    #        line_dash="dash", 
    #        line_color="orange"
    #    )
    # Add invisible scatter point to create legend entry
    #    figure.add_scatter(
    #        x=[None], y=[None],
    #        mode='lines',
    #        line=dict(color='orange', dash='dash'),
    #        name=f'CDPHE Chronic Standard ({chronic_level})',
    #        showlegend=True
    #    )
    
    # Update figure layout with dynamic title
    title_parts = [f'{characteristic} Over Time']

    # Add basin info (only if site is not selected)
    if site and site != 'All':
        # If site is selected, add site name (don't add basin info)
        title_parts.append(f'{site}')
    else:
        # If site is not selected, show basin info
        if basin and basin != 'All':
            title_parts.append(f'{basin}')
        else:
            title_parts.append('All Basins')
        
        # Add "All Monitoring Locations" if no site is selected
        title_parts.append('All Monitoring Locations')

    # Join all parts with ' - '
    title = ' - '.join(title_parts)

    figure.update_layout(
        title=title,
        xaxis_title='Date',
        yaxis_title=f'Concentration ({unit})',
        hovermode='x unified',
        legend_title_text='Monitoring Location',
    
    # Dark theme settings
    plot_bgcolor='#2d2d2d',  # Dark gray plot area
    paper_bgcolor='#1e1e1e',  # Dark background around plot
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
        color='white'
    ),
    yaxis=dict(
        gridcolor='#404040',
        zerolinecolor='#404040',
        color='white'
    ),
    legend=dict(
        orientation="h",          
        yanchor="top",            
        y=-0.15,                  
        xanchor="center",         
        x=0.5,                    
        bgcolor='rgba(45, 45, 45, 0.8)',
        bordercolor='#555',
        font=dict(color='white')
    )
)
# Add y-axis configurations
if has_flow:
    # Primary y-axis (left) for selected characteristic
    layout_config['yaxis'] = dict(
    title=f'{characteristic} ({unit})',
            gridcolor='#404040',
            zerolinecolor='#404040',
            color='white'
        )
        # Secondary y-axis (right) for flow
        layout_config['yaxis2'] = dict(
            title='Flow (cfs)',
            overlaying='y',
            side='right',
            gridcolor='#404040',
            zerolinecolor='#404040',
            color='lightblue',
            showgrid=False  # Don't show grid for secondary axis to avoid clutter
        )
    else:
        # Just primary y-axis
        layout_config['yaxis'] = dict(
            title=f'Concentration ({unit})',
            gridcolor='#404040',
            zerolinecolor='#404040',
            color='white'
        )
    
    fig.update_layout(**layout_config)
    
    return fig
        

# SUMMARY TABLE AND DATE RANGE DISPLAY 
# Date Range Display
@app.callback(
        Output('date-range-display', 'children'),
        [Input('date-slider', 'value'),
        Input('characteristic-select', 'value'),
        Input('fraction-select', 'value'),
        Input('basin-select', 'value'),
        Input('site-select', 'value'),
        Input('canal-toggle', 'value'),
        Input('sample-type-select', 'value')
        ],
        prevent_initial_call=True
    )
def update_date_range_display(date_range, characteristic, fraction, basin, site, canal_toggle,sample_type):
        # Get the actual data to find the real date range within the selection
        data = filter_data(CSU_df, characteristic, fraction, basin, site, canal_toggle, sample_type, date_range[0], date_range[1])

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
     Input('canal-toggle', 'value'),
     Input('sample-type-select', 'value'),
     Input('date-slider', 'value')
    ],
    prevent_initial_call=True
)

def update_table(characteristic, fraction, basin, site, canal_toggle, sample_type, date_range):
    # Store original characteristic before converting to None
    original_characteristic = characteristic

    # Convert "All" to None
    if characteristic == "All":
        characteristic = None
    if basin == "All":
        basin = None
    if site == "All":
        site = None
    if sample_type == "All":
            sample_type = None

    data = filter_data(CSU_df, characteristic, fraction, basin, site, canal_toggle, sample_type, date_range[0], date_range[1])
    
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
     Input('canal-toggle', 'value'),
     Input('sample-type-select', 'value'),
     Input('date-slider', 'value')
    ],
    prevent_initial_call=True
)
def plot_heatmap(characteristic, fraction, basin, site, canal_toggle, sample_type, date_range):
    # Convert "All" to None
    if characteristic == "All":
        characteristic = None
    if basin == "All":
        basin = None
    if site == "All":
        site = None
    if sample_type == "All":
        sample_type = None
    
    data = filter_data(CSU_df, characteristic, fraction, basin, site, canal_toggle, sample_type, date_range[0], date_range[1])
    
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
            title=f'{characteristic} Heatmap - No Valid Data',
            title_font=dict(color='white')
        )
        return fig
    
    # Get the appropriate unit for this characteristic
    unit = UNITS_MAP.get(characteristic, 'units')
    
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
                text=f"{characteristic}<br>({unit})",
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
                      f'{characteristic}: %{{z:.1f}} {unit}<br>' +
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
            text=f'{characteristic} Concentration Heatmap ({unit})<br><sub>Range: {min_val:.2f}-{max_val:.2f} {unit} | Median: {median_val:.2f} {unit}</sub>',
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


    

"""
- Add dropdown to select for characteristic. Set some thresholds for characteristics and color code based on above/below/near threshold.

- Add summary statistics table on basin and/or site basis. 
- Add water route?
"""

if __name__ == "__main__":
    app.run(debug=True)